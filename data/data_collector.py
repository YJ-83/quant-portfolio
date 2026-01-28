"""
데이터 수집기 모듈

한국투자증권 API 또는 대안 데이터 소스를 사용하여 데이터를 수집합니다.
"""
from datetime import datetime, timedelta
from typing import Optional, List
import pandas as pd
from tqdm import tqdm

from .kis_api import KoreaInvestmentAPI, create_api
from .database import Database
from config.settings import settings


class DataCollector:
    """
    주식 데이터 수집기

    한국투자증권 API를 사용하여 데이터를 수집합니다.
    """

    def __init__(self, api: Optional[KoreaInvestmentAPI] = None, db: Optional[Database] = None):
        self.api = api or create_api()
        self.db = db or Database()

    def connect(self) -> bool:
        """API 연결"""
        return self.api.connect()

    def collect_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """
        종목 리스트 수집 및 저장

        Args:
            market: "KOSPI", "KOSDAQ", "ALL"

        Returns:
            종목 리스트 DataFrame
        """
        print(f"종목 리스트 수집 중... (market={market})")

        df = self.api.get_stock_list(market)

        # 섹터 정보 추가
        sectors = []
        for code in tqdm(df['code'], desc="섹터 정보 수집"):
            try:
                sector = self.api.get_sector_info(code)
                sectors.append(sector)
            except:
                sectors.append("기타")

        df['sector'] = sectors

        # DB 저장
        self.db.save_stocks(df)

        print(f"총 {len(df)}개 종목 수집 완료")
        return df

    def collect_price_data(self,
                           codes: Optional[List[str]] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           days: int = 365 * 3) -> None:
        """
        주가 데이터 수집 및 저장

        Args:
            codes: 종목코드 리스트 (None이면 전체)
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            days: start_date 미지정시 오늘 기준 수집 일수
        """
        if codes is None:
            stocks = self.db.get_stocks()
            codes = stocks['code'].tolist()

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        print(f"주가 데이터 수집: {start_date} ~ {end_date}")
        print(f"대상 종목: {len(codes)}개")

        for code in tqdm(codes, desc="주가 수집"):
            try:
                df = self.api.get_daily_price(code, start_date, end_date)
                if not df.empty:
                    self.db.save_prices(code, df)
            except Exception as e:
                print(f"\n{code} 주가 수집 실패: {e}")
                continue

        print("주가 데이터 수집 완료")

    def collect_financial_data(self, codes: Optional[List[str]] = None) -> None:
        """
        재무 데이터 수집 및 저장

        Args:
            codes: 종목코드 리스트 (None이면 전체)
        """
        if codes is None:
            stocks = self.db.get_stocks()
            codes = stocks['code'].tolist()

        print(f"재무 데이터 수집: {len(codes)}개 종목")

        current_year = datetime.now().year

        for code in tqdm(codes, desc="재무 수집"):
            try:
                data = self.api.get_stock_info(code)
                if data:
                    self.db.save_financials(code, data, current_year)
            except Exception as e:
                print(f"\n{code} 재무 수집 실패: {e}")
                continue

        print("재무 데이터 수집 완료")

    def collect_all(self, market: str = "ALL") -> None:
        """
        전체 데이터 수집

        Args:
            market: "KOSPI", "KOSDAQ", "ALL"
        """
        print("=" * 50)
        print("전체 데이터 수집 시작")
        print("=" * 50)

        # 1. 종목 리스트
        self.collect_stock_list(market)

        # 2. 주가 데이터
        self.collect_price_data()

        # 3. 재무 데이터
        self.collect_financial_data()

        print("=" * 50)
        print("전체 데이터 수집 완료")
        print("=" * 50)

    def update_daily(self) -> None:
        """일일 데이터 업데이트"""
        print("일일 데이터 업데이트 시작...")

        # 최근 5일치 주가만 업데이트
        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")

        stocks = self.db.get_stocks()
        codes = stocks['code'].tolist()

        for code in tqdm(codes, desc="주가 업데이트"):
            try:
                df = self.api.get_daily_price(code, start_date)
                if not df.empty:
                    self.db.save_prices(code, df)
            except:
                continue

        print("일일 업데이트 완료")


class AlternativeDataCollector:
    """
    대안 데이터 수집기

    키움 API 없이 FinanceDataReader, pykrx 등을 사용
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self._fdr = None
        self._pykrx = None
        self._dart = None

    def _init_fdr(self):
        """FinanceDataReader 초기화"""
        if self._fdr is None:
            import FinanceDataReader as fdr
            self._fdr = fdr

    def _init_pykrx(self):
        """pykrx 초기화"""
        if self._pykrx is None:
            from pykrx import stock
            self._pykrx = stock

    def collect_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """종목 리스트 수집 (FinanceDataReader)"""
        self._init_fdr()

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
            df = df.rename(columns={'Code': 'code', 'Name': 'name', 'Sector': 'sector'})
        elif 'Symbol' in df.columns:
            df = df.rename(columns={'Symbol': 'code', 'Name': 'name', 'Sector': 'sector'})

        # 우선주, 스팩, ETF 등 제외
        df = df[~df['name'].str.contains('스팩|ETF|ETN|리츠|우$|우B|우C', na=False)]

        # DB 저장
        self.db.save_stocks(df[['code', 'name', 'market', 'sector']])

        return df

    def collect_price_data(self,
                           codes: Optional[List[str]] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> None:
        """주가 데이터 수집 (FinanceDataReader)"""
        self._init_fdr()

        if codes is None:
            stocks = self.db.get_stocks()
            codes = stocks['code'].tolist()

        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")
        else:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"

        for code in tqdm(codes, desc="주가 수집"):
            try:
                df = self._fdr.DataReader(code, start_date, end_date)
                if df is not None and not df.empty:
                    df = df.reset_index()
                    df = df.rename(columns={
                        'Date': 'date',
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    self.db.save_prices(code, df[['date', 'open', 'high', 'low', 'close', 'volume']])
            except Exception as e:
                continue

    def collect_financial_data_from_krx(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        KRX에서 재무 데이터 수집 (pykrx)

        Args:
            date: 조회일 (YYYYMMDD)
        """
        self._init_pykrx()

        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        # 전체 종목 재무 데이터
        df = self._pykrx.get_market_fundamental(date, market="ALL")

        if df is not None and not df.empty:
            df = df.reset_index()
            df = df.rename(columns={
                '티커': 'code',
                'BPS': 'bps',
                'PER': 'per',
                'PBR': 'pbr',
                'EPS': 'eps',
                'DIV': 'dividend_yield',
                'DPS': 'dps'
            })

        return df

    def collect_all(self, market: str = "ALL") -> None:
        """전체 데이터 수집"""
        print("대안 데이터 소스로 수집 시작...")

        self.collect_stock_list(market)
        self.collect_price_data()

        print("수집 완료")
