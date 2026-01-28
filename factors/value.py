"""
밸류 팩터 모듈

밸류 팩터는 기업의 내재가치 대비 현재 주가 수준을 측정합니다.
저평가된 기업을 찾아 투자하는 가치투자의 핵심 지표입니다.
"""
from typing import List, Dict
import pandas as pd
import numpy as np

from .base import BaseFactor


class ValueFactor(BaseFactor):
    """
    밸류 팩터

    구성 지표:
    - PER (Price to Earnings Ratio): 주가수익비율
    - PBR (Price to Book Ratio): 주가순자산비율
    - PSR (Price to Sales Ratio): 주가매출비율
    - PCR (Price to Cash flow Ratio): 주가현금흐름비율
    - EY (Earnings Yield): 이익수익률 (마법공식)
    """

    def __init__(self):
        super().__init__(name='value')

    def get_factor_names(self) -> List[str]:
        return ['per', 'pbr', 'psr', 'pcr', 'earnings_yield']

    def get_ascending_map(self) -> Dict[str, bool]:
        """밸류 지표는 대부분 낮을수록 좋음 (저평가)"""
        return {
            'per': True,             # 낮을수록 좋음
            'pbr': True,             # 낮을수록 좋음
            'psr': True,             # 낮을수록 좋음
            'pcr': True,             # 낮을수록 좋음
            'earnings_yield': False  # 높을수록 좋음 (이익수익률)
        }

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        밸류 팩터 계산

        필요한 컬럼:
        - market_cap: 시가총액
        - net_income: 순이익
        - total_equity: 자기자본 (또는 book_value)
        - revenue: 매출액
        - operating_cf: 영업현금흐름
        - ebit: 이자 및 세전이익
        - net_debt: 순차입금

        Args:
            data: 재무/가격 데이터 DataFrame

        Returns:
            밸류 팩터가 추가된 DataFrame
        """
        result = data.copy()

        # PER = 시가총액 / 순이익
        if 'market_cap' in data.columns and 'net_income' in data.columns:
            result['per'] = self._safe_divide(
                data['market_cap'],
                data['net_income']
            )
            # 음수 PER 제거 (적자 기업)
            result.loc[result['per'] < 0, 'per'] = np.nan

        # PBR = 시가총액 / 자기자본
        equity_col = None
        for col in ['book_value', 'total_equity', 'equity']:
            if col in data.columns:
                equity_col = col
                break

        if 'market_cap' in data.columns and equity_col:
            result['pbr'] = self._safe_divide(
                data['market_cap'],
                data[equity_col]
            )
            result.loc[result['pbr'] < 0, 'pbr'] = np.nan

        # PSR = 시가총액 / 매출액
        if 'market_cap' in data.columns and 'revenue' in data.columns:
            result['psr'] = self._safe_divide(
                data['market_cap'],
                data['revenue']
            )

        # PCR = 시가총액 / 영업현금흐름
        if 'market_cap' in data.columns and 'operating_cf' in data.columns:
            result['pcr'] = self._safe_divide(
                data['market_cap'],
                data['operating_cf']
            )
            result.loc[result['pcr'] < 0, 'pcr'] = np.nan

        # EY (이익수익률) = EBIT / (시가총액 + 순차입금)
        if all(col in data.columns for col in ['ebit', 'market_cap', 'net_debt']):
            enterprise_value = data['market_cap'] + data['net_debt']
            result['earnings_yield'] = self._safe_divide(
                data['ebit'],
                enterprise_value
            )

        return result

    def calculate_per(self, market_cap: pd.Series, net_income: pd.Series) -> pd.Series:
        """
        PER (주가수익비율) 계산

        PER = 시가총액 / 순이익
        또는 주가 / EPS

        낮은 PER은 이익 대비 저평가를 의미
        단, 저성장 기업도 PER이 낮을 수 있음

        Args:
            market_cap: 시가총액
            net_income: 순이익

        Returns:
            PER Series
        """
        per = self._safe_divide(market_cap, net_income)
        per[per < 0] = np.nan  # 적자 기업 제외
        return per

    def calculate_pbr(self, market_cap: pd.Series, book_value: pd.Series) -> pd.Series:
        """
        PBR (주가순자산비율) 계산

        PBR = 시가총액 / 순자산
        또는 주가 / BPS

        PBR < 1 은 청산가치보다 저평가됨을 의미
        자산 기반 가치평가

        Args:
            market_cap: 시가총액
            book_value: 순자산 (자기자본)

        Returns:
            PBR Series
        """
        pbr = self._safe_divide(market_cap, book_value)
        pbr[pbr < 0] = np.nan
        return pbr

    def calculate_psr(self, market_cap: pd.Series, revenue: pd.Series) -> pd.Series:
        """
        PSR (주가매출비율) 계산

        PSR = 시가총액 / 매출액

        적자 기업에도 적용 가능
        매출 대비 시장 평가 수준 측정

        Args:
            market_cap: 시가총액
            revenue: 매출액

        Returns:
            PSR Series
        """
        return self._safe_divide(market_cap, revenue)

    def calculate_pcr(self, market_cap: pd.Series, operating_cf: pd.Series) -> pd.Series:
        """
        PCR (주가현금흐름비율) 계산

        PCR = 시가총액 / 영업현금흐름

        현금 창출 능력 대비 주가 수준
        회계 조작에 덜 민감

        Args:
            market_cap: 시가총액
            operating_cf: 영업현금흐름

        Returns:
            PCR Series
        """
        pcr = self._safe_divide(market_cap, operating_cf)
        pcr[pcr < 0] = np.nan
        return pcr

    def calculate_earnings_yield(self,
                                  ebit: pd.Series,
                                  market_cap: pd.Series,
                                  net_debt: pd.Series) -> pd.Series:
        """
        이익수익률 (Earnings Yield) 계산

        EY = EBIT / (시가총액 + 순차입금)
           = EBIT / Enterprise Value

        마법공식에서 사용하는 밸류 지표
        기업가치 대비 영업이익 수준

        높은 EY는 저평가를 의미

        Args:
            ebit: 이자 및 세전이익 (영업이익)
            market_cap: 시가총액
            net_debt: 순차입금 (총차입금 - 현금)

        Returns:
            이익수익률 Series
        """
        enterprise_value = market_cap + net_debt
        return self._safe_divide(ebit, enterprise_value)

    def calculate_ev_ebitda(self,
                            market_cap: pd.Series,
                            net_debt: pd.Series,
                            ebitda: pd.Series) -> pd.Series:
        """
        EV/EBITDA 계산

        EV/EBITDA = (시가총액 + 순차입금) / EBITDA

        기업인수 시 가장 많이 사용되는 밸류에이션 지표
        감가상각 영향 제거

        Args:
            market_cap: 시가총액
            net_debt: 순차입금
            ebitda: 이자, 세금, 감가상각 전 이익

        Returns:
            EV/EBITDA Series
        """
        enterprise_value = market_cap + net_debt
        ev_ebitda = self._safe_divide(enterprise_value, ebitda)
        ev_ebitda[ev_ebitda < 0] = np.nan
        return ev_ebitda

    def _safe_divide(self, numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        """안전한 나눗셈"""
        with np.errstate(divide='ignore', invalid='ignore'):
            result = numerator / denominator
            result = result.replace([np.inf, -np.inf], np.nan)
        return result
