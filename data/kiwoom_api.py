"""
키움 API 연동 모듈

주의사항:
- Windows 환경에서만 동작
- 32bit Python 필요
- 키움증권 OpenAPI+ 설치 필요
- 1초당 5회 조회 제한
"""
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

from config.settings import settings


class KiwoomAPI:
    """키움 증권 OpenAPI+ 래퍼 클래스"""

    def __init__(self):
        self.api = None
        self.connected = False
        self._last_request_time = 0

    def connect(self) -> bool:
        """
        키움 API 연결

        Returns:
            bool: 연결 성공 여부
        """
        try:
            from pykiwoom.kiwoom import Kiwoom
            self.api = Kiwoom()
            self.api.CommConnect(block=True)
            self.connected = True
            print("키움 API 연결 성공")
            return True
        except ImportError:
            print("pykiwoom 패키지가 설치되어 있지 않습니다.")
            print("Windows 환경에서 pip install pykiwoom 으로 설치해주세요.")
            return False
        except Exception as e:
            print(f"키움 API 연결 실패: {e}")
            return False

    def _rate_limit(self):
        """API 호출 속도 제한"""
        elapsed = time.time() - self._last_request_time
        if elapsed < settings.KIWOOM_API_DELAY:
            time.sleep(settings.KIWOOM_API_DELAY - elapsed)
        self._last_request_time = time.time()

    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """
        전체 종목 리스트 조회

        Args:
            market: "KOSPI", "KOSDAQ", "ALL"

        Returns:
            종목코드, 종목명 DataFrame
        """
        if not self.connected:
            raise ConnectionError("키움 API에 연결되어 있지 않습니다.")

        self._rate_limit()

        stocks = []

        if market in ["KOSPI", "ALL"]:
            kospi_codes = self.api.GetCodeListByMarket("0")
            for code in kospi_codes:
                name = self.api.GetMasterCodeName(code)
                stocks.append({
                    "code": code,
                    "name": name,
                    "market": "KOSPI"
                })

        if market in ["KOSDAQ", "ALL"]:
            kosdaq_codes = self.api.GetCodeListByMarket("10")
            for code in kosdaq_codes:
                name = self.api.GetMasterCodeName(code)
                stocks.append({
                    "code": code,
                    "name": name,
                    "market": "KOSDAQ"
                })

        df = pd.DataFrame(stocks)

        # 우선주, 스팩, ETF 등 제외
        df = df[~df['name'].str.contains('스팩|ETF|ETN|리츠|우$|우B|우C', na=False)]

        return df

    def get_price_data(self,
                       code: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        주가 데이터 조회 (일봉)

        Args:
            code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)

        Returns:
            OHLCV DataFrame
        """
        if not self.connected:
            raise ConnectionError("키움 API에 연결되어 있지 않습니다.")

        self._rate_limit()

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        # opt10081: 주식일봉차트조회요청
        df = self.api.block_request(
            "opt10081",
            종목코드=code,
            기준일자=end_date,
            수정주가구분=1,
            output="주식일봉차트조회",
            next=0
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # 컬럼명 정리
        df = df.rename(columns={
            '일자': 'date',
            '시가': 'open',
            '고가': 'high',
            '저가': 'low',
            '현재가': 'close',
            '거래량': 'volume'
        })

        # 숫자형 변환
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').abs()

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        # 기간 필터링
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df['date'] >= start_dt]

        return df[['date', 'open', 'high', 'low', 'close', 'volume']]

    def get_financial_data(self, code: str) -> Dict:
        """
        재무 데이터 조회

        Args:
            code: 종목코드

        Returns:
            재무 데이터 딕셔너리
        """
        if not self.connected:
            raise ConnectionError("키움 API에 연결되어 있지 않습니다.")

        self._rate_limit()

        # opt10001: 주식기본정보요청
        df = self.api.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        if df is None or df.empty:
            return {}

        result = df.iloc[0].to_dict() if len(df) > 0 else {}

        # opt10014: 재무정보요청 (더 상세한 재무 데이터)
        self._rate_limit()
        fin_df = self.api.block_request(
            "opt10014",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        if fin_df is not None and not fin_df.empty:
            result.update(fin_df.iloc[0].to_dict())

        return result

    def get_sector_info(self, code: str) -> str:
        """
        종목의 섹터/업종 정보 조회

        Args:
            code: 종목코드

        Returns:
            업종명
        """
        if not self.connected:
            raise ConnectionError("키움 API에 연결되어 있지 않습니다.")

        self._rate_limit()

        # opt10001에서 업종 정보 추출
        df = self.api.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        if df is not None and '업종' in df.columns:
            return df['업종'].iloc[0]

        return "기타"

    def get_market_cap(self, code: str) -> Optional[float]:
        """
        시가총액 조회

        Args:
            code: 종목코드

        Returns:
            시가총액 (원)
        """
        if not self.connected:
            raise ConnectionError("키움 API에 연결되어 있지 않습니다.")

        self._rate_limit()

        df = self.api.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        if df is not None and '시가총액' in df.columns:
            try:
                return float(str(df['시가총액'].iloc[0]).replace(',', '')) * 100000000
            except:
                return None

        return None


class MockKiwoomAPI:
    """
    테스트용 Mock 키움 API

    키움 API가 없는 환경(Mac, Linux)에서 개발/테스트용으로 사용
    FinanceDataReader를 백엔드로 사용
    """

    def __init__(self):
        self.connected = False
        self._fdr = None

    def connect(self) -> bool:
        """Mock 연결"""
        try:
            import FinanceDataReader as fdr
            self._fdr = fdr
            self.connected = True
            print("Mock 키움 API 연결 (FinanceDataReader 사용)")
            return True
        except ImportError:
            print("FinanceDataReader가 설치되어 있지 않습니다.")
            return False

    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """종목 리스트 조회 (FinanceDataReader 사용)"""
        if not self.connected:
            raise ConnectionError("연결되어 있지 않습니다.")

        stocks = []

        if market in ["KOSPI", "ALL"]:
            kospi = self._fdr.StockListing('KOSPI')
            kospi['market'] = 'KOSPI'
            stocks.append(kospi)

        if market in ["KOSDAQ", "ALL"]:
            kosdaq = self._fdr.StockListing('KOSDAQ')
            kosdaq['market'] = 'KOSDAQ'
            stocks.append(kosdaq)

        df = pd.concat(stocks, ignore_index=True)

        # 컬럼명 정리
        if 'Code' in df.columns:
            df = df.rename(columns={'Code': 'code', 'Name': 'name'})
        elif 'Symbol' in df.columns:
            df = df.rename(columns={'Symbol': 'code', 'Name': 'name'})

        # 우선주, 스팩, ETF 등 제외
        df = df[~df['name'].str.contains('스팩|ETF|ETN|리츠|우$|우B|우C', na=False)]

        return df[['code', 'name', 'market']]

    def get_price_data(self,
                       code: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """주가 데이터 조회 (FinanceDataReader 사용)"""
        if not self.connected:
            raise ConnectionError("연결되어 있지 않습니다.")

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")
        else:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"

        if end_date:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        df = self._fdr.DataReader(code, start_date, end_date)

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        df = df.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        return df[['date', 'open', 'high', 'low', 'close', 'volume']]

    def get_financial_data(self, code: str) -> Dict:
        """재무 데이터 조회 (제한적)"""
        # FinanceDataReader는 재무 데이터 제공이 제한적
        # 실제로는 OpenDartReader 등을 사용해야 함
        return {}

    def get_sector_info(self, code: str) -> str:
        """섹터 정보 조회"""
        # 실제 구현 시 pykrx 등 사용
        return "기타"


def create_api(use_mock: bool = False) -> KiwoomAPI:
    """
    API 인스턴스 생성

    Args:
        use_mock: True면 Mock API 사용 (Mac/Linux 개발용)

    Returns:
        KiwoomAPI 또는 MockKiwoomAPI 인스턴스
    """
    import platform

    if use_mock or platform.system() != "Windows":
        print("Non-Windows 환경 감지: Mock API를 사용합니다.")
        return MockKiwoomAPI()

    return KiwoomAPI()
