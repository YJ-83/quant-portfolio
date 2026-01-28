"""
랭킹 및 정규화 유틸리티
"""
from typing import Optional
import pandas as pd
import numpy as np


class RankingCalculator:
    """랭킹 및 Z-score 계산"""

    @staticmethod
    def rank(values: pd.Series,
             ascending: bool = True,
             method: str = 'min') -> pd.Series:
        """
        랭킹 계산

        Args:
            values: 팩터 값 Series
            ascending: True면 작은 값이 높은 랭킹
            method: 동점 처리 방법 ('min', 'max', 'average', 'first', 'dense')

        Returns:
            랭킹 Series
        """
        return values.rank(ascending=ascending, method=method, na_option='keep')

    @staticmethod
    def percentile_rank(values: pd.Series, ascending: bool = True) -> pd.Series:
        """
        백분위 랭킹 계산 (0~1)

        Args:
            values: 팩터 값 Series
            ascending: True면 작은 값이 높은 백분위

        Returns:
            백분위 랭킹 Series (0~1)
        """
        ranks = RankingCalculator.rank(values, ascending=ascending)
        return (ranks - 1) / (len(values.dropna()) - 1)

    @staticmethod
    def zscore(values: pd.Series) -> pd.Series:
        """
        Z-score 정규화

        공식: (x - mean) / std

        Args:
            values: 팩터 값 Series

        Returns:
            Z-score Series
        """
        mean = values.mean()
        std = values.std()

        if std == 0 or pd.isna(std):
            return pd.Series(0, index=values.index)

        return (values - mean) / std

    @staticmethod
    def zscore_rank(values: pd.Series, ascending: bool = True) -> pd.Series:
        """
        랭킹의 Z-score 계산

        멀티팩터 전략에서 사용하는 표준 방법:
        Z-Score(Rank(팩터))

        Args:
            values: 팩터 값 Series
            ascending: 팩터 방향 (True: 낮을수록 좋음, False: 높을수록 좋음)

        Returns:
            Z-score 정규화된 랭킹 Series
        """
        ranks = RankingCalculator.rank(values, ascending=ascending)
        return RankingCalculator.zscore(ranks)

    @staticmethod
    def sector_neutral_zscore(values: pd.Series,
                               sectors: pd.Series,
                               ascending: bool = True) -> pd.Series:
        """
        섹터 중립 Z-score 계산

        각 섹터 내에서 별도로 Z-score 계산하여
        특정 섹터에 편중되지 않도록 함

        Args:
            values: 팩터 값 Series
            sectors: 섹터 정보 Series (같은 인덱스)
            ascending: 팩터 방향

        Returns:
            섹터 중립 Z-score Series
        """
        df = pd.DataFrame({
            'value': values,
            'sector': sectors
        })

        def sector_zscore(group):
            ranks = RankingCalculator.rank(group, ascending=ascending)
            return RankingCalculator.zscore(ranks)

        result = df.groupby('sector')['value'].transform(sector_zscore)
        return result

    @staticmethod
    def combine_factors(factor_df: pd.DataFrame,
                        weights: Optional[dict] = None,
                        ascending_map: Optional[dict] = None) -> pd.Series:
        """
        여러 팩터를 결합하여 최종 점수 계산

        공식: Σ Z-Score(Rank(팩터_i)) × 가중치_i

        Args:
            factor_df: 팩터 값 DataFrame (컬럼이 각 팩터)
            weights: 팩터별 가중치 딕셔너리
            ascending_map: 팩터별 정렬 방향 딕셔너리
                          (True: 낮을수록 좋음, False: 높을수록 좋음)

        Returns:
            최종 점수 Series
        """
        if weights is None:
            weights = {col: 1/len(factor_df.columns) for col in factor_df.columns}

        if ascending_map is None:
            ascending_map = {col: True for col in factor_df.columns}

        # 각 팩터별 Z-score(Rank) 계산
        zscore_df = pd.DataFrame(index=factor_df.index)

        for col in factor_df.columns:
            ascending = ascending_map.get(col, True)
            zscore_df[col] = RankingCalculator.zscore_rank(
                factor_df[col],
                ascending=ascending
            )

        # 가중 합산
        final_score = pd.Series(0, index=factor_df.index)

        for col in factor_df.columns:
            weight = weights.get(col, 1/len(factor_df.columns))
            final_score += zscore_df[col] * weight

        return final_score

    @staticmethod
    def select_top_n(scores: pd.Series, n: int = 30) -> pd.Index:
        """
        상위 N개 종목 선정

        Args:
            scores: 최종 점수 Series
            n: 선정 종목 수

        Returns:
            선정된 종목 인덱스
        """
        # 높은 점수가 좋음
        return scores.nlargest(n).index
