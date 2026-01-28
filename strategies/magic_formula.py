"""
마법공식 전략 (Magic Formula)

조엘 그린블라트(Joel Greenblatt)의 "주식시장을 이기는 작은 책"에서 소개된 전략

핵심 원칙: "좋은 기업을 싸게 사라"
- 퀄리티: 투하자본수익률 (ROC) - 높을수록 좋음
- 밸류: 이익수익률 (EY) - 높을수록 좋음
"""
from typing import Optional, Dict
import pandas as pd
import numpy as np

from .base import BaseStrategy, SelectionResult
from factors.quality import QualityFactor
from factors.value import ValueFactor
from utils.ranking import RankingCalculator


class MagicFormulaStrategy(BaseStrategy):
    """
    마법공식 전략

    Joel Greenblatt의 마법공식:
    1. 이익수익률(Earnings Yield) 랭킹 계산
    2. 투하자본수익률(ROC) 랭킹 계산
    3. 두 랭킹의 합이 낮은 순으로 종목 선정

    참고:
    - "The Little Book That Beats the Market" (2005)
    - 원래 공식은 미국 대형주 기준이나 한국 시장에도 적용 가능
    """

    def __init__(self,
                 top_n: int = 30,
                 min_market_cap: float = None,
                 exclude_financials: bool = True,
                 use_simplified: bool = False):
        """
        Args:
            top_n: 선정 종목 수
            min_market_cap: 최소 시가총액
            exclude_financials: 금융주 제외
            use_simplified: 간소화된 버전 사용 (ROE, PER 기반)
        """
        super().__init__(top_n, min_market_cap, exclude_financials)
        self.use_simplified = use_simplified
        self.quality_factor = QualityFactor()
        self.value_factor = ValueFactor()

    @property
    def name(self) -> str:
        return "마법공식 (Magic Formula)"

    @property
    def description(self) -> str:
        return "이익수익률(EY)과 투하자본수익률(ROC)을 결합하여 저평가된 우량주를 선정하는 전략"

    def calculate_score(self, data: pd.DataFrame) -> pd.Series:
        """
        마법공식 점수 계산

        점수 = Z-Score(EY Rank) + Z-Score(ROC Rank)

        Args:
            data: 종목 데이터
                필수 컬럼 (원본):
                - ebit: 영업이익
                - market_cap: 시가총액
                - net_debt: 순차입금
                - invested_capital: 투하자본

                또는 (간소화):
                - per: PER
                - roe: ROE

        Returns:
            종목별 점수 Series
        """
        df = data.copy()

        if self.use_simplified:
            return self._calculate_simplified_score(df)

        return self._calculate_original_score(df)

    def _calculate_original_score(self, df: pd.DataFrame) -> pd.Series:
        """
        원본 마법공식 점수 계산

        EY = EBIT / (시가총액 + 순차입금)
        ROC = EBIT / 투하자본
        """
        # 이익수익률 계산
        if all(col in df.columns for col in ['ebit', 'market_cap', 'net_debt']):
            enterprise_value = df['market_cap'] + df['net_debt']
            df['earnings_yield'] = df['ebit'] / enterprise_value
        elif 'earnings_yield' not in df.columns:
            # 대안: EPS/주가 사용
            if 'eps' in df.columns and 'price' in df.columns:
                df['earnings_yield'] = df['eps'] / df['price']
            else:
                raise ValueError("이익수익률 계산에 필요한 데이터가 없습니다.")

        # 투하자본수익률 계산
        if 'ebit' in df.columns and 'invested_capital' in df.columns:
            df['roc'] = df['ebit'] / df['invested_capital']
        elif 'roc' not in df.columns:
            # 대안: ROE 사용
            if 'roe' in df.columns:
                df['roc'] = df['roe']
            else:
                raise ValueError("투하자본수익률 계산에 필요한 데이터가 없습니다.")

        # 윈저라이징 적용
        df['earnings_yield'] = self.winsorize(df['earnings_yield'])
        df['roc'] = self.winsorize(df['roc'])

        # 음수 값 제외
        df.loc[df['earnings_yield'] < 0, 'earnings_yield'] = np.nan
        df.loc[df['roc'] < 0, 'roc'] = np.nan

        # 랭킹 계산 (높을수록 좋음 -> ascending=False)
        ey_rank = df['earnings_yield'].rank(ascending=False, na_option='keep')
        roc_rank = df['roc'].rank(ascending=False, na_option='keep')

        # Z-score 정규화
        ey_zscore = self.ranking_calc.zscore(ey_rank)
        roc_zscore = self.ranking_calc.zscore(roc_rank)

        # 최종 점수 (두 Z-score의 합)
        final_score = ey_zscore + roc_zscore

        return final_score

    def _calculate_simplified_score(self, df: pd.DataFrame) -> pd.Series:
        """
        간소화된 마법공식 점수 계산

        PER (낮을수록) + ROE (높을수록)
        """
        if 'per' not in df.columns or 'roe' not in df.columns:
            raise ValueError("간소화된 마법공식에는 PER, ROE 데이터가 필요합니다.")

        # 윈저라이징 적용
        df['per'] = self.winsorize(df['per'])
        df['roe'] = self.winsorize(df['roe'])

        # 음수/0 제외
        df.loc[df['per'] <= 0, 'per'] = np.nan
        df.loc[df['roe'] <= 0, 'roe'] = np.nan

        # 랭킹 계산
        # PER: 낮을수록 좋음 (ascending=True)
        # ROE: 높을수록 좋음 (ascending=False)
        per_rank = df['per'].rank(ascending=True, na_option='keep')
        roe_rank = df['roe'].rank(ascending=False, na_option='keep')

        # Z-score 정규화
        per_zscore = self.ranking_calc.zscore(per_rank)
        roe_zscore = self.ranking_calc.zscore(roe_rank)

        # 최종 점수
        final_score = per_zscore + roe_zscore

        return final_score

    def _apply_outlier_handling(self, data: pd.DataFrame) -> pd.DataFrame:
        """이상치 처리"""
        df = data.copy()
        numeric_cols = ['ebit', 'market_cap', 'net_debt', 'invested_capital',
                        'earnings_yield', 'roc', 'per', 'roe']
        existing_cols = [c for c in numeric_cols if c in df.columns]

        if existing_cols:
            df = self.outlier_handler.process_dataframe(
                df,
                method='winsorize',
                columns=existing_cols
            )

        return df

    def analyze_correlation(self, data: pd.DataFrame) -> float:
        """
        EY와 ROC의 상관관계 분석

        마법공식의 핵심 통찰:
        - 퀄리티(ROC)와 밸류(EY)는 음의 상관관계
        - 좋은 기업은 비싸고, 싼 기업은 퀄리티가 낮음
        - 마법공식은 이 음의 상관관계를 극복하여
          "좋으면서도 싼" 기업을 찾음

        Args:
            data: 종목 데이터

        Returns:
            스피어만 상관계수
        """
        df = data.copy()

        # 팩터 계산
        if 'earnings_yield' not in df.columns:
            if all(col in df.columns for col in ['ebit', 'market_cap', 'net_debt']):
                ev = df['market_cap'] + df['net_debt']
                df['earnings_yield'] = df['ebit'] / ev

        if 'roc' not in df.columns:
            if all(col in df.columns for col in ['ebit', 'invested_capital']):
                df['roc'] = df['ebit'] / df['invested_capital']

        # 상관관계 계산
        if 'earnings_yield' in df.columns and 'roc' in df.columns:
            correlation = df['earnings_yield'].corr(df['roc'], method='spearman')
            return correlation

        return np.nan

    def get_factor_distribution(self, result: SelectionResult) -> Dict:
        """
        선정 종목의 팩터 분포 분석

        Args:
            result: 선정 결과

        Returns:
            팩터 분포 통계
        """
        stocks = result.stocks
        stats = {}

        if 'earnings_yield' in stocks.columns:
            stats['earnings_yield'] = {
                'mean': stocks['earnings_yield'].mean(),
                'median': stocks['earnings_yield'].median(),
                'std': stocks['earnings_yield'].std(),
                'min': stocks['earnings_yield'].min(),
                'max': stocks['earnings_yield'].max()
            }

        if 'roc' in stocks.columns:
            stats['roc'] = {
                'mean': stocks['roc'].mean(),
                'median': stocks['roc'].median(),
                'std': stocks['roc'].std(),
                'min': stocks['roc'].min(),
                'max': stocks['roc'].max()
            }

        return stats
