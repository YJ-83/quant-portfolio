"""
성과 지표 계산 모듈
"""
from typing import Optional
import pandas as pd
import numpy as np

from config.settings import settings


class PerformanceMetrics:
    """투자 성과 지표 계산 클래스"""

    @staticmethod
    def calculate_total_return(initial_value: float, final_value: float) -> float:
        """
        총 수익률 계산

        Args:
            initial_value: 초기 자산
            final_value: 최종 자산

        Returns:
            총 수익률 (예: 0.5 = 50%)
        """
        if initial_value <= 0:
            return 0
        return (final_value - initial_value) / initial_value

    @staticmethod
    def calculate_cagr(initial_value: float,
                       final_value: float,
                       years: float) -> float:
        """
        CAGR (연평균 복합 성장률) 계산

        CAGR = (최종가치/초기가치)^(1/년수) - 1

        Args:
            initial_value: 초기 자산
            final_value: 최종 자산
            years: 투자 기간 (년)

        Returns:
            CAGR (예: 0.15 = 15%)
        """
        if initial_value <= 0 or years <= 0:
            return 0

        if final_value <= 0:
            return -1

        return (final_value / initial_value) ** (1 / years) - 1

    @staticmethod
    def calculate_volatility(returns: pd.Series,
                             annualize: bool = True) -> float:
        """
        변동성 계산

        변동성 = 일간수익률의 표준편차 × √252

        Args:
            returns: 수익률 Series
            annualize: 연율화 여부

        Returns:
            변동성
        """
        if len(returns) < 2:
            return 0

        daily_vol = returns.std()

        if annualize:
            return daily_vol * np.sqrt(settings.TRADING_DAYS_PER_YEAR)

        return daily_vol

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series,
                               risk_free_rate: float = None) -> float:
        """
        샤프 비율 계산

        샤프비율 = (포트폴리오 수익률 - 무위험 수익률) / 변동성

        Args:
            returns: 일간 수익률 Series
            risk_free_rate: 무위험 수익률 (연율, 기본값: settings.RISK_FREE_RATE)

        Returns:
            샤프 비율
        """
        if len(returns) < 2:
            return 0

        if risk_free_rate is None:
            risk_free_rate = settings.RISK_FREE_RATE

        # 일간 무위험 수익률
        daily_rf = risk_free_rate / settings.TRADING_DAYS_PER_YEAR

        # 초과 수익률
        excess_returns = returns - daily_rf

        # 연율화 샤프 비율
        if excess_returns.std() == 0:
            return 0

        sharpe = excess_returns.mean() / excess_returns.std()
        return sharpe * np.sqrt(settings.TRADING_DAYS_PER_YEAR)

    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series,
                                risk_free_rate: float = None) -> float:
        """
        소르티노 비율 계산

        하방 변동성만 고려한 위험 조정 수익률
        소르티노 = (수익률 - 무위험수익률) / 하방편차

        Args:
            returns: 일간 수익률 Series
            risk_free_rate: 무위험 수익률

        Returns:
            소르티노 비율
        """
        if len(returns) < 2:
            return 0

        if risk_free_rate is None:
            risk_free_rate = settings.RISK_FREE_RATE

        daily_rf = risk_free_rate / settings.TRADING_DAYS_PER_YEAR
        excess_returns = returns - daily_rf

        # 하방 편차 (음수 수익률만)
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return float('inf') if excess_returns.mean() > 0 else 0

        downside_std = downside_returns.std()
        sortino = excess_returns.mean() / downside_std

        return sortino * np.sqrt(settings.TRADING_DAYS_PER_YEAR)

    @staticmethod
    def calculate_mdd(values: pd.Series) -> float:
        """
        MDD (최대 낙폭) 계산

        MDD = max((고점 - 저점) / 고점)

        Args:
            values: 포트폴리오 가치 Series

        Returns:
            MDD (예: 0.3 = -30%)
        """
        if len(values) < 2:
            return 0

        # 누적 최고점
        running_max = values.expanding().max()

        # 낙폭
        drawdown = (values - running_max) / running_max

        # 최대 낙폭
        mdd = drawdown.min()

        return abs(mdd)

    @staticmethod
    def calculate_drawdown_series(values: pd.Series) -> pd.Series:
        """
        낙폭 시리즈 계산

        Args:
            values: 포트폴리오 가치 Series

        Returns:
            낙폭 Series
        """
        running_max = values.expanding().max()
        drawdown = (values - running_max) / running_max
        return drawdown

    @staticmethod
    def calculate_calmar_ratio(cagr: float, mdd: float) -> float:
        """
        칼마 비율 계산

        칼마 = CAGR / MDD

        위험 대비 수익률 측정

        Args:
            cagr: 연평균 복합 성장률
            mdd: 최대 낙폭

        Returns:
            칼마 비율
        """
        if mdd == 0:
            return float('inf') if cagr > 0 else 0
        return cagr / mdd

    @staticmethod
    def calculate_win_rate(returns: pd.Series) -> float:
        """
        승률 계산

        양수 수익률 비중

        Args:
            returns: 수익률 Series

        Returns:
            승률 (예: 0.55 = 55%)
        """
        if len(returns) == 0:
            return 0

        wins = (returns > 0).sum()
        return wins / len(returns)

    @staticmethod
    def calculate_profit_loss_ratio(returns: pd.Series) -> float:
        """
        손익비 계산

        평균 이익 / 평균 손실

        Args:
            returns: 수익률 Series

        Returns:
            손익비
        """
        profits = returns[returns > 0]
        losses = returns[returns < 0]

        if len(losses) == 0 or losses.mean() == 0:
            return float('inf') if len(profits) > 0 else 0

        avg_profit = profits.mean() if len(profits) > 0 else 0
        avg_loss = abs(losses.mean())

        return avg_profit / avg_loss

    @staticmethod
    def calculate_information_ratio(returns: pd.Series,
                                     benchmark_returns: pd.Series) -> float:
        """
        정보 비율 계산

        IR = 초과수익률 / 추적오차

        Args:
            returns: 포트폴리오 수익률
            benchmark_returns: 벤치마크 수익률

        Returns:
            정보 비율
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0

        # 데이터 정렬
        common_idx = returns.index.intersection(benchmark_returns.index)
        returns = returns.loc[common_idx]
        benchmark_returns = benchmark_returns.loc[common_idx]

        # 초과 수익률
        excess = returns - benchmark_returns

        if excess.std() == 0:
            return 0

        ir = excess.mean() / excess.std()
        return ir * np.sqrt(settings.TRADING_DAYS_PER_YEAR)

    @staticmethod
    def calculate_beta(returns: pd.Series,
                       benchmark_returns: pd.Series) -> float:
        """
        베타 계산

        베타 = Cov(Rp, Rm) / Var(Rm)

        Args:
            returns: 포트폴리오 수익률
            benchmark_returns: 시장 수익률

        Returns:
            베타
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 1

        common_idx = returns.index.intersection(benchmark_returns.index)
        returns = returns.loc[common_idx]
        benchmark_returns = benchmark_returns.loc[common_idx]

        covariance = returns.cov(benchmark_returns)
        variance = benchmark_returns.var()

        if variance == 0:
            return 1

        return covariance / variance

    @staticmethod
    def calculate_alpha(returns: pd.Series,
                        benchmark_returns: pd.Series,
                        risk_free_rate: float = None) -> float:
        """
        알파(Jensen's Alpha) 계산

        알파 = Rp - (Rf + β × (Rm - Rf))

        Args:
            returns: 포트폴리오 수익률
            benchmark_returns: 시장 수익률
            risk_free_rate: 무위험 수익률

        Returns:
            알파 (연율화)
        """
        if len(returns) < 2:
            return 0

        if risk_free_rate is None:
            risk_free_rate = settings.RISK_FREE_RATE

        daily_rf = risk_free_rate / settings.TRADING_DAYS_PER_YEAR

        common_idx = returns.index.intersection(benchmark_returns.index)
        returns = returns.loc[common_idx]
        benchmark_returns = benchmark_returns.loc[common_idx]

        beta = PerformanceMetrics.calculate_beta(returns, benchmark_returns)

        expected_return = daily_rf + beta * (benchmark_returns.mean() - daily_rf)
        alpha = returns.mean() - expected_return

        return alpha * settings.TRADING_DAYS_PER_YEAR

    @staticmethod
    def calculate_all_metrics(values: pd.Series,
                              benchmark_values: pd.Series = None,
                              risk_free_rate: float = None) -> dict:
        """
        모든 성과 지표 계산

        Args:
            values: 포트폴리오 가치 Series
            benchmark_values: 벤치마크 가치 Series
            risk_free_rate: 무위험 수익률

        Returns:
            성과 지표 딕셔너리
        """
        if risk_free_rate is None:
            risk_free_rate = settings.RISK_FREE_RATE

        # 수익률 계산
        returns = values.pct_change().dropna()

        # 투자 기간 (년)
        if isinstance(values.index, pd.DatetimeIndex):
            years = (values.index[-1] - values.index[0]).days / 365
        else:
            years = len(values) / settings.TRADING_DAYS_PER_YEAR

        metrics = {
            'initial_value': values.iloc[0],
            'final_value': values.iloc[-1],
            'total_return': PerformanceMetrics.calculate_total_return(
                values.iloc[0], values.iloc[-1]
            ),
            'cagr': PerformanceMetrics.calculate_cagr(
                values.iloc[0], values.iloc[-1], years
            ),
            'volatility': PerformanceMetrics.calculate_volatility(returns),
            'sharpe_ratio': PerformanceMetrics.calculate_sharpe_ratio(
                returns, risk_free_rate
            ),
            'sortino_ratio': PerformanceMetrics.calculate_sortino_ratio(
                returns, risk_free_rate
            ),
            'mdd': PerformanceMetrics.calculate_mdd(values),
            'win_rate': PerformanceMetrics.calculate_win_rate(returns),
            'profit_loss_ratio': PerformanceMetrics.calculate_profit_loss_ratio(returns),
            'years': years
        }

        # 칼마 비율
        metrics['calmar_ratio'] = PerformanceMetrics.calculate_calmar_ratio(
            metrics['cagr'], metrics['mdd']
        )

        # 벤치마크 대비 지표
        if benchmark_values is not None and len(benchmark_values) > 0:
            benchmark_returns = benchmark_values.pct_change().dropna()

            metrics['beta'] = PerformanceMetrics.calculate_beta(
                returns, benchmark_returns
            )
            metrics['alpha'] = PerformanceMetrics.calculate_alpha(
                returns, benchmark_returns, risk_free_rate
            )
            metrics['information_ratio'] = PerformanceMetrics.calculate_information_ratio(
                returns, benchmark_returns
            )
            metrics['benchmark_return'] = PerformanceMetrics.calculate_total_return(
                benchmark_values.iloc[0], benchmark_values.iloc[-1]
            )
            metrics['excess_return'] = metrics['total_return'] - metrics['benchmark_return']

        return metrics
