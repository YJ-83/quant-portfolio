"""
백테스트 페이지
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import json
import os

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backtest.metrics import PerformanceMetrics
from backtest.report import BacktestResult

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection

# 스윙 포인트 감지 함수 import
from dashboard.utils.chart_utils import detect_swing_points

# 모의투자 기록 저장 경로
SIMULATION_HISTORY_FILE = os.path.join(Path(__file__).parent.parent.parent, "data", "simulation_history.json")


def render_backtest():
    """백테스트 페이지 렌더링"""

    # 페이지 전용 CSS
    st.markdown("""
    <style>
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        @keyframes shimmer {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }

        @keyframes countUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .hero-backtest {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 50%, #00f2fe 100%);
            background-size: 200% 200%;
            animation: gradientBG 8s ease infinite;
            padding: 2.5rem;
            border-radius: 24px;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }

        .hero-backtest::before {
            content: '';
            position: absolute;
            top: 0;
            left: -200%;
            width: 200%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s infinite;
        }

        .backtest-card {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.08);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 2px solid transparent;
            animation: slideUp 0.6s ease-out;
        }

        .backtest-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 50px rgba(17, 153, 142, 0.2);
            border-color: #11998e;
        }

        .metric-card-top {
            background: linear-gradient(135deg, var(--color) 0%, var(--color-end) 100%);
            padding: 1.75rem;
            border-radius: 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            animation: slideUp 0.5s ease-out;
        }

        .metric-card-top::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }

        .metric-card-bottom {
            background: white;
            padding: 1.25rem;
            border-radius: 16px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.06);
            text-align: center;
            transition: all 0.3s ease;
            animation: slideUp 0.5s ease-out;
        }

        .metric-card-bottom:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 35px rgba(0,0,0,0.1);
        }

        .chart-container {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.06);
            margin-bottom: 1.5rem;
            animation: fadeIn 0.8s ease-out;
        }

        .settings-section {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 1.5rem;
            border-radius: 20px;
            margin-bottom: 1.5rem;
        }

        .run-button-container {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, #11998e10 0%, #38ef7d10 100%);
            border-radius: 20px;
            margin: 1.5rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

    # 히어로 헤더
    st.markdown("""
    <div class='hero-backtest'>
        <div style='position: relative; z-index: 1;'>
            <div style='font-size: 4rem; margin-bottom: 0.5rem; animation: float 3s ease-in-out infinite;'>📈</div>
            <h1 style='color: white; font-size: 2.5rem; margin: 0 0 0.5rem 0; font-weight: 800; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>백테스트 & 모의투자</h1>
            <p style='color: rgba(255,255,255,0.95); font-size: 1.1rem; margin: 0;'>전략의 과거 성과와 미래 예측을 검증합니다</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["📊 과거 백테스트", "🎯 차트전략 모의투자", "📈 모의투자 성과분석"])

    with tab1:
        _render_traditional_backtest()

    with tab2:
        _render_chart_strategy_simulation()

    with tab3:
        _render_simulation_analysis()


def _render_traditional_backtest():
    """기존 백테스트 섹션"""
    # 설정 섹션
    st.markdown("""
    <div class='settings-section'>
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <span style='font-size: 1.75rem;'>⚙️</span>
            <h3 style='margin: 0; color: #333;'>백테스트 설정</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 설정 카드들
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='backtest-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>🎯</span>
                <h4 style='margin: 0; color: #333;'>전략 & 기간</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)

        strategy_option = st.selectbox(
            "전략 선택",
            ["마법공식 (Magic Formula)", "멀티팩터", "섹터 중립", "전체 비교"],
            label_visibility="collapsed"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            start_date = st.date_input(
                "시작일",
                value=datetime.now() - timedelta(days=365*3),
                max_value=datetime.now()
            )
        with col_b:
            end_date = st.date_input(
                "종료일",
                value=datetime.now(),
                max_value=datetime.now()
            )

    with col2:
        st.markdown("""
        <div class='backtest-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>💰</span>
                <h4 style='margin: 0; color: #333;'>투자 설정</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)

        initial_capital = st.number_input(
            "초기 투자금 (원)",
            min_value=10000000,
            max_value=10000000000,
            value=100000000,
            step=10000000,
            format="%d"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            rebalance_period = st.selectbox(
                "리밸런싱 주기",
                ["quarterly", "monthly", "yearly"],
                format_func=lambda x: {"quarterly": "분기별", "monthly": "월별", "yearly": "연별"}[x]
            )
        with col_b:
            benchmark = st.selectbox(
                "벤치마크",
                ["KOSPI", "KOSDAQ", "없음"]
            )

    # 실행 버튼
    st.markdown("""
    <div class='run-button-container'>
        <p style='color: #666; margin-bottom: 1rem; font-size: 1rem;'>설정을 완료하고 백테스트를 실행하세요</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_backtest = st.button(
            "🚀 백테스트 실행",
            type="primary",
            use_container_width=True
        )

    if run_backtest:
        with st.spinner("📊 백테스트 실행 중..."):
            result = _generate_sample_backtest_result(
                strategy_option,
                start_date,
                end_date,
                initial_capital,
                rebalance_period
            )
            st.session_state['backtest_result'] = result
            st.success("✅ 백테스트 완료!")

    # 결과 표시
    if 'backtest_result' in st.session_state:
        result = st.session_state['backtest_result']

        st.markdown("---")

        # 핵심 지표 카드
        st.markdown("""
        <div style='display: flex; align-items: center; gap: 1rem; margin: 2rem 0 1.5rem 0;'>
            <span style='font-size: 2.5rem;'>📊</span>
            <h2 style='margin: 0; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;'>성과 요약</h2>
        </div>
        """, unsafe_allow_html=True)

        # 상단 메트릭 카드
        col1, col2, col3, col4 = st.columns(4)

        metrics_top = [
            {"label": "총 수익률", "value": f"{result.total_return:.1%}", "icon": "💰",
             "color": "#667eea" if result.total_return >= 0 else "#f5576c",
             "color_end": "#764ba2" if result.total_return >= 0 else "#f093fb"},
            {"label": "CAGR", "value": f"{result.cagr:.1%}", "icon": "📈",
             "color": "#11998e" if result.cagr >= 0 else "#f5576c",
             "color_end": "#38ef7d" if result.cagr >= 0 else "#f093fb"},
            {"label": "샤프 비율", "value": f"{result.sharpe_ratio:.2f}", "icon": "⚡",
             "color": "#4facfe" if result.sharpe_ratio >= 1 else "#f093fb",
             "color_end": "#00f2fe" if result.sharpe_ratio >= 1 else "#f5576c"},
            {"label": "MDD", "value": f"{result.mdd:.1%}", "icon": "📉",
             "color": "#f5576c", "color_end": "#f093fb"},
        ]

        for col, metric in zip([col1, col2, col3, col4], metrics_top):
            with col:
                st.markdown(f"""
                <div class='metric-card-top' style='--color: {metric["color"]}; --color-end: {metric["color_end"]}'>
                    <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>{metric["icon"]}</p>
                    <p style='color: white; font-size: 2rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>{metric["value"]}</p>
                    <p style='color: rgba(255,255,255,0.9); font-size: 0.95rem; margin: 0; position: relative; z-index: 1;'>{metric["label"]}</p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 하단 메트릭 카드
        col1, col2, col3, col4 = st.columns(4)

        metrics_bottom = [
            {"label": "변동성", "value": f"{result.volatility:.1%}", "icon": "🎢", "color": "#667eea"},
            {"label": "소르티노", "value": f"{result.sortino_ratio:.2f}", "icon": "🎯", "color": "#11998e"},
            {"label": "칼마 비율", "value": f"{result.calmar_ratio:.2f}", "icon": "⚖️", "color": "#f093fb"},
            {"label": "승률", "value": f"{result.win_rate:.1%}", "icon": "🏆", "color": "#4facfe"},
        ]

        for col, metric in zip([col1, col2, col3, col4], metrics_bottom):
            with col:
                st.markdown(f"""
                <div class='metric-card-bottom'>
                    <p style='font-size: 2rem; margin: 0;'>{metric["icon"]}</p>
                    <p style='color: {metric["color"]}; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{metric["value"]}</p>
                    <p style='color: #888; font-size: 0.85rem; margin: 0;'>{metric["label"]}</p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # 포트폴리오 성과 차트
        st.markdown("""
        <div class='chart-container'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.75rem;'>📈</span>
                <h3 style='margin: 0; color: #333;'>포트폴리오 가치 추이</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=result.portfolio_history.index,
            y=result.portfolio_history['total_value'],
            mode='lines',
            name='포트폴리오',
            line=dict(color='#11998e', width=3),
            fill='tozeroy',
            fillcolor='rgba(17, 153, 142, 0.15)'
        ))

        if 'benchmark_value' in result.portfolio_history.columns:
            fig.add_trace(go.Scatter(
                x=result.portfolio_history.index,
                y=result.portfolio_history['benchmark_value'],
                mode='lines',
                name='벤치마크 (KOSPI)',
                line=dict(color='#888', width=2, dash='dash')
            ))

        fig.update_layout(
            xaxis_title="",
            yaxis_title="포트폴리오 가치 (원)",
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(t=50, b=30, l=60, r=30),
            yaxis_tickformat=',',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=400
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')

        st.plotly_chart(fig, use_container_width=True)

        # 낙폭 차트
        st.markdown("""
        <div class='chart-container'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.75rem;'>📉</span>
                <h3 style='margin: 0; color: #333;'>낙폭 (Drawdown)</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        drawdown = result.get_drawdown_series()

        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values * 100,
            fill='tozeroy',
            fillcolor='rgba(245, 87, 108, 0.3)',
            line=dict(color='#f5576c', width=2),
            name='Drawdown'
        ))

        fig_dd.update_layout(
            xaxis_title="",
            yaxis_title="낙폭 (%)",
            hovermode='x unified',
            margin=dict(t=20, b=30, l=60, r=30),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=300
        )
        fig_dd.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')
        fig_dd.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)')

        st.plotly_chart(fig_dd, use_container_width=True)

        # 월간/연간 수익률
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            <div class='chart-container'>
                <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                    <span style='font-size: 1.5rem;'>📅</span>
                    <h4 style='margin: 0; color: #333;'>월간 수익률 히트맵</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)

            monthly_returns = result.get_monthly_returns()
            monthly_df = monthly_returns.to_frame('return')
            monthly_df['year'] = monthly_df.index.year
            monthly_df['month'] = monthly_df.index.month
            pivot_df = monthly_df.pivot(index='year', columns='month', values='return')

            fig_monthly = px.imshow(
                pivot_df.values * 100,
                x=['1월', '2월', '3월', '4월', '5월', '6월',
                   '7월', '8월', '9월', '10월', '11월', '12월'][:pivot_df.shape[1]],
                y=pivot_df.index.tolist(),
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                aspect='auto'
            )
            fig_monthly.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                coloraxis_colorbar=dict(title="%")
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

        with col2:
            st.markdown("""
            <div class='chart-container'>
                <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                    <span style='font-size: 1.5rem;'>📊</span>
                    <h4 style='margin: 0; color: #333;'>연간 수익률</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)

            yearly_returns = result.get_yearly_returns()
            colors = ['#11998e' if r >= 0 else '#f5576c' for r in yearly_returns.values]

            fig_yearly = go.Figure(go.Bar(
                x=[str(d.year) for d in yearly_returns.index],
                y=yearly_returns.values * 100,
                marker_color=colors,
                text=[f'{r:.1%}' for r in yearly_returns.values],
                textposition='outside'
            ))

            fig_yearly.update_layout(
                xaxis_title="",
                yaxis_title="수익률 (%)",
                margin=dict(t=20, b=30, l=40, r=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_yearly, use_container_width=True)

        st.markdown("---")

        # 상세 지표 테이블
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            <div class='backtest-card'>
                <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                    <span style='font-size: 1.5rem;'>📋</span>
                    <h4 style='margin: 0; color: #333;'>수익률 지표</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)

            return_metrics = pd.DataFrame({
                '지표': ['초기 자본', '최종 자산', '총 수익률', 'CAGR', '벤치마크 수익률', '초과 수익률'],
                '값': [
                    f"{result.initial_capital:,.0f}원",
                    f"{result.final_value:,.0f}원",
                    f"{result.total_return:.2%}",
                    f"{result.cagr:.2%}",
                    f"{result.metrics.get('benchmark_return', 0):.2%}",
                    f"{result.metrics.get('excess_return', 0):.2%}"
                ]
            })
            st.dataframe(return_metrics, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("""
            <div class='backtest-card'>
                <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                    <span style='font-size: 1.5rem;'>📋</span>
                    <h4 style='margin: 0; color: #333;'>위험 지표</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 손익비 계산
            profit_loss_ratio = result.metrics.get('profit_loss_ratio', 0)
            info_ratio = result.metrics.get('information_ratio', 0)

            risk_metrics = pd.DataFrame({
                '지표': ['변동성 (연율)', 'MDD', '샤프 비율', '소르티노 비율', '칼마 비율', '승률', '손익비', '정보비율'],
                '값': [
                    f"{result.volatility:.2%}",
                    f"{result.mdd:.2%}",
                    f"{result.sharpe_ratio:.2f}",
                    f"{result.sortino_ratio:.2f}",
                    f"{result.calmar_ratio:.2f}",
                    f"{result.win_rate:.2%}",
                    f"{profit_loss_ratio:.2f}",
                    f"{info_ratio:.2f}"
                ]
            })
            st.dataframe(risk_metrics, use_container_width=True, hide_index=True)

        # 다운로드 버튼
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)

        with col1:
            report_text = result.summary()
            st.download_button(
                label="📄 리포트 다운로드",
                data=report_text,
                file_name=f"backtest_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )

        with col2:
            csv_data = result.portfolio_history.to_csv()
            st.download_button(
                label="📊 데이터 다운로드 (CSV)",
                data=csv_data,
                file_name=f"portfolio_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col3:
            trades_csv = result.trade_history.to_csv(index=False)
            st.download_button(
                label="📋 거래내역 다운로드",
                data=trades_csv,
                file_name=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )


def _generate_sample_backtest_result(strategy_name: str,
                                      start_date,
                                      end_date,
                                      initial_capital: float,
                                      rebalance_period: str) -> BacktestResult:
    """샘플 백테스트 결과 생성"""

    dates = pd.date_range(start=start_date, end=end_date, freq='B')

    seed_map = {
        "마법공식 (Magic Formula)": 42,
        "멀티팩터": 123,
        "섹터 중립": 456,
        "전체 비교": 789
    }
    np.random.seed(seed_map.get(strategy_name, 42))

    if strategy_name == "마법공식 (Magic Formula)":
        daily_returns = np.random.normal(0.0005, 0.015, len(dates))
    elif strategy_name == "멀티팩터":
        daily_returns = np.random.normal(0.0006, 0.012, len(dates))
    elif strategy_name == "섹터 중립":
        daily_returns = np.random.normal(0.0004, 0.010, len(dates))
    else:
        daily_returns = np.random.normal(0.0005, 0.014, len(dates))

    cumulative_returns = (1 + daily_returns).cumprod()
    portfolio_values = initial_capital * cumulative_returns

    benchmark_returns = np.random.normal(0.0003, 0.012, len(dates))
    benchmark_cumulative = (1 + benchmark_returns).cumprod()
    benchmark_values = initial_capital * benchmark_cumulative

    portfolio_history = pd.DataFrame({
        'total_value': portfolio_values,
        'benchmark_value': benchmark_values,
        'cash': portfolio_values * 0.02,
        'stock_value': portfolio_values * 0.98,
        'num_positions': 30
    }, index=dates)

    trade_history = pd.DataFrame({
        'date': dates[::63][:10],
        'code': ['005930', '000660', '035720', '005380', '051910'] * 2,
        'action': ['BUY'] * 5 + ['SELL'] * 5,
        'shares': [100, 50, 200, 30, 100] * 2,
        'price': [70000, 80000, 50000, 200000, 150000] * 2,
        'value': [7000000, 4000000, 10000000, 6000000, 15000000] * 2
    })

    final_value = portfolio_values[-1]
    returns = pd.Series(daily_returns, index=dates)
    years = (dates[-1] - dates[0]).days / 365

    metrics = {
        'profit_loss_ratio': 1.5 + np.random.random() * 0.5,
        'beta': 0.8 + np.random.random() * 0.4,
        'alpha': 0.05 + np.random.random() * 0.05,
        'benchmark_return': (benchmark_values[-1] - initial_capital) / initial_capital,
        'excess_return': (final_value - benchmark_values[-1]) / initial_capital
    }

    result = BacktestResult(
        strategy_name=strategy_name,
        start_date=str(start_date),
        end_date=str(end_date),
        initial_capital=initial_capital,
        final_value=final_value,
        total_return=(final_value - initial_capital) / initial_capital,
        cagr=PerformanceMetrics.calculate_cagr(initial_capital, final_value, years),
        sharpe_ratio=PerformanceMetrics.calculate_sharpe_ratio(returns),
        sortino_ratio=PerformanceMetrics.calculate_sortino_ratio(returns),
        mdd=PerformanceMetrics.calculate_mdd(pd.Series(portfolio_values, index=dates)),
        volatility=PerformanceMetrics.calculate_volatility(returns),
        win_rate=PerformanceMetrics.calculate_win_rate(returns),
        calmar_ratio=PerformanceMetrics.calculate_cagr(initial_capital, final_value, years) /
                     max(PerformanceMetrics.calculate_mdd(pd.Series(portfolio_values, index=dates)), 0.01),
        portfolio_history=portfolio_history,
        trade_history=trade_history,
        metrics=metrics
    )

    return result


def _render_chart_strategy_simulation():
    """차트전략 모의투자 검증 섹션"""
    st.markdown("""
    <div class='settings-section'>
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <span style='font-size: 1.75rem;'>🎯</span>
            <h3 style='margin: 0; color: #333;'>모의투자 등록</h3>
        </div>
        <p style='color: #666; margin: 0;'>종목을 검색하여 선택하고, 매입가/수량을 입력하여 모의투자를 등록합니다. 일정 기간 후 실제 수익률을 확인할 수 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = get_api_connection()

    # API 연결 상태 표시
    if api:
        st.success("✅ API 연결됨 - 실시간 데이터 사용")
    else:
        st.warning("⚠️ API 미연결 - 샘플 데이터 사용")

    # 종목 검색 영역
    st.markdown("### 🔍 종목 검색")

    # 시장 선택
    col_market, col_search, col_code = st.columns([1, 2, 1])

    with col_market:
        market_choice = st.selectbox(
            "시장 선택",
            ["전체", "KOSPI", "KOSDAQ"],
            key="sim_market_choice"
        )

    # 선택된 시장에 따라 종목 리스트 로드
    all_stocks = _get_all_stocks_for_selection(market_choice)

    with col_search:
        # 드롭다운 선택 (선택하세요... 형태)
        stock_options = ["선택하세요..."] + [f"{name} ({code})" for code, name, market in all_stocks]
        selected_option = st.selectbox(
            "종목 선택",
            options=stock_options,
            key="sim_stock_dropdown",
            label_visibility="collapsed"
        )

    with col_code:
        # 종목코드 직접입력
        direct_code = st.text_input(
            "종목코드 직접입력",
            placeholder="005930",
            key="sim_direct_code"
        )

    # 선택된 종목 결정
    selected_code_only = None
    selected_name = None

    # 직접입력 우선
    if direct_code and len(direct_code) == 6 and direct_code.isdigit():
        selected_code_only = direct_code
        # 종목명 찾기
        for code, name, market in all_stocks:
            if code == direct_code:
                selected_name = name
                break
        if not selected_name:
            selected_name = f"종목 {direct_code}"
    elif selected_option and selected_option != "선택하세요...":
        # 드롭다운에서 선택
        parts = selected_option.split(" (")
        selected_name = parts[0]
        selected_code_only = parts[1].split(")")[0]

    # 종목이 선택된 경우
    if selected_code_only:
        st.markdown("---")

        # 현재가 및 주가 데이터 조회 (실제 API 사용)
        with st.spinner(f"'{selected_name}' 데이터 조회 중..."):
            current_price, price_data, api_connected = _get_stock_price_with_history(api, selected_code_only)

        # 종목 정보 및 차트 표시
        col_info, col_chart = st.columns([1, 2])

        with col_info:
            st.markdown("""
            <div class='backtest-card'>
                <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                    <span style='font-size: 1.5rem;'>📊</span>
                    <h4 style='margin: 0; color: #333;'>종목 정보</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.metric("종목명", f"{selected_name}")
            st.caption(f"종목코드: {selected_code_only}")

            # 현재가 표시 (API 연결 여부 표시)
            if api_connected:
                st.metric("현재가 (실시간)", f"{current_price:,.0f}원")
            else:
                st.metric("현재가 (샘플)", f"{current_price:,.0f}원")
                st.caption("⚠️ API 미연결로 샘플 데이터 표시")

            # 등락률 계산 (가능한 경우)
            if price_data is not None and len(price_data) >= 2:
                prev_close = price_data['close'].iloc[-2]
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                change_color = "🔴" if change < 0 else "🟢"
                st.metric("전일대비", f"{change_color} {change:+,.0f}원 ({change_pct:+.2f}%)")

        with col_chart:
            if api_connected:
                st.markdown("#### 📈 최근 60일 차트 (실시간)")
            else:
                st.markdown("#### 📈 최근 60일 차트 (샘플)")

            if price_data is not None and len(price_data) > 0:
                # 캔들스틱 차트 생성
                fig = go.Figure()

                # 캔들스틱
                fig.add_trace(go.Candlestick(
                    x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                    open=price_data['open'],
                    high=price_data['high'],
                    low=price_data['low'],
                    close=price_data['close'],
                    name='주가',
                    increasing_line_color='#FF3B30',
                    decreasing_line_color='#007AFF',
                    increasing_fillcolor='#FF3B30',
                    decreasing_fillcolor='#007AFF',
                    line=dict(width=1),
                    whiskerwidth=0.8
                ))

                # 이동평균선 추가 (5, 20, 60, 120일)
                if len(price_data) >= 5:
                    ma5 = price_data['close'].rolling(5).mean()
                    fig.add_trace(go.Scatter(
                        x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                        y=ma5,
                        mode='lines',
                        name='MA5',
                        line=dict(color='#FF9800', width=1)
                    ))

                if len(price_data) >= 20:
                    ma20 = price_data['close'].rolling(20).mean()
                    fig.add_trace(go.Scatter(
                        x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                        y=ma20,
                        mode='lines',
                        name='MA20',
                        line=dict(color='#2196F3', width=1)
                    ))

                if len(price_data) >= 60:
                    ma60 = price_data['close'].rolling(60).mean()
                    fig.add_trace(go.Scatter(
                        x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                        y=ma60,
                        mode='lines',
                        name='MA60',
                        line=dict(color='#9C27B0', width=1)
                    ))

                if len(price_data) >= 120:
                    ma120 = price_data['close'].rolling(120).mean()
                    fig.add_trace(go.Scatter(
                        x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                        y=ma120,
                        mode='lines',
                        name='MA120',
                        line=dict(color='#E91E63', width=1)
                    ))

                # 200일선 (장기 추세 기준 — 진홍·두껍게)
                if len(price_data) >= 200:
                    ma200 = price_data['close'].rolling(200).mean()
                    fig.add_trace(go.Scatter(
                        x=price_data['date'] if 'date' in price_data.columns else price_data.index,
                        y=ma200,
                        mode='lines',
                        name='MA200',
                        line=dict(color='#DC143C', width=2.5)
                    ))

                # 스윙 포인트 (저점/고점 마커)
                if len(price_data) >= 10:
                    swing_order = 3 if len(price_data) < 100 else 5
                    swing_high_idx, swing_low_idx = detect_swing_points(price_data, order=swing_order)

                    x_data = price_data['date'] if 'date' in price_data.columns else price_data.index
                    price_range = price_data['high'].max() - price_data['low'].min()
                    marker_offset = price_range * 0.02

                    # 저점 마커
                    if len(swing_low_idx) > 0:
                        recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                        low_x = x_data.iloc[recent_low_idx] if hasattr(x_data, 'iloc') else [x_data[i] for i in recent_low_idx]
                        low_prices = price_data['low'].iloc[recent_low_idx]

                        fig.add_trace(go.Scatter(
                            x=low_x,
                            y=low_prices - marker_offset,
                            mode='markers+text',
                            name='스윙 저점',
                            marker=dict(symbol='triangle-up', size=12, color='#00C853',
                                       line=dict(color='white', width=1)),
                            text=[f'{p:,.0f}' for p in low_prices],
                            textposition='bottom center',
                            textfont=dict(size=9, color='#00C853'),
                            hovertemplate='저점: %{text}<extra></extra>',
                            showlegend=True
                        ))

                    # 고점 마커
                    if len(swing_high_idx) > 0:
                        recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
                        high_x = x_data.iloc[recent_high_idx] if hasattr(x_data, 'iloc') else [x_data[i] for i in recent_high_idx]
                        high_prices = price_data['high'].iloc[recent_high_idx]

                        fig.add_trace(go.Scatter(
                            x=high_x,
                            y=high_prices + marker_offset,
                            mode='markers+text',
                            name='스윙 고점',
                            marker=dict(symbol='triangle-down', size=12, color='#FF3B30',
                                       line=dict(color='white', width=1)),
                            text=[f'{p:,.0f}' for p in high_prices],
                            textposition='top center',
                            textfont=dict(size=9, color='#FF3B30'),
                            hovertemplate='고점: %{text}<extra></extra>',
                            showlegend=True
                        ))

                    # ========== 추세선 추가 (저점/고점 연결) ==========
                    from scipy import stats

                    # 가격 범위 계산 (Y축 클리핑용)
                    price_high = price_data['high'].max()
                    price_low = price_data['low'].min()
                    price_margin = (price_high - price_low) * 0.1  # 10% 여유

                    # 상승 추세선 (저점 연결)
                    if len(swing_low_idx) >= 2:
                        recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                        tl_low_x = list(recent_lows)
                        tl_low_y = [price_data['low'].iloc[i] for i in recent_lows]
                        slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

                        if slope > 0:
                            tl_x_start = min(recent_lows)
                            tl_x_end = len(price_data) - 1
                            tl_y_start = slope * tl_x_start + intercept
                            tl_y_end = slope * tl_x_end + intercept

                            # Y값 클리핑 (차트 범위 내로 제한)
                            tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                            tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                            tl_date_start = x_data.iloc[tl_x_start] if hasattr(x_data, 'iloc') else x_data[tl_x_start]
                            tl_date_end = x_data.iloc[tl_x_end] if hasattr(x_data, 'iloc') else x_data[tl_x_end]

                            fig.add_trace(go.Scatter(
                                x=[tl_date_start, tl_date_end],
                                y=[tl_y_start, tl_y_end],
                                mode='lines',
                                name='상승 추세선',
                                line=dict(color='#00C853', width=2, dash='solid'),
                                hovertemplate='상승 추세선<extra></extra>',
                                showlegend=True
                            ))

                    # 하락 추세선 (고점 연결)
                    if len(swing_high_idx) >= 2:
                        recent_highs = swing_high_idx[-5:] if len(swing_high_idx) >= 5 else swing_high_idx
                        tl_high_x = list(recent_highs)
                        tl_high_y = [price_data['high'].iloc[i] for i in recent_highs]
                        slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

                        if slope < 0:
                            tl_x_start = min(recent_highs)
                            tl_x_end = len(price_data) - 1
                            tl_y_start = slope * tl_x_start + intercept
                            tl_y_end = slope * tl_x_end + intercept

                            # Y값 클리핑 (차트 범위 내로 제한)
                            tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                            tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                            tl_date_start = x_data.iloc[tl_x_start] if hasattr(x_data, 'iloc') else x_data[tl_x_start]
                            tl_date_end = x_data.iloc[tl_x_end] if hasattr(x_data, 'iloc') else x_data[tl_x_end]

                            fig.add_trace(go.Scatter(
                                x=[tl_date_start, tl_date_end],
                                y=[tl_y_start, tl_y_end],
                                mode='lines',
                                name='하락 추세선',
                                line=dict(color='#FF3B30', width=2, dash='solid'),
                                hovertemplate='하락 추세선<extra></extra>',
                                showlegend=True
                            ))

                fig.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis_rangeslider_visible=False,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("차트 데이터를 불러올 수 없습니다.")

        # 매입 정보 입력
        st.markdown("---")
        st.markdown("""
        <div class='backtest-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>💰</span>
                <h4 style='margin: 0; color: #333;'>매입 정보 입력</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            buy_price = st.number_input(
                "매입가 (원)",
                min_value=100,
                max_value=100000000,
                value=int(current_price) if current_price > 0 else 10000,
                step=100,
                key="sim_buy_price"
            )

        with col2:
            quantity = st.number_input(
                "매수 수량 (주)",
                min_value=1,
                max_value=100000,
                value=10,
                step=1,
                key="sim_quantity"
            )

        with col3:
            total_amount = buy_price * quantity
            st.metric("총 매입금액", f"{total_amount:,.0f}원")

        # 보유 기간 및 전략 선택
        col1, col2 = st.columns(2)

        with col1:
            holding_period = st.selectbox(
                "목표 보유 기간",
                ["3일", "5일", "7일", "10일", "14일", "30일"],
                key="sim_holding_period"
            )

        with col2:
            # 전략 유형 선택 (차트전략/전략실행 관련성)
            strategy_type = st.selectbox(
                "📊 투자 전략 유형",
                [
                    "선택 안함",
                    "--- 차트 전략 ---",
                    "골든크로스 (5일선/20일선)",
                    "정배열 (MA5>MA20>MA60)",
                    "눌림목 (20일선 지지)",
                    "120일선 돌파",
                    "거래량 급증 + 양봉",
                    "볼린저밴드 하단 반등",
                    "RSI 과매도 반등",
                    "MACD 골든크로스",
                    "--- 퀀트 전략 ---",
                    "마법공식 (상위종목)",
                    "멀티팩터 (고득점)",
                    "섹터중립 (상위종목)",
                    "저PER + 저PBR",
                    "고배당 + 저변동",
                    "--- 기타 ---",
                    "뉴스/이슈 매매",
                    "실적 발표 기대",
                    "기타 (직접 입력)"
                ],
                key="sim_strategy_type"
            )

        # 투자 근거 태그 선택 (다중 선택)
        st.markdown("##### 📝 투자 근거 선택")

        # 태그 그룹 정의
        tag_groups = {
            "📊 기술적 분석": [
                "이평선 정배열", "이평선 역배열", "골든크로스", "데드크로스",
                "거래량 증가", "거래량 감소", "RSI 과매도", "RSI 과매수",
                "MACD 상승", "MACD 하락", "BB 상단", "BB 하단",
                "추세선 지지", "추세선 저항", "피보나치 지지", "피보나치 저항",
                "R:R 1:1 이상", "R:R 1:2 이상", "R:R 1:3 이상"
            ],
            "👥 수급 분석": [
                "기관 순매수", "기관 순매도", "외국인 순매수", "외국인 순매도",
                "개인 순매수", "개인 순매도", "기관+외국인 동반 매수"
            ],
            "💰 가치 분석": [
                "저PER", "저PBR", "고ROE", "저평가",
                "고배당", "실적 개선", "실적 악화"
            ],
            "📰 이슈/이벤트": [
                "실적 발표 기대", "신사업 진출", "M&A 기대",
                "테마주", "정책 수혜", "계절성"
            ]
        }

        selected_tags = []

        # 2열로 태그 그룹 표시
        col1, col2 = st.columns(2)
        group_names = list(tag_groups.keys())

        for i, group_name in enumerate(group_names):
            with col1 if i % 2 == 0 else col2:
                with st.expander(group_name, expanded=(i < 2)):
                    tags = tag_groups[group_name]
                    group_selected = st.multiselect(
                        f"{group_name} 태그",
                        options=tags,
                        default=[],
                        key=f"memo_tags_{i}",
                        label_visibility="collapsed"
                    )
                    selected_tags.extend(group_selected)

        # 추가 메모 (자유 입력)
        additional_memo = st.text_input(
            "추가 메모 (선택)",
            placeholder="기타 특이사항 입력",
            key="sim_additional_memo"
        )

        # 선택된 태그들을 strategy_memo로 조합
        strategy_memo = ", ".join(selected_tags)
        if additional_memo:
            strategy_memo = f"{strategy_memo}, {additional_memo}" if strategy_memo else additional_memo

        # 선택된 태그 미리보기
        if selected_tags:
            st.caption(f"선택됨: {', '.join(selected_tags)}")

        # 전략 유형이 "기타 (직접 입력)"인 경우 추가 입력
        if strategy_type == "기타 (직접 입력)":
            custom_strategy = st.text_input(
                "전략명 직접 입력",
                placeholder="사용한 전략명을 입력하세요",
                key="sim_custom_strategy"
            )
        else:
            custom_strategy = ""

        # 목표가/손절가 설정 (선택)
        with st.expander("📊 목표가/손절가 설정 (선택사항)"):
            col1, col2 = st.columns(2)
            with col1:
                target_price = st.number_input(
                    "목표가 (원)",
                    min_value=0,
                    value=int(buy_price * 1.05),
                    step=100,
                    key="sim_target_price"
                )
                if target_price > 0:
                    target_pct = ((target_price - buy_price) / buy_price) * 100
                    st.caption(f"예상 수익률: {target_pct:+.1f}%")

            with col2:
                stop_loss = st.number_input(
                    "손절가 (원)",
                    min_value=0,
                    value=int(buy_price * 0.95),
                    step=100,
                    key="sim_stop_loss"
                )
                if stop_loss > 0:
                    stop_pct = ((stop_loss - buy_price) / buy_price) * 100
                    st.caption(f"손절률: {stop_pct:.1f}%")

        # 등록 버튼
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 모의투자 등록", type="primary", use_container_width=True, key="sim_register"):
                holding_days = int(holding_period.replace("일", ""))

                # 전략 유형 결정
                final_strategy_type = strategy_type
                if strategy_type == "기타 (직접 입력)" and custom_strategy:
                    final_strategy_type = custom_strategy
                elif strategy_type.startswith("---"):
                    final_strategy_type = "선택 안함"

                # 모의투자 데이터 구성
                stock_data = {
                    'code': selected_code_only,
                    'name': selected_name,
                    'buy_price': buy_price,
                    'quantity': quantity,
                    'total_amount': total_amount,
                    'current_price': current_price,
                    'target_price': target_price if target_price > 0 else None,
                    'stop_loss': stop_loss if stop_loss > 0 else None,
                    'strategy_type': final_strategy_type,  # 전략 유형 추가
                    'strategy_memo': strategy_memo,
                    'investment_tags': selected_tags  # 투자 근거 태그 (통계용)
                }

                # 모의투자 등록
                simulation_id = _register_simulation_v2(
                    stock_data,
                    holding_days
                )

                st.success(f"✅ 모의투자 등록 완료!")
                st.info(f"📅 {holding_days}일 후 결과를 확인하세요. '모의투자 성과분석' 탭에서 진행 상황을 볼 수 있습니다.")

                # 초기화
                st.rerun()

    # 등록된 모의투자 목록 간단히 표시
    st.markdown("---")
    st.markdown("### 📋 최근 등록된 모의투자")

    history = _load_simulation_history()
    recent_pending = [h for h in history if h.get('status') == 'pending'][-5:]

    if recent_pending:
        for sim in recent_pending:
            stock = sim.get('stock', {})
            end_date = datetime.fromisoformat(sim['end_date'])
            days_left = max(0, (end_date - datetime.now()).days)

            st.markdown(f"""
            <div class='backtest-card' style='margin-bottom: 0.5rem; padding: 1rem;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <strong>{stock.get('name', 'N/A')}</strong> ({stock.get('code', '')})<br>
                        <span style='font-size: 0.85rem; color: #666;'>
                            매입가: {stock.get('buy_price', 0):,.0f}원 × {stock.get('quantity', 0)}주 = {stock.get('total_amount', 0):,.0f}원
                        </span>
                    </div>
                    <div style='text-align: right;'>
                        <span style='background: #ffc107; color: white; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem;'>
                            D-{days_left}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("등록된 모의투자가 없습니다.")


def _render_simulation_analysis():
    """모의투자 성과분석 섹션"""
    st.markdown("""
    <div class='settings-section'>
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <span style='font-size: 1.75rem;'>📈</span>
            <h3 style='margin: 0; color: #333;'>모의투자 성과분석</h3>
        </div>
        <p style='color: #666; margin: 0;'>등록된 모의투자의 결과를 추적하고 성공률을 분석합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = get_api_connection()

    # 기록 로드
    history = _load_simulation_history()

    if not history:
        st.info("📭 등록된 모의투자가 없습니다. '차트전략 모의투자' 탭에서 종목을 등록하세요.")
        return

    # 결과 업데이트 버튼 (상단에 배치)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 현재가 조회 및 결과 업데이트", type="primary", use_container_width=True, key="sim_update"):
            with st.spinner("현재가 조회 및 결과 업데이트 중..."):
                updated_count = _update_simulation_results_v2(api)
                st.success(f"✅ 업데이트 완료!")
                st.rerun()

    st.markdown("---")

    # 통계 계산
    stats = _calculate_stats_v2(history)

    # 전체 통계 카드
    st.markdown("### 📊 전체 성과 요약")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class='metric-card-top' style='--color: #667eea; --color-end: #764ba2'>
            <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>📋</p>
            <p style='color: white; font-size: 2rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1;'>{stats['total_count']}</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.95rem; margin: 0; position: relative; z-index: 1;'>총 모의투자</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class='metric-card-top' style='--color: #11998e; --color-end: #38ef7d'>
            <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>✅</p>
            <p style='color: white; font-size: 2rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1;'>{stats['completed_count']}</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.95rem; margin: 0; position: relative; z-index: 1;'>완료된 투자</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        win_rate = stats['win_rate']
        rate_color = "#11998e" if win_rate >= 50 else "#f5576c"
        st.markdown(f"""
        <div class='metric-card-top' style='--color: {rate_color}; --color-end: {"#38ef7d" if win_rate >= 50 else "#f093fb"}'>
            <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>🏆</p>
            <p style='color: white; font-size: 2rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1;'>{win_rate:.1f}%</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.95rem; margin: 0; position: relative; z-index: 1;'>승률</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        avg_return = stats['avg_return']
        return_color = "#11998e" if avg_return >= 0 else "#f5576c"
        st.markdown(f"""
        <div class='metric-card-top' style='--color: {return_color}; --color-end: {"#38ef7d" if avg_return >= 0 else "#f093fb"}'>
            <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>💰</p>
            <p style='color: white; font-size: 2rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1;'>{avg_return:+.2f}%</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.95rem; margin: 0; position: relative; z-index: 1;'>평균 수익률</p>
        </div>
        """, unsafe_allow_html=True)

    # 추가 통계
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class='metric-card-bottom'>
            <p style='font-size: 2rem; margin: 0;'>💵</p>
            <p style='color: #667eea; font-size: 1.3rem; font-weight: 700; margin: 0.25rem 0;'>{stats['total_invested']:,.0f}원</p>
            <p style='color: #888; font-size: 0.85rem; margin: 0;'>총 투자금액</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        profit_color = "#11998e" if stats['total_profit'] >= 0 else "#f5576c"
        st.markdown(f"""
        <div class='metric-card-bottom'>
            <p style='font-size: 2rem; margin: 0;'>📈</p>
            <p style='color: {profit_color}; font-size: 1.3rem; font-weight: 700; margin: 0.25rem 0;'>{stats['total_profit']:+,.0f}원</p>
            <p style='color: #888; font-size: 0.85rem; margin: 0;'>총 손익</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class='metric-card-bottom'>
            <p style='font-size: 2rem; margin: 0;'>⏳</p>
            <p style='color: #ffc107; font-size: 1.3rem; font-weight: 700; margin: 0.25rem 0;'>{stats['pending_count']}</p>
            <p style='color: #888; font-size: 0.85rem; margin: 0;'>진행중</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class='metric-card-bottom'>
            <p style='font-size: 2rem; margin: 0;'>🎯</p>
            <p style='color: #11998e; font-size: 1.3rem; font-weight: 700; margin: 0.25rem 0;'>{stats['win_count']}/{stats['completed_count']}</p>
            <p style='color: #888; font-size: 0.85rem; margin: 0;'>승리/완료</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 진행중/완료 모의투자 목록
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ⏳ 진행중인 모의투자")
        pending = [h for h in history if h.get('status') == 'pending']

        if pending:
            for idx, sim in enumerate(pending):
                stock = sim.get('stock', {})
                sim_id = sim.get('id', idx)
                end_date = datetime.fromisoformat(sim['end_date'])
                days_left = max(0, (end_date - datetime.now()).days)

                # 현재 평가손익 계산
                current_price = stock.get('current_price_now', stock.get('buy_price', 0))
                buy_price = stock.get('buy_price', 0)
                quantity = stock.get('quantity', 0)

                if buy_price > 0:
                    current_return = ((current_price - buy_price) / buy_price) * 100
                    current_profit = (current_price - buy_price) * quantity
                else:
                    current_return = 0
                    current_profit = 0

                return_color = "#11998e" if current_return >= 0 else "#f5576c"

                # 전략 유형 및 메모
                strategy_type = stock.get('strategy_type', '')
                strategy_memo = stock.get('strategy_memo', '')

                # Streamlit 네이티브 컴포넌트로 카드 표시
                with st.container(border=True):
                    info_col, stat_col, btn_col = st.columns([3, 2, 1])

                    with info_col:
                        st.markdown(f"**{stock.get('name', 'N/A')}** ({stock.get('code', '')})")
                        if strategy_type and strategy_type != "선택 안함":
                            st.caption(f"🏷️ {strategy_type}")
                        st.caption(f"매입: {buy_price:,.0f}원 × {quantity}주")
                        st.caption(f"현재: {current_price:,.0f}원")
                        if strategy_memo:
                            st.caption(f"📝 {strategy_memo[:30]}{'...' if len(strategy_memo) > 30 else ''}")

                    with stat_col:
                        # 검정 배경 스타일 수익률 표시
                        return_sign = "+" if current_return >= 0 else ""
                        profit_sign = "+" if current_profit >= 0 else ""
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                                    padding: 12px; border-radius: 8px; text-align: center;'>
                            <div style='color: #aaa; font-size: 0.8rem; margin-bottom: 4px;'>D-{days_left}</div>
                            <div style='color: {return_color}; font-size: 1.4rem; font-weight: bold;'>{return_sign}{current_return:.1f}%</div>
                            <div style='color: {return_color}; font-size: 0.9rem;'>{profit_sign}{current_profit:,.0f}원</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with btn_col:
                        # 추가매수 버튼
                        if st.button("➕", key=f"add_buy_pending_{sim_id}", help="추가 매수"):
                            st.session_state[f'show_add_buy_{sim_id}'] = True

                        # 매도(종료) 버튼
                        if st.button("💰", key=f"sell_pending_{sim_id}", help="매도(종료)"):
                            st.session_state[f'show_sell_{sim_id}'] = True

                # 추가 매수 폼
                if st.session_state.get(f'show_add_buy_{sim_id}', False):
                    with st.expander(f"➕ {stock.get('name', '')} 추가 매수", expanded=True):
                        add_col1, add_col2 = st.columns(2)
                        with add_col1:
                            add_price = st.number_input(
                                "추가 매수가 (원)",
                                min_value=100,
                                value=int(current_price) if current_price > 0 else int(buy_price),
                                step=100,
                                key=f"add_price_{sim_id}"
                            )
                        with add_col2:
                            add_qty = st.number_input(
                                "추가 수량 (주)",
                                min_value=1,
                                value=quantity,
                                step=1,
                                key=f"add_qty_{sim_id}"
                            )

                        add_btn_col1, add_btn_col2 = st.columns(2)
                        with add_btn_col1:
                            if st.button("✅ 추가 매수 확인", key=f"confirm_add_{sim_id}", type="primary"):
                                _add_buy_to_simulation(sim_id, add_price, add_qty)
                                st.session_state[f'show_add_buy_{sim_id}'] = False
                                st.rerun()
                        with add_btn_col2:
                            if st.button("❌ 취소", key=f"cancel_add_{sim_id}"):
                                st.session_state[f'show_add_buy_{sim_id}'] = False
                                st.rerun()

                # 매도(종료) 폼
                if st.session_state.get(f'show_sell_{sim_id}', False):
                    with st.expander(f"💰 {stock.get('name', '')} 매도(종료)", expanded=True):
                        sell_col1, sell_col2 = st.columns(2)
                        with sell_col1:
                            sell_price = st.number_input(
                                "매도가 (원)",
                                min_value=100,
                                value=int(current_price) if current_price > 0 else int(buy_price),
                                step=100,
                                key=f"sell_price_{sim_id}"
                            )
                        with sell_col2:
                            # 매도 시 예상 수익률 표시 (buy_price = 평균단가)
                            expected_return = ((sell_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
                            expected_profit = (sell_price - buy_price) * quantity
                            exp_color = "#11998e" if expected_return >= 0 else "#f5576c"
                            exp_sign = "+" if expected_return >= 0 else ""
                            st.markdown(f"""
                            <div style='padding: 8px; background: rgba(0,0,0,0.1); border-radius: 8px; margin-top: 28px;'>
                                <span style='color: {exp_color}; font-weight: bold;'>
                                    예상 수익: {exp_sign}{expected_return:.1f}% ({exp_sign}{expected_profit:,.0f}원)
                                </span>
                            </div>
                            """, unsafe_allow_html=True)

                        sell_btn_col1, sell_btn_col2 = st.columns(2)
                        with sell_btn_col1:
                            if st.button("✅ 매도 확정", key=f"confirm_sell_{sim_id}", type="primary"):
                                _complete_simulation(sim_id, sell_price)
                                st.session_state[f'show_sell_{sim_id}'] = False
                                st.rerun()
                        with sell_btn_col2:
                            if st.button("❌ 취소", key=f"cancel_sell_{sim_id}"):
                                st.session_state[f'show_sell_{sim_id}'] = False
                                st.rerun()

                st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)
        else:
            st.info("진행중인 모의투자가 없습니다.")

    with col2:
        st.markdown("### ✅ 완료된 모의투자")
        completed = [h for h in history if h.get('status') == 'completed']

        if completed:
            for idx, sim in enumerate(completed[-10:]):
                stock = sim.get('stock', {})
                sim_id = sim.get('id', f"completed_{idx}")
                result_return = sim.get('result_return', 0)
                result_profit = sim.get('result_profit', 0)
                result_icon = "🟢" if result_return >= 0 else "🔴"
                # 전략 유형: stock 내부 또는 sim 상위에서 가져오기
                strategy_type = stock.get('strategy_type', '') or sim.get('strategy', '')
                strategy_memo_orig = stock.get('strategy_memo', '')
                memo = sim.get('memo', '')

                # Streamlit 네이티브 컴포넌트로 카드 표시
                with st.container(border=True):
                    info_col, stat_col, btn_col = st.columns([3, 2, 1])

                    with info_col:
                        st.markdown(f"**{stock.get('name', 'N/A')}** ({stock.get('code', '')})")
                        if strategy_type and strategy_type != "선택 안함":
                            st.caption(f"🏷️ {strategy_type}")
                        st.caption(f"매입: {stock.get('buy_price', 0):,.0f}원 → 매도: {sim.get('exit_price', 0):,.0f}원")
                        if strategy_memo_orig:
                            st.caption(f"💡 {strategy_memo_orig[:25]}{'...' if len(strategy_memo_orig) > 25 else ''}")
                        if memo:
                            st.caption(f"📝 {memo[:30]}{'...' if len(memo) > 30 else ''}")

                    with stat_col:
                        # 검정 배경 스타일 수익률 표시
                        return_color = "#11998e" if result_return >= 0 else "#f5576c"
                        return_sign = "+" if result_return >= 0 else ""
                        profit_sign = "+" if result_profit >= 0 else ""
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                                    padding: 12px; border-radius: 8px; text-align: center;'>
                            <div style='color: #aaa; font-size: 0.8rem; margin-bottom: 4px;'>{result_icon} 수익률</div>
                            <div style='color: {return_color}; font-size: 1.4rem; font-weight: bold;'>{return_sign}{result_return:.1f}%</div>
                            <div style='color: {return_color}; font-size: 0.9rem;'>{profit_sign}{result_profit:,.0f}원</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with btn_col:
                        # 메모 버튼
                        if st.button("📝", key=f"memo_completed_{sim_id}", help="메모"):
                            st.session_state[f'show_memo_{sim_id}'] = not st.session_state.get(f'show_memo_{sim_id}', False)
                        # 삭제 버튼
                        if st.button("🗑️", key=f"del_completed_{sim_id}", help="삭제"):
                            st.session_state[f'confirm_delete_comp_{sim_id}'] = True

                # 메모 입력
                if st.session_state.get(f'show_memo_{sim_id}', False):
                    with st.container():
                        memo_text = st.text_area(
                            "메모 입력",
                            value=memo,
                            key=f"memo_input_{sim_id}",
                            height=80,
                            placeholder="매매 근거, 느낀점, 개선사항 등..."
                        )
                        memo_col1, memo_col2 = st.columns(2)
                        with memo_col1:
                            if st.button("💾 저장", key=f"save_memo_{sim_id}"):
                                if _update_simulation_memo(sim_id, memo_text):
                                    st.success("메모 저장 완료!")
                                    st.session_state[f'show_memo_{sim_id}'] = False
                                    st.rerun()
                        with memo_col2:
                            if st.button("❌ 취소", key=f"cancel_memo_{sim_id}"):
                                st.session_state[f'show_memo_{sim_id}'] = False
                                st.rerun()

                # 삭제 확인
                if st.session_state.get(f'confirm_delete_comp_{sim_id}', False):
                    st.warning(f"⚠️ '{stock.get('name', '')}' 결과를 삭제하시겠습니까?")
                    del_col1, del_col2 = st.columns(2)
                    with del_col1:
                        if st.button("✅ 삭제", key=f"confirm_del_comp_{sim_id}", type="primary"):
                            _delete_simulation(sim_id)
                            st.session_state[f'confirm_delete_comp_{sim_id}'] = False
                            st.rerun()
                    with del_col2:
                        if st.button("❌ 취소", key=f"cancel_del_comp_{sim_id}"):
                            st.session_state[f'confirm_delete_comp_{sim_id}'] = False
                            st.rerun()
        else:
            st.info("완료된 모의투자가 없습니다.")

    # 상세 내역 테이블
    st.markdown("---")
    st.markdown("### 📋 전체 모의투자 내역")

    # 시총·상장주식수 + 섹터 일괄 조회
    try:
        from data.market_data_cache import (
            get_market_cap_dict, format_market_cap, format_shares,
            get_sector_cached,
        )
        cap_table = get_market_cap_dict("ALL")
    except Exception:
        cap_table = {}
        format_market_cap = lambda x: '-'
        format_shares = lambda x: '-'
        get_sector_cached = lambda x: '기타'

    # 데이터프레임 생성
    table_data = []
    for sim in history:
        stock = sim.get('stock', {})
        status = "진행중" if sim.get('status') == 'pending' else "완료"
        code_str = str(stock.get('code', ''))
        cap_info = cap_table.get(code_str, {})
        try:
            sector_str = get_sector_cached(code_str)
        except Exception:
            sector_str = '기타'

        table_data.append({
            '종목명': stock.get('name', 'N/A'),
            '종목코드': stock.get('code', ''),
            '섹터': sector_str,
            '시가총액': format_market_cap(int(cap_info.get('market_cap', 0))),
            '상장주식수': format_shares(int(cap_info.get('shares', 0))),
            '매입가': stock.get('buy_price', 0),
            '수량': stock.get('quantity', 0),
            '투자금액': stock.get('total_amount', 0),
            '상태': status,
            '수익률(%)': sim.get('result_return', 0) if sim.get('status') == 'completed' else '-',
            '손익': sim.get('result_profit', 0) if sim.get('status') == 'completed' else '-',
            '등록일': sim.get('start_date', '')[:10],
            '만료일': sim.get('end_date', '')[:10]
        })

    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # 전략별 수익 확률 분석
    _render_strategy_analysis(history)


def _render_strategy_analysis(history: list):
    """전략별 수익 확률 분석 렌더링"""
    completed = [h for h in history if h.get('status') == 'completed']

    if not completed:
        return

    st.markdown("---")
    st.markdown("### 📊 전략별 수익 확률 분석")

    # 전략별 통계 집계
    strategy_stats = {}
    for sim in completed:
        stock = sim.get('stock', {})
        # 전략 유형: stock 내부 또는 sim 상위에서 가져오기
        strategy = stock.get('strategy_type', '') or sim.get('strategy', '') or '기타'
        # 선택 안함이나 구분자는 '기타'로 처리
        if not strategy or strategy == "선택 안함" or strategy.startswith("---"):
            strategy = '기타'

        if strategy not in strategy_stats:
            strategy_stats[strategy] = {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'returns': [],
                'profits': []
            }

        strategy_stats[strategy]['total'] += 1
        result_return = sim.get('result_return', 0)
        result_profit = sim.get('result_profit', 0)
        strategy_stats[strategy]['returns'].append(result_return)
        strategy_stats[strategy]['profits'].append(result_profit)

        if result_return > 0:
            strategy_stats[strategy]['wins'] += 1
        else:
            strategy_stats[strategy]['losses'] += 1

    # 전략별 카드 표시
    cols = st.columns(min(len(strategy_stats), 4))

    for idx, (strategy, stats) in enumerate(strategy_stats.items()):
        col_idx = idx % 4
        total = stats['total']
        wins = stats['wins']
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_return = np.mean(stats['returns']) if stats['returns'] else 0
        total_profit = sum(stats['profits'])
        max_return = max(stats['returns']) if stats['returns'] else 0
        min_return = min(stats['returns']) if stats['returns'] else 0

        # 색상 결정
        if win_rate >= 70:
            rate_color = "#11998e"  # 녹색
            grade = "A"
        elif win_rate >= 50:
            rate_color = "#FFA500"  # 주황
            grade = "B"
        else:
            rate_color = "#f5576c"  # 빨강
            grade = "C"

        with cols[col_idx]:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                        padding: 1rem; border-radius: 12px; margin-bottom: 1rem;
                        border: 1px solid #667eea30;'>
                <div style='font-weight: bold; font-size: 1rem; margin-bottom: 0.5rem;'>
                    🎯 {strategy}
                </div>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                    <span>승률</span>
                    <span style='color: {rate_color}; font-weight: bold; font-size: 1.3rem;'>
                        {win_rate:.1f}% ({grade})
                    </span>
                </div>
                <div style='font-size: 0.85rem; color: #666;'>
                    📈 총 {total}건 (승리 {wins} / 패배 {stats['losses']})<br>
                    💰 평균 수익률: <span style='color: {"#11998e" if avg_return >= 0 else "#f5576c"};'>{avg_return:+.2f}%</span><br>
                    📊 최고: {max_return:+.1f}% / 최저: {min_return:+.1f}%<br>
                    💵 총 손익: <span style='color: {"#11998e" if total_profit >= 0 else "#f5576c"};'>{total_profit:+,.0f}원</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 종합 요약
    if len(completed) >= 3:
        st.markdown("#### 📋 종합 분석")

        total_wins = sum(s['wins'] for s in strategy_stats.values())
        total_trades = sum(s['total'] for s in strategy_stats.values())
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        all_returns = [r for s in strategy_stats.values() for r in s['returns']]
        overall_avg_return = np.mean(all_returns) if all_returns else 0

        # 가장 성공적인 전략 찾기
        best_strategy = max(strategy_stats.items(), key=lambda x: (x[1]['wins'] / x[1]['total'] * 100) if x[1]['total'] > 0 else 0)
        best_win_rate = (best_strategy[1]['wins'] / best_strategy[1]['total'] * 100) if best_strategy[1]['total'] > 0 else 0

        summary_col1, summary_col2, summary_col3 = st.columns(3)

        with summary_col1:
            st.metric("전체 승률", f"{overall_win_rate:.1f}%", f"{total_wins}/{total_trades} 승")

        with summary_col2:
            st.metric("평균 수익률", f"{overall_avg_return:+.2f}%")

        with summary_col3:
            st.metric("최고 전략", best_strategy[0], f"승률 {best_win_rate:.1f}%")

        # 추천 메시지
        if overall_win_rate >= 60:
            st.success(f"🎉 전체 승률 {overall_win_rate:.1f}%로 우수한 성과입니다! '{best_strategy[0]}' 전략이 가장 효과적입니다.")
        elif overall_win_rate >= 40:
            st.info(f"📈 승률 개선이 필요합니다. '{best_strategy[0]}' 전략에 집중해 보세요.")
        else:
            st.warning(f"⚠️ 전략 재검토가 필요합니다. 손절 기준과 진입 타이밍을 점검해 보세요.")


# _get_api_connection 함수는 dashboard/utils/api_helper.py로 통합됨
# 아래 호출부에서 get_api_connection() 사용


def _get_all_stocks_for_selection(market: str = "전체") -> list:
    """드롭다운용 전체 종목 리스트 (code, name, market) 형태로 반환"""
    try:
        from data.stock_list import get_kospi_stocks, get_kosdaq_stocks

        stocks = []

        # KOSPI 종목
        if market in ["전체", "KOSPI"]:
            kospi = get_kospi_stocks()
            for code, name in kospi:  # 전체 종목
                stocks.append((code, name, "KOSPI"))

        # KOSDAQ 종목
        if market in ["전체", "KOSDAQ"]:
            kosdaq = get_kosdaq_stocks()
            for code, name in kosdaq:  # 전체 종목
                stocks.append((code, name, "KOSDAQ"))

        return stocks
    except Exception as e:
        # 기본 종목
        return [
            ('005930', '삼성전자', 'KOSPI'),
            ('000660', 'SK하이닉스', 'KOSPI'),
            ('373220', 'LG에너지솔루션', 'KOSPI'),
            ('207940', '삼성바이오로직스', 'KOSPI'),
            ('005380', '현대자동차', 'KOSPI'),
            ('000270', '기아', 'KOSPI'),
            ('068270', '셀트리온', 'KOSPI'),
            ('035420', 'NAVER', 'KOSPI'),
            ('006400', '삼성SDI', 'KOSPI'),
            ('051910', 'LG화학', 'KOSPI'),
            ('247540', '에코프로비엠', 'KOSDAQ'),
            ('086520', '에코프로', 'KOSDAQ'),
            ('091990', '셀트리온헬스케어', 'KOSDAQ'),
            ('263750', '펄어비스', 'KOSDAQ'),
            ('352820', '하이브', 'KOSDAQ'),
        ]


def _search_stocks(keyword: str, market: str) -> list:
    """종목 검색"""
    try:
        from data.stock_list import get_kospi_stocks, get_kosdaq_stocks

        if market == "KOSPI":
            stocks = get_kospi_stocks()
        elif market == "KOSDAQ":
            stocks = get_kosdaq_stocks()
        else:
            stocks = get_kospi_stocks() + get_kosdaq_stocks()

        # 키워드로 필터링
        keyword = keyword.strip().upper()
        results = []

        for code, name in stocks:
            if keyword in name.upper() or keyword in code:
                results.append({'code': code, 'name': name})
                if len(results) >= 20:
                    break

        return results
    except Exception as e:
        # 기본 종목 반환
        return [
            {'code': '005930', 'name': '삼성전자'},
            {'code': '000660', 'name': 'SK하이닉스'},
            {'code': '035420', 'name': 'NAVER'},
        ]


def _get_stock_current_price(api, code: str) -> float:
    """종목 현재가 조회"""
    if api:
        try:
            price_info = api.get_stock_price(code)
            return float(price_info.get('stck_prpr', 0))
        except:
            pass

    # 샘플 가격 반환
    sample_prices = {
        '005930': 71000,
        '000660': 185000,
        '035420': 195000,
        '005380': 245000,
        '051910': 380000,
    }
    return sample_prices.get(code, 50000)


def _get_stock_price_with_history(api, code: str, days: int = 60):
    """종목 현재가 및 과거 주가 데이터 조회"""
    current_price = 0
    price_data = None
    api_connected = False

    if api:
        try:
            # 현재가 조회
            price_info = api.get_stock_price(code)
            current_price = float(price_info.get('stck_prpr', 0))

            if current_price > 0:
                api_connected = True

            # 과거 주가 데이터 조회 (get_daily_price 사용)
            try:
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
                hist_data = api.get_daily_price(code, start_date=start_date, end_date=end_date)

                if hist_data is not None and len(hist_data) > 0:
                    # API가 이미 정규화된 컬럼(date, open, high, low, close, volume)을 반환
                    # 숫자형 변환
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        if col in hist_data.columns:
                            hist_data[col] = pd.to_numeric(hist_data[col], errors='coerce')
                    # 날짜 변환 및 정렬
                    if 'date' in hist_data.columns:
                        hist_data['date'] = pd.to_datetime(hist_data['date'])
                        hist_data = hist_data.sort_values('date').reset_index(drop=True)
                    price_data = hist_data
            except Exception as e:
                pass
        except:
            pass

    # API 실패 시 샘플 데이터 생성
    if current_price == 0:
        sample_prices = {
            '005930': 71000,
            '000660': 185000,
            '035420': 195000,
            '005380': 245000,
            '051910': 380000,
        }
        current_price = sample_prices.get(code, 50000)

    # 차트 데이터가 없으면 샘플 생성
    if price_data is None:
        price_data = _generate_sample_price_data(current_price, days)

    return current_price, price_data, api_connected


def _generate_sample_price_data(current_price: float, days: int = 60) -> pd.DataFrame:
    """샘플 주가 데이터 생성 (차트 표시용)"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    np.random.seed(42)

    # 랜덤 워크로 가격 생성 (현재가 기준 역산)
    returns = np.random.normal(0.001, 0.02, days)
    prices = [current_price]

    for i in range(days - 1, 0, -1):
        prev_price = prices[0] / (1 + returns[i])
        prices.insert(0, prev_price)

    prices = np.array(prices)

    # OHLC 데이터 생성
    data = {
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, days)),
        'low': prices * (1 - np.random.uniform(0, 0.03, days)),
        'close': prices,
        'volume': np.random.randint(100000, 10000000, days)
    }

    df = pd.DataFrame(data)

    # high >= close, open 보장, low <= close, open 보장
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


def _register_simulation_v2(stock_data: dict, holding_days: int) -> str:
    """모의투자 등록 (v2 - 단일 종목)"""
    import uuid

    simulation_id = str(uuid.uuid4())[:8]
    start_date = datetime.now()
    end_date = start_date + timedelta(days=holding_days)

    record = {
        'id': simulation_id,
        'stock': stock_data,
        'holding_days': holding_days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'status': 'pending',
        'result_return': None,
        'result_profit': None,
        'exit_price': None
    }

    # 기존 기록 로드
    history = _load_simulation_history()
    history.append(record)

    # 저장
    _save_simulation_history(history)

    return simulation_id


def _update_simulation_results_v2(api) -> int:
    """모의투자 결과 업데이트 (v2)"""
    history = _load_simulation_history()
    updated_count = 0
    now = datetime.now()

    for record in history:
        stock = record.get('stock', {})
        code = stock.get('code', '')

        if not code:
            continue

        # 현재가 조회
        current_price = _get_stock_current_price(api, code)

        if record.get('status') == 'pending':
            # 현재가 업데이트
            stock['current_price_now'] = current_price
            record['stock'] = stock

            # 만료 확인
            end_date = datetime.fromisoformat(record['end_date'])

            if now >= end_date:
                # 결과 계산
                buy_price = stock.get('buy_price', 0)
                quantity = stock.get('quantity', 0)

                if buy_price > 0:
                    result_return = ((current_price - buy_price) / buy_price) * 100
                    result_profit = (current_price - buy_price) * quantity
                else:
                    result_return = 0
                    result_profit = 0

                record['status'] = 'completed'
                record['result_return'] = result_return
                record['result_profit'] = result_profit
                record['exit_price'] = current_price

            updated_count += 1

    _save_simulation_history(history)
    return updated_count


def _calculate_stats_v2(history: list) -> dict:
    """통계 계산 (v2)"""
    stats = {
        'total_count': len(history),
        'pending_count': 0,
        'completed_count': 0,
        'win_count': 0,
        'win_rate': 0,
        'avg_return': 0,
        'total_invested': 0,
        'total_profit': 0
    }

    returns = []

    for record in history:
        stock = record.get('stock', {})
        total_amount = stock.get('total_amount', 0)
        stats['total_invested'] += total_amount

        if record.get('status') == 'pending':
            stats['pending_count'] += 1
        elif record.get('status') == 'completed':
            stats['completed_count'] += 1

            result_return = record.get('result_return', 0)
            result_profit = record.get('result_profit', 0)

            returns.append(result_return)
            stats['total_profit'] += result_profit

            if result_return > 0:
                stats['win_count'] += 1

    if stats['completed_count'] > 0:
        stats['win_rate'] = (stats['win_count'] / stats['completed_count']) * 100
        stats['avg_return'] = np.mean(returns) if returns else 0

    return stats


def _find_strategy_candidates(api, strategy_type: str, market: str) -> list:
    """전략별 후보 종목 검색"""
    if api is None:
        # API 없으면 샘플 데이터 반환
        return _get_sample_candidates(strategy_type)

    try:
        # 실제 API 연결시 chart_strategy의 함수 호출
        from dashboard.views.chart_strategy import (
            _get_market_stocks, _get_stock_data
        )
        import numpy as np

        stocks = _get_market_stocks(market)[:100]
        results = []

        for code, name in stocks[:50]:
            try:
                data = _get_stock_data(api, code, 60)
                if data is None or len(data) < 30:
                    continue

                current = data['close'].iloc[-1]
                change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100
                recent_high = data['high'].iloc[-20:].max()
                recent_low = data['low'].iloc[-20:].min()

                # 간단한 조건 체크 (실제로는 각 전략별 상세 로직 적용)
                ma5 = data['close'].rolling(5).mean().iloc[-1]
                ma20 = data['close'].rolling(20).mean().iloc[-1]

                if not np.isnan(ma5) and not np.isnan(ma20):
                    if ma5 > ma20:  # 간단한 상승 추세 조건
                        entry = current
                        stop = recent_low * 0.97
                        target = recent_high * 1.05

                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': strategy_type,
                                'reason': f'MA5 > MA20 상승추세',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })

                if len(results) >= 15:
                    break
            except:
                continue

        return results if results else _get_sample_candidates(strategy_type)
    except:
        return _get_sample_candidates(strategy_type)


def _get_sample_candidates(strategy_type: str) -> list:
    """샘플 후보 종목 데이터"""
    samples = [
        {'code': '005930', 'name': '삼성전자', 'signal': strategy_type, 'reason': '패턴 감지',
         'change_rate': 1.5, 'current_price': 71000, 'entry_price': 71000,
         'stop_loss': 68000, 'target_price': 78000},
        {'code': '000660', 'name': 'SK하이닉스', 'signal': strategy_type, 'reason': '패턴 감지',
         'change_rate': 2.1, 'current_price': 185000, 'entry_price': 185000,
         'stop_loss': 175000, 'target_price': 205000},
        {'code': '035420', 'name': 'NAVER', 'signal': strategy_type, 'reason': '패턴 감지',
         'change_rate': -0.5, 'current_price': 195000, 'entry_price': 195000,
         'stop_loss': 185000, 'target_price': 215000},
        {'code': '005380', 'name': '현대차', 'signal': strategy_type, 'reason': '패턴 감지',
         'change_rate': 0.8, 'current_price': 245000, 'entry_price': 245000,
         'stop_loss': 235000, 'target_price': 270000},
        {'code': '051910', 'name': 'LG화학', 'signal': strategy_type, 'reason': '패턴 감지',
         'change_rate': 1.2, 'current_price': 380000, 'entry_price': 380000,
         'stop_loss': 360000, 'target_price': 420000},
    ]
    return samples


def _register_simulation(strategy: str, stocks: list, amount: int, holding_days: int) -> str:
    """모의투자 등록"""
    import uuid

    simulation_id = str(uuid.uuid4())[:8]
    start_date = datetime.now()
    end_date = start_date + timedelta(days=holding_days)

    record = {
        'id': simulation_id,
        'strategy': strategy,
        'stocks': stocks,
        'amount_per_stock': amount,
        'holding_days': holding_days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'status': 'pending',
        'result_return': None,
        'result_details': None
    }

    # 기존 기록 로드
    history = _load_simulation_history()
    history.append(record)

    # 저장
    _save_simulation_history(history)

    return simulation_id


def _load_simulation_history() -> list:
    """모의투자 기록 로드"""
    try:
        if os.path.exists(SIMULATION_HISTORY_FILE):
            with open(SIMULATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []


def _save_simulation_history(history: list):
    """모의투자 기록 저장"""
    try:
        os.makedirs(os.path.dirname(SIMULATION_HISTORY_FILE), exist_ok=True)
        with open(SIMULATION_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"저장 실패: {e}")


def _delete_simulation(sim_id):
    """모의투자 기록 삭제"""
    history = _load_simulation_history()
    original_len = len(history)

    # id로 찾아서 삭제
    history = [h for h in history if h.get('id') != sim_id]

    # id가 없는 경우 인덱스로 시도
    if len(history) == original_len and isinstance(sim_id, int):
        if 0 <= sim_id < len(history):
            history.pop(sim_id)

    _save_simulation_history(history)
    st.success("✅ 모의투자가 삭제되었습니다.")


def _complete_simulation(sim_id, sell_price: float):
    """모의투자 매도(종료) 처리"""
    history = _load_simulation_history()

    for record in history:
        if record.get('id') == sim_id or (isinstance(sim_id, int) and history.index(record) == sim_id):
            if record.get('status') == 'pending':
                stock = record.get('stock', {})

                # 매입 정보
                buy_price = stock.get('buy_price', 0)
                quantity = stock.get('quantity', 0)

                # 수익률/손익 계산
                if buy_price > 0 and quantity > 0:
                    result_return = ((sell_price - buy_price) / buy_price) * 100
                    result_profit = (sell_price - buy_price) * quantity
                else:
                    result_return = 0
                    result_profit = 0

                # 상태 업데이트
                record['status'] = 'completed'
                record['result_return'] = result_return
                record['result_profit'] = result_profit
                record['exit_price'] = sell_price
                record['exit_date'] = datetime.now().isoformat()

                _save_simulation_history(history)

                # 결과 메시지
                result_sign = "+" if result_return >= 0 else ""
                profit_sign = "+" if result_profit >= 0 else ""
                result_emoji = "🎉" if result_return >= 0 else "😢"
                st.success(f"{result_emoji} 매도 완료! 수익률: {result_sign}{result_return:.1f}% ({profit_sign}{result_profit:,.0f}원)")
                return

    st.error("모의투자를 찾을 수 없습니다.")


def _add_buy_to_simulation(sim_id, add_price: int, add_qty: int):
    """모의투자에 추가 매수"""
    history = _load_simulation_history()

    for record in history:
        if record.get('id') == sim_id or (isinstance(sim_id, int) and history.index(record) == sim_id):
            if record.get('status') == 'pending':
                stock = record.get('stock', {})

                # 기존 매입 정보
                old_price = stock.get('buy_price', 0)
                old_qty = stock.get('quantity', 0)
                old_total = old_price * old_qty

                # 추가 매입 정보
                add_total = add_price * add_qty

                # 평균 단가 계산 (물타기)
                new_total_qty = old_qty + add_qty
                new_avg_price = (old_total + add_total) / new_total_qty if new_total_qty > 0 else old_price

                # 업데이트
                stock['buy_price'] = new_avg_price
                stock['quantity'] = new_total_qty
                stock['total_amount'] = new_avg_price * new_total_qty

                # 추가 매수 이력 저장
                if 'add_buys' not in record:
                    record['add_buys'] = []
                record['add_buys'].append({
                    'date': datetime.now().isoformat(),
                    'price': add_price,
                    'quantity': add_qty,
                    'total': add_total
                })

                record['stock'] = stock
                break

    _save_simulation_history(history)
    st.success(f"✅ 추가 매수 완료! (평균단가: {new_avg_price:,.0f}원, 총 {new_total_qty}주)")


def _update_simulation_results(api) -> int:
    """만료된 모의투자 결과 업데이트"""
    history = _load_simulation_history()
    updated_count = 0
    now = datetime.now()

    for record in history:
        if record.get('status') == 'pending':
            end_date = datetime.fromisoformat(record['end_date'])

            if now >= end_date:
                # 결과 계산
                total_return = 0
                details = []

                for stock in record['stocks']:
                    # 실제 현재가 조회 (또는 시뮬레이션)
                    if api:
                        try:
                            current_price = _get_current_price(api, stock['code'])
                        except:
                            current_price = stock['entry_price'] * (1 + np.random.uniform(-0.1, 0.15))
                    else:
                        # 시뮬레이션: 랜덤 수익률
                        current_price = stock['entry_price'] * (1 + np.random.uniform(-0.1, 0.15))

                    stock_return = (current_price - stock['entry_price']) / stock['entry_price'] * 100
                    total_return += stock_return

                    details.append({
                        'code': stock['code'],
                        'name': stock['name'],
                        'entry_price': stock['entry_price'],
                        'exit_price': current_price,
                        'return': stock_return
                    })

                avg_return = total_return / len(record['stocks']) if record['stocks'] else 0

                record['status'] = 'completed'
                record['result_return'] = avg_return
                record['result_details'] = details
                updated_count += 1

    if updated_count > 0:
        _save_simulation_history(history)

    return updated_count


def _get_current_price(api, code: str) -> float:
    """현재가 조회"""
    try:
        price_info = api.get_stock_price(code)
        return float(price_info.get('stck_prpr', 0))
    except:
        return 0


def _update_simulation_memo(sim_id, memo: str):
    """모의투자 메모 업데이트"""
    history = _load_simulation_history()

    for record in history:
        if record.get('id') == sim_id:
            record['memo'] = memo
            _save_simulation_history(history)
            return True

    return False


def _calculate_strategy_stats(history: list, api) -> dict:
    """전략별 통계 계산"""
    stats = {
        'total_trades': len(history),
        'completed_trades': 0,
        'win_count': 0,
        'total_return': 0,
        'strategy_stats': {}
    }

    strategy_data = {}

    for record in history:
        strategy = record['strategy']

        if strategy not in strategy_data:
            strategy_data[strategy] = {
                'total': 0,
                'completed': 0,
                'wins': 0,
                'returns': []
            }

        strategy_data[strategy]['total'] += 1

        if record.get('status') == 'completed':
            stats['completed_trades'] += 1
            strategy_data[strategy]['completed'] += 1

            result_return = record.get('result_return', 0)
            stats['total_return'] += result_return
            strategy_data[strategy]['returns'].append(result_return)

            if result_return > 0:
                stats['win_count'] += 1
                strategy_data[strategy]['wins'] += 1

    # 전략별 통계 정리
    for strategy, data in strategy_data.items():
        win_rate = (data['wins'] / data['completed'] * 100) if data['completed'] > 0 else 0
        avg_return = np.mean(data['returns']) if data['returns'] else 0

        stats['strategy_stats'][strategy] = {
            '총 투자': data['total'],
            '완료': data['completed'],
            '승리': data['wins'],
            '승률(%)': win_rate,
            '평균수익률(%)': avg_return
        }

    # 전체 평균 수익률
    if stats['completed_trades'] > 0:
        stats['total_return'] = stats['total_return'] / stats['completed_trades']

    return stats
