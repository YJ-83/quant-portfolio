"""
전략 모듈 테스트
"""
import pytest
import pandas as pd
import numpy as np

from strategies.magic_formula import MagicFormulaStrategy
from strategies.multifactor import MultifactorStrategy
from strategies.sector_neutral import SectorNeutralStrategy


class TestMagicFormulaStrategy:
    """마법공식 전략 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 샘플 데이터"""
        np.random.seed(42)
        n = 200

        return pd.DataFrame({
            'code': [f'{i:06d}' for i in range(1, n + 1)],
            'name': [f'종목{i}' for i in range(1, n + 1)],
            'sector': np.random.choice(['IT', '금융', '소재', '산업재'], n),
            'market_cap': np.random.uniform(1e11, 1e13, n),
            'ebit': np.random.uniform(1e9, 1e11, n),
            'net_debt': np.random.uniform(-1e11, 1e12, n),
            'invested_capital': np.random.uniform(1e10, 1e12, n),
            'roe': np.random.uniform(-0.1, 0.3, n),
            'per': np.random.uniform(3, 50, n)
        })

    def test_select_stocks(self, sample_data):
        """종목 선정 테스트"""
        strategy = MagicFormulaStrategy(top_n=30)
        result = strategy.select_stocks(sample_data)

        assert result.selected_count <= 30
        assert result.selected_count > 0
        assert 'score' in result.stocks.columns
        assert 'rank' in result.stocks.columns

    def test_simplified_version(self, sample_data):
        """간소화 버전 테스트"""
        strategy = MagicFormulaStrategy(top_n=30, use_simplified=True)
        result = strategy.select_stocks(sample_data)

        assert result.selected_count <= 30

    def test_exclude_financials(self, sample_data):
        """금융주 제외 테스트"""
        strategy = MagicFormulaStrategy(top_n=30, exclude_financials=True)
        result = strategy.select_stocks(sample_data)

        # 선정된 종목 중 금융 섹터가 없어야 함
        financial_count = result.stocks['sector'].str.contains('금융').sum()
        assert financial_count == 0


class TestMultifactorStrategy:
    """멀티팩터 전략 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 샘플 데이터"""
        np.random.seed(42)
        n = 200

        return pd.DataFrame({
            'code': [f'{i:06d}' for i in range(1, n + 1)],
            'name': [f'종목{i}' for i in range(1, n + 1)],
            'sector': np.random.choice(['IT', '소재', '산업재', '필수소비재'], n),
            'market_cap': np.random.uniform(1e11, 1e13, n),
            # 퀄리티
            'roe': np.random.uniform(-0.1, 0.3, n),
            'gpa': np.random.uniform(0, 0.5, n),
            'cfo_ratio': np.random.uniform(-0.1, 0.2, n),
            # 밸류
            'per': np.random.uniform(3, 50, n),
            'pbr': np.random.uniform(0.3, 5, n),
            'psr': np.random.uniform(0.5, 10, n),
            'pcr': np.random.uniform(2, 30, n),
            # 모멘텀
            'momentum_3m': np.random.uniform(-0.3, 0.5, n),
            'momentum_6m': np.random.uniform(-0.4, 0.6, n),
            'momentum_12m': np.random.uniform(-0.5, 1.0, n)
        })

    def test_select_stocks(self, sample_data):
        """종목 선정 테스트"""
        strategy = MultifactorStrategy(top_n=30)
        result = strategy.select_stocks(sample_data)

        assert result.selected_count <= 30
        assert result.selected_count > 0

    def test_custom_weights(self, sample_data):
        """커스텀 가중치 테스트"""
        strategy = MultifactorStrategy(
            top_n=30,
            weights={'quality': 0.5, 'value': 0.3, 'momentum': 0.2}
        )
        result = strategy.select_stocks(sample_data)

        assert result.selected_count <= 30

    def test_factor_correlations(self, sample_data):
        """팩터 상관관계 테스트"""
        strategy = MultifactorStrategy(top_n=30)
        correlations = strategy.get_factor_correlations(sample_data)

        assert 'quality' in correlations.columns or len(correlations.columns) > 0


class TestSectorNeutralStrategy:
    """섹터 중립 전략 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 샘플 데이터"""
        np.random.seed(42)
        n = 200

        sectors = ['IT', '소재', '산업재', '필수소비재', '금융']
        sector_list = np.random.choice(sectors, n)

        return pd.DataFrame({
            'code': [f'{i:06d}' for i in range(1, n + 1)],
            'name': [f'종목{i}' for i in range(1, n + 1)],
            'sector': sector_list,
            'market_cap': np.random.uniform(1e11, 1e13, n),
            'momentum_12m': np.random.uniform(-0.5, 1.0, n)
        })

    def test_select_stocks(self, sample_data):
        """종목 선정 테스트"""
        strategy = SectorNeutralStrategy(
            top_n=30,
            factor_name='momentum_12m'
        )
        result = strategy.select_stocks(sample_data)

        assert result.selected_count <= 30

    def test_sector_distribution(self, sample_data):
        """섹터 분포 테스트"""
        strategy = SectorNeutralStrategy(
            top_n=30,
            factor_name='momentum_12m'
        )
        result = strategy.select_stocks(sample_data)

        # 여러 섹터에 분산되어야 함
        unique_sectors = result.stocks['sector'].nunique()
        assert unique_sectors > 1

    def test_fixed_per_sector(self, sample_data):
        """섹터당 고정 종목 수 테스트"""
        strategy = SectorNeutralStrategy(
            top_n=30,
            factor_name='momentum_12m',
            stocks_per_sector=3
        )
        result = strategy.select_stocks(sample_data)

        # 각 섹터에서 최대 3개씩 선정
        max_per_sector = result.stocks.groupby('sector').size().max()
        assert max_per_sector <= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
