"""
백테스트 모듈 테스트
"""
import pytest
import pandas as pd
import numpy as np

from backtest.metrics import PerformanceMetrics


class TestPerformanceMetrics:
    """성과 지표 테스트"""

    @pytest.fixture
    def sample_returns(self):
        """테스트용 수익률 시리즈"""
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', periods=252, freq='B')
        returns = np.random.normal(0.0005, 0.02, len(dates))
        return pd.Series(returns, index=dates)

    @pytest.fixture
    def sample_values(self):
        """테스트용 포트폴리오 가치 시리즈"""
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', periods=252, freq='B')
        returns = np.random.normal(0.0005, 0.02, len(dates))
        values = 100000000 * (1 + returns).cumprod()
        return pd.Series(values, index=dates)

    def test_total_return(self):
        """총 수익률 테스트"""
        total_return = PerformanceMetrics.calculate_total_return(100, 150)
        assert total_return == 0.5

        total_return_loss = PerformanceMetrics.calculate_total_return(100, 80)
        assert total_return_loss == -0.2

    def test_cagr(self):
        """CAGR 테스트"""
        # 2년간 100 -> 121 = CAGR 10%
        cagr = PerformanceMetrics.calculate_cagr(100, 121, 2)
        assert abs(cagr - 0.10) < 0.01

        # 3년간 100 -> 133.1 = CAGR 10%
        cagr_3y = PerformanceMetrics.calculate_cagr(100, 133.1, 3)
        assert abs(cagr_3y - 0.10) < 0.01

    def test_volatility(self, sample_returns):
        """변동성 테스트"""
        vol = PerformanceMetrics.calculate_volatility(sample_returns)

        # 연율화 변동성은 양수
        assert vol > 0

        # 일간 변동성
        daily_vol = PerformanceMetrics.calculate_volatility(sample_returns, annualize=False)
        assert daily_vol < vol

    def test_sharpe_ratio(self, sample_returns):
        """샤프 비율 테스트"""
        sharpe = PerformanceMetrics.calculate_sharpe_ratio(sample_returns)

        # 샤프 비율은 실수
        assert isinstance(sharpe, float)

    def test_mdd(self, sample_values):
        """MDD 테스트"""
        mdd = PerformanceMetrics.calculate_mdd(sample_values)

        # MDD는 0 이상
        assert mdd >= 0
        # MDD는 1 이하 (100% 손실 이하)
        assert mdd <= 1

    def test_win_rate(self, sample_returns):
        """승률 테스트"""
        win_rate = PerformanceMetrics.calculate_win_rate(sample_returns)

        assert 0 <= win_rate <= 1

    def test_sortino_ratio(self, sample_returns):
        """소르티노 비율 테스트"""
        sortino = PerformanceMetrics.calculate_sortino_ratio(sample_returns)

        # 소르티노 비율은 실수
        assert isinstance(sortino, float)

    def test_calmar_ratio(self):
        """칼마 비율 테스트"""
        calmar = PerformanceMetrics.calculate_calmar_ratio(0.15, 0.10)
        assert calmar == 1.5

        # MDD가 0이면 무한대
        calmar_zero_mdd = PerformanceMetrics.calculate_calmar_ratio(0.15, 0)
        assert calmar_zero_mdd == float('inf')

    def test_beta(self, sample_returns):
        """베타 테스트"""
        np.random.seed(123)
        benchmark_returns = pd.Series(
            np.random.normal(0.0003, 0.015, len(sample_returns)),
            index=sample_returns.index
        )

        beta = PerformanceMetrics.calculate_beta(sample_returns, benchmark_returns)

        # 베타는 실수
        assert isinstance(beta, float)

    def test_alpha(self, sample_returns):
        """알파 테스트"""
        np.random.seed(123)
        benchmark_returns = pd.Series(
            np.random.normal(0.0003, 0.015, len(sample_returns)),
            index=sample_returns.index
        )

        alpha = PerformanceMetrics.calculate_alpha(sample_returns, benchmark_returns)

        # 알파는 실수
        assert isinstance(alpha, float)

    def test_calculate_all_metrics(self, sample_values):
        """전체 지표 계산 테스트"""
        metrics = PerformanceMetrics.calculate_all_metrics(sample_values)

        assert 'total_return' in metrics
        assert 'cagr' in metrics
        assert 'volatility' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'mdd' in metrics
        assert 'win_rate' in metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
