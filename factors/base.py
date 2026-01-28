"""
팩터 베이스 클래스
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from utils.ranking import RankingCalculator
from utils.outlier import OutlierHandler


class BaseFactor(ABC):
    """팩터 베이스 클래스"""

    def __init__(self, name: str):
        self.name = name
        self.ranking_calc = RankingCalculator()
        self.outlier_handler = OutlierHandler()

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        팩터 값 계산

        Args:
            data: 입력 데이터 DataFrame

        Returns:
            팩터 값이 포함된 DataFrame
        """
        pass

    @abstractmethod
    def get_factor_names(self) -> List[str]:
        """
        팩터 이름 목록 반환

        Returns:
            팩터 이름 리스트
        """
        pass

    @abstractmethod
    def get_ascending_map(self) -> Dict[str, bool]:
        """
        팩터별 정렬 방향 반환

        True: 낮을수록 좋음 (예: PER, PBR)
        False: 높을수록 좋음 (예: ROE, 모멘텀)

        Returns:
            팩터별 정렬 방향 딕셔너리
        """
        pass

    def preprocess(self,
                   data: pd.DataFrame,
                   method: str = 'winsorize') -> pd.DataFrame:
        """
        데이터 전처리 (이상치 처리)

        Args:
            data: 입력 데이터
            method: 이상치 처리 방법

        Returns:
            전처리된 DataFrame
        """
        factor_names = self.get_factor_names()
        existing_cols = [col for col in factor_names if col in data.columns]

        if not existing_cols:
            return data

        return self.outlier_handler.process_dataframe(
            data,
            method=method,
            columns=existing_cols
        )

    def rank_factors(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        팩터 값에 대한 랭킹 계산

        Args:
            data: 팩터 값 DataFrame

        Returns:
            랭킹이 추가된 DataFrame
        """
        ascending_map = self.get_ascending_map()
        result = data.copy()

        for factor_name in self.get_factor_names():
            if factor_name not in data.columns:
                continue

            ascending = ascending_map.get(factor_name, True)
            result[f'{factor_name}_rank'] = self.ranking_calc.rank(
                data[factor_name],
                ascending=ascending
            )

        return result

    def zscore_factors(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        팩터 값에 대한 Z-score 계산

        Args:
            data: 팩터 값 DataFrame

        Returns:
            Z-score가 추가된 DataFrame
        """
        ascending_map = self.get_ascending_map()
        result = data.copy()

        for factor_name in self.get_factor_names():
            if factor_name not in data.columns:
                continue

            ascending = ascending_map.get(factor_name, True)
            result[f'{factor_name}_zscore'] = self.ranking_calc.zscore_rank(
                data[factor_name],
                ascending=ascending
            )

        return result

    def get_combined_score(self,
                           data: pd.DataFrame,
                           weights: Optional[Dict[str, float]] = None) -> pd.Series:
        """
        팩터들을 결합한 최종 점수 계산

        Args:
            data: 팩터 값 DataFrame
            weights: 팩터별 가중치 (None이면 동일 가중치)

        Returns:
            최종 점수 Series
        """
        factor_names = self.get_factor_names()
        existing_factors = [f for f in factor_names if f in data.columns]

        if not existing_factors:
            return pd.Series(dtype=float)

        factor_df = data[existing_factors]

        if weights is None:
            weights = {f: 1/len(existing_factors) for f in existing_factors}

        ascending_map = self.get_ascending_map()

        return self.ranking_calc.combine_factors(
            factor_df,
            weights=weights,
            ascending_map=ascending_map
        )
