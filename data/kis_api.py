"""
한국투자증권 Open API 연동 모듈

한국투자증권 KIS Developers REST API를 사용합니다.
- 플랫폼 독립적 (Windows, Mac, Linux 모두 지원)
- REST API 기반 (JSON, WebSocket)
- WebSocket 실시간 시세 지원

API 신청: https://apiportal.koreainvestment.com/intro
"""
import os
import time
import json
import requests
import threading
import queue
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Callable
import pandas as pd
import numpy as np
from pathlib import Path

# .env 파일 자동 로드 (override=True로 최신 값 반영)
from dotenv import load_dotenv
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

# Streamlit secrets 지원 함수
def _get_secret(key: str, default: str = None) -> str:
    """환경변수 또는 Streamlit secrets에서 값 가져오기"""
    # 1. 환경변수 먼저 확인
    value = os.getenv(key)
    if value:
        return value

    # 2. Streamlit secrets 확인 (Streamlit Cloud 배포 시)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return default

from config.settings import settings

# 토큰 캐시 파일 경로
TOKEN_CACHE_FILE = Path(__file__).parent.parent / ".token_cache.json"


class KoreaInvestmentAPI:
    """
    한국투자증권 Open API 클래스

    REST API 기반으로 Windows, Mac, Linux 모두에서 동작합니다.

    사용 전 준비:
    1. 한국투자증권 계좌 개설
    2. KIS Developers 서비스 신청 (https://apiportal.koreainvestment.com)
    3. APP Key, APP Secret 발급
    """

    # API 엔드포인트
    BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"  # 실전
    BASE_URL_MOCK = "https://openapivts.koreainvestment.com:29443"  # 모의

    def __init__(self,
                 app_key: str = None,
                 app_secret: str = None,
                 account_no: str = None,
                 is_mock: bool = False):
        """
        Args:
            app_key: 앱 키 (환경변수 KIS_APP_KEY로도 설정 가능)
            app_secret: 앱 시크릿 (환경변수 KIS_APP_SECRET으로도 설정 가능)
            account_no: 계좌번호 (환경변수 KIS_ACCOUNT_NO로도 설정 가능)
            is_mock: True면 모의투자 서버 사용
        """
        self.app_key = app_key or _get_secret("KIS_APP_KEY")
        self.app_secret = app_secret or _get_secret("KIS_APP_SECRET")
        self.account_no = account_no or _get_secret("KIS_ACCOUNT_NO")
        # is_mock 환경변수/secrets 지원
        is_mock_env = _get_secret("KIS_IS_MOCK", "false")
        self.is_mock = is_mock or (is_mock_env.lower() == "true")

        self.base_url = self.BASE_URL_MOCK if is_mock else self.BASE_URL_REAL
        self.access_token = None
        self.token_expires_at = None

        self._last_request_time = 0
        self._request_delay = 0.1  # 초당 10회 제한 고려

    def _get_account_parts(self) -> tuple:
        """
        계좌번호를 CANO(8자리)와 ACNT_PRDT_CD(2자리)로 분리

        Returns:
            (CANO, ACNT_PRDT_CD) 튜플
        """
        if not self.account_no:
            return ("", "")

        # 하이픈 제거
        clean_account = self.account_no.replace("-", "")

        # 10자리로 패딩 (앞 8자리 계좌, 뒤 2자리 상품코드)
        if len(clean_account) >= 10:
            return (clean_account[:8], clean_account[8:10])
        elif len(clean_account) == 8:
            return (clean_account, "01")  # 기본 상품코드
        else:
            return (clean_account, "")

    def connect(self) -> bool:
        """
        API 연결 (토큰 발급)

        Returns:
            bool: 연결 성공 여부
        """
        if not all([self.app_key, self.app_secret]):
            print("❌ APP Key와 APP Secret이 필요합니다.")
            print("환경변수 설정: KIS_APP_KEY, KIS_APP_SECRET")
            print("또는 생성자에 직접 전달")
            return False

        return self._get_access_token()

    def _load_cached_token(self) -> bool:
        """파일에서 캐시된 토큰 로드"""
        try:
            if TOKEN_CACHE_FILE.exists():
                with open(TOKEN_CACHE_FILE, 'r') as f:
                    cache = json.load(f)

                # 같은 앱 키로 발급된 토큰인지 확인
                if cache.get('app_key') == self.app_key:
                    expires_at = datetime.fromisoformat(cache.get('expires_at', ''))
                    # 아직 유효한 토큰인지 확인 (5분 여유)
                    if datetime.now() < expires_at - timedelta(minutes=5):
                        self.access_token = cache.get('access_token')
                        self.token_expires_at = expires_at
                        return True
        except Exception:
            pass
        return False

    def _save_token_cache(self):
        """토큰을 파일에 캐시"""
        try:
            cache = {
                'app_key': self.app_key,
                'access_token': self.access_token,
                'expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
                'is_mock': self.is_mock
            }
            with open(TOKEN_CACHE_FILE, 'w') as f:
                json.dump(cache, f)
        except Exception:
            pass

    def _get_access_token(self) -> bool:
        """접근 토큰 발급 - 캐시된 토큰이 있으면 재사용"""
        # 1. 메모리에 유효한 토큰이 있으면 재사용
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return True

        # 2. 파일에 캐시된 토큰이 있으면 로드
        if self._load_cached_token():
            print(f"✅ 한국투자증권 API 연결 성공 (캐시 토큰)")
            print(f"   모드: {'모의투자' if self.is_mock else '실전투자'}")
            return True

        # 3. 새 토큰 발급
        url = f"{self.base_url}/oauth2/tokenP"

        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            # 요청 간격 제한 (최소 1초)
            time.sleep(1)

            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()

            data = response.json()
            self.access_token = data.get("access_token")
            expires_in = int(data.get("expires_in", 86400))
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            # 토큰을 파일에 캐시
            self._save_token_cache()

            print(f"✅ 한국투자증권 API 연결 성공 (새 토큰)")
            print(f"   모드: {'모의투자' if self.is_mock else '실전투자'}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ 토큰 발급 실패: {e}")
            return False

    def _ensure_token(self):
        """토큰 유효성 확인 및 갱신"""
        if self.token_expires_at is None or datetime.now() >= self.token_expires_at:
            self._get_access_token()

    def _rate_limit(self):
        """API 호출 속도 제한"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
        self._last_request_time = time.time()

    def _get_headers(self, tr_id: str) -> dict:
        """API 호출 헤더 생성"""
        self._ensure_token()

        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }

    def _request(self,
                 method: str,
                 endpoint: str,
                 tr_id: str,
                 params: dict = None,
                 body: dict = None) -> Optional[dict]:
        """API 요청 공통 메서드"""
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(tr_id)

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            else:
                response = requests.post(url, headers=headers, json=body)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"API 요청 실패: {e}")
            return None

    # ========== 시세 조회 ==========

    def get_stock_price(self, code: str) -> Optional[dict]:
        """
        주식 현재가 조회

        Args:
            code: 종목코드 (6자리)

        Returns:
            현재가 정보 딕셔너리
        """
        tr_id = "FHKST01010100"  # 주식현재가 시세

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": code
        }

        result = self._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-price", tr_id, params)

        if result and result.get("rt_cd") == "0":
            return result.get("output")
        return None

    def get_daily_price(self,
                        code: str,
                        start_date: str = None,
                        end_date: str = None,
                        period: str = "D") -> pd.DataFrame:
        """
        주식 일별 시세 조회 (기간별시세 API 사용, 100개씩 페이징)

        Args:
            code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: D(일), W(주), M(월)

        Returns:
            OHLCV DataFrame
        """
        tr_id = "FHKST03010100"  # 기간별시세 (100개씩 반환)

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        all_data = []
        current_end = end_date
        max_iterations = 10  # 최대 10번 반복
        start_dt = datetime.strptime(start_date, "%Y%m%d")

        # 주봉/월봉은 페이징 간격 조정
        if period == "W":
            day_offset = 7  # 주봉: 7일
        elif period == "M":
            day_offset = 31  # 월봉: 31일
        else:
            day_offset = 1  # 일봉: 1일

        for iteration in range(max_iterations):
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": current_end,
                "FID_PERIOD_DIV_CODE": period,
                "FID_ORG_ADJ_PRC": "0"  # 수정주가
            }

            result = self._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", tr_id, params)

            if not result or result.get("rt_cd") != "0":
                # 첫 번째 호출에서 실패하면 로그 출력
                if iteration == 0:
                    print(f"[API] {code} period={period}: 조회 실패 - {result.get('msg1', '알 수 없음') if result else 'No response'}")
                break

            # 기간별시세 API는 output2에 데이터를 반환
            output = result.get("output2", [])
            if not output:
                # 첫 번째 호출에서 데이터 없으면 로그 출력
                if iteration == 0:
                    print(f"[API] {code} period={period}: 데이터 없음")
                break

            all_data.extend(output)

            # 가장 오래된 날짜 확인 (output은 최신순으로 정렬되어 있음)
            oldest_date_str = output[-1].get("stck_bsop_date", "")
            if not oldest_date_str:
                break

            try:
                oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            except:
                break

            # 요청한 시작일에 도달했으면 종료
            if oldest_dt <= start_dt:
                break

            # 다음 조회를 위해 가장 오래된 날짜의 이전 기간으로 설정
            current_end = (oldest_dt - timedelta(days=day_offset)).strftime("%Y%m%d")

            # 데이터가 100개 미만이면 더 이상 없음
            if len(output) < 100:
                break

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        # 중복 제거
        df = df.drop_duplicates(subset=['stck_bsop_date'])

        # 컬럼 매핑
        column_map = {
            "stck_bsop_date": "date",
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_clpr": "close",
            "acml_vol": "volume"
        }

        df = df.rename(columns=column_map)

        # 필요한 컬럼만 선택
        cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        existing_cols = [c for c in cols if c in df.columns]
        df = df[existing_cols]

        # 데이터 타입 변환
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        # 시작일 이후 데이터만 필터링
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        df = df[df['date'] >= start_dt].reset_index(drop=True)

        return df

    def get_minute_price(self, code: str, minute: int = 1) -> pd.DataFrame:
        """
        주식 분봉 시세 조회 (당일 전체 분봉 연속 조회)

        Args:
            code: 종목코드
            minute: 분봉 단위 (1, 5, 15, 30, 60)

        Returns:
            OHLCV DataFrame

        Note:
            - 당일 분봉만 제공됩니다
            - 주말/공휴일에는 빈 DataFrame 반환
        """
        import time as time_module
        from datetime import time as dt_time

        tr_id = "FHKST03010200"  # 주식당일분봉조회

        now = datetime.now()
        current_time = now.time()

        # 주말 체크
        if now.weekday() >= 5:
            return pd.DataFrame()

        # 조회 시작 시간 설정
        # 장 마감 후(15:30 이후)면 15:30:00부터 역순 조회
        if current_time > dt_time(15, 30):
            time_str = "153000"
        elif current_time < dt_time(9, 0):
            # 장 시작 전이면 빈 데이터
            return pd.DataFrame()
        else:
            time_str = now.strftime("%H%M%S")

        all_data = []
        max_iterations = 10  # 최대 반복 횟수 (API 호출 제한 방지)

        for _ in range(max_iterations):
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_HOUR_1": time_str,
                "FID_PW_DATA_INCU_YN": "Y",  # 과거 데이터 포함
                "FID_ETC_CLS_CODE": ""  # 기타 구분 코드
            }

            result = self._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", tr_id, params)

            if not result or result.get("rt_cd") != "0":
                break

            output = result.get("output2", [])
            if not output or not isinstance(output, list) or len(output) == 0:
                break

            all_data.extend(output)

            # 마지막 데이터의 시간으로 다음 조회 시간 설정
            last_time = output[-1].get("stck_cntg_hour", "")
            if not last_time or last_time <= "090000":
                break  # 장 시작 시간 도달

            # 다음 조회를 위해 시간 갱신
            time_str = last_time

            # API 호출 간격 (초당 20회 제한 대응)
            time_module.sleep(0.1)

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        # 컬럼 매핑
        column_map = {
            "stck_cntg_hour": "time",
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_prpr": "close",
            "cntg_vol": "volume"
        }

        df = df.rename(columns=column_map)

        # 필요한 컬럼만 선택
        cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        existing_cols = [c for c in cols if c in df.columns]
        if not existing_cols:
            return pd.DataFrame()

        df = df[existing_cols]

        # 중복 제거 (연속 조회 시 중복 가능)
        df = df.drop_duplicates(subset=['time'], keep='first')

        # 데이터 타입 변환
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 시간 처리
        if 'time' in df.columns:
            today = now.strftime("%Y%m%d")
            df['datetime'] = pd.to_datetime(today + df['time'], format='%Y%m%d%H%M%S', errors='coerce')
            df = df.dropna(subset=['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)

        # 분봉 리샘플링 (1분봉 -> N분봉)
        if minute > 1 and 'datetime' in df.columns and len(df) > 0:
            df = df.set_index('datetime')
            df = df.resample(f'{minute}min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna().reset_index()

        return df

    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """
        전체 종목 리스트 조회

        Args:
            market: "KOSPI", "KOSDAQ", "ALL"

        Returns:
            종목 리스트 DataFrame
        """
        # 한국투자증권 API는 종목 리스트 직접 조회 기능이 제한적
        # KRX에서 종목 리스트를 가져오는 대안 사용
        try:
            from pykrx import stock

            if market == "KOSPI":
                tickers = stock.get_market_ticker_list(market="KOSPI")
                market_type = "KOSPI"
            elif market == "KOSDAQ":
                tickers = stock.get_market_ticker_list(market="KOSDAQ")
                market_type = "KOSDAQ"
            else:
                kospi = stock.get_market_ticker_list(market="KOSPI")
                kosdaq = stock.get_market_ticker_list(market="KOSDAQ")
                tickers = kospi + kosdaq
                market_type = None

            stocks = []
            for ticker in tickers:
                name = stock.get_market_ticker_name(ticker)
                stocks.append({
                    "code": ticker,
                    "name": name,
                    "market": market_type or ("KOSPI" if ticker in kospi else "KOSDAQ") if market == "ALL" else market_type
                })

            df = pd.DataFrame(stocks)

            # 우선주, 스팩, ETF 등 제외
            df = df[~df['name'].str.contains('스팩|ETF|ETN|리츠|우$|우B|우C', na=False)]

            return df

        except ImportError:
            print("pykrx 패키지가 필요합니다: pip install pykrx")
            return pd.DataFrame()

    def get_financial_ratio(self, code: str) -> Optional[dict]:
        """
        주식 재무비율 조회

        Args:
            code: 종목코드

        Returns:
            재무비율 딕셔너리
        """
        tr_id = "FHKST01010700"  # 주식현재가 투자자

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code
        }

        result = self._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-investor", tr_id, params)

        if result and result.get("rt_cd") == "0":
            return result.get("output")
        return None

    def get_stock_info(self, code: str) -> Optional[dict]:
        """
        종목 기본 정보 조회 (PER, PBR, 시가총액 등)

        Args:
            code: 종목코드

        Returns:
            종목 정보 딕셔너리
        """
        price_data = self.get_stock_price(code)

        if not price_data:
            return None

        return {
            "code": code,
            "name": price_data.get("hts_kor_isnm", ""),
            "price": int(price_data.get("stck_prpr", 0)),
            "market_cap": int(price_data.get("hts_avls", 0)) * 100000000,  # 억원 -> 원
            "per": float(price_data.get("per", 0) or 0),
            "pbr": float(price_data.get("pbr", 0) or 0),
            "eps": float(price_data.get("eps", 0) or 0),
            "bps": float(price_data.get("bps", 0) or 0),
            "volume": int(price_data.get("acml_vol", 0)),
            "change_rate": float(price_data.get("prdy_ctrt", 0) or 0)
        }

    def get_sector_info(self, code: str) -> str:
        """
        종목의 업종 정보 조회

        Args:
            code: 종목코드

        Returns:
            업종명
        """
        try:
            from pykrx import stock
            # pykrx를 통해 업종 정보 조회
            return stock.get_market_ticker_name(code)  # 간이 구현
        except:
            return "기타"

    def get_company_overview(self, code: str) -> Optional[dict]:
        """
        기업 개요 정보 조회 (업종, 시가총액, 기업 설명 등)

        Args:
            code: 종목코드

        Returns:
            기업 개요 정보 딕셔너리
        """
        try:
            from pykrx import stock
            import datetime

            # 기본 정보
            result = {
                'code': code,
                'name': '',
                'sector': '',
                'market': '',
                'market_cap': 0,
                'shares': 0,
                'description': ''
            }

            # 종목명 조회
            try:
                result['name'] = stock.get_market_ticker_name(code)
            except:
                pass

            # 시가총액 및 상장주식수 조회
            try:
                today = datetime.datetime.now().strftime("%Y%m%d")
                cap_df = stock.get_market_cap(today, today, code)
                if cap_df is not None and not cap_df.empty:
                    result['market_cap'] = int(cap_df['시가총액'].iloc[-1])
                    result['shares'] = int(cap_df['상장주식수'].iloc[-1])
            except:
                pass

            # 업종 정보 조회 (KRX 업종 분류)
            try:
                # KOSPI/KOSDAQ 구분
                kospi_tickers = stock.get_market_ticker_list(market="KOSPI")
                kosdaq_tickers = stock.get_market_ticker_list(market="KOSDAQ")

                if code in kospi_tickers:
                    result['market'] = 'KOSPI'
                elif code in kosdaq_tickers:
                    result['market'] = 'KOSDAQ'
                else:
                    result['market'] = 'ETF/기타'

                # 업종 정보 (pykrx의 업종 분류 사용)
                sector_info = self._get_sector_from_krx(code)
                if sector_info:
                    result['sector'] = sector_info
            except:
                pass

            # 간단한 기업 설명 생성
            if result['name'] and result['sector']:
                market_cap_text = ""
                if result['market_cap'] > 0:
                    if result['market_cap'] >= 1_000_000_000_000:  # 1조 이상
                        market_cap_text = f"시가총액 {result['market_cap'] / 1_000_000_000_000:.1f}조원"
                    else:
                        market_cap_text = f"시가총액 {result['market_cap'] / 100_000_000:.0f}억원"

                result['description'] = f"{result['market']} 상장 {result['sector']} 기업. {market_cap_text}"

            return result

        except Exception as e:
            return None

    def _get_sector_from_krx(self, code: str) -> str:
        """KRX 업종 정보 조회 (내부 헬퍼)"""
        try:
            from pykrx import stock
            import datetime

            today = datetime.datetime.now().strftime("%Y%m%d")

            # WICS 업종 분류 시도
            try:
                # 주요 업종 매핑
                sector_mapping = {
                    # 대형주 업종 (수동 매핑)
                    '005930': '반도체', '000660': '반도체',  # 삼성전자, SK하이닉스
                    '005380': '자동차', '005490': '철강',    # 현대차, POSCO
                    '035420': '인터넷', '035720': '게임',    # 네이버, 카카오
                    '051910': '화학', '006400': '전기전자',  # LG화학, 삼성SDI
                    '028260': '엔터테인먼트', '352820': '바이오',  # 하이브, 하이브
                    '207940': '바이오', '068270': '게임',    # 삼성바이오, 셀트리온
                }

                if code in sector_mapping:
                    return sector_mapping[code]

                # 업종별 시세에서 찾기
                for market in ['KOSPI', 'KOSDAQ']:
                    try:
                        fundamental = stock.get_market_fundamental(today, market=market)
                        if fundamental is not None and code in fundamental.index:
                            # 기본 재무정보에서 업종 추정
                            return f"{market} 상장사"
                    except:
                        continue

            except:
                pass

            return "기타"

        except:
            return "기타"

    # ========== 매매 기능 ==========

    def buy_stock(self,
                  code: str,
                  quantity: int,
                  price: int = 0,
                  order_type: str = "00") -> Optional[dict]:
        """
        주식 매수 주문

        Args:
            code: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)
            order_type: 00(지정가), 01(시장가), 02(조건부지정가) 등

        Returns:
            주문 결과
        """
        if not self.account_no:
            print("계좌번호가 필요합니다.")
            return None

        tr_id = "VTTC0802U" if self.is_mock else "TTTC0802U"  # 주식 현금 매수

        cano, acnt_prdt_cd = self._get_account_parts()

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price)
        }

        return self._request("POST", "/uapi/domestic-stock/v1/trading/order-cash", tr_id, body=body)

    def sell_stock(self,
                   code: str,
                   quantity: int,
                   price: int = 0,
                   order_type: str = "00") -> Optional[dict]:
        """
        주식 매도 주문

        Args:
            code: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)
            order_type: 주문 유형

        Returns:
            주문 결과
        """
        if not self.account_no:
            print("계좌번호가 필요합니다.")
            return None

        tr_id = "VTTC0801U" if self.is_mock else "TTTC0801U"  # 주식 현금 매도

        cano, acnt_prdt_cd = self._get_account_parts()

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price)
        }

        return self._request("POST", "/uapi/domestic-stock/v1/trading/order-cash", tr_id, body=body)

    def get_index_price(self, index_code: str = "KOSPI") -> Optional[dict]:
        """
        국내 지수 현재가 조회 (네이버 금융 크롤링 - API 제한으로 대체)

        Args:
            index_code: 지수코드 ("KOSPI", "KOSDAQ")

        Returns:
            지수 정보 딕셔너리 (현재가, 전일대비, 등락률 등)
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            # 네이버 금융 지수 페이지
            if index_code == "KOSPI" or index_code == "0001":
                url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
                name = "코스피"
            elif index_code == "KOSDAQ" or index_code == "1001":
                url = "https://finance.naver.com/sise/sise_index.naver?code=KOSDAQ"
                name = "코스닥"
            else:
                return None

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'html.parser')

            # 현재 지수
            now_value = soup.select_one("#now_value")
            price = float(now_value.text.strip().replace(",", "")) if now_value else 0

            # 전일대비
            change_value = soup.select_one("#change_value_and_rate")
            if change_value:
                change_text = change_value.text.strip()
                # "상승 12.34 +0.50%" 또는 "하락 12.34 -0.50%" 형식
                parts = change_text.split()
                if len(parts) >= 2:
                    direction = parts[0]  # 상승/하락
                    change = float(parts[1].replace(",", ""))
                    if direction == "하락":
                        change = -change

                    # 등락률
                    if len(parts) >= 3:
                        rate_text = parts[2].replace("%", "").replace("+", "")
                        change_rate = float(rate_text)
                    else:
                        change_rate = (change / price * 100) if price else 0
                else:
                    change = 0
                    change_rate = 0
            else:
                change = 0
                change_rate = 0

            return {
                "name": name,
                "price": price,
                "change": change,
                "change_rate": change_rate,
                "open": 0,
                "high": 0,
                "low": 0,
                "volume": 0,
                "value": 0,
            }

        except Exception as e:
            print(f"지수 조회 오류: {e}")
            return None

    def get_exchange_rate(self, currency: str = "USD") -> Optional[dict]:
        """
        환율 정보 조회 (네이버 금융 크롤링 - API 미지원으로 대체)

        Args:
            currency: 통화코드 (USD, JPY, EUR, CNY 등)

        Returns:
            환율 정보 딕셔너리
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            url = "https://finance.naver.com/marketindex/exchangeList.naver"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'html.parser')

            # 환율 테이블에서 해당 통화 찾기
            currency_map = {
                "USD": "미국 USD",
                "JPY": "일본 JPY",
                "EUR": "유럽연합 EUR",
                "CNY": "중국 CNY",
            }

            target_name = currency_map.get(currency, f"{currency}")

            rows = soup.select("table.tbl_exchange tbody tr")
            for row in rows:
                name_elem = row.select_one("td.tit a")
                if name_elem and target_name in name_elem.text:
                    rate_elem = row.select_one("td.sale")
                    change_elem = row.select_one("td.change")

                    rate = float(rate_elem.text.strip().replace(",", "")) if rate_elem else 0
                    change_text = change_elem.text.strip().replace(",", "") if change_elem else "0"

                    # 상승/하락 여부 확인
                    is_up = "up" in row.get("class", []) or row.select_one(".up") is not None

                    try:
                        change = float(change_text)
                        if not is_up and change > 0:
                            change = -change
                    except:
                        change = 0

                    return {
                        "currency": currency,
                        "name": name_elem.text.strip(),
                        "rate": rate,
                        "change": change,
                        "change_rate": (change / rate * 100) if rate else 0
                    }

            return None

        except Exception as e:
            print(f"환율 조회 오류: {e}")
            return None

    def get_market_indices(self) -> dict:
        """
        주요 시장 지수 일괄 조회 (코스피, 코스닥, 환율)

        Returns:
            시장 지수 딕셔너리
        """
        result = {}

        # 코스피 지수
        kospi = self.get_index_price("KOSPI")
        if kospi:
            result['kospi'] = kospi

        # 코스닥 지수
        kosdaq = self.get_index_price("KOSDAQ")
        if kosdaq:
            result['kosdaq'] = kosdaq

        # 환율 (USD)
        usd = self.get_exchange_rate("USD")
        if usd:
            result['usd'] = usd

        return result

    def get_investor_trading(self, code: str, period: str = "D", count: int = 7) -> Optional[pd.DataFrame]:
        """
        투자자별 매매동향 조회 (개인/기관/외국인)

        Args:
            code: 종목코드 (6자리)
            period: 기간구분 (D: 일, W: 주, M: 월)
            count: 조회할 데이터 수 (기본 7일)

        Returns:
            DataFrame with columns: date, individual, institution, foreign, total
            - 양수: 순매수, 음수: 순매도 (단위: 주)
        """
        try:
            # 네이버 금융에서 투자자별 매매동향 조회
            import requests
            from bs4 import BeautifulSoup

            url = f"https://finance.naver.com/item/frgn.naver?code={code}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'html.parser')

            # 테이블 파싱 - 두 번째 type2 테이블이 투자자별 매매동향
            tables = soup.select("table.type2")
            if len(tables) < 2:
                return None
            table = tables[1]  # 두 번째 테이블

            rows = table.select("tr")
            data = []

            for row in rows[2:]:  # 헤더 2줄 스킵 (날짜/종가/전일비 + 순매매량/보유주수)
                cols = row.select("td")
                if len(cols) >= 7:
                    try:
                        date_text = cols[0].text.strip()
                        if not date_text or date_text == '-' or not date_text[0].isdigit():
                            continue

                        # 가격 정보 (col 1: 종가)
                        close_text = cols[1].text.strip().replace(",", "")
                        close_price = int(close_text) if close_text.isdigit() else 0

                        # 전일대비 (col 2: "상승30" 또는 "하락30" 형태)
                        change_text = cols[2].text.strip()
                        change = 0
                        if '상승' in change_text:
                            change = int(change_text.replace('상승', '').replace(',', '') or 0)
                        elif '하락' in change_text:
                            change = -int(change_text.replace('하락', '').replace(',', '') or 0)

                        # 거래량 (col 4)
                        volume_text = cols[4].text.strip().replace(",", "")
                        total_volume = int(volume_text) if volume_text.isdigit() else 0

                        # 기관 순매매 (col 5)
                        inst_text = cols[5].text.strip().replace(",", "").replace("+", "")
                        institution = int(inst_text) if inst_text.lstrip('-').isdigit() else 0

                        # 외국인 순매매 (col 6)
                        frgn_text = cols[6].text.strip().replace(",", "").replace("+", "")
                        foreign = int(frgn_text) if frgn_text.lstrip('-').isdigit() else 0

                        # 개인 = -(기관 + 외국인) 근사치
                        individual = -(institution + foreign)

                        data.append({
                            'date': date_text,
                            'close': close_price,
                            'change': change,
                            'volume': total_volume,
                            'institution': institution,
                            'foreign': foreign,
                            'individual': individual
                        })

                        if len(data) >= count:
                            break
                    except (ValueError, IndexError) as e:
                        continue

            if not data:
                return None

            df = pd.DataFrame(data)
            return df

        except Exception as e:
            print(f"투자자 매매동향 조회 오류: {e}")
            return None

    def get_investor_summary(self, code: str, days: int = 5) -> Optional[dict]:
        """
        투자자별 매매동향 요약 (최근 N일 합계)

        Args:
            code: 종목코드
            days: 집계 기간 (기본 5일)

        Returns:
            요약 딕셔너리: individual_sum, institution_sum, foreign_sum, trend
        """
        df = self.get_investor_trading(code, count=days)
        if df is None or df.empty:
            return None

        result = {
            'individual_sum': int(df['individual'].sum()),
            'institution_sum': int(df['institution'].sum()),
            'foreign_sum': int(df['foreign'].sum()),
            'individual_avg': int(df['individual'].mean()),
            'institution_avg': int(df['institution'].mean()),
            'foreign_avg': int(df['foreign'].mean()),
            'days': len(df)
        }

        # 추세 판단 (외국인+기관 순매수가 양수면 '매집', 음수면 '매도')
        big_player_sum = result['institution_sum'] + result['foreign_sum']
        if big_player_sum > 0:
            result['trend'] = '매집'
            result['trend_color'] = '#11998e'
        elif big_player_sum < 0:
            result['trend'] = '매도'
            result['trend_color'] = '#f5576c'
        else:
            result['trend'] = '중립'
            result['trend_color'] = '#888'

        return result

    def get_balance(self) -> Optional[dict]:
        """
        계좌 잔고 조회

        Returns:
            잔고 정보
        """
        if not self.account_no:
            print("계좌번호가 필요합니다.")
            return None

        tr_id = "VTTC8434R" if self.is_mock else "TTTC8434R"

        cano, acnt_prdt_cd = self._get_account_parts()

        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }

        result = self._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance", tr_id, params)

        if result and result.get("rt_cd") == "0":
            return {
                "holdings": result.get("output1", []),
                "summary": result.get("output2", [])
            }
        return None


def create_api(app_key: str = None,
               app_secret: str = None,
               account_no: str = None,
               is_mock: bool = False) -> KoreaInvestmentAPI:
    """
    한국투자증권 API 인스턴스 생성

    Args:
        app_key: 앱 키 (환경변수로도 설정 가능)
        app_secret: 앱 시크릿
        account_no: 계좌번호
        is_mock: 모의투자 여부

    Returns:
        KoreaInvestmentAPI 인스턴스
    """
    return KoreaInvestmentAPI(
        app_key=app_key,
        app_secret=app_secret,
        account_no=account_no,
        is_mock=is_mock
    )


# ========== WebSocket 실시간 시세 ==========

class KoreaInvestmentWebSocket:
    """
    한국투자증권 WebSocket 실시간 시세 클래스

    실시간 체결가(H0STCNT0), 호가(H0STASP0) 데이터를 수신합니다.

    제한사항:
    - 최대 20개 종목 동시 구독 가능 (체결가 + 호가 합산)
    - HTS ID 필요 (KIS Developers에서 확인)

    사용 예:
        ws = KoreaInvestmentWebSocket()
        ws.connect()
        ws.subscribe(['005930', '000660'])  # 삼성전자, SK하이닉스
        price = ws.get_realtime_price('005930')
    """

    # WebSocket 엔드포인트
    WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
    WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"

    def __init__(self,
                 app_key: str = None,
                 app_secret: str = None,
                 hts_id: str = None,
                 is_mock: bool = False):
        """
        Args:
            app_key: 앱 키 (환경변수 KIS_APP_KEY로도 설정 가능)
            app_secret: 앱 시크릿 (환경변수 KIS_APP_SECRET으로도 설정 가능)
            hts_id: HTS ID (환경변수 KIS_HTS_ID로도 설정 가능)
            is_mock: True면 모의투자 서버 사용
        """
        self.app_key = app_key or os.getenv("KIS_APP_KEY")
        self.app_secret = app_secret or os.getenv("KIS_APP_SECRET")
        self.hts_id = hts_id or os.getenv("KIS_HTS_ID")
        self.is_mock = is_mock

        self.ws_url = self.WS_URL_MOCK if is_mock else self.WS_URL_REAL
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        self.approval_key = None

        # 실시간 데이터 저장소 (thread-safe)
        self._price_data: Dict[str, dict] = {}
        self._orderbook_data: Dict[str, dict] = {}
        self._data_lock = threading.Lock()

        # 구독 종목 관리
        self._subscribed_codes: set = set()
        self._max_subscriptions = 20

        # 메시지 큐 (Streamlit과 통신용)
        self.message_queue = queue.Queue(maxsize=1000)

        # 콜백 함수
        self._on_price_callback: Optional[Callable] = None
        self._on_orderbook_callback: Optional[Callable] = None

        # 재연결 설정
        self._reconnect_delay = 5
        self._should_reconnect = True

    def _get_approval_key(self) -> Optional[str]:
        """WebSocket 접속키 발급"""
        url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"

        headers = {"content-type": "application/json; utf-8"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("approval_key")
        except Exception as e:
            print(f"❌ WebSocket 접속키 발급 실패: {e}")
            return None

    def connect(self) -> bool:
        """
        WebSocket 연결

        Returns:
            bool: 연결 성공 여부
        """
        if not all([self.app_key, self.app_secret]):
            print("❌ APP Key와 APP Secret이 필요합니다.")
            return False

        if not self.hts_id:
            print("❌ HTS ID가 필요합니다.")
            print("   환경변수 KIS_HTS_ID 설정 또는 생성자에 hts_id 전달")
            return False

        # 접속키 발급
        self.approval_key = self._get_approval_key()
        if not self.approval_key:
            return False

        # WebSocket 연결 스레드 시작
        self._should_reconnect = True
        self.ws_thread = threading.Thread(target=self._ws_connect_loop, daemon=True)
        self.ws_thread.start()

        # 연결 대기 (최대 5초)
        for _ in range(50):
            if self.is_connected:
                print(f"✅ WebSocket 연결 성공")
                print(f"   모드: {'모의투자' if self.is_mock else '실전투자'}")
                return True
            time.sleep(0.1)

        print("❌ WebSocket 연결 타임아웃")
        return False

    def _ws_connect_loop(self):
        """WebSocket 연결 루프 (재연결 포함)"""
        try:
            import websocket
        except ImportError:
            print("❌ websocket-client 패키지가 필요합니다: pip install websocket-client")
            return

        while self._should_reconnect:
            try:
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.run_forever()

                # 연결 종료 후 재연결 대기
                if self._should_reconnect:
                    print(f"WebSocket 재연결 대기 ({self._reconnect_delay}초)...")
                    time.sleep(self._reconnect_delay)

            except Exception as e:
                print(f"WebSocket 오류: {e}")
                if self._should_reconnect:
                    time.sleep(self._reconnect_delay)

    def _on_open(self, ws):
        """WebSocket 연결 성공 콜백"""
        self.is_connected = True

        # 이전에 구독했던 종목들 재구독
        for code in list(self._subscribed_codes):
            self._send_subscribe(code, subscribe=True)

    def _on_message(self, ws, message):
        """WebSocket 메시지 수신 콜백"""
        try:
            # 암호화된 데이터는 | 로 구분됨
            if '|' in message:
                # 체결가/호가 데이터 파싱
                parts = message.split('|')
                if len(parts) >= 4:
                    encrypt_flag = parts[0]
                    tr_id = parts[1]
                    data_count = parts[2]
                    data = parts[3]

                    if tr_id == "H0STCNT0":  # 체결가
                        self._parse_price_data(data)
                    elif tr_id == "H0STASP0":  # 호가
                        self._parse_orderbook_data(data)
            else:
                # JSON 응답 (구독 확인 등)
                try:
                    data = json.loads(message)
                    # 구독 확인 메시지 처리
                    if data.get("header", {}).get("tr_id") in ["H0STCNT0", "H0STASP0"]:
                        msg_cd = data.get("body", {}).get("msg_cd", "")
                        if msg_cd == "OPSP0000":
                            pass  # 구독 성공
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"메시지 처리 오류: {e}")

    def _parse_price_data(self, data: str):
        """체결가 데이터 파싱 (H0STCNT0)"""
        try:
            fields = data.split('^')
            if len(fields) < 20:
                return

            code = fields[0]  # 종목코드

            price_info = {
                "code": code,
                "time": fields[1],  # 체결시간 HHMMSS
                "price": int(fields[2]) if fields[2] else 0,  # 현재가
                "change_sign": fields[3],  # 부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
                "change": int(fields[4]) if fields[4] else 0,  # 전일대비
                "change_rate": float(fields[5]) if fields[5] else 0.0,  # 등락률
                "volume": int(fields[9]) if fields[9] else 0,  # 누적거래량
                "trade_volume": int(fields[10]) if fields[10] else 0,  # 체결거래량
                "open": int(fields[13]) if fields[13] else 0,  # 시가
                "high": int(fields[14]) if fields[14] else 0,  # 고가
                "low": int(fields[15]) if fields[15] else 0,  # 저가
                "updated_at": datetime.now()
            }

            with self._data_lock:
                self._price_data[code] = price_info

            # 콜백 호출
            if self._on_price_callback:
                try:
                    self._on_price_callback(price_info)
                except Exception:
                    pass

            # 메시지 큐에 추가 (Streamlit용)
            try:
                self.message_queue.put_nowait(("price", price_info))
            except queue.Full:
                pass

        except Exception as e:
            print(f"체결가 파싱 오류: {e}")

    def _parse_orderbook_data(self, data: str):
        """호가 데이터 파싱 (H0STASP0)"""
        try:
            fields = data.split('^')
            if len(fields) < 40:
                return

            code = fields[0]  # 종목코드

            # 매도호가 (1~10)
            asks = []
            for i in range(10):
                idx = 3 + i * 2
                if idx + 1 < len(fields):
                    price = int(fields[idx]) if fields[idx] else 0
                    volume = int(fields[idx + 1]) if fields[idx + 1] else 0
                    if price > 0:
                        asks.append({"price": price, "volume": volume})

            # 매수호가 (1~10)
            bids = []
            for i in range(10):
                idx = 23 + i * 2
                if idx + 1 < len(fields):
                    price = int(fields[idx]) if fields[idx] else 0
                    volume = int(fields[idx + 1]) if fields[idx + 1] else 0
                    if price > 0:
                        bids.append({"price": price, "volume": volume})

            orderbook_info = {
                "code": code,
                "time": fields[1],  # 호가시간
                "asks": asks,  # 매도호가 (낮은가격순)
                "bids": bids,  # 매수호가 (높은가격순)
                "updated_at": datetime.now()
            }

            with self._data_lock:
                self._orderbook_data[code] = orderbook_info

            # 콜백 호출
            if self._on_orderbook_callback:
                try:
                    self._on_orderbook_callback(orderbook_info)
                except Exception:
                    pass

        except Exception as e:
            print(f"호가 파싱 오류: {e}")

    def _on_error(self, ws, error):
        """WebSocket 오류 콜백"""
        print(f"WebSocket 오류: {error}")
        self.is_connected = False

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료 콜백"""
        print(f"WebSocket 연결 종료: {close_status_code} - {close_msg}")
        self.is_connected = False

    def _send_subscribe(self, code: str, subscribe: bool = True, tr_type: str = "price"):
        """구독/해제 메시지 전송"""
        if not self.ws or not self.is_connected:
            return

        # tr_id 결정
        if tr_type == "price":
            tr_id = "H0STCNT0"  # 실시간 체결가
        else:
            tr_id = "H0STASP0"  # 실시간 호가

        msg = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",  # 개인
                "tr_type": "1" if subscribe else "2",  # 1:구독, 2:해제
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": code
                }
            }
        }

        try:
            self.ws.send(json.dumps(msg))
        except Exception as e:
            print(f"구독 메시지 전송 실패: {e}")

    def subscribe(self, codes: List[str], include_orderbook: bool = False) -> bool:
        """
        종목 실시간 시세 구독

        Args:
            codes: 종목코드 리스트
            include_orderbook: 호가 데이터도 구독할지 여부

        Returns:
            bool: 구독 성공 여부
        """
        if not self.is_connected:
            print("❌ WebSocket이 연결되지 않았습니다.")
            return False

        # 구독 수 제한 체크
        subscription_count = len(codes)
        if include_orderbook:
            subscription_count *= 2  # 체결가 + 호가

        current_count = len(self._subscribed_codes)
        if include_orderbook:
            current_count *= 2

        if current_count + subscription_count > self._max_subscriptions:
            print(f"❌ 구독 한도 초과: 최대 {self._max_subscriptions}개 (현재: {current_count})")
            return False

        for code in codes:
            if code not in self._subscribed_codes:
                self._send_subscribe(code, subscribe=True, tr_type="price")
                if include_orderbook:
                    self._send_subscribe(code, subscribe=True, tr_type="orderbook")
                self._subscribed_codes.add(code)
                time.sleep(0.1)  # API 호출 간격

        return True

    def unsubscribe(self, codes: List[str]):
        """
        종목 실시간 시세 구독 해제

        Args:
            codes: 종목코드 리스트
        """
        for code in codes:
            if code in self._subscribed_codes:
                self._send_subscribe(code, subscribe=False, tr_type="price")
                self._send_subscribe(code, subscribe=False, tr_type="orderbook")
                self._subscribed_codes.discard(code)
                time.sleep(0.1)

                # 캐시 데이터 삭제
                with self._data_lock:
                    self._price_data.pop(code, None)
                    self._orderbook_data.pop(code, None)

    def unsubscribe_all(self):
        """모든 종목 구독 해제"""
        self.unsubscribe(list(self._subscribed_codes))

    def get_realtime_price(self, code: str) -> Optional[dict]:
        """
        실시간 체결가 조회

        Args:
            code: 종목코드

        Returns:
            실시간 가격 정보 (없으면 None)
        """
        with self._data_lock:
            return self._price_data.get(code)

    def get_realtime_orderbook(self, code: str) -> Optional[dict]:
        """
        실시간 호가 조회

        Args:
            code: 종목코드

        Returns:
            실시간 호가 정보 (없으면 None)
        """
        with self._data_lock:
            return self._orderbook_data.get(code)

    def get_all_prices(self) -> Dict[str, dict]:
        """모든 구독 종목의 실시간 가격 조회"""
        with self._data_lock:
            return dict(self._price_data)

    def set_price_callback(self, callback: Callable[[dict], None]):
        """
        체결가 수신 콜백 설정

        Args:
            callback: 콜백 함수 (price_info dict를 인자로 받음)
        """
        self._on_price_callback = callback

    def set_orderbook_callback(self, callback: Callable[[dict], None]):
        """
        호가 수신 콜백 설정

        Args:
            callback: 콜백 함수 (orderbook_info dict를 인자로 받음)
        """
        self._on_orderbook_callback = callback

    def get_subscribed_codes(self) -> List[str]:
        """구독 중인 종목 리스트"""
        return list(self._subscribed_codes)

    def get_subscription_count(self) -> int:
        """현재 구독 수"""
        return len(self._subscribed_codes)

    def disconnect(self):
        """WebSocket 연결 종료"""
        self._should_reconnect = False
        self.unsubscribe_all()

        if self.ws:
            try:
                self.ws.close()
            except:
                pass

        self.is_connected = False
        print("WebSocket 연결 종료됨")


