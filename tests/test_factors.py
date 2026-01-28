"""
팩터 모듈 테스트
"""
import pytest
import pandas as pd
import numpy as np

from factors.quality import QualityFactor
from factors.value import ValueFactor
from factors.momentum import MomentumFactor
from utils.ranking import RankingCalculator
from utils.outlier import OutlierHandler


class TestQualityFactor:
    """퀄리티 팩터 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 샘플 데이터"""
        np.random.seed(42)
        return pd.DataFrame({
            'code': [f'{i:06d}' for i in range(1, 101)],
            'net_income': np.random.uniform(1e9, 1e11, 100),
            'total_equity': np.random.uniform(1e10, 1e12, 100),
            'gross_profit': np.random.uniform(1e9, 1e11, 100),
            'total_assets': np.random.uniform(1e10, 1e12, 100),
            'operating_cf': np.random.uniform(-1e10, 1e11, 100)
        })

    def test_calculate_roe(self, sample_data):
        """ROE 계산 테스트"""
        factor = QualityFactor()
        result = factor.calculate(sample_data)

        assert 'roe' in result.columns
        assert result['roe'].notna().sum() > 0
        assert (result['roe'] >= -1).all()  # 합리적인 범위

    def test_calculate_gpa(self, sample_data):
        """GPA 계산 테스트"""
        factor = QualityFactor()
        result = factor.calculate(sample_data)

        assert 'gpa' in result.columns
        assert result['gpa'].notna().sum() > 0

    def test_calculate_cfo_ratio(self, sample_data):
        """영업현금흐름율 계산 테스트"""
        factor = QualityFactor()
        result = factor.calculate(sample_data)

        assert 'cfo_ratio' in result.columns


class TestValueFactor:
    """밸류 팩터 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 샘플 데이터"""
        np.random.seed(42)
        return pd.DataFrame({
            'code': [f'{i:06d}' for i in range(1, 101)],
            'market_cap': np.random.uniform(1e11, 1e13, 100),
            'net_income': np.random.uniform(1e9, 1e11, 100),
            'total_equity': np.random.uniform(1e10, 1e12, 100),
            'revenue': np.random.uniform(1e10, 1e12, 100),
            'operating_cf': np.random.uniform(1e9, 1e11, 100),
            'ebit': np.random.uniform(1e9, 1e11, 100),
            'net_debt': np.random.uniform(-1e11, 1e12, 100)
        })

    def test_calculate_per(self, sample_data):
        """PER 계산 테스트"""
        factor = ValueFactor()
        result = factor.calculate(sample_data)

        assert 'per' in result.columns
        # 음수 PER은 NaN이어야 함
        assert result.loc[result['per'].notna(), 'per'].min() >= 0

    def test_calculate_pbr(self, sample_data):
        """PBR 계산 테스트"""
        factor = ValueFactor()
        result = factor.calculate(sample_data)

        assert 'pbr' in result.columns

    def test_calculate_earnings_yield(self, sample_data):
        """이익수익률 계산 테스트"""
        factor = ValueFactor()
        result = factor.calculate(sample_data)

        assert 'earnings_yield' in result.columns


class TestMomentumFactor:
    """모멘텀 팩터 테스트"""

    @pytest.fixture
    def price_series(self):
        """테스트용 가격 시리즈"""
        np.random.seed(42)
        dates = pd.date_range(start='2020-01-01', periods=300, freq='B')
        prices = 10000 * (1 + np.random.normal(0.001, 0.02, len(dates))).cumprod()
        return pd.Series(prices, index=dates)

    def test_calculate_single_momentum(self, price_series):
        """단일 종목 모멘텀 계산 테스트"""
        factor = MomentumFactor()

        mom_3m = factor.calculate_single_momentum(price_series, months=3)
        mom_12m = factor.calculate_single_momentum(price_series, months=12)

        assert len(mom_3m) == len(price_series)
        assert len(mom_12m) == len(price_series)

    def test_momentum_12_1(self, price_series):
        """12-1 모멘텀 테스트"""
        factor = MomentumFactor()

        mom_12_1 = factor.calculate_momentum_12_1(price_series)

        assert len(mom_12_1) == len(price_series)


class TestRankingCalculator:
    """랭킹 계산 테스트"""

    @pytest.fixture
    def sample_series(self):
        """테스트용 시리즈"""
        return pd.Series([10, 20, 30, 40, 50, np.nan, 15, 25])

    def test_rank(self, sample_series):
        """랭킹 테스트"""
        calc = RankingCalculator()

        ranks = calc.rank(sample_series, ascending=True)

        assert ranks.notna().sum() == 7  # NaN 제외
        assert ranks.min() == 1

    def test_zscore(self, sample_series):
        """Z-score 테스트"""
        calc = RankingCalculator()

        zscores = calc.zscore(sample_series)

        # Z-score 평균은 0에 가까워야 함
        assert abs(zscores.mean()) < 0.01

    def test_zscore_rank(self, sample_series):
        """Z-score(Rank) 테스트"""
        calc = RankingCalculator()

        zscore_rank = calc.zscore_rank(sample_series, ascending=True)

        assert len(zscore_rank) == len(sample_series)

    def test_combine_factors(self):
        """팩터 결합 테스트"""
        calc = RankingCalculator()

        factor_df = pd.DataFrame({
            'factor_a': [10, 20, 30, 40, 50],
            'factor_b': [50, 40, 30, 20, 10]
        })

        combined = calc.combine_factors(
            factor_df,
            weights={'factor_a': 0.5, 'factor_b': 0.5},
            ascending_map={'factor_a': True, 'factor_b': True}
        )

        assert len(combined) == 5


class TestOutlierHandler:
    """이상치 처리 테스트"""

    @pytest.fixture
    def sample_with_outliers(self):
        """이상치 포함 샘플"""
        np.random.seed(42)
        data = np.random.normal(100, 20, 100)
        data[0] = 1000  # 이상치
        data[1] = -500  # 이상치
        return pd.Series(data)

    def test_winsorize(self, sample_with_outliers):
        """윈저라이징 테스트"""
        handler = OutlierHandler()

        result = handler.winsorize(sample_with_outliers, 0.01, 0.99)

        assert result.max() < sample_with_outliers.max()
        assert result.min() > sample_with_outliers.min()
        assert len(result) == len(sample_with_outliers)

    def test_trim(self, sample_with_outliers):
        """트림 테스트"""
        handler = OutlierHandler()

        result = handler.trim(sample_with_outliers, 0.01, 0.99)

        # 이상치가 NaN으로 변경되어야 함
        assert result.isna().sum() > 0

    def test_zscore_filter(self, sample_with_outliers):
        """Z-score 필터 테스트"""
        handler = OutlierHandler()

        result = handler.zscore_filter(sample_with_outliers, threshold=3.0)

        # 극단적인 이상치는 NaN
        assert result.isna().sum() >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
