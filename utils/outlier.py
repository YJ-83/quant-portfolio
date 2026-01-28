"""
이상치 처리 유틸리티
"""
from typing import Tuple
import pandas as pd
import numpy as np
from scipy import stats

from config.settings import settings


class OutlierHandler:
    """이상치 처리 클래스"""

    @staticmethod
    def trim(values: pd.Series,
             lower_percentile: float = 0.01,
             upper_percentile: float = 0.99) -> pd.Series:
        """
        트림(Trim) 처리

        상하위 지정 백분위수 밖의 데이터를 NA로 변경

        장점: 극단치 제거
        단점: 데이터 손실, 우수 종목 제외 가능

        Args:
            values: 원본 데이터 Series
            lower_percentile: 하위 백분위수 (기본 1%)
            upper_percentile: 상위 백분위수 (기본 99%)

        Returns:
            트림 처리된 Series
        """
        lower_bound = values.quantile(lower_percentile)
        upper_bound = values.quantile(upper_percentile)

        result = values.copy()
        result[(result < lower_bound) | (result > upper_bound)] = np.nan

        return result

    @staticmethod
    def winsorize(values: pd.Series,
                  lower_percentile: float = None,
                  upper_percentile: float = None) -> pd.Series:
        """
        윈저라이징(Winsorizing) 처리

        상하위 지정 백분위수 밖의 데이터를 해당 분위수 값으로 대체

        장점: 데이터 손실 없음, 포트폴리오 구성에 적합
        단점: 극단값의 영향이 일부 남음

        Args:
            values: 원본 데이터 Series
            lower_percentile: 하위 백분위수 (기본값: settings.WINSORIZE_LOWER)
            upper_percentile: 상위 백분위수 (기본값: settings.WINSORIZE_UPPER)

        Returns:
            윈저라이징 처리된 Series
        """
        if lower_percentile is None:
            lower_percentile = settings.WINSORIZE_LOWER
        if upper_percentile is None:
            upper_percentile = settings.WINSORIZE_UPPER

        lower_bound = values.quantile(lower_percentile)
        upper_bound = values.quantile(upper_percentile)

        result = values.copy()
        result = result.clip(lower=lower_bound, upper=upper_bound)

        return result

    @staticmethod
    def zscore_filter(values: pd.Series, threshold: float = 3.0) -> pd.Series:
        """
        Z-score 기반 이상치 필터링

        Z-score 절대값이 threshold를 초과하는 값을 NA로 처리

        Args:
            values: 원본 데이터 Series
            threshold: Z-score 임계값 (기본 3.0)

        Returns:
            필터링된 Series
        """
        zscore = (values - values.mean()) / values.std()

        result = values.copy()
        result[abs(zscore) > threshold] = np.nan

        return result

    @staticmethod
    def iqr_filter(values: pd.Series, k: float = 1.5) -> pd.Series:
        """
        IQR(Interquartile Range) 기반 이상치 필터링

        Q1 - k*IQR ~ Q3 + k*IQR 범위 밖의 값을 NA로 처리

        Args:
            values: 원본 데이터 Series
            k: IQR 배수 (기본 1.5)

        Returns:
            필터링된 Series
        """
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower_bound = q1 - k * iqr
        upper_bound = q3 + k * iqr

        result = values.copy()
        result[(result < lower_bound) | (result > upper_bound)] = np.nan

        return result

    @staticmethod
    def mad_filter(values: pd.Series, threshold: float = 3.0) -> pd.Series:
        """
        MAD(Median Absolute Deviation) 기반 이상치 필터링

        중앙값 기반으로 더 로버스트한 이상치 탐지

        Args:
            values: 원본 데이터 Series
            threshold: MAD 배수 임계값 (기본 3.0)

        Returns:
            필터링된 Series
        """
        median = values.median()
        mad = np.median(np.abs(values - median))

        if mad == 0:
            return values

        modified_zscore = 0.6745 * (values - median) / mad

        result = values.copy()
        result[abs(modified_zscore) > threshold] = np.nan

        return result

    @staticmethod
    def process_dataframe(df: pd.DataFrame,
                          method: str = 'winsorize',
                          columns: list = None,
                          **kwargs) -> pd.DataFrame:
        """
        DataFrame 전체에 이상치 처리 적용

        Args:
            df: 원본 DataFrame
            method: 처리 방법 ('trim', 'winsorize', 'zscore', 'iqr', 'mad')
            columns: 처리할 컬럼 리스트 (None이면 숫자형 전체)
            **kwargs: 각 메서드에 전달할 추가 인자

        Returns:
            이상치 처리된 DataFrame
        """
        result = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        method_map = {
            'trim': OutlierHandler.trim,
            'winsorize': OutlierHandler.winsorize,
            'zscore': OutlierHandler.zscore_filter,
            'iqr': OutlierHandler.iqr_filter,
            'mad': OutlierHandler.mad_filter
        }

        if method not in method_map:
            raise ValueError(f"Unknown method: {method}. Use one of {list(method_map.keys())}")

        handler = method_map[method]

        for col in columns:
            result[col] = handler(result[col], **kwargs)

        return result

    @staticmethod
    def get_outlier_stats(values: pd.Series) -> dict:
        """
        이상치 통계 정보 반환

        Args:
            values: 데이터 Series

        Returns:
            통계 정보 딕셔너리
        """
        clean_values = values.dropna()

        q1 = clean_values.quantile(0.25)
        q3 = clean_values.quantile(0.75)
        iqr = q3 - q1

        return {
            'count': len(clean_values),
            'mean': clean_values.mean(),
            'std': clean_values.std(),
            'min': clean_values.min(),
            'max': clean_values.max(),
            'median': clean_values.median(),
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'lower_fence': q1 - 1.5 * iqr,
            'upper_fence': q3 + 1.5 * iqr,
            'skewness': clean_values.skew(),
            'kurtosis': clean_values.kurtosis(),
            'outliers_iqr': ((clean_values < q1 - 1.5 * iqr) | (clean_values > q3 + 1.5 * iqr)).sum()
        }
