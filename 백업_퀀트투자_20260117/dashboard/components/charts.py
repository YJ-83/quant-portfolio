"""
차트 컴포넌트
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional


def create_portfolio_value_chart(portfolio_history: pd.DataFrame,
                                  benchmark_history: Optional[pd.DataFrame] = None,
                                  title: str = "포트폴리오 가치 추이") -> go.Figure:
    """
    포트폴리오 가치 추이 차트

    Args:
        portfolio_history: 포트폴리오 히스토리 (index=date, columns=['total_value'])
        benchmark_history: 벤치마크 히스토리 (선택)
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    # 포트폴리오
    fig.add_trace(go.Scatter(
        x=portfolio_history.index,
        y=portfolio_history['total_value'],
        mode='lines',
        name='포트폴리오',
        line=dict(color='#1f77b4', width=2)
    ))

    # 벤치마크
    if benchmark_history is not None:
        fig.add_trace(go.Scatter(
            x=benchmark_history.index,
            y=benchmark_history['value'],
            mode='lines',
            name='벤치마크',
            line=dict(color='gray', width=1, dash='dash')
        ))

    fig.update_layout(
        title=title,
        xaxis_title="날짜",
        yaxis_title="가치 (원)",
        hovermode='x unified',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template='plotly_white'
    )

    return fig


def create_drawdown_chart(values: pd.Series,
                          title: str = "낙폭 (Drawdown)") -> go.Figure:
    """
    낙폭 차트

    Args:
        values: 포트폴리오 가치 Series
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    running_max = values.expanding().max()
    drawdown = (values - running_max) / running_max * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=values.index,
        y=drawdown,
        fill='tozeroy',
        fillcolor='rgba(255, 0, 0, 0.2)',
        line=dict(color='red', width=1),
        name='Drawdown'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="날짜",
        yaxis_title="낙폭 (%)",
        hovermode='x unified',
        template='plotly_white'
    )

    return fig


def create_monthly_returns_heatmap(returns: pd.Series,
                                    title: str = "월별 수익률 히트맵") -> go.Figure:
    """
    월별 수익률 히트맵

    Args:
        returns: 월간 수익률 Series (index=date)
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    df = returns.to_frame('return')
    df['year'] = df.index.year
    df['month'] = df.index.month

    pivot = df.pivot(index='year', columns='month', values='return')

    months = ['1월', '2월', '3월', '4월', '5월', '6월',
              '7월', '8월', '9월', '10월', '11월', '12월']

    fig = px.imshow(
        pivot.values * 100,
        x=months[:pivot.shape[1]],
        y=pivot.index.tolist(),
        color_continuous_scale='RdYlGn',
        color_continuous_midpoint=0,
        aspect='auto'
    )

    fig.update_layout(
        title=title,
        xaxis_title="월",
        yaxis_title="연도"
    )

    return fig


def create_yearly_returns_bar(returns: pd.Series,
                               title: str = "연간 수익률") -> go.Figure:
    """
    연간 수익률 막대 차트

    Args:
        returns: 연간 수익률 Series
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    colors = ['green' if r >= 0 else 'red' for r in returns.values]

    fig = go.Figure(go.Bar(
        x=[str(d.year) for d in returns.index],
        y=returns.values * 100,
        marker_color=colors,
        text=[f'{r:.1%}' for r in returns.values],
        textposition='outside'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="연도",
        yaxis_title="수익률 (%)",
        template='plotly_white'
    )

    return fig


def create_sector_pie_chart(sector_data: dict,
                            title: str = "섹터 분포") -> go.Figure:
    """
    섹터 분포 파이 차트

    Args:
        sector_data: 섹터별 비중 딕셔너리
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    fig = px.pie(
        values=list(sector_data.values()),
        names=list(sector_data.keys()),
        title=title
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')

    return fig


def create_factor_scatter(data: pd.DataFrame,
                          x_factor: str,
                          y_factor: str,
                          color_by: str = None,
                          title: str = None) -> go.Figure:
    """
    팩터 산점도

    Args:
        data: 팩터 데이터 DataFrame
        x_factor: X축 팩터
        y_factor: Y축 팩터
        color_by: 색상 구분 컬럼
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    if title is None:
        title = f"{x_factor} vs {y_factor}"

    fig = px.scatter(
        data,
        x=x_factor,
        y=y_factor,
        color=color_by,
        hover_data=['code', 'name'] if 'code' in data.columns else None,
        title=title
    )

    fig.update_layout(template='plotly_white')

    return fig


def create_holdings_bar_chart(holdings: pd.DataFrame,
                               metric: str = 'pnl_pct',
                               title: str = "종목별 수익률") -> go.Figure:
    """
    보유 종목 막대 차트

    Args:
        holdings: 보유 종목 DataFrame
        metric: 표시할 지표 (pnl_pct, current_value 등)
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    sorted_holdings = holdings.sort_values(metric)

    if metric == 'pnl_pct':
        colors = ['green' if x >= 0 else 'red' for x in sorted_holdings[metric]]
        values = sorted_holdings[metric] * 100
        y_label = "수익률 (%)"
    else:
        colors = '#1f77b4'
        values = sorted_holdings[metric]
        y_label = metric

    fig = go.Figure(go.Bar(
        x=values,
        y=sorted_holdings['name'],
        orientation='h',
        marker_color=colors
    ))

    fig.update_layout(
        title=title,
        xaxis_title=y_label,
        yaxis_title="종목",
        height=max(400, len(holdings) * 25),
        template='plotly_white'
    )

    return fig
