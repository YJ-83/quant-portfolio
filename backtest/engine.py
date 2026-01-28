"""
백테스트 엔진 모듈
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from strategies.base import BaseStrategy
from .metrics import PerformanceMetrics
from .report import BacktestResult
from data.database import Database
from config.settings import settings
from utils.helpers import get_rebalance_dates, equal_weight_allocation


@dataclass
class Position:
    """포지션 정보"""
    code: str
    shares: int
    avg_price: float
    current_price: float = 0

    @property
    def value(self) -> float:
        return self.shares * self.current_price

    @property
    def pnl(self) -> float:
        return (self.current_price - self.avg_price) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.avg_price == 0:
            return 0
        return (self.current_price - self.avg_price) / self.avg_price


@dataclass
class Portfolio:
    """포트폴리오 상태"""
    positions: Dict[str, Position] = field(default_factory=dict)
    cash: float = 0

    @property
    def total_value(self) -> float:
        stock_value = sum(p.value for p in self.positions.values())
        return stock_value + self.cash

    def update_prices(self, prices: Dict[str, float]):
        """현재가 업데이트"""
        for code, position in self.positions.items():
            if code in prices:
                position.current_price = prices[code]


class BacktestEngine:
    """
    백테스트 엔진

    전략의 과거 성과를 시뮬레이션합니다.
    """

    def __init__(self,
                 strategy: BaseStrategy,
                 start_date: str,
                 end_date: str,
                 initial_capital: float = None,
                 rebalance_period: str = None,
                 benchmark: str = None,
                 slippage: float = 0.001,
                 commission: float = 0.00015):
        """
        Args:
            strategy: 백테스트할 전략
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            initial_capital: 초기 자본금
            rebalance_period: 리밸런싱 주기 ('monthly', 'quarterly', 'yearly')
            benchmark: 벤치마크 코드 (예: 'KOSPI', '069500')
            slippage: 슬리피지 비율
            commission: 거래 수수료 비율
        """
        self.strategy = strategy
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital or settings.DEFAULT_INITIAL_CAPITAL
        self.rebalance_period = rebalance_period or settings.DEFAULT_REBALANCE_PERIOD
        self.benchmark = benchmark
        self.slippage = slippage
        self.commission = commission

        self.db = Database()
        self.portfolio = Portfolio(cash=self.initial_capital)
        self.portfolio_history: List[Dict] = []
        self.trade_history: List[Dict] = []

    def run(self) -> BacktestResult:
        """
        백테스트 실행

        Returns:
            BacktestResult 객체
        """
        print(f"백테스트 시작: {self.strategy.name}")
        print(f"기간: {self.start_date.date()} ~ {self.end_date.date()}")
        print(f"초기 자본: {self.initial_capital:,.0f}원")

        # 리밸런싱 날짜 생성
        rebalance_dates = get_rebalance_dates(
            self.start_date.strftime('%Y-%m-%d'),
            self.end_date.strftime('%Y-%m-%d'),
            self.rebalance_period
        )

        print(f"리밸런싱 횟수: {len(rebalance_dates)}회 ({self.rebalance_period})")

        # 전체 거래일 가져오기
        trading_days = self._get_trading_days()

        if trading_days.empty:
            raise ValueError("거래일 데이터가 없습니다.")

        # 초기 상태 기록
        self._record_portfolio_state(trading_days.iloc[0])

        # 각 거래일 시뮬레이션
        for date in trading_days:
            # 리밸런싱 날짜인 경우
            if date in rebalance_dates:
                self._rebalance(date)

            # 포트폴리오 가치 업데이트
            self._update_portfolio_value(date)

            # 상태 기록
            self._record_portfolio_state(date)

        # 결과 생성
        result = self._generate_result()

        print(f"\n백테스트 완료!")
        print(f"총 수익률: {result.total_return:.2%}")
        print(f"CAGR: {result.cagr:.2%}")
        print(f"샤프 비율: {result.sharpe_ratio:.2f}")
        print(f"MDD: {result.mdd:.2%}")

        return result

    def _get_trading_days(self) -> pd.DatetimeIndex:
        """거래일 목록 조회"""
        # DB에서 가격 데이터가 있는 날짜 조회
        query = f"""
            SELECT DISTINCT date FROM prices
            WHERE date >= '{self.start_date.strftime('%Y-%m-%d')}'
            AND date <= '{self.end_date.strftime('%Y-%m-%d')}'
            ORDER BY date
        """
        df = self.db.execute_query(query)

        if df.empty:
            # 데이터가 없으면 영업일 기준 생성
            return pd.bdate_range(self.start_date, self.end_date)

        return pd.to_datetime(df['date'])

    def _rebalance(self, date: datetime):
        """
        리밸런싱 실행

        Args:
            date: 리밸런싱 날짜
        """
        print(f"\n리밸런싱: {date.date()}")

        # 1. 현재 데이터로 종목 선정
        data = self._get_stock_data(date)

        if data.empty:
            print("  데이터 없음, 스킵")
            return

        # 2. 전략으로 종목 선정
        result = self.strategy.select_stocks(data)
        selected_codes = result.stocks['code'].tolist()

        print(f"  선정 종목 수: {len(selected_codes)}")

        # 3. 현재 가격 조회
        prices = self._get_current_prices(date, selected_codes)

        # 4. 기존 포지션 청산
        self._liquidate_all(date, prices)

        # 5. 새 포지션 매수
        self._buy_portfolio(date, selected_codes, prices)

    def _get_stock_data(self, date: datetime) -> pd.DataFrame:
        """
        특정 날짜의 종목 데이터 조회

        재무 데이터 + 가격 데이터 결합
        """
        # 종목 목록
        stocks = self.db.get_stocks()

        if stocks.empty:
            return pd.DataFrame()

        # 재무 데이터 (가장 최근 연도)
        year = date.year if date.month > 3 else date.year - 1
        financials = self.db.get_financials(year=year)

        # 가격 데이터로 모멘텀 계산
        price_data = self._calculate_momentum(date, stocks['code'].tolist())

        # 데이터 병합
        data = stocks.merge(financials, on='code', how='left')

        if not price_data.empty:
            data = data.merge(price_data, on='code', how='left')

        return data

    def _calculate_momentum(self, date: datetime, codes: List[str]) -> pd.DataFrame:
        """
        모멘텀 계산

        Args:
            date: 기준 날짜
            codes: 종목 코드 리스트

        Returns:
            모멘텀 DataFrame
        """
        momentum_data = []

        for code in codes:
            prices = self.db.get_prices(
                code,
                start_date=(date - timedelta(days=400)).strftime('%Y-%m-%d'),
                end_date=date.strftime('%Y-%m-%d')
            )

            if prices.empty or len(prices) < 21:
                continue

            current_price = prices['close'].iloc[-1]

            momentum = {'code': code, 'close': current_price}

            # 3개월 모멘텀
            if len(prices) >= 63:
                price_3m = prices['close'].iloc[-63]
                momentum['momentum_3m'] = (current_price - price_3m) / price_3m

            # 6개월 모멘텀
            if len(prices) >= 126:
                price_6m = prices['close'].iloc[-126]
                momentum['momentum_6m'] = (current_price - price_6m) / price_6m

            # 12개월 모멘텀
            if len(prices) >= 252:
                price_12m = prices['close'].iloc[-252]
                momentum['momentum_12m'] = (current_price - price_12m) / price_12m

            momentum_data.append(momentum)

        return pd.DataFrame(momentum_data)

    def _get_current_prices(self, date: datetime, codes: List[str]) -> Dict[str, float]:
        """현재가 조회"""
        prices = {}

        for code in codes:
            df = self.db.get_prices(
                code,
                start_date=(date - timedelta(days=10)).strftime('%Y-%m-%d'),
                end_date=date.strftime('%Y-%m-%d')
            )

            if not df.empty:
                prices[code] = df['close'].iloc[-1]

        return prices

    def _liquidate_all(self, date: datetime, prices: Dict[str, float]):
        """전체 포지션 청산"""
        for code, position in list(self.portfolio.positions.items()):
            if code in prices:
                sell_price = prices[code] * (1 - self.slippage)
                proceeds = position.shares * sell_price
                commission = proceeds * self.commission

                self.portfolio.cash += proceeds - commission

                # 거래 기록
                self.trade_history.append({
                    'date': date,
                    'code': code,
                    'action': 'SELL',
                    'shares': position.shares,
                    'price': sell_price,
                    'value': proceeds,
                    'commission': commission
                })

        self.portfolio.positions.clear()

    def _buy_portfolio(self, date: datetime, codes: List[str], prices: Dict[str, float]):
        """포트폴리오 매수"""
        if not codes:
            return

        # 동일 비중 배분
        available_cash = self.portfolio.cash * 0.99  # 여유 현금 1%
        allocation = available_cash / len(codes)

        for code in codes:
            if code not in prices or prices[code] <= 0:
                continue

            buy_price = prices[code] * (1 + self.slippage)
            shares = int(allocation / buy_price)

            if shares <= 0:
                continue

            cost = shares * buy_price
            commission = cost * self.commission
            total_cost = cost + commission

            if total_cost > self.portfolio.cash:
                continue

            self.portfolio.cash -= total_cost
            self.portfolio.positions[code] = Position(
                code=code,
                shares=shares,
                avg_price=buy_price,
                current_price=prices[code]
            )

            # 거래 기록
            self.trade_history.append({
                'date': date,
                'code': code,
                'action': 'BUY',
                'shares': shares,
                'price': buy_price,
                'value': cost,
                'commission': commission
            })

    def _update_portfolio_value(self, date: datetime):
        """포트폴리오 가치 업데이트"""
        codes = list(self.portfolio.positions.keys())

        if not codes:
            return

        prices = self._get_current_prices(date, codes)
        self.portfolio.update_prices(prices)

    def _record_portfolio_state(self, date: datetime):
        """포트폴리오 상태 기록"""
        self.portfolio_history.append({
            'date': date,
            'total_value': self.portfolio.total_value,
            'cash': self.portfolio.cash,
            'stock_value': self.portfolio.total_value - self.portfolio.cash,
            'num_positions': len(self.portfolio.positions)
        })

    def _generate_result(self) -> BacktestResult:
        """백테스트 결과 생성"""
        # 포트폴리오 히스토리 DataFrame
        portfolio_df = pd.DataFrame(self.portfolio_history)
        portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
        portfolio_df = portfolio_df.set_index('date')

        # 거래 히스토리 DataFrame
        trade_df = pd.DataFrame(self.trade_history) if self.trade_history else pd.DataFrame()

        # 성과 지표 계산
        values = portfolio_df['total_value']

        # 벤치마크 데이터
        benchmark_values = None
        if self.benchmark:
            benchmark_values = self._get_benchmark_data()

        metrics = PerformanceMetrics.calculate_all_metrics(
            values,
            benchmark_values
        )

        return BacktestResult(
            strategy_name=self.strategy.name,
            start_date=self.start_date.strftime('%Y-%m-%d'),
            end_date=self.end_date.strftime('%Y-%m-%d'),
            initial_capital=self.initial_capital,
            final_value=metrics['final_value'],
            total_return=metrics['total_return'],
            cagr=metrics['cagr'],
            sharpe_ratio=metrics['sharpe_ratio'],
            sortino_ratio=metrics.get('sortino_ratio', 0),
            mdd=metrics['mdd'],
            volatility=metrics['volatility'],
            win_rate=metrics['win_rate'],
            calmar_ratio=metrics.get('calmar_ratio', 0),
            portfolio_history=portfolio_df,
            trade_history=trade_df,
            metrics=metrics
        )

    def _get_benchmark_data(self) -> Optional[pd.Series]:
        """벤치마크 데이터 조회"""
        try:
            prices = self.db.get_prices(
                self.benchmark,
                self.start_date.strftime('%Y-%m-%d'),
                self.end_date.strftime('%Y-%m-%d')
            )

            if prices.empty:
                return None

            prices['date'] = pd.to_datetime(prices['date'])
            prices = prices.set_index('date')

            return prices['close']
        except:
            return None


class SimpleBacktestEngine:
    """
    간단한 백테스트 엔진

    데이터가 이미 준비되어 있는 경우 사용
    (연구/분석 목적)
    """

    def __init__(self,
                 strategy: BaseStrategy,
                 price_data: pd.DataFrame,
                 stock_data: pd.DataFrame,
                 rebalance_dates: List[datetime],
                 initial_capital: float = 100_000_000):
        """
        Args:
            strategy: 전략
            price_data: 가격 데이터 (index=date, columns=codes)
            stock_data: 종목 데이터 (팩터 포함)
            rebalance_dates: 리밸런싱 날짜 리스트
            initial_capital: 초기 자본금
        """
        self.strategy = strategy
        self.price_data = price_data
        self.stock_data = stock_data
        self.rebalance_dates = rebalance_dates
        self.initial_capital = initial_capital

    def run(self) -> pd.DataFrame:
        """
        간단한 백테스트 실행

        Returns:
            포트폴리오 가치 DataFrame
        """
        portfolio_values = []
        current_holdings = {}
        cash = self.initial_capital

        for i, date in enumerate(self.price_data.index):
            # 리밸런싱
            if date in self.rebalance_dates:
                # 전량 매도
                for code, shares in current_holdings.items():
                    if code in self.price_data.columns:
                        cash += shares * self.price_data.loc[date, code]

                current_holdings = {}

                # 종목 선정
                result = self.strategy.select_stocks(self.stock_data)
                selected = result.stocks['code'].tolist()

                # 동일 비중 매수
                if selected:
                    allocation = cash / len(selected)
                    for code in selected:
                        if code in self.price_data.columns:
                            price = self.price_data.loc[date, code]
                            if price > 0:
                                shares = int(allocation / price)
                                current_holdings[code] = shares
                                cash -= shares * price

            # 포트폴리오 가치 계산
            stock_value = sum(
                shares * self.price_data.loc[date, code]
                for code, shares in current_holdings.items()
                if code in self.price_data.columns
            )

            portfolio_values.append({
                'date': date,
                'total_value': cash + stock_value,
                'cash': cash,
                'stock_value': stock_value
            })

        return pd.DataFrame(portfolio_values).set_index('date')
