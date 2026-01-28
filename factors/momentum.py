"""
모멘텀 팩터 모듈

모멘텀 팩터는 과거 주가 수익률을 기반으로 미래 수익을 예측합니다.
"추세는 지속된다"는 가정에 기반합니다.
"""
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from .base import BaseFactor


class MomentumFactor(BaseFactor):
    """
    모멘텀 팩터

    구성 지표:
    - 3개월 수익률
    - 6개월 수익률
    - 12개월 수익률 (최근 1개월 제외 가능)
    """

    def __init__(self, periods: Optional[List[int]] = None):
        """
        Args:
            periods: 모멘텀 계산 기간 (개월) 리스트
        """
        super().__init__(name='momentum')
        self.periods = periods or [3, 6, 12]

    def get_factor_names(self) -> List[str]:
        return [f'momentum_{p}m' for p in self.periods]

    def get_ascending_map(self) -> Dict[str, bool]:
        """모멘텀은 높을수록 좋음"""
        return {f'momentum_{p}m': False for p in self.periods}

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        모멘텀 팩터 계산

        필요한 컬럼:
        - prices DataFrame: index=date, columns=stock codes

        또는

        - 개별 종목 가격 데이터

        Args:
            data: 가격 데이터 DataFrame

        Returns:
            모멘텀 팩터가 추가된 DataFrame
        """
        result = data.copy()

        # DataFrame 형태에 따라 처리
        if 'close' in data.columns:
            # 단일 종목 데이터
            for period in self.periods:
                result[f'momentum_{period}m'] = self.calculate_single_momentum(
                    data['close'],
                    period
                )
        else:
            # 멀티 종목 데이터 (columns = codes)
            for period in self.periods:
                result[f'momentum_{period}m'] = self.calculate_cross_sectional_momentum(
                    data,
                    period
                )

        return result

    def calculate_single_momentum(self,
                                   prices: pd.Series,
                                   months: int,
                                   skip_recent: int = 0) -> pd.Series:
        """
        단일 종목 모멘텀 계산

        Args:
            prices: 가격 Series (index=date)
            months: 모멘텀 기간 (개월)
            skip_recent: 최근 제외 기간 (개월), 반전효과 방지용

        Returns:
            모멘텀 수익률 Series
        """
        trading_days = months * 21  # 월 평균 21 거래일
        skip_days = skip_recent * 21

        if len(prices) < trading_days + skip_days:
            return pd.Series(np.nan, index=prices.index)

        if skip_days > 0:
            current = prices.shift(skip_days)
            past = prices.shift(trading_days + skip_days)
        else:
            current = prices
            past = prices.shift(trading_days)

        momentum = (current - past) / past
        return momentum

    def calculate_cross_sectional_momentum(self,
                                            price_df: pd.DataFrame,
                                            months: int,
                                            skip_recent: int = 0) -> pd.Series:
        """
        횡단면 모멘텀 계산 (여러 종목 동시)

        Args:
            price_df: 가격 DataFrame (index=date, columns=codes)
            months: 모멘텀 기간 (개월)
            skip_recent: 최근 제외 기간 (개월)

        Returns:
            종목별 모멘텀 Series
        """
        trading_days = months * 21
        skip_days = skip_recent * 21

        if len(price_df) < trading_days + skip_days + 1:
            return pd.Series(dtype=float)

        if skip_days > 0:
            current_prices = price_df.iloc[-(skip_days + 1)]
            past_prices = price_df.iloc[-(trading_days + skip_days + 1)]
        else:
            current_prices = price_df.iloc[-1]
            past_prices = price_df.iloc[-(trading_days + 1)]

        momentum = (current_prices - past_prices) / past_prices
        return momentum

    def calculate_momentum_12_1(self, prices: pd.Series) -> pd.Series:
        """
        12-1 모멘텀 계산

        12개월 수익률에서 최근 1개월 제외
        단기 반전효과(short-term reversal)를 피하기 위함

        Jegadeesh & Titman (1993) 연구에서 제안된 방법

        Args:
            prices: 가격 Series

        Returns:
            12-1 모멘텀 Series
        """
        return self.calculate_single_momentum(prices, months=12, skip_recent=1)

    def calculate_relative_strength(self,
                                     stock_prices: pd.Series,
                                     benchmark_prices: pd.Series,
                                     months: int = 12) -> pd.Series:
        """
        상대 강도 계산

        개별 종목 수익률 - 벤치마크 수익률

        Args:
            stock_prices: 개별 종목 가격
            benchmark_prices: 벤치마크 (예: KOSPI) 가격
            months: 기간 (개월)

        Returns:
            상대 강도 Series
        """
        stock_momentum = self.calculate_single_momentum(stock_prices, months)
        benchmark_momentum = self.calculate_single_momentum(benchmark_prices, months)

        return stock_momentum - benchmark_momentum

    def calculate_acceleration(self,
                                prices: pd.Series,
                                short_period: int = 3,
                                long_period: int = 12) -> pd.Series:
        """
        모멘텀 가속도 계산

        단기 모멘텀 - 장기 모멘텀
        양수면 추세 강화, 음수면 추세 약화

        Args:
            prices: 가격 Series
            short_period: 단기 기간 (개월)
            long_period: 장기 기간 (개월)

        Returns:
            모멘텀 가속도 Series
        """
        short_momentum = self.calculate_single_momentum(prices, short_period)
        long_momentum = self.calculate_single_momentum(prices, long_period)

        return short_momentum - long_momentum

    def get_momentum_quintiles(self,
                                momentum_values: pd.Series,
                                n_groups: int = 5) -> pd.Series:
        """
        모멘텀 분위수 그룹 할당

        Args:
            momentum_values: 모멘텀 값 Series
            n_groups: 분위수 (기본 5분위)

        Returns:
            분위수 그룹 Series (1=최저, n_groups=최고)
        """
        return pd.qcut(
            momentum_values.rank(method='first'),
            q=n_groups,
            labels=range(1, n_groups + 1)
        )
