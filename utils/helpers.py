"""
유틸리티 헬퍼 함수
"""
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np


def calculate_returns(prices: pd.Series,
                      periods: int = 1,
                      method: str = 'simple') -> pd.Series:
    """
    수익률 계산

    Args:
        prices: 가격 Series
        periods: 기간 (일 수)
        method: 'simple' 또는 'log'

    Returns:
        수익률 Series
    """
    if method == 'simple':
        return prices.pct_change(periods)
    elif method == 'log':
        return np.log(prices / prices.shift(periods))
    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_momentum(prices: pd.DataFrame, months: int) -> pd.Series:
    """
    N개월 모멘텀 계산

    Args:
        prices: 가격 DataFrame (index: date, columns: code)
        months: 모멘텀 기간 (개월)

    Returns:
        모멘텀 수익률 Series (종목별)
    """
    trading_days = months * 21  # 월 평균 21 거래일

    if len(prices) < trading_days:
        return pd.Series(dtype=float)

    current_price = prices.iloc[-1]
    past_price = prices.iloc[-trading_days]

    momentum = (current_price - past_price) / past_price

    return momentum


def resample_to_monthly(df: pd.DataFrame,
                        date_col: str = 'date',
                        value_col: str = 'close',
                        method: str = 'last') -> pd.DataFrame:
    """
    일간 데이터를 월간으로 리샘플링

    Args:
        df: 일간 데이터 DataFrame
        date_col: 날짜 컬럼명
        value_col: 값 컬럼명
        method: 리샘플링 방법 ('last', 'first', 'mean')

    Returns:
        월간 데이터 DataFrame
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)

    if method == 'last':
        monthly = df.resample('ME')[value_col].last()
    elif method == 'first':
        monthly = df.resample('ME')[value_col].first()
    elif method == 'mean':
        monthly = df.resample('ME')[value_col].mean()
    else:
        raise ValueError(f"Unknown method: {method}")

    return monthly.reset_index()


def get_rebalance_dates(start_date: str,
                        end_date: str,
                        frequency: str = 'quarterly') -> List[datetime]:
    """
    리밸런싱 날짜 생성

    Args:
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        frequency: 'monthly', 'quarterly', 'yearly'

    Returns:
        리밸런싱 날짜 리스트
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    if frequency == 'monthly':
        dates = pd.date_range(start=start, end=end, freq='ME')
    elif frequency == 'quarterly':
        dates = pd.date_range(start=start, end=end, freq='QE')
    elif frequency == 'yearly':
        dates = pd.date_range(start=start, end=end, freq='YE')
    else:
        raise ValueError(f"Unknown frequency: {frequency}")

    return dates.tolist()


def get_trading_day(date: datetime,
                    direction: str = 'forward') -> datetime:
    """
    거래일 찾기 (주말/공휴일 제외)

    Args:
        date: 기준 날짜
        direction: 'forward' (다음 거래일) 또는 'backward' (이전 거래일)

    Returns:
        거래일 datetime
    """
    # 간단한 주말 체크만 수행
    # 실제로는 공휴일 달력 필요

    while date.weekday() >= 5:  # 토(5), 일(6)
        if direction == 'forward':
            date = date + timedelta(days=1)
        else:
            date = date - timedelta(days=1)

    return date


def calculate_portfolio_value(holdings: dict,
                              prices: dict,
                              cash: float = 0) -> float:
    """
    포트폴리오 가치 계산

    Args:
        holdings: 보유 종목 {code: shares}
        prices: 현재가 {code: price}
        cash: 현금

    Returns:
        총 포트폴리오 가치
    """
    stock_value = sum(
        holdings.get(code, 0) * prices.get(code, 0)
        for code in holdings
    )
    return stock_value + cash


def equal_weight_allocation(capital: float,
                            codes: List[str],
                            prices: dict) -> dict:
    """
    동일 비중 배분

    Args:
        capital: 투자 금액
        codes: 종목 코드 리스트
        prices: 현재가 {code: price}

    Returns:
        종목별 매수 수량 {code: shares}
    """
    if not codes:
        return {}

    allocation = capital / len(codes)
    holdings = {}

    for code in codes:
        price = prices.get(code, 0)
        if price > 0:
            shares = int(allocation / price)  # 정수 주수
            holdings[code] = shares

    return holdings


def format_currency(value: float, currency: str = 'KRW') -> str:
    """
    금액 포맷팅

    Args:
        value: 금액
        currency: 통화 (KRW, USD)

    Returns:
        포맷팅된 문자열
    """
    if currency == 'KRW':
        if abs(value) >= 1e8:
            return f"{value/1e8:,.1f}억원"
        elif abs(value) >= 1e4:
            return f"{value/1e4:,.0f}만원"
        else:
            return f"{value:,.0f}원"
    else:
        return f"${value:,.2f}"


def format_percent(value: float, decimals: int = 2) -> str:
    """
    퍼센트 포맷팅

    Args:
        value: 비율 (0.15 = 15%)
        decimals: 소수점 자릿수

    Returns:
        포맷팅된 문자열
    """
    return f"{value * 100:.{decimals}f}%"
