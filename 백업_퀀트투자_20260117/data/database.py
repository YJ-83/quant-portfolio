"""
데이터베이스 관리 모듈
"""
from datetime import datetime
from typing import Optional, List
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import settings


class Database:
    """SQLite 데이터베이스 관리"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(settings.DB_PATH)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self._create_tables()

    def _create_tables(self):
        """테이블 생성"""
        with self.engine.connect() as conn:
            # 종목 정보 테이블
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    sector TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # 주가 데이터 테이블
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prices (
                    code TEXT,
                    date DATE,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (code, date)
                )
            """))

            # 재무 데이터 테이블
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS financials (
                    code TEXT,
                    year INTEGER,
                    quarter INTEGER,
                    revenue REAL,
                    operating_income REAL,
                    net_income REAL,
                    total_assets REAL,
                    total_liabilities REAL,
                    total_equity REAL,
                    operating_cf REAL,
                    gross_profit REAL,
                    ebit REAL,
                    invested_capital REAL,
                    market_cap REAL,
                    shares_outstanding INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, year, quarter)
                )
            """))

            # 팩터 값 테이블
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS factor_values (
                    code TEXT,
                    date DATE,
                    factor_name TEXT,
                    value REAL,
                    rank INTEGER,
                    zscore REAL,
                    PRIMARY KEY (code, date, factor_name)
                )
            """))

            # 백테스트 결과 테이블
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT,
                    start_date DATE,
                    end_date DATE,
                    initial_capital REAL,
                    final_value REAL,
                    total_return REAL,
                    cagr REAL,
                    sharpe_ratio REAL,
                    mdd REAL,
                    volatility REAL,
                    win_rate REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.commit()

    def save_stocks(self, df: pd.DataFrame):
        """종목 정보 저장"""
        df['updated_at'] = datetime.now()
        df.to_sql('stocks', self.engine, if_exists='replace', index=False)

    def get_stocks(self, market: Optional[str] = None) -> pd.DataFrame:
        """종목 정보 조회"""
        query = "SELECT * FROM stocks"
        if market:
            query += f" WHERE market = '{market}'"
        return pd.read_sql(query, self.engine)

    def save_prices(self, code: str, df: pd.DataFrame):
        """주가 데이터 저장"""
        if df.empty:
            return

        df = df.copy()
        df['code'] = code

        # 기존 데이터 삭제 후 저장
        with self.engine.connect() as conn:
            conn.execute(text(f"DELETE FROM prices WHERE code = '{code}'"))
            conn.commit()

        df.to_sql('prices', self.engine, if_exists='append', index=False)

    def get_prices(self,
                   code: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> pd.DataFrame:
        """주가 데이터 조회"""
        query = f"SELECT * FROM prices WHERE code = '{code}'"

        if start_date:
            query += f" AND date >= '{start_date}'"
        if end_date:
            query += f" AND date <= '{end_date}'"

        query += " ORDER BY date"

        df = pd.read_sql(query, self.engine)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def save_financials(self, code: str, data: dict, year: int, quarter: int = 4):
        """재무 데이터 저장"""
        data['code'] = code
        data['year'] = year
        data['quarter'] = quarter
        data['updated_at'] = datetime.now()

        df = pd.DataFrame([data])
        df.to_sql('financials', self.engine, if_exists='replace', index=False)

    def get_financials(self,
                       code: Optional[str] = None,
                       year: Optional[int] = None) -> pd.DataFrame:
        """재무 데이터 조회"""
        query = "SELECT * FROM financials WHERE 1=1"

        if code:
            query += f" AND code = '{code}'"
        if year:
            query += f" AND year = {year}"

        return pd.read_sql(query, self.engine)

    def save_factor_values(self, df: pd.DataFrame):
        """팩터 값 저장"""
        df.to_sql('factor_values', self.engine, if_exists='append', index=False)

    def get_factor_values(self,
                          date: str,
                          factor_name: Optional[str] = None) -> pd.DataFrame:
        """팩터 값 조회"""
        query = f"SELECT * FROM factor_values WHERE date = '{date}'"

        if factor_name:
            query += f" AND factor_name = '{factor_name}'"

        return pd.read_sql(query, self.engine)

    def save_backtest_result(self, result: dict):
        """백테스트 결과 저장"""
        df = pd.DataFrame([result])
        df['created_at'] = datetime.now()
        df.to_sql('backtest_results', self.engine, if_exists='append', index=False)

    def get_backtest_results(self, strategy_name: Optional[str] = None) -> pd.DataFrame:
        """백테스트 결과 조회"""
        query = "SELECT * FROM backtest_results"

        if strategy_name:
            query += f" WHERE strategy_name = '{strategy_name}'"

        query += " ORDER BY created_at DESC"

        return pd.read_sql(query, self.engine)

    def execute_query(self, query: str) -> pd.DataFrame:
        """직접 쿼리 실행"""
        return pd.read_sql(query, self.engine)
