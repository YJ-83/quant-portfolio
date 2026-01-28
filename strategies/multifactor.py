"""
멀티팩터 전략

여러 팩터를 결합하여 종목을 선정하는 전략
- 퀄리티: ROE, GPA, 영업현금흐름율
- 밸류: PER, PBR, PSR, PCR
- 모멘텀: 3개월, 6개월, 12개월 수익률
"""
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .base import BaseStrategy, SelectionResult
from factors.quality import QualityFactor
from factors.value import ValueFactor
from factors.momentum import MomentumFactor
from utils.ranking import RankingCalculator
from config.settings import settings


class MultifactorStrategy(BaseStrategy):
    """
    멀티팩터 전략

    여러 팩터를 Z-Score(Rank) 방식으로 결합:
    최종점수 = Σ Z-Score(Rank(팩터_i)) × 가중치_i

    기본 구성:
    - 퀄리티 (33%): ROE, GPA, CFO Ratio
    - 밸류 (33%): PER, PBR, PSR, PCR
    - 모멘텀 (34%): 3M, 6M, 12M 수익률
    """

    def __init__(self,
                 top_n: int = 30,
                 weights: Dict[str, float] = None,
                 quality_factors: List[str] = None,
                 value_factors: List[str] = None,
                 momentum_periods: List[int] = None,
                 min_market_cap: float = None,
                 exclude_financials: bool = True):
        """
        Args:
            top_n: 선정 종목 수
            weights: 팩터 그룹별 가중치 {'quality': 0.33, 'value': 0.33, 'momentum': 0.34}
            quality_factors: 퀄리티 팩터 목록
            value_factors: 밸류 팩터 목록
            momentum_periods: 모멘텀 기간 목록 (개월)
            min_market_cap: 최소 시가총액
            exclude_financials: 금융주 제외
        """
        super().__init__(top_n, min_market_cap, exclude_financials)

        self.weights = weights or settings.DEFAULT_FACTOR_WEIGHTS
        self.quality_factors = quality_factors or settings.QUALITY_FACTORS
        self.value_factors = value_factors or settings.VALUE_FACTORS
        self.momentum_periods = momentum_periods or settings.MOMENTUM_PERIODS

        self.quality = QualityFactor()
        self.value = ValueFactor()
        self.momentum = MomentumFactor(self.momentum_periods)

    @property
    def name(self) -> str:
        return "멀티팩터 전략"

    @property
    def description(self) -> str:
        return f"퀄리티({self.weights.get('quality', 0.33):.0%}), 밸류({self.weights.get('value', 0.33):.0%}), 모멘텀({self.weights.get('momentum', 0.34):.0%}) 팩터를 결합한 전략"

    def calculate_score(self, data: pd.DataFrame) -> pd.Series:
        """
        멀티팩터 점수 계산

        Args:
            data: 종목 데이터
                퀄리티 팩터: roe, gpa, cfo_ratio
                밸류 팩터: per, pbr, psr, pcr
                모멘텀 팩터: momentum_3m, momentum_6m, momentum_12m

        Returns:
            종목별 점수 Series
        """
        df = data.copy()

        # 1. 각 팩터 그룹별 점수 계산
        quality_score = self._calculate_quality_score(df)
        value_score = self._calculate_value_score(df)
        momentum_score = self._calculate_momentum_score(df)

        # 2. 가중 합산
        final_score = pd.Series(0.0, index=df.index)

        if quality_score is not None:
            final_score += quality_score * self.weights.get('quality', 0.33)

        if value_score is not None:
            final_score += value_score * self.weights.get('value', 0.33)

        if momentum_score is not None:
            final_score += momentum_score * self.weights.get('momentum', 0.34)

        return final_score

    def _calculate_quality_score(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """퀄리티 팩터 점수 계산"""
        available_factors = [f for f in self.quality_factors if f in df.columns]

        if not available_factors:
            return None

        # 퀄리티 팩터는 모두 높을수록 좋음
        ascending_map = {f: False for f in available_factors}

        factor_df = df[available_factors].copy()

        # 윈저라이징
        for col in factor_df.columns:
            factor_df[col] = self.winsorize(factor_df[col])

        return self.ranking_calc.combine_factors(
            factor_df,
            ascending_map=ascending_map
        )

    def _calculate_value_score(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """밸류 팩터 점수 계산"""
        available_factors = [f for f in self.value_factors if f in df.columns]

        if not available_factors:
            return None

        # 밸류 팩터는 모두 낮을수록 좋음 (저평가)
        ascending_map = {f: True for f in available_factors}

        factor_df = df[available_factors].copy()

        # 윈저라이징 및 음수 제거
        for col in factor_df.columns:
            factor_df[col] = self.winsorize(factor_df[col])
            factor_df.loc[factor_df[col] <= 0, col] = np.nan

        return self.ranking_calc.combine_factors(
            factor_df,
            ascending_map=ascending_map
        )

    def _calculate_momentum_score(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """모멘텀 팩터 점수 계산"""
        momentum_cols = [f'momentum_{p}m' for p in self.momentum_periods]
        available_factors = [f for f in momentum_cols if f in df.columns]

        if not available_factors:
            return None

        # 모멘텀 팩터는 모두 높을수록 좋음
        ascending_map = {f: False for f in available_factors}

        factor_df = df[available_factors].copy()

        # 윈저라이징
        for col in factor_df.columns:
            factor_df[col] = self.winsorize(factor_df[col])

        return self.ranking_calc.combine_factors(
            factor_df,
            ascending_map=ascending_map
        )

    def _apply_outlier_handling(self, data: pd.DataFrame) -> pd.DataFrame:
        """이상치 처리"""
        df = data.copy()

        all_factors = (
            self.quality_factors +
            self.value_factors +
            [f'momentum_{p}m' for p in self.momentum_periods]
        )

        existing_cols = [c for c in all_factors if c in df.columns]

        if existing_cols:
            df = self.outlier_handler.process_dataframe(
                df,
                method='winsorize',
                columns=existing_cols
            )

        return df

    def get_factor_correlations(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        팩터 간 상관관계 분석

        멀티팩터 전략의 핵심 장점:
        - 팩터 간 낮은 상관관계 → 분산 효과
        - 한 팩터가 부진해도 다른 팩터가 보완

        Args:
            data: 종목 데이터

        Returns:
            상관관계 매트릭스 DataFrame
        """
        df = data.copy()

        # 각 팩터 그룹별 점수 계산
        scores = pd.DataFrame(index=df.index)

        quality_score = self._calculate_quality_score(df)
        if quality_score is not None:
            scores['quality'] = quality_score

        value_score = self._calculate_value_score(df)
        if value_score is not None:
            scores['value'] = value_score

        momentum_score = self._calculate_momentum_score(df)
        if momentum_score is not None:
            scores['momentum'] = momentum_score

        return scores.corr(method='spearman')

    def get_factor_contributions(self, result: SelectionResult) -> Dict:
        """
        선정 종목의 팩터별 기여도 분석

        Args:
            result: 선정 결과

        Returns:
            팩터별 기여도
        """
        stocks = result.stocks

        contributions = {}

        # 퀄리티 기여도
        quality_cols = [f for f in self.quality_factors if f in stocks.columns]
        if quality_cols:
            contributions['quality'] = {
                'factors': quality_cols,
                'avg_values': {col: stocks[col].mean() for col in quality_cols}
            }

        # 밸류 기여도
        value_cols = [f for f in self.value_factors if f in stocks.columns]
        if value_cols:
            contributions['value'] = {
                'factors': value_cols,
                'avg_values': {col: stocks[col].mean() for col in value_cols}
            }

        # 모멘텀 기여도
        momentum_cols = [f'momentum_{p}m' for p in self.momentum_periods
                         if f'momentum_{p}m' in stocks.columns]
        if momentum_cols:
            contributions['momentum'] = {
                'factors': momentum_cols,
                'avg_values': {col: stocks[col].mean() for col in momentum_cols}
            }

        return contributions

    def set_weights(self, quality: float, value: float, momentum: float):
        """
        팩터 가중치 설정

        Args:
            quality: 퀄리티 가중치
            value: 밸류 가중치
            momentum: 모멘텀 가중치
        """
        total = quality + value + momentum
        self.weights = {
            'quality': quality / total,
            'value': value / total,
            'momentum': momentum / total
        }

    def customize_factors(self,
                          quality: List[str] = None,
                          value: List[str] = None,
                          momentum: List[int] = None):
        """
        팩터 구성 커스터마이징

        Args:
            quality: 퀄리티 팩터 목록
            value: 밸류 팩터 목록
            momentum: 모멘텀 기간 목록
        """
        if quality:
            self.quality_factors = quality
        if value:
            self.value_factors = value
        if momentum:
            self.momentum_periods = momentum
            self.momentum = MomentumFactor(momentum)
