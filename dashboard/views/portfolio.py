"""
포트폴리오 현황 페이지
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px


def render_portfolio():
    """포트폴리오 현황 페이지 렌더링"""

    # 페이지 전용 CSS
    st.markdown("""
    <style>
        @keyframes slideLeft {
            from { opacity: 0; transform: translateX(-30px); }
            to { opacity: 1; transform: translateX(0); }
        }

        @keyframes slideRight {
            from { opacity: 0; transform: translateX(30px); }
            to { opacity: 1; transform: translateX(0); }
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }

        @keyframes shimmer {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }

        @keyframes glow {
            0%, 100% { box-shadow: 0 0 5px rgba(79, 172, 254, 0.3); }
            50% { box-shadow: 0 0 20px rgba(79, 172, 254, 0.6); }
        }

        .hero-portfolio {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 50%, #667eea 100%);
            background-size: 200% 200%;
            animation: gradientBG 8s ease infinite;
            padding: 2.5rem;
            border-radius: 24px;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }

        .hero-portfolio::before {
            content: '';
            position: absolute;
            top: 0;
            left: -200%;
            width: 200%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s infinite;
        }

        .summary-card {
            background: linear-gradient(135deg, var(--color) 0%, var(--color-end) 100%);
            padding: 1.75rem;
            border-radius: 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            animation: slideLeft 0.5s ease-out;
        }

        .summary-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }

        .portfolio-card {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.08);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 2px solid transparent;
        }

        .portfolio-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 50px rgba(79, 172, 254, 0.2);
            border-color: #4facfe;
        }

        .holding-item {
            background: white;
            border-radius: 16px;
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            border-left: 4px solid transparent;
        }

        .holding-item:hover {
            transform: translateX(5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            border-left-color: #4facfe;
        }

        .pnl-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem 1rem;
            border-radius: 12px;
            font-weight: 700;
            animation: bounce 2s ease-in-out infinite;
        }

        .trade-item {
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }

        .trade-item:hover {
            background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%);
            transform: scale(1.01);
        }

        .action-badge {
            display: inline-block;
            padding: 0.4rem 1rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.85rem;
        }

        .rebalance-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 20px;
            padding: 1.5rem;
            border: 2px dashed #dee2e6;
            transition: all 0.3s ease;
        }

        .rebalance-card:hover {
            border-color: #4facfe;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        }
    </style>
    """, unsafe_allow_html=True)

    # 히어로 헤더
    st.markdown("""
    <div class='hero-portfolio'>
        <div style='position: relative; z-index: 1;'>
            <div style='font-size: 4rem; margin-bottom: 0.5rem; animation: float 3s ease-in-out infinite;'>💼</div>
            <h1 style='color: white; font-size: 2.5rem; margin: 0 0 0.5rem 0; font-weight: 800; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>포트폴리오 현황</h1>
            <p style='color: rgba(255,255,255,0.95); font-size: 1.1rem; margin: 0;'>현재 포트폴리오 상태와 성과를 실시간으로 확인합니다</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 샘플 포트폴리오 데이터
    portfolio = _get_sample_portfolio()

    # 요약 카드
    col1, col2, col3, col4 = st.columns(4)

    summary_cards = [
        {"label": "총 자산", "value": f"{portfolio['total_value']:,.0f}원",
         "delta": f"{portfolio['total_return']:.1%}", "icon": "💰",
         "color": "#667eea", "color_end": "#764ba2"},
        {"label": "투자 원금", "value": f"{portfolio['initial_capital']:,.0f}원",
         "delta": None, "icon": "💵", "color": "#11998e", "color_end": "#38ef7d"},
        {"label": "평가 손익", "value": f"{portfolio['total_pnl']:+,.0f}원",
         "delta": f"{portfolio['total_pnl_pct']:.1%}", "icon": "📈" if portfolio['total_pnl'] >= 0 else "📉",
         "color": "#38ef7d" if portfolio['total_pnl'] >= 0 else "#f5576c",
         "color_end": "#11998e" if portfolio['total_pnl'] >= 0 else "#f093fb"},
        {"label": "보유 종목", "value": f"{portfolio['num_positions']}개",
         "delta": None, "icon": "📊", "color": "#4facfe", "color_end": "#00f2fe"},
    ]

    for col, card in zip([col1, col2, col3, col4], summary_cards):
        with col:
            delta_html = ""
            if card['delta']:
                delta_color = "#38ef7d" if '+' in str(card['delta']) or (card['delta'] and float(card['delta'].replace('%', '')) > 0) else "#f5576c"
                delta_html = f"<p style='color: rgba(255,255,255,0.9); font-size: 0.9rem; margin: 0.25rem 0 0 0;'>{card['delta']}</p>"

            st.markdown(f"""
            <div class='summary-card' style='--color: {card["color"]}; --color-end: {card["color_end"]}'>
                <p style='font-size: 2.5rem; margin: 0; position: relative; z-index: 1;'>{card["icon"]}</p>
                <p style='color: white; font-size: 1.6rem; font-weight: 800; margin: 0.5rem 0; position: relative; z-index: 1; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>{card["value"]}</p>
                <p style='color: rgba(255,255,255,0.85); font-size: 0.9rem; margin: 0; position: relative; z-index: 1;'>{card["label"]}</p>
                {delta_html}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 자산 배분 차트
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='portfolio-card'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.75rem;'>🎯</span>
                <h3 style='margin: 0; color: #333;'>자산 구성</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig = go.Figure(data=[go.Pie(
            labels=['주식', '현금'],
            values=[portfolio['stock_value'], portfolio['cash']],
            hole=0.65,
            marker_colors=['#4facfe', '#e0e0e0'],
            textinfo='percent',
            textfont_size=14,
            hovertemplate='%{label}<br>%{value:,.0f}원<br>%{percent}<extra></extra>'
        )])

        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
            margin=dict(t=20, b=50, l=20, r=20),
            annotations=[dict(
                text=f'<b>{portfolio["stock_value"]/portfolio["total_value"]:.0%}</b><br>주식',
                x=0.5, y=0.5, font_size=18, showarrow=False,
                font_color='#4facfe'
            )]
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("""
        <div class='portfolio-card'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.75rem;'>📊</span>
                <h3 style='margin: 0; color: #333;'>섹터 배분</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        sector_data = portfolio['sector_allocation']

        fig = px.pie(
            values=list(sector_data.values()),
            names=list(sector_data.keys()),
            hole=0.5,
            color_discrete_sequence=['#667eea', '#4facfe', '#11998e', '#38ef7d', '#f093fb', '#f5576c']
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
            margin=dict(t=20, b=50, l=20, r=20)
        )
        fig.update_traces(
            textinfo='percent',
            hovertemplate='%{label}<br>%{value:,.0f}원<br>%{percent}<extra></extra>'
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 보유 종목 리스트
    st.markdown("""
    <div class='portfolio-card' style='margin-bottom: 1.5rem;'>
        <div style='display: flex; align-items: center; gap: 0.75rem;'>
            <span style='font-size: 1.75rem;'>📋</span>
            <h3 style='margin: 0; color: #333;'>보유 종목</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    holdings = portfolio['holdings']

    # 정렬 옵션
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sort_option = st.selectbox(
            "정렬 기준",
            ["평가금액 (높은순)", "수익률 (높은순)", "수익률 (낮은순)", "종목명"],
            label_visibility="collapsed"
        )

    if sort_option == "평가금액 (높은순)":
        holdings = holdings.sort_values('current_value', ascending=False)
    elif sort_option == "수익률 (높은순)":
        holdings = holdings.sort_values('pnl_pct', ascending=False)
    elif sort_option == "수익률 (낮은순)":
        holdings = holdings.sort_values('pnl_pct', ascending=True)
    else:
        holdings = holdings.sort_values('name')

    # 보유 종목 카드 형태로 표시
    for idx, (_, row) in enumerate(holdings.iterrows()):
        pnl_color = "#38ef7d" if row['pnl'] >= 0 else "#f5576c"
        pnl_bg = f"{pnl_color}15"
        pnl_icon = "📈" if row['pnl'] >= 0 else "📉"

        st.markdown(f"""
        <div class='holding-item' style='border-left-color: {pnl_color};'>
            <div style='display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;'>
                <div style='min-width: 150px;'>
                    <p style='margin: 0; font-weight: 700; color: #333; font-size: 1.05rem;'>{row['name']}</p>
                    <p style='margin: 0; font-size: 0.8rem; color: #888;'>{row['code']} · {row['sector']}</p>
                </div>
                <div style='text-align: right; min-width: 100px;'>
                    <p style='margin: 0; font-size: 0.75rem; color: #888;'>현재가</p>
                    <p style='margin: 0; font-weight: 600; color: #333;'>{row['current_price']:,.0f}원</p>
                </div>
                <div style='text-align: right; min-width: 120px;'>
                    <p style='margin: 0; font-size: 0.75rem; color: #888;'>평가금액</p>
                    <p style='margin: 0; font-weight: 600; color: #333;'>{row['current_value']:,.0f}원</p>
                </div>
                <div style='text-align: right; min-width: 120px;'>
                    <p style='margin: 0; font-size: 0.75rem; color: #888;'>평가손익</p>
                    <p style='margin: 0; font-weight: 700; color: {pnl_color};'>{row['pnl']:+,.0f}원</p>
                </div>
                <div class='pnl-badge' style='background: {pnl_bg}; min-width: 80px;'>
                    <span style='font-size: 1.1rem; margin-right: 0.25rem;'>{pnl_icon}</span>
                    <span style='color: {pnl_color}; font-size: 1rem;'>{row['pnl_pct']:+.1%}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 종목별 수익률 차트
    st.markdown("""
    <div class='portfolio-card' style='margin-bottom: 1.5rem;'>
        <div style='display: flex; align-items: center; gap: 0.75rem;'>
            <span style='font-size: 1.75rem;'>📊</span>
            <h3 style='margin: 0; color: #333;'>종목별 수익률</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    holdings_sorted = holdings.sort_values('pnl_pct')
    colors = ['#38ef7d' if x >= 0 else '#f5576c' for x in holdings_sorted['pnl_pct']]

    fig = go.Figure(go.Bar(
        x=holdings_sorted['pnl_pct'] * 100,
        y=holdings_sorted['name'],
        orientation='h',
        marker_color=colors,
        text=[f'{x:.1%}' for x in holdings_sorted['pnl_pct']],
        textposition='outside',
        hovertemplate='%{y}<br>수익률: %{x:.1f}%<extra></extra>'
    ))

    fig.update_layout(
        xaxis_title="수익률 (%)",
        yaxis_title="",
        height=max(400, len(holdings) * 45),
        margin=dict(t=20, b=40, l=100, r=80),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)', zeroline=True, zerolinewidth=2, zerolinecolor='#333')
    fig.update_yaxes(showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 최근 거래 내역
    st.markdown("""
    <div class='portfolio-card' style='margin-bottom: 1.5rem;'>
        <div style='display: flex; align-items: center; gap: 0.75rem;'>
            <span style='font-size: 1.75rem;'>📜</span>
            <h3 style='margin: 0; color: #333;'>최근 거래 내역</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    trades = portfolio['recent_trades']

    if not trades.empty:
        for _, trade in trades.iterrows():
            action_color = "#4facfe" if trade['action'] == '매수' else "#f5576c"
            action_bg = f"{action_color}20"
            action_icon = "🛒" if trade['action'] == '매수' else "💸"

            st.markdown(f"""
            <div class='trade-item'>
                <div style='display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;'>
                    <div style='min-width: 100px;'>
                        <p style='margin: 0; font-size: 0.85rem; color: #888;'>{trade['date'].strftime('%Y-%m-%d')}</p>
                    </div>
                    <div style='min-width: 140px;'>
                        <p style='margin: 0; font-weight: 600; color: #333;'>{trade['name']}</p>
                        <p style='margin: 0; font-size: 0.8rem; color: #888;'>{trade['code']}</p>
                    </div>
                    <div>
                        <span class='action-badge' style='background: {action_bg}; color: {action_color};'>
                            {action_icon} {trade['action']}
                        </span>
                    </div>
                    <div style='text-align: right; min-width: 100px;'>
                        <p style='margin: 0; font-size: 0.85rem; color: #333;'>{trade['shares']}주</p>
                        <p style='margin: 0; font-size: 0.8rem; color: #888;'>@ {trade['price']:,.0f}원</p>
                    </div>
                    <div style='text-align: right; min-width: 120px;'>
                        <p style='margin: 0; font-weight: 600; color: #333; font-size: 1rem;'>{trade['value']:,.0f}원</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📭 최근 거래 내역이 없습니다.")

    st.markdown("---")

    # 리밸런싱 제안
    st.markdown("""
    <div class='rebalance-card'>
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;'>
            <span style='font-size: 1.75rem;'>🔄</span>
            <h3 style='margin: 0; color: #333;'>리밸런싱 제안</h3>
        </div>
        <p style='color: #666; font-size: 0.95rem; margin: 0;'>포트폴리오 균형을 분석하고 최적화 제안을 받아보세요</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button("📊 리밸런싱 분석 실행", type="primary", use_container_width=True):
            with st.spinner("포트폴리오 분석 중..."):
                import time
                time.sleep(1)

                st.success("✅ 분석 완료!")

                st.markdown("""
                <div style='margin-top: 1.5rem;'>
                    <h4 style='margin: 0 0 1rem 0; color: #333;'>📋 리밸런싱 권고사항</h4>

                    <div style='background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%); padding: 1.25rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #ffc107;'>
                        <p style='margin: 0; color: #856404;'>
                            <strong>⚠️ IT 섹터 과대비중</strong><br>
                            <span style='font-size: 0.9rem;'>현재 25% → 목표 20% (5% 축소 권장)</span>
                        </p>
                    </div>

                    <div style='background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); padding: 1.25rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #28a745;'>
                        <p style='margin: 0; color: #155724;'>
                            <strong>✅ 금융 섹터 확대 권장</strong><br>
                            <span style='font-size: 0.9rem;'>현재 10% → 목표 15% (5% 확대 권장)</span>
                        </p>
                    </div>

                    <div style='background: linear-gradient(135deg, #cce5ff 0%, #b8daff 100%); padding: 1.25rem; border-radius: 12px; border-left: 4px solid #007bff;'>
                        <p style='margin: 0; color: #004085;'>
                            <strong>💡 현금 비중 조정</strong><br>
                            <span style='font-size: 0.9rem;'>현재 2% → 목표 5% (3% 확대 권장)</span>
                        </p>
                    </div>
                </div>
                """, unsafe_allow_html=True)


def _get_sample_portfolio() -> dict:
    """샘플 포트폴리오 데이터"""

    np.random.seed(42)

    holdings_data = {
        'code': ['005930', '000660', '035720', '005380', '051910',
                 '006400', '003550', '034730', '105560', '055550'],
        'name': ['삼성전자', 'SK하이닉스', '카카오', '현대차', 'LG화학',
                 '삼성SDI', 'LG', 'SK', 'KB금융', '신한지주'],
        'sector': ['IT', 'IT', 'IT', '산업재', '소재',
                   'IT', '산업재', '에너지', '금융', '금융'],
        'shares': [100, 50, 30, 20, 10, 15, 25, 20, 50, 40],
        'avg_price': [65000, 120000, 55000, 180000, 500000,
                      450000, 80000, 180000, 55000, 35000],
        'current_price': [70000, 130000, 48000, 195000, 480000,
                          500000, 85000, 175000, 60000, 38000]
    }

    holdings = pd.DataFrame(holdings_data)
    holdings['current_value'] = holdings['shares'] * holdings['current_price']
    holdings['cost'] = holdings['shares'] * holdings['avg_price']
    holdings['pnl'] = holdings['current_value'] - holdings['cost']
    holdings['pnl_pct'] = holdings['pnl'] / holdings['cost']

    stock_value = holdings['current_value'].sum()
    cash = 5000000
    total_value = stock_value + cash
    total_cost = holdings['cost'].sum() + cash
    initial_capital = 100000000

    sector_allocation = holdings.groupby('sector')['current_value'].sum().to_dict()

    recent_trades = pd.DataFrame({
        'date': pd.date_range(end=datetime.now(), periods=5, freq='W'),
        'code': ['005930', '000660', '035720', '005380', '051910'],
        'name': ['삼성전자', 'SK하이닉스', '카카오', '현대차', 'LG화학'],
        'action': ['매수', '매수', '매도', '매수', '매수'],
        'shares': [50, 25, 20, 10, 5],
        'price': [68000, 125000, 52000, 185000, 490000],
        'value': [3400000, 3125000, 1040000, 1850000, 2450000]
    })

    return {
        'total_value': total_value,
        'initial_capital': initial_capital,
        'total_return': (total_value - initial_capital) / initial_capital,
        'total_pnl': total_value - total_cost,
        'total_pnl_pct': (total_value - total_cost) / total_cost,
        'stock_value': stock_value,
        'cash': cash,
        'num_positions': len(holdings),
        'holdings': holdings,
        'sector_allocation': sector_allocation,
        'recent_trades': recent_trades
    }