# WebSocket 싱글톤 인스턴스 (전역 사용)
_ws_instance: Optional[KoreaInvestmentWebSocket] = None
_ws_lock = threading.Lock()


def get_websocket_instance(force_new: bool = False) -> KoreaInvestmentWebSocket:
    """
    WebSocket 싱글톤 인스턴스 반환

    Streamlit 환경에서 여러 세션이 공유할 수 있는 싱글톤 패턴

    Args:
        force_new: True면 기존 인스턴스를 닫고 새로 생성

    Returns:
        KoreaInvestmentWebSocket 인스턴스
    """
    global _ws_instance

    with _ws_lock:
        if force_new and _ws_instance:
            _ws_instance.disconnect()
            _ws_instance = None

        if _ws_instance is None:
            _ws_instance = KoreaInvestmentWebSocket()

        return _ws_instance


def create_websocket(app_key: str = None,
                     app_secret: str = None,
                     hts_id: str = None,
                     is_mock: bool = False) -> KoreaInvestmentWebSocket:
    """
    한국투자증권 WebSocket 인스턴스 생성

    Args:
        app_key: 앱 키 (환경변수로도 설정 가능)
        app_secret: 앱 시크릿
        hts_id: HTS ID
        is_mock: 모의투자 여부

    Returns:
        KoreaInvestmentWebSocket 인스턴스
    """
    return KoreaInvestmentWebSocket(
        app_key=app_key,
        app_secret=app_secret,
        hts_id=hts_id,
        is_mock=is_mock
    )
