"""
전략 베이스 클래스
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

from utils.ranking import RankingCalculator
from utils.outlier import OutlierHandler
from config.settings import settings


@dataclass
class SelectionResult:
    """종목 선정 결과"""
    strategy_name: str
    selected_date: str
    stocks: pd.DataFrame  # code, name, score, rank 등
    total_candidates: int
    selected_count: int
    metadata: Dict = None


class BaseStrategy(ABC):
    """전략 베이스 클래스"""

    def __init__(self,
                 top_n: int = None,
                 min_market_cap: float = None,
                 exclude_financials: bool = True):
        """
        Args:
            top_n: 선정 종목 수
            min_market_cap: 최소 시가총액 필터 (원)
            exclude_financials: 금융주 제외 여부
        """
        self.top_n = top_n or settings.DEFAULT_TOP_N
        self.min_market_cap = min_market_cap
        self.exclude_financials = exclude_financials
        self.ranking_calc = RankingCalculator()
        self.outlier_handler = OutlierHandler()

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """전략 설명"""
        pass

    @abstractmethod
    def calculate_score(self, data: pd.DataFrame) -> pd.Series:
        """
        종목별 점수 계산

        Args:
            data: 종목 데이터 DataFrame

        Returns:
            종목별 점수 Series
        """
        pass

    def select_stocks(self, data: pd.DataFrame) -> SelectionResult:
        """
        종목 선정

        Args:
            data: 종목 데이터 DataFrame
                  필수 컬럼: code, name

        Returns:
            SelectionResult 객체
        """
        # 데이터 복사
        df = data.copy()

        # 1. 기본 필터링
        df = self._apply_filters(df)

        # 2. 이상치 처리
        df = self._apply_outlier_handling(df)

        # 3. 점수 계산
        df['score'] = self.calculate_score(df)

        # 4. 결측치 제거
        df = df.dropna(subset=['score'])

        # 5. 랭킹 및 정렬
        df['rank'] = df['score'].rank(ascending=False)
        df = df.sort_values('rank')

        # 6. 상위 N개 선정
        selected = df.head(self.top_n).copy()

        # 결과 반환
        return SelectionResult(
            strategy_name=self.name,
            selected_date=pd.Timestamp.now().strftime('%Y-%m-%d'),
            stocks=selected,
            total_candidates=len(data),
            selected_count=len(selected),
            metadata={
                'top_n': self.top_n,
                'min_market_cap': self.min_market_cap,
                'exclude_financials': self.exclude_financials
            }
        )

    def _apply_filters(self, data: pd.DataFrame) -> pd.DataFrame:
        """기본 필터 적용"""
        df = data.copy()

        # 시가총액 필터
        if self.min_market_cap and 'market_cap' in df.columns:
            df = df[df['market_cap'] >= self.min_market_cap]

        # 금융주 제외
        if self.exclude_financials and 'sector' in df.columns:
            df = df[~df['sector'].str.contains('금융|보험|증권|은행', na=False)]

        # 관리종목/거래정지 제외 (있는 경우)
        if 'status' in df.columns:
            df = df[df['status'] == 'normal']

        return df

    def _apply_outlier_handling(self, data: pd.DataFrame) -> pd.DataFrame:
        """이상치 처리 적용"""
        # 서브클래스에서 재정의 가능
        return data

    def winsorize(self,
                  values: pd.Series,
                  lower: float = None,
                  upper: float = None) -> pd.Series:
        """윈저라이징 적용"""
        lower = lower or settings.WINSORIZE_LOWER
        upper = upper or settings.WINSORIZE_UPPER
        return self.outlier_handler.winsorize(values, lower, upper)

    def get_factor_summary(self, result: SelectionResult) -> pd.DataFrame:
        """
        선정 종목의 팩터 요약 통계

        Args:
            result: 선정 결과

        Returns:
            요약 통계 DataFrame
        """
        stocks = result.stocks

        # 숫자형 컬럼만 선택
        numeric_cols = stocks.select_dtypes(include=[np.number]).columns
        exclude_cols = ['rank', 'score']
        factor_cols = [c for c in numeric_cols if c not in exclude_cols]

        summary = stocks[factor_cols].describe()
        return summary

    def explain_selection(self, result: SelectionResult) -> str:
        """
        선정 결과 설명 생성

        Args:
            result: 선정 결과

        Returns:
            설명 문자열
        """
        lines = [
            f"전략: {self.name}",
            f"설명: {self.description}",
            f"선정일: {result.selected_date}",
            f"",
            f"후보 종목 수: {result.total_candidates:,}개",
            f"선정 종목 수: {result.selected_count:,}개",
            f"",
            f"상위 5개 종목:",
        ]

        top5 = result.stocks.head(5)
        for _, row in top5.iterrows():
            lines.append(f"  - {row.get('name', row.get('code'))}: 점수 {row['score']:.4f}")

        return "\n".join(lines)
