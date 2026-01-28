"""
테이블 컴포넌트
"""
import pandas as pd
import streamlit as st
from typing import List, Optional


def format_currency(value: float, unit: str = '원') -> str:
    """금액 포맷팅"""
    if abs(value) >= 1e8:
        return f"{value/1e8:,.1f}억{unit}"
    elif abs(value) >= 1e4:
        return f"{value/1e4:,.0f}만{unit}"
    return f"{value:,.0f}{unit}"


def format_percent(value: float) -> str:
    """퍼센트 포맷팅"""
    return f"{value:.2%}"


def create_holdings_table(holdings: pd.DataFrame,
                          columns: Optional[List[str]] = None) -> pd.DataFrame:
    """
    보유 종목 테이블 생성

    Args:
        holdings: 보유 종목 DataFrame
        columns: 표시할 컬럼 리스트

    Returns:
        포맷팅된 DataFrame
    """
    if columns is None:
        columns = ['code', 'name', 'sector', 'shares', 'avg_price',
                   'current_price', 'current_value', 'pnl', 'pnl_pct']

    available_columns = [c for c in columns if c in holdings.columns]
    df = holdings[available_columns].copy()

    # 컬럼명 한글화
    column_names = {
        'code': '종목코드',
        'name': '종목명',
        'sector': '섹터',
        'shares': '보유수량',
        'avg_price': '매수단가',
        'current_price': '현재가',
        'current_value': '평가금액',
        'pnl': '평가손익',
        'pnl_pct': '수익률'
    }

    df = df.rename(columns={c: column_names.get(c, c) for c in df.columns})

    # 포맷팅
    if '매수단가' in df.columns:
        df['매수단가'] = df['매수단가'].apply(lambda x: f'{x:,.0f}')
    if '현재가' in df.columns:
        df['현재가'] = df['현재가'].apply(lambda x: f'{x:,.0f}')
    if '평가금액' in df.columns:
        df['평가금액'] = df['평가금액'].apply(lambda x: f'{x:,.0f}')
    if '평가손익' in df.columns:
        df['평가손익'] = df['평가손익'].apply(lambda x: f'{x:+,.0f}')
    if '수익률' in df.columns:
        df['수익률'] = df['수익률'].apply(lambda x: f'{x:+.2%}')

    return df


def create_metrics_table(metrics: dict) -> pd.DataFrame:
    """
    성과 지표 테이블 생성

    Args:
        metrics: 성과 지표 딕셔너리

    Returns:
        포맷팅된 DataFrame
    """
    rows = []

    # 지표별 포맷팅
    format_map = {
        'total_return': ('총 수익률', format_percent),
        'cagr': ('CAGR', format_percent),
        'volatility': ('변동성', format_percent),
        'sharpe_ratio': ('샤프 비율', lambda x: f'{x:.2f}'),
        'sortino_ratio': ('소르티노 비율', lambda x: f'{x:.2f}'),
        'mdd': ('MDD', format_percent),
        'calmar_ratio': ('칼마 비율', lambda x: f'{x:.2f}'),
        'win_rate': ('승률', format_percent),
        'initial_value': ('초기 자본', format_currency),
        'final_value': ('최종 자산', format_currency),
    }

    for key, value in metrics.items():
        if key in format_map:
            name, formatter = format_map[key]
            rows.append({
                '지표': name,
                '값': formatter(value)
            })

    return pd.DataFrame(rows)


def create_trade_history_table(trades: pd.DataFrame) -> pd.DataFrame:
    """
    거래 내역 테이블 생성

    Args:
        trades: 거래 내역 DataFrame

    Returns:
        포맷팅된 DataFrame
    """
    if trades.empty:
        return pd.DataFrame()

    df = trades.copy()

    # 컬럼명 한글화
    column_names = {
        'date': '날짜',
        'code': '종목코드',
        'name': '종목명',
        'action': '매매',
        'shares': '수량',
        'price': '가격',
        'value': '금액',
        'commission': '수수료'
    }

    df = df.rename(columns={c: column_names.get(c, c) for c in df.columns})

    # 포맷팅
    if '가격' in df.columns:
        df['가격'] = df['가격'].apply(lambda x: f'{x:,.0f}')
    if '금액' in df.columns:
        df['금액'] = df['금액'].apply(lambda x: f'{x:,.0f}')
    if '수수료' in df.columns:
        df['수수료'] = df['수수료'].apply(lambda x: f'{x:,.0f}')

    return df


def create_stock_selection_table(stocks: pd.DataFrame) -> pd.DataFrame:
    """
    종목 선정 결과 테이블 생성

    Args:
        stocks: 선정 종목 DataFrame

    Returns:
        포맷팅된 DataFrame
    """
    df = stocks.copy()

    # 표시할 컬럼
    display_cols = ['rank', 'code', 'name', 'score']

    # 추가 컬럼
    optional_cols = ['sector', 'market_cap', 'roe', 'per', 'pbr', 'momentum_12m']
    for col in optional_cols:
        if col in df.columns:
            display_cols.append(col)

    df = df[display_cols]

    # 컬럼명 한글화
    column_names = {
        'rank': '순위',
        'code': '종목코드',
        'name': '종목명',
        'score': '점수',
        'sector': '섹터',
        'market_cap': '시가총액',
        'roe': 'ROE',
        'per': 'PER',
        'pbr': 'PBR',
        'momentum_12m': '12M 모멘텀'
    }

    df = df.rename(columns={c: column_names.get(c, c) for c in df.columns})

    # 포맷팅
    if '시가총액' in df.columns:
        df['시가총액'] = df['시가총액'].apply(lambda x: format_currency(x))
    if 'ROE' in df.columns:
        df['ROE'] = df['ROE'].apply(lambda x: f'{x:.1%}' if pd.notna(x) else '-')
    if 'PER' in df.columns:
        df['PER'] = df['PER'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else '-')
    if 'PBR' in df.columns:
        df['PBR'] = df['PBR'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else '-')
    if '12M 모멘텀' in df.columns:
        df['12M 모멘텀'] = df['12M 모멘텀'].apply(lambda x: f'{x:.1%}' if pd.notna(x) else '-')
    if '점수' in df.columns:
        df['점수'] = df['점수'].apply(lambda x: f'{x:.4f}')

    return df


def display_styled_table(df: pd.DataFrame,
                         highlight_column: str = None,
                         use_container_width: bool = True):
    """
    스타일링된 테이블 표시

    Args:
        df: DataFrame
        highlight_column: 하이라이트할 컬럼 (양수=녹색, 음수=빨강)
        use_container_width: 컨테이너 너비 사용 여부
    """
    st.dataframe(df, use_container_width=use_container_width, hide_index=True)
