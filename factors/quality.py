"""
퀄리티 팩터 모듈

퀄리티 팩터는 기업의 수익성과 재무 건전성을 측정합니다.
높은 퀄리티 기업은 지속적인 수익 창출 능력이 있습니다.
"""
from typing import List, Dict
import pandas as pd
import numpy as np

from .base import BaseFactor


class QualityFactor(BaseFactor):
    """
    퀄리티 팩터

    구성 지표:
    - ROE (Return on Equity): 자기자본이익률
    - GPA (Gross Profit to Assets): 매출총이익율
    - CFO (Cash Flow from Operations) Ratio: 영업현금흐름율
    """

    def __init__(self):
        super().__init__(name='quality')

    def get_factor_names(self) -> List[str]:
        return ['roe', 'gpa', 'cfo_ratio']

    def get_ascending_map(self) -> Dict[str, bool]:
        """퀄리티 지표는 모두 높을수록 좋음"""
        return {
            'roe': False,       # 높을수록 좋음
            'gpa': False,       # 높을수록 좋음
            'cfo_ratio': False  # 높을수록 좋음
        }

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        퀄리티 팩터 계산

        필요한 컬럼:
        - net_income: 순이익
        - equity (또는 total_equity): 자기자본
        - gross_profit: 매출총이익
        - total_assets: 총자산
        - operating_cf: 영업현금흐름

        Args:
            data: 재무 데이터 DataFrame

        Returns:
            퀄리티 팩터가 추가된 DataFrame
        """
        result = data.copy()

        # ROE = 순이익 / 자기자본
        if 'net_income' in data.columns:
            equity_col = 'equity' if 'equity' in data.columns else 'total_equity'
            if equity_col in data.columns:
                result['roe'] = self._safe_divide(
                    data['net_income'],
                    data[equity_col]
                )

        # GPA = 매출총이익 / 총자산
        if 'gross_profit' in data.columns and 'total_assets' in data.columns:
            result['gpa'] = self._safe_divide(
                data['gross_profit'],
                data['total_assets']
            )

        # CFO Ratio = 영업현금흐름 / 총자산
        if 'operating_cf' in data.columns and 'total_assets' in data.columns:
            result['cfo_ratio'] = self._safe_divide(
                data['operating_cf'],
                data['total_assets']
            )

        return result

    def calculate_roe(self, net_income: pd.Series, equity: pd.Series) -> pd.Series:
        """
        ROE (자기자본이익률) 계산

        ROE = 순이익 / 자기자본

        높은 ROE는 주주 자본을 효율적으로 활용하고 있음을 의미

        Args:
            net_income: 순이익
            equity: 자기자본

        Returns:
            ROE Series
        """
        return self._safe_divide(net_income, equity)

    def calculate_gpa(self, gross_profit: pd.Series, total_assets: pd.Series) -> pd.Series:
        """
        GPA (매출총이익률) 계산

        GPA = 매출총이익 / 총자산

        Robert Novy-Marx의 연구에서 GPA가 강력한 수익 예측 지표임을 발견
        "The other side of value: The gross profitability premium" (2013)

        Args:
            gross_profit: 매출총이익
            total_assets: 총자산

        Returns:
            GPA Series
        """
        return self._safe_divide(gross_profit, total_assets)

    def calculate_cfo_ratio(self, operating_cf: pd.Series, total_assets: pd.Series) -> pd.Series:
        """
        영업현금흐름율 계산

        CFO Ratio = 영업현금흐름 / 총자산

        실제 현금 창출 능력을 측정
        회계적 이익 조작에 덜 취약

        Args:
            operating_cf: 영업현금흐름
            total_assets: 총자산

        Returns:
            CFO Ratio Series
        """
        return self._safe_divide(operating_cf, total_assets)

    def calculate_roc(self, ebit: pd.Series, invested_capital: pd.Series) -> pd.Series:
        """
        ROC (투하자본수익률) 계산

        ROC = EBIT / 투하자본

        마법공식에서 사용하는 퀄리티 지표
        투하자본 = 순운전자본 + 순고정자산

        Args:
            ebit: 이자 및 세전이익
            invested_capital: 투하자본

        Returns:
            ROC Series
        """
        return self._safe_divide(ebit, invested_capital)

    def _safe_divide(self, numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        """
        안전한 나눗셈 (0으로 나누기 방지)

        Args:
            numerator: 분자
            denominator: 분모

        Returns:
            나눗셈 결과 (분모가 0이면 NaN)
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            result = numerator / denominator
            result = result.replace([np.inf, -np.inf], np.nan)
        return result
