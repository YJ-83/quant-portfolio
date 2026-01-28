"""
섹터 중립 전략

특정 섹터에 편중되지 않도록 섹터 내에서 상대적 강도를 비교하는 전략
특히 모멘텀 전략에서 섹터 편중 현상을 방지하기 위해 사용됩니다.
"""
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .base import BaseStrategy, SelectionResult
from utils.ranking import RankingCalculator
from config.settings import settings


class SectorNeutralStrategy(BaseStrategy):
    """
    섹터 중립 전략

    문제점:
    - 특정 팩터 전략(특히 모멘텀)은 특정 섹터에 편중되는 현상 발생
    - 예: 상승장에서 성장주 섹터에 집중, 하락장에서 방어주 섹터에 집중

    해결방법:
    - 섹터별로 별도의 Z-score 계산
    - 전체 수익률 비교 대신 섹터 내 상대적 강도 비교
    - 각 섹터에서 균등하게 또는 비율에 따라 종목 선정

    효과:
    - 여러 섹터에 분산된 포트폴리오 구성
    - 섹터 로테이션 리스크 감소
    """

    def __init__(self,
                 top_n: int = 30,
                 factor_name: str = 'momentum_12m',
                 ascending: bool = False,
                 stocks_per_sector: int = None,
                 min_market_cap: float = None,
                 exclude_financials: bool = True):
        """
        Args:
            top_n: 선정 종목 수
            factor_name: 사용할 팩터명
            ascending: 팩터 방향 (True: 낮을수록 좋음)
            stocks_per_sector: 섹터당 선정 종목 수 (None이면 비례 배분)
            min_market_cap: 최소 시가총액
            exclude_financials: 금융주 제외
        """
        super().__init__(top_n, min_market_cap, exclude_financials)
        self.factor_name = factor_name
        self.ascending = ascending
        self.stocks_per_sector = stocks_per_sector

    @property
    def name(self) -> str:
        return "섹터 중립 전략"

    @property
    def description(self) -> str:
        return f"섹터 내 {self.factor_name} 기준 상대 강도로 종목을 선정하여 섹터 편중을 방지하는 전략"

    def calculate_score(self, data: pd.DataFrame) -> pd.Series:
        """
        섹터 중립 점수 계산

        각 섹터 내에서 별도로 Z-score 계산

        Args:
            data: 종목 데이터
                필수 컬럼: sector, {factor_name}

        Returns:
            섹터 중립 점수 Series
        """
        if 'sector' not in data.columns:
            raise ValueError("섹터 중립 전략에는 'sector' 컬럼이 필요합니다.")

        if self.factor_name not in data.columns:
            raise ValueError(f"팩터 '{self.factor_name}' 컬럼이 필요합니다.")

        df = data.copy()

        # 섹터별 Z-score 계산
        sector_neutral_score = self.ranking_calc.sector_neutral_zscore(
            df[self.factor_name],
            df['sector'],
            ascending=self.ascending
        )

        return sector_neutral_score

    def select_stocks(self, data: pd.DataFrame) -> SelectionResult:
        """
        섹터 중립 종목 선정

        두 가지 방식 지원:
        1. 섹터당 고정 종목 수 (stocks_per_sector)
        2. 섹터 비중에 따른 비례 배분

        Args:
            data: 종목 데이터

        Returns:
            SelectionResult 객체
        """
        df = data.copy()

        # 기본 필터링
        df = self._apply_filters(df)

        # 팩터 값 확인
        if self.factor_name not in df.columns:
            raise ValueError(f"팩터 '{self.factor_name}' 컬럼이 필요합니다.")

        # 이상치 처리
        df[self.factor_name] = self.winsorize(df[self.factor_name])

        # 섹터별 선정
        if self.stocks_per_sector:
            selected = self._select_fixed_per_sector(df)
        else:
            selected = self._select_proportional(df)

        # 최종 점수 및 랭킹
        selected['score'] = self.calculate_score(selected)
        selected['rank'] = selected['score'].rank(ascending=False)
        selected = selected.sort_values('rank')

        return SelectionResult(
            strategy_name=self.name,
            selected_date=pd.Timestamp.now().strftime('%Y-%m-%d'),
            stocks=selected,
            total_candidates=len(data),
            selected_count=len(selected),
            metadata={
                'factor_name': self.factor_name,
                'stocks_per_sector': self.stocks_per_sector,
                'sector_distribution': selected['sector'].value_counts().to_dict()
            }
        )

    def _select_fixed_per_sector(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        섹터당 고정 종목 수 선정

        Args:
            df: 필터링된 데이터

        Returns:
            선정된 종목 DataFrame
        """
        selected_list = []

        for sector in df['sector'].unique():
            sector_df = df[df['sector'] == sector].copy()

            if len(sector_df) == 0:
                continue

            # 섹터 내 랭킹
            sector_df['sector_rank'] = sector_df[self.factor_name].rank(
                ascending=self.ascending
            )

            # 상위 N개 선정
            top_n = min(self.stocks_per_sector, len(sector_df))
            sector_selected = sector_df.nsmallest(top_n, 'sector_rank')

            selected_list.append(sector_selected)

        if not selected_list:
            return pd.DataFrame()

        return pd.concat(selected_list, ignore_index=True)

    def _select_proportional(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        섹터 비중에 따른 비례 배분

        Args:
            df: 필터링된 데이터

        Returns:
            선정된 종목 DataFrame
        """
        # 섹터별 종목 수 비중
        sector_counts = df['sector'].value_counts()
        sector_ratios = sector_counts / sector_counts.sum()

        # 섹터별 할당 종목 수
        sector_allocations = (sector_ratios * self.top_n).round().astype(int)

        # 총합이 top_n이 되도록 조정
        diff = self.top_n - sector_allocations.sum()
        if diff != 0:
            # 가장 큰 섹터에서 조정
            sector_allocations.iloc[0] += diff

        selected_list = []

        for sector, allocation in sector_allocations.items():
            if allocation <= 0:
                continue

            sector_df = df[df['sector'] == sector].copy()

            if len(sector_df) == 0:
                continue

            # 섹터 내 Z-score
            sector_df['sector_zscore'] = self.ranking_calc.zscore_rank(
                sector_df[self.factor_name],
                ascending=self.ascending
            )

            # 상위 N개 선정
            top_n = min(allocation, len(sector_df))
            sector_selected = sector_df.nlargest(top_n, 'sector_zscore')

            selected_list.append(sector_selected)

        if not selected_list:
            return pd.DataFrame()

        return pd.concat(selected_list, ignore_index=True)

    def get_sector_distribution(self, result: SelectionResult) -> pd.DataFrame:
        """
        선정 결과의 섹터 분포

        Args:
            result: 선정 결과

        Returns:
            섹터 분포 DataFrame
        """
        stocks = result.stocks

        distribution = stocks.groupby('sector').agg({
            'code': 'count',
            'score': 'mean'
        }).rename(columns={
            'code': 'count',
            'score': 'avg_score'
        })

        distribution['weight'] = distribution['count'] / distribution['count'].sum()

        return distribution.sort_values('count', ascending=False)

    def compare_with_raw(self, data: pd.DataFrame) -> Dict:
        """
        섹터 중립 vs 원본 전략 비교

        Args:
            data: 종목 데이터

        Returns:
            비교 결과
        """
        df = data.copy()
        df = self._apply_filters(df)

        # 원본 (섹터 중립 없이)
        raw_ranks = df[self.factor_name].rank(ascending=self.ascending)
        raw_top = df.nsmallest(self.top_n, raw_ranks.name) if self.ascending else df.nlargest(self.top_n, self.factor_name)
        raw_distribution = raw_top['sector'].value_counts()

        # 섹터 중립
        neutral_result = self.select_stocks(data)
        neutral_distribution = neutral_result.stocks['sector'].value_counts()

        return {
            'raw_strategy': {
                'sector_distribution': raw_distribution.to_dict(),
                'max_sector_weight': raw_distribution.max() / self.top_n,
                'num_sectors': len(raw_distribution)
            },
            'sector_neutral': {
                'sector_distribution': neutral_distribution.to_dict(),
                'max_sector_weight': neutral_distribution.max() / self.top_n,
                'num_sectors': len(neutral_distribution)
            }
        }


class SectorNeutralMultifactor(SectorNeutralStrategy):
    """
    섹터 중립 멀티팩터 전략

    여러 팩터를 섹터 중립 방식으로 결합
    """

    def __init__(self,
                 top_n: int = 30,
                 factors: List[str] = None,
                 ascending_map: Dict[str, bool] = None,
                 weights: Dict[str, float] = None,
                 min_market_cap: float = None):
        """
        Args:
            top_n: 선정 종목 수
            factors: 사용할 팩터 목록
            ascending_map: 팩터별 정렬 방향
            weights: 팩터별 가중치
            min_market_cap: 최소 시가총액
        """
        super().__init__(top_n, min_market_cap=min_market_cap)

        self.factors = factors or ['roe', 'per', 'momentum_12m']
        self.ascending_map = ascending_map or {
            'roe': False,        # 높을수록 좋음
            'per': True,         # 낮을수록 좋음
            'momentum_12m': False  # 높을수록 좋음
        }
        self.factor_weights = weights

    @property
    def name(self) -> str:
        return "섹터 중립 멀티팩터"

    def calculate_score(self, data: pd.DataFrame) -> pd.Series:
        """
        섹터 중립 멀티팩터 점수 계산
        """
        if 'sector' not in data.columns:
            raise ValueError("섹터 정보가 필요합니다.")

        df = data.copy()
        available_factors = [f for f in self.factors if f in df.columns]

        if not available_factors:
            raise ValueError("사용 가능한 팩터가 없습니다.")

        # 각 팩터별 섹터 중립 Z-score 계산
        factor_scores = pd.DataFrame(index=df.index)

        for factor in available_factors:
            ascending = self.ascending_map.get(factor, True)
            factor_scores[factor] = self.ranking_calc.sector_neutral_zscore(
                df[factor],
                df['sector'],
                ascending=ascending
            )

        # 가중 합산
        if self.factor_weights:
            weights = {f: self.factor_weights.get(f, 1/len(available_factors))
                      for f in available_factors}
        else:
            weights = {f: 1/len(available_factors) for f in available_factors}

        final_score = pd.Series(0.0, index=df.index)
        for factor, weight in weights.items():
            if factor in factor_scores.columns:
                final_score += factor_scores[factor] * weight

        return final_score
