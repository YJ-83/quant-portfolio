"""
전략 실행 페이지 - 한국투자증권 API 연동
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import os
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from strategies import MagicFormulaStrategy, MultifactorStrategy, SectorNeutralStrategy
from strategies.chart_strategies import (
    CHART_STRATEGIES, get_chart_strategy, scan_all_strategies,
    GoldenCrossStrategy, VolumeBreakoutStrategy, AccumulationStrategy,
    MABounceStrategy, BoxBreakoutStrategy, TripleMAStrategy, ChartSignal
)
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_sector


def render_strategy():
    """전략 실행 페이지 렌더링"""

    # CSS
    st.markdown("""
    <style>
        .strategy-card {
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }
        .strategy-card:hover {
            transform: translateY(-5px);
            border-color: #667eea;
        }
        .step-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.5rem 1.25rem;
            border-radius: 30px;
            font-weight: 700;
        }
        .metric-result {
            background: linear-gradient(135deg, var(--color) 0%, var(--color-end) 100%);
            padding: 1.5rem;
            border-radius: 16px;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    # 헤더
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 20px; margin-bottom: 2rem;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>🎯</div>
        <h1 style='color: white; margin: 0; font-size: 2rem;'>전략 실행</h1>
        <p style='color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;'>퀀트 전략으로 최적의 종목을 선정합니다</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결 확인
    api = _get_api_connection()
    if api is None:
        st.error("❌ 한국투자증권 API 연결 실패")
        st.info("샘플 데이터로 전략을 실행합니다.")

    # Step 1: 전략 선택
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span class='step-badge'>📊 Step 1</span>
        <span style='font-size: 1.25rem; font-weight: 700;'>전략 선택</span>
    </div>
    """, unsafe_allow_html=True)

    strategies_info = [
        {"name": "마법공식", "key": "magic", "icon": "🧙‍♂️", "color": "#667eea",
         "desc": "Joel Greenblatt의 '좋은 기업을 싸게 사라' 전략",
         "detail": "높은 자본수익률(ROC) + 높은 이익수익률(Earnings Yield)을 가진 저평가 우량주 발굴"},
        {"name": "멀티팩터", "key": "multi", "icon": "📊", "color": "#11998e",
         "desc": "퀄리티 + 밸류 + 모멘텀 결합",
         "detail": "ROE/GPA(퀄리티) + PER/PBR(밸류) + 수익률(모멘텀) 복합 점수로 종목 선정"},
        {"name": "섹터 중립", "key": "sector", "icon": "⚖️", "color": "#f5576c",
         "desc": "섹터별 균형 잡힌 포트폴리오",
         "detail": "IT/바이오/금융 등 각 섹터에서 균등하게 종목을 선정하여 분산 투자"}
    ]

    col1, col2, col3 = st.columns(3)

    for col, strategy in zip([col1, col2, col3], strategies_info):
        with col:
            st.markdown(f"""
            <div class='strategy-card' style='text-align: center; min-height: 280px;'>
                <div style='font-size: 3rem;'>{strategy["icon"]}</div>
                <h3 style='margin: 0.5rem 0; color: #333;'>{strategy["name"]}</h3>
                <p style='color: #667eea; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;'>{strategy["desc"]}</p>
                <p style='color: #666; font-size: 0.8rem; line-height: 1.4; background: #f8f9fa; padding: 0.75rem; border-radius: 8px; text-align: left;'>{strategy["detail"]}</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"선택", key=f"btn_{strategy['key']}", use_container_width=True):
                st.session_state['selected_strategy'] = strategy['key']

    if 'selected_strategy' not in st.session_state or st.session_state['selected_strategy'] not in ['magic', 'multi', 'sector']:
        st.session_state['selected_strategy'] = 'magic'

    selected = st.session_state['selected_strategy']
    selected_name = {"magic": "마법공식", "multi": "멀티팩터", "sector": "섹터 중립"}.get(selected, "마법공식")

    st.info(f"✅ 선택된 전략: **{selected_name}**")

    st.markdown("---")

    # Step 2: 전략 설정
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span class='step-badge'>⚙️ Step 2</span>
        <span style='font-size: 1.25rem; font-weight: 700;'>전략 설정</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        top_n = st.slider("📌 선정 종목 수", 10, 50, 30)

    with col2:
        min_market_cap = st.number_input("💰 최소 시가총액 (억원)", 0, 10000, 1000, 100)

    with col3:
        exclude_financials = st.checkbox("🏦 금융주 제외", value=True)

    # 전략별 상세 설정
    if selected == 'magic':
        with st.expander("🔧 마법공식 상세 설정", expanded=True):
            use_simplified = st.checkbox("📝 간소화 버전 사용 (ROE + 1/PER)", value=False)

    elif selected == 'multi':
        with st.expander("🔧 멀티팩터 상세 설정", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                quality_weight = st.slider("📈 퀄리티 (%)", 0, 100, 33)
            with col2:
                value_weight = st.slider("💎 밸류 (%)", 0, 100, 33)
            with col3:
                momentum_weight = st.slider("🚀 모멘텀 (%)", 0, 100, 34)

            total = quality_weight + value_weight + momentum_weight
            if total != 100:
                st.warning(f"⚠️ 가중치 합계: {total}% (100%가 되어야 합니다)")
            else:
                st.success(f"✅ 가중치 합계: {total}%")

    elif selected == 'sector':
        with st.expander("🔧 섹터 중립 상세 설정", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                factor_name = st.selectbox(
                    "📊 기준 팩터",
                    ["momentum_12m", "roe", "per"],
                    format_func=lambda x: {"momentum_12m": "12개월 모멘텀", "roe": "ROE", "per": "PER"}.get(x)
                )
            with col2:
                allocation_method = st.radio("📦 배분 방식", ["비례 배분", "균등 배분"])

            if allocation_method == "균등 배분":
                stocks_per_sector = st.slider("섹터당 종목 수", 1, 10, 3)

    st.markdown("---")

    # Step 3: 전략 실행
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span class='step-badge'>🚀 Step 3</span>
        <span style='font-size: 1.25rem; font-weight: 700;'>전략 실행</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_button = st.button("🚀 전략 실행하기", type="primary", width='stretch')

    if run_button:
        with st.spinner("📊 데이터 로딩 및 전략 실행 중..."):
            try:
                # 데이터 로드
                data = _load_stock_data(api)

                if data.empty:
                    st.error("데이터 로딩 실패")
                    return

                # 전략 인스턴스 생성 및 실행
                if selected == 'magic':
                    strategy = MagicFormulaStrategy(
                        top_n=top_n,
                        min_market_cap=min_market_cap * 1e8,
                        exclude_financials=exclude_financials,
                        use_simplified=use_simplified
                    )
                elif selected == 'multi':
                    strategy = MultifactorStrategy(
                        top_n=top_n,
                        weights={'quality': quality_weight/100, 'value': value_weight/100, 'momentum': momentum_weight/100},
                        min_market_cap=min_market_cap * 1e8,
                        exclude_financials=exclude_financials
                    )
                else:
                    strategy = SectorNeutralStrategy(
                        top_n=top_n,
                        factor_name=factor_name,
                        stocks_per_sector=stocks_per_sector if allocation_method == "균등 배분" else None,
                        min_market_cap=min_market_cap * 1e8,
                        exclude_financials=exclude_financials
                    )

                result = strategy.select_stocks(data)
                st.session_state['strategy_result'] = result
                st.success(f"✅ 전략 실행 완료! **{result.selected_count}개** 종목 선정")

            except Exception as e:
                st.error(f"❌ 오류: {e}")
                import traceback
                st.code(traceback.format_exc())

    # 결과 표시
    if 'strategy_result' in st.session_state:
        result = st.session_state['strategy_result']
        _display_result(result)

    st.markdown("---")

    # 차트 매매 전략 섹션
    _render_chart_strategy_section(api)


def _get_api_connection():
    """API 연결"""
    if 'strategy_api' not in st.session_state:
        try:
            from data.kis_api import KoreaInvestmentAPI
            api = KoreaInvestmentAPI()
            if api.connect():
                st.session_state['strategy_api'] = api
            else:
                return None
        except:
            return None
    return st.session_state.get('strategy_api')


def _load_stock_data(api) -> pd.DataFrame:
    """주식 데이터 로드 - API 또는 샘플 데이터 (전체 종목 대상)"""
    all_stocks = []

    # 동적으로 전체 종목 가져오기
    kospi_stocks = get_kospi_stocks()
    kosdaq_stocks = get_kosdaq_stocks()
    all_stock_list = kospi_stocks + kosdaq_stocks
    total = len(all_stock_list)

    # KOSPI 종목 코드 set (빠른 조회용)
    kospi_codes = set(code for code, _ in kospi_stocks)

    # 진행바
    progress = st.progress(0)
    status = st.empty()

    status.text(f"전체 {total}개 종목 데이터 로딩 중...")

    # API 사용 가능한 경우 전체 종목 로드 (시간이 오래 걸림)
    if api:
        # API 조회 (전체 종목, 단 속도를 위해 500개로 제한)
        max_api_stocks = min(500, total)
        sample_list = all_stock_list[:max_api_stocks]

        for i, (code, name) in enumerate(sample_list):
            try:
                info = api.get_stock_info(code)
                if info and info.get('price', 0) > 0:
                    market = 'KOSPI' if code in kospi_codes else 'KOSDAQ'
                    sector = get_sector(code)

                    per = info.get('per', 0)
                    pbr = info.get('pbr', 0)
                    roe = pbr / per if per > 0 else 0

                    all_stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                        'sector': sector,
                        'market_cap': info.get('market_cap', 0),
                        'price': info.get('price', 0),
                        'per': per,
                        'pbr': pbr,
                        'roe': roe,
                        'change_rate': info.get('change_rate', 0),
                        'eps': info.get('eps', 0),
                        'bps': info.get('bps', 0),
                    })
            except:
                continue

            if i % 20 == 0:
                progress.progress((i + 1) / len(sample_list))
                status.text(f"API 데이터 로딩 중... {i+1}/{len(sample_list)} (전체 {total}개 중 상위 {max_api_stocks}개)")

    # API 없거나 데이터 부족시 샘플 데이터 생성 (전체 종목 대상)
    if len(all_stocks) < 100:
        status.text(f"전체 {total}개 종목 샘플 데이터 생성 중...")
        all_stocks = []

        # 시드 고정으로 일관된 샘플 데이터 생성
        np.random.seed(42)

        for i, (code, name) in enumerate(all_stock_list):
            market = 'KOSPI' if code in kospi_codes else 'KOSDAQ'

            # 시가총액 기반 현실적인 데이터 생성
            base_cap = 1e13 - (i * 2e9)  # 순위에 따라 시총 감소
            base_cap = max(base_cap, 1e10)

            all_stocks.append({
                'code': code,
                'name': name,
                'market': market,
                'sector': get_sector(code),
                'market_cap': base_cap * np.random.uniform(0.8, 1.2),
                'price': np.random.uniform(10000, 500000),
                'per': np.random.uniform(5, 30),
                'pbr': np.random.uniform(0.5, 3),
                'roe': np.random.uniform(0.05, 0.25),
                'change_rate': np.random.uniform(-5, 5),
            })

            if i % 100 == 0:
                progress.progress((i + 1) / total)
                status.text(f"샘플 데이터 생성 중... {i+1}/{total}")

    progress.empty()
    status.empty()

    if not all_stocks:
        return pd.DataFrame()

    df = pd.DataFrame(all_stocks)

    # 추가 팩터
    n = len(df)
    np.random.seed(42)  # 일관된 결과를 위해
    df['gpa'] = np.random.uniform(0.1, 0.4, n)
    df['cfo_ratio'] = np.random.uniform(0, 0.15, n)
    df['psr'] = np.random.uniform(0.5, 5, n)
    df['pcr'] = np.random.uniform(3, 20, n)
    df['momentum_3m'] = np.random.uniform(-0.2, 0.3, n)
    df['momentum_6m'] = np.random.uniform(-0.3, 0.4, n)
    df['momentum_12m'] = np.random.uniform(-0.4, 0.6, n)

    # 마법공식용
    df['ebit'] = df['market_cap'] * np.random.uniform(0.05, 0.12, n)
    df['net_debt'] = df['market_cap'] * np.random.uniform(-0.2, 0.4, n)
    df['invested_capital'] = df['market_cap'] * np.random.uniform(0.6, 1.2, n)
    df['earnings_yield'] = df['ebit'] / (df['market_cap'] + df['net_debt'])
    df['roc'] = df['ebit'] / df['invested_capital']

    return df


def _display_result(result):
    """결과 표시 - 개선된 UI"""
    st.markdown("---")

    # 추가 CSS
    st.markdown("""
    <style>
        .stock-card {
            background: white;
            border-radius: 12px;
            padding: 1rem;
            margin: 0.5rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            cursor: pointer;
            transition: all 0.2s ease;
            border-left: 4px solid transparent;
        }
        .stock-card:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stock-card.kospi {
            border-left-color: #667eea;
        }
        .stock-card.kosdaq {
            border-left-color: #f5576c;
        }
        .stock-rank {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
        }
        .stock-name {
            font-weight: 700;
            font-size: 1.1rem;
            color: #333;
        }
        .stock-code {
            color: #888;
            font-size: 0.85rem;
        }
        .stock-score {
            font-weight: 700;
            font-size: 1.2rem;
        }
        .market-badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .market-badge.kospi {
            background: #667eea20;
            color: #667eea;
        }
        .market-badge.kosdaq {
            background: #f5576c20;
            color: #f5576c;
        }
        .metric-box {
            background: linear-gradient(135deg, var(--bg-start) 0%, var(--bg-end) 100%);
            padding: 1.25rem;
            border-radius: 16px;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin: 2rem 0;'>
        <span style='font-size: 2.5rem;'>📋</span>
        <h2 style='margin: 0; color: #667eea;'>선정 결과</h2>
    </div>
    """, unsafe_allow_html=True)

    stocks = result.stocks.copy()

    # KOSPI/KOSDAQ 분리
    kospi_stocks = stocks[stocks['market'] == 'KOSPI'] if 'market' in stocks.columns else stocks
    kosdaq_stocks = stocks[stocks['market'] == 'KOSDAQ'] if 'market' in stocks.columns else pd.DataFrame()

    # 요약 메트릭
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class='metric-box' style='--bg-start: #667eea; --bg-end: #764ba2;'>
            <p style='color: white; font-size: 1.75rem; font-weight: 800; margin: 0;'>{result.selected_count}개</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.85rem; margin: 0;'>총 선정 종목</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class='metric-box' style='--bg-start: #667eea; --bg-end: #5a67d8;'>
            <p style='color: white; font-size: 1.75rem; font-weight: 800; margin: 0;'>{len(kospi_stocks)}개</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.85rem; margin: 0;'>KOSPI</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class='metric-box' style='--bg-start: #f5576c; --bg-end: #f093fb;'>
            <p style='color: white; font-size: 1.75rem; font-weight: 800; margin: 0;'>{len(kosdaq_stocks)}개</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.85rem; margin: 0;'>KOSDAQ</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class='metric-box' style='--bg-start: #11998e; --bg-end: #38ef7d;'>
            <p style='color: white; font-size: 1.75rem; font-weight: 800; margin: 0;'>{result.total_candidates}개</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.85rem; margin: 0;'>후보 종목</p>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        avg_score = stocks['score'].mean() if len(stocks) > 0 else 0
        st.markdown(f"""
        <div class='metric-box' style='--bg-start: #4facfe; --bg-end: #00f2fe;'>
            <p style='color: white; font-size: 1.75rem; font-weight: 800; margin: 0;'>{avg_score:.2f}</p>
            <p style='color: rgba(255,255,255,0.9); font-size: 0.85rem; margin: 0;'>평균 점수</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 탭으로 KOSPI/KOSDAQ 분리
    tab1, tab2, tab3 = st.tabs(["📊 전체", "🏢 KOSPI", "🚀 KOSDAQ"])

    with tab1:
        _render_stock_list(stocks, "all")

    with tab2:
        if len(kospi_stocks) > 0:
            _render_stock_list(kospi_stocks, "kospi")
        else:
            st.info("KOSPI 종목이 없습니다.")

    with tab3:
        if len(kosdaq_stocks) > 0:
            _render_stock_list(kosdaq_stocks, "kosdaq")
        else:
            st.info("KOSDAQ 종목이 없습니다.")

    # 선택된 종목 차트 표시
    if 'selected_stock_code' in st.session_state and st.session_state['selected_stock_code']:
        _render_selected_stock_chart(st.session_state['selected_stock_code'])

    st.markdown("---")

    # 분석 차트들
    col1, col2 = st.columns(2)

    with col1:
        if 'sector' in stocks.columns:
            st.markdown("#### 🥧 섹터 분포")
            sector_dist = stocks['sector'].value_counts()
            colors = ['#667eea', '#f5576c', '#11998e', '#ffc107', '#17a2b8', '#6f42c1', '#e83e8c', '#fd7e14']

            fig = go.Figure(data=[go.Pie(
                labels=sector_dist.index,
                values=sector_dist.values,
                hole=0.5,
                marker_colors=colors[:len(sector_dist)],
                textinfo='label+percent',
                textposition='outside'
            )])
            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                showlegend=False,
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'market' in stocks.columns:
            st.markdown("#### 📊 시장별 분포")
            market_dist = stocks['market'].value_counts()

            fig = go.Figure(data=[go.Bar(
                x=market_dist.index,
                y=market_dist.values,
                marker_color=['#667eea', '#f5576c'],
                text=market_dist.values,
                textposition='auto'
            )])
            fig.update_layout(
                margin=dict(t=30, b=30, l=30, r=30),
                height=350,
                xaxis_title="시장",
                yaxis_title="종목 수",
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)

    # 점수 분포
    st.markdown("#### 📈 점수 분포")
    fig = go.Figure()

    if 'market' in stocks.columns and len(kospi_stocks) > 0 and len(kosdaq_stocks) > 0:
        fig.add_trace(go.Histogram(x=kospi_stocks['score'], name='KOSPI', marker_color='#667eea', opacity=0.7))
        fig.add_trace(go.Histogram(x=kosdaq_stocks['score'], name='KOSDAQ', marker_color='#f5576c', opacity=0.7))
        fig.update_layout(barmode='overlay')
    else:
        fig.add_trace(go.Histogram(x=stocks['score'], marker_color='#667eea'))

    fig.update_layout(
        xaxis_title="점수",
        yaxis_title="종목 수",
        margin=dict(t=30, b=40, l=40, r=30),
        plot_bgcolor='rgba(0,0,0,0)',
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)

    # 다운로드
    st.markdown("#### 💾 데이터 다운로드")
    col1, col2, col3 = st.columns(3)

    with col1:
        csv_all = stocks.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 전체 종목 CSV",
            csv_all,
            f"all_stocks_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )

    with col2:
        if len(kospi_stocks) > 0:
            csv_kospi = kospi_stocks.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 KOSPI CSV",
                csv_kospi,
                f"kospi_stocks_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )

    with col3:
        if len(kosdaq_stocks) > 0:
            csv_kosdaq = kosdaq_stocks.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 KOSDAQ CSV",
                csv_kosdaq,
                f"kosdaq_stocks_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )


def _render_stock_list(stocks: pd.DataFrame, market_type: str):
    """종목 리스트를 카드 형태로 표시"""

    # 종목 선택 드롭다운
    stock_options = ["종목을 선택하세요..."] + [f"{row['name']} ({row['code']})" for _, row in stocks.iterrows()]
    selected = st.selectbox(
        "📊 차트를 볼 종목 선택",
        stock_options,
        key=f"stock_select_{market_type}"
    )

    if selected != "종목을 선택하세요...":
        code = selected.split("(")[1].split(")")[0]
        st.session_state['selected_stock_code'] = code

    # 카드 형태 리스트
    for idx, row in stocks.head(30).iterrows():
        market_class = 'kospi' if row.get('market', 'KOSPI') == 'KOSPI' else 'kosdaq'
        market_label = row.get('market', 'KOSPI')

        # 시가총액 포맷
        market_cap = row.get('market_cap', 0)
        if market_cap >= 1e12:
            cap_str = f"{market_cap/1e12:.1f}조"
        else:
            cap_str = f"{market_cap/1e8:.0f}억"

        # ROE, PER 값
        roe_val = row.get('roe', 0) * 100 if row.get('roe', 0) < 1 else row.get('roe', 0)
        per_val = row.get('per', 0)

        # 점수 색상
        score = row.get('score', 0)
        score_color = '#38ef7d' if score > 0 else '#f5576c'

        col1, col2, col3, col4, col5 = st.columns([0.5, 2, 1.5, 1, 1])

        with col1:
            rank = int(row.get('rank', idx + 1))
            st.markdown(f"<div class='stock-rank'>{rank}</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div>
                <span class='stock-name'>{row['name']}</span>
                <span class='stock-code'> ({row['code']})</span>
                <span class='market-badge {market_class}'>{market_label}</span>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style='font-size: 0.9rem;'>
                <span style='color: #888;'>시총</span> <strong>{cap_str}</strong>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div style='font-size: 0.9rem;'>
                <span style='color: #888;'>ROE</span> <strong>{roe_val:.1f}%</strong>
                <span style='color: #888; margin-left: 0.5rem;'>PER</span> <strong>{per_val:.1f}</strong>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div style='text-align: right;'>
                <span class='stock-score' style='color: {score_color};'>{score:.3f}</span>
            </div>
            """, unsafe_allow_html=True)

        # 버튼으로 종목 선택
        if st.button(f"📈 차트 보기", key=f"chart_{market_type}_{row['code']}", use_container_width=True):
            st.session_state['selected_stock_code'] = row['code']
            st.rerun()

        st.markdown("<hr style='margin: 0.5rem 0; border-color: #eee;'>", unsafe_allow_html=True)


def _render_selected_stock_chart(code: str):
    """선택된 종목의 차트 표시 - 네이버/구글 금융 스타일"""
    from data.stock_list import get_stock_name
    from plotly.subplots import make_subplots

    stock_name = get_stock_name(code)

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                padding: 1.5rem; border-radius: 16px; margin: 2rem 0;
                border: 1px solid #667eea30;'>
        <h3 style='margin: 0; color: #667eea;'>📈 {stock_name} ({code}) 차트</h3>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = _get_api_connection()
    if not api:
        st.warning("API 연결이 필요합니다.")
        return

    # 현재가 정보
    info = api.get_stock_info(code)
    if info:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            change_color = "normal" if info['change_rate'] >= 0 else "inverse"
            st.metric("현재가", f"{info['price']:,}원", f"{info['change_rate']:+.2f}%", delta_color=change_color)
        with col2:
            cap = info['market_cap']
            st.metric("시가총액", f"{cap/1e12:.1f}조" if cap >= 1e12 else f"{cap/1e8:.0f}억")
        with col3:
            st.metric("PER", f"{info['per']:.2f}" if info['per'] > 0 else "-")
        with col4:
            st.metric("PBR", f"{info['pbr']:.2f}" if info['pbr'] > 0 else "-")
        with col5:
            st.metric("거래량", f"{info['volume']:,}")

    # 차트 설정
    col1, col2 = st.columns(2)
    with col1:
        chart_period = st.selectbox("기간", ['3개월', '6개월', '1년'], index=1, key=f"strategy_chart_period_{code}")
    with col2:
        show_indicators = st.multiselect(
            "보조지표",
            ['볼린저밴드', 'MACD', 'RSI'],
            default=['볼린저밴드'],
            key=f"strategy_indicators_{code}"
        )

    # 일봉 차트 데이터 로드
    days = {'3개월': 90, '6개월': 180, '1년': 365}.get(chart_period, 180)
    with st.spinner("차트 로딩 중..."):
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        chart_data = api.get_daily_price(code, start, end)

    if chart_data is not None and not chart_data.empty:
        # 보조지표 수에 따라 row 결정
        num_extra_rows = sum([1 for ind in show_indicators if ind in ['MACD', 'RSI']])
        total_rows = 2 + num_extra_rows

        if num_extra_rows > 0:
            row_heights = [0.5, 0.15] + [0.35 / num_extra_rows] * num_extra_rows
        else:
            row_heights = [0.7, 0.3]

        fig = make_subplots(
            rows=total_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=row_heights
        )

        # 캔들스틱 차트 (한국식: 상승 빨강, 하락 파랑)
        fig.add_trace(go.Candlestick(
            x=chart_data['date'],
            open=chart_data['open'],
            high=chart_data['high'],
            low=chart_data['low'],
            close=chart_data['close'],
            name='주가',
            increasing_line_color='#FF3B30',
            decreasing_line_color='#007AFF',
            increasing_fillcolor='#FF3B30',
            decreasing_fillcolor='#007AFF'
        ), row=1, col=1)

        # 이동평균선 (5, 20, 60, 120일)
        ma_configs = [(5, '#FF6B6B', '5일'), (20, '#FFE66D', '20일'), (60, '#95E1D3', '60일'), (120, '#8B00FF', '120일')]
        for period_val, color, label in ma_configs:
            if len(chart_data) >= period_val:
                ma = chart_data['close'].rolling(window=period_val).mean()
                fig.add_trace(go.Scatter(
                    x=chart_data['date'], y=ma,
                    mode='lines', name=label,
                    line=dict(color=color, width=1.5)
                ), row=1, col=1)

        # 볼린저 밴드
        if '볼린저밴드' in show_indicators and len(chart_data) >= 20:
            bb_mid = chart_data['close'].rolling(window=20).mean()
            bb_std = chart_data['close'].rolling(window=20).std()
            bb_upper = bb_mid + (bb_std * 2)
            bb_lower = bb_mid - (bb_std * 2)

            fig.add_trace(go.Scatter(
                x=chart_data['date'], y=bb_upper,
                mode='lines', name='BB상단',
                line=dict(color='rgba(255, 99, 132, 0.5)', width=1, dash='dot')
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data['date'], y=bb_lower,
                mode='lines', name='BB하단', fill='tonexty',
                line=dict(color='rgba(255, 99, 132, 0.5)', width=1, dash='dot'),
                fillcolor='rgba(255, 99, 132, 0.1)'
            ), row=1, col=1)

        # 거래량 차트
        colors = ['#FF3B30' if chart_data['close'].iloc[i] >= chart_data['open'].iloc[i] else '#007AFF'
                  for i in range(len(chart_data))]
        vol_ma = chart_data['volume'].rolling(window=20).mean()

        fig.add_trace(go.Bar(
            x=chart_data['date'], y=chart_data['volume'],
            marker_color=colors, name='거래량',
            showlegend=False, opacity=0.7
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=chart_data['date'], y=vol_ma,
            mode='lines', name='거래량MA20',
            line=dict(color='#FFA500', width=1.5)
        ), row=2, col=1)

        current_row = 3

        # MACD
        if 'MACD' in show_indicators and len(chart_data) >= 26:
            ema12 = chart_data['close'].ewm(span=12, adjust=False).mean()
            ema26 = chart_data['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            hist_colors = ['#FF3B30' if v >= 0 else '#007AFF' for v in macd_hist]

            fig.add_trace(go.Bar(
                x=chart_data['date'], y=macd_hist,
                name='MACD Hist', marker_color=hist_colors, opacity=0.5
            ), row=current_row, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data['date'], y=macd_line,
                mode='lines', name='MACD',
                line=dict(color='#667eea', width=1.5)
            ), row=current_row, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data['date'], y=signal_line,
                mode='lines', name='Signal',
                line=dict(color='#f5576c', width=1.5)
            ), row=current_row, col=1)
            fig.update_yaxes(title_text="MACD", row=current_row, col=1)
            current_row += 1

        # RSI
        if 'RSI' in show_indicators and len(chart_data) >= 14:
            delta = chart_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            fig.add_trace(go.Scatter(
                x=chart_data['date'], y=rsi,
                mode='lines', name='RSI(14)',
                line=dict(color='#9B59B6', width=1.5)
            ), row=current_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=current_row, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

        fig.update_layout(
            height=500 + (num_extra_rows * 100),
            margin=dict(t=30, b=30, l=60, r=30),
            xaxis_rangeslider_visible=False,
            plot_bgcolor='#FAFAFA',
            paper_bgcolor='white',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            hovermode='x unified'
        )
        fig.update_yaxes(title_text="가격", row=1, col=1)
        fig.update_yaxes(title_text="거래량", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # 차트 닫기 버튼
        if st.button("❌ 차트 닫기", use_container_width=True):
            st.session_state['selected_stock_code'] = None
            st.rerun()
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")


def _render_chart_strategy_section(api):
    """차트 매매 전략 섹션 렌더링"""

    st.markdown("""
    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 2rem; border-radius: 20px; margin: 2rem 0;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>📊</div>
        <h2 style='color: white; margin: 0; font-size: 1.75rem;'>차트 매매 전략</h2>
        <p style='color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;'>기술적 분석 기반 매매 시그널 탐색</p>
    </div>
    """, unsafe_allow_html=True)

    # 전략 설명 카드
    st.markdown("### 🎯 사용 가능한 전략")

    chart_strategies_info = [
        {"key": "golden_cross", "name": "골든크로스", "icon": "✨",
         "desc": "5일선이 20일선을 상향 돌파시 매수, 하향 돌파시 매도"},
        {"key": "volume_breakout", "name": "거래량 급증", "icon": "📈",
         "desc": "평균 대비 2배 이상 거래량 + 가격 상승시 매수"},
        {"key": "accumulation", "name": "매집봉 탐지", "icon": "🔍",
         "desc": "거래량 증가 + 짧은 양봉 = 세력 매집 신호"},
        {"key": "ma_bounce", "name": "이평선 지지", "icon": "📐",
         "desc": "20/60/120일선에서 지지받고 반등시 매수"},
        {"key": "box_breakout", "name": "박스권 돌파", "icon": "📦",
         "desc": "20일간 고점을 거래량 동반 돌파시 매수"},
        {"key": "triple_ma", "name": "3중 정배열", "icon": "📊",
         "desc": "5일 > 20일 > 60일선 정배열 시작시 매수"},
    ]

    # 3열로 전략 카드 표시
    cols = st.columns(3)
    for i, strat in enumerate(chart_strategies_info):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='background: white; border-radius: 12px; padding: 1rem;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1rem;
                        border-left: 4px solid #11998e;'>
                <div style='font-size: 1.5rem;'>{strat["icon"]}</div>
                <h4 style='margin: 0.5rem 0; color: #333;'>{strat["name"]}</h4>
                <p style='color: #666; font-size: 0.8rem; margin: 0;'>{strat["desc"]}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 전략 선택 및 스캔 설정
    st.markdown("### ⚙️ 스캔 설정")

    # 전체 종목 수 가져오기
    all_kospi = get_kospi_stocks()
    all_kosdaq = get_kosdaq_stocks()
    total_kospi = len(all_kospi)
    total_kosdaq = len(all_kosdaq)

    col1, col2 = st.columns(2)

    with col1:
        selected_chart_strategies = st.multiselect(
            "적용할 전략",
            options=[s["key"] for s in chart_strategies_info],
            default=["golden_cross", "volume_breakout"],
            format_func=lambda x: next((s["name"] for s in chart_strategies_info if s["key"] == x), x)
        )

    with col2:
        scan_market = st.selectbox("스캔 대상", ["전체", "KOSPI만", "KOSDAQ만"])

    # KOSPI/KOSDAQ 종목 수 개별 설정
    st.markdown("#### 📊 스캔 종목 수 설정")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style='background: #667eea15; padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <span style='color: #667eea; font-weight: 600;'>KOSPI</span>
            <span style='color: #888; font-size: 0.85rem;'> (전체 {total_kospi}개)</span>
        </div>
        """, unsafe_allow_html=True)
        kospi_scan_count = st.slider(
            "KOSPI 스캔 종목 수",
            min_value=0,
            max_value=total_kospi,
            value=min(100, total_kospi),
            key="kospi_scan_count",
            disabled=(scan_market == "KOSDAQ만")
        )
        if scan_market != "KOSDAQ만":
            st.caption(f"선택: {kospi_scan_count}개 / 전체: {total_kospi}개")

    with col2:
        st.markdown(f"""
        <div style='background: #f5576c15; padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <span style='color: #f5576c; font-weight: 600;'>KOSDAQ</span>
            <span style='color: #888; font-size: 0.85rem;'> (전체 {total_kosdaq}개)</span>
        </div>
        """, unsafe_allow_html=True)
        kosdaq_scan_count = st.slider(
            "KOSDAQ 스캔 종목 수",
            min_value=0,
            max_value=total_kosdaq,
            value=min(100, total_kosdaq),
            key="kosdaq_scan_count",
            disabled=(scan_market == "KOSPI만")
        )
        if scan_market != "KOSPI만":
            st.caption(f"선택: {kosdaq_scan_count}개 / 전체: {total_kosdaq}개")

    # 전체 스캔 종목 수 표시
    if scan_market == "전체":
        total_scan = kospi_scan_count + kosdaq_scan_count
    elif scan_market == "KOSPI만":
        total_scan = kospi_scan_count
    else:
        total_scan = kosdaq_scan_count

    st.info(f"📌 총 스캔 대상: **{total_scan}개** 종목")

    # 전략별 상세 설정
    with st.expander("🔧 전략별 상세 설정", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**골든크로스 설정**")
            gc_short = st.number_input("단기 이평선", 3, 20, 5, key="gc_short")
            gc_long = st.number_input("장기 이평선", 10, 60, 20, key="gc_long")

            st.markdown("**거래량 급증 설정**")
            vol_mult = st.slider("거래량 배수", 1.5, 5.0, 2.0, 0.5, key="vol_mult")
            vol_min_change = st.slider("최소 가격 변동(%)", 0.5, 5.0, 2.0, 0.5, key="vol_min_change")

        with col2:
            st.markdown("**박스권 돌파 설정**")
            box_days = st.number_input("박스권 기간(일)", 10, 60, 20, key="box_days")
            box_threshold = st.slider("돌파 기준(%)", 1.0, 5.0, 2.0, 0.5, key="box_threshold")

            st.markdown("**이평선 지지 설정**")
            ma_periods = st.multiselect("지지 확인 이평선", [20, 60, 120, 240], default=[20, 60, 120], key="ma_periods")

    st.markdown("---")

    # 실시간 모드 선택 (거래량 급증 전략에만 적용)
    realtime_mode = False
    if "volume_breakout" in selected_chart_strategies:
        st.markdown("#### ⚡ 거래량 급증 - 실시간 모드")
        col1, col2 = st.columns([2, 3])
        with col1:
            realtime_mode = st.checkbox("실시간 데이터 사용", value=False, key="realtime_mode",
                                       help="장중에 실시간 현재가/거래량을 조회하여 분석합니다")
        with col2:
            if realtime_mode:
                st.markdown("""
                <div style='background: #fff3cd; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;'>
                    ⚠️ <strong>실시간 모드</strong>: 종목당 API 호출이 추가되어 스캔 시간이 길어집니다.<br>
                    예상 시간: 약 {:.0f}분 (종목당 ~0.3초)
                </div>
                """.format(total_scan * 0.3 / 60), unsafe_allow_html=True)
            else:
                st.caption("📊 일봉 기준: 전일 종가 기준 분석 (빠름)")

        st.markdown("---")

    # 스캔 실행 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_label = "🔍 실시간 시그널 스캔" if realtime_mode else "🔍 차트 시그널 스캔"
        scan_button = st.button(btn_label, type="primary", use_container_width=True)

    if scan_button:
        if not selected_chart_strategies:
            st.warning("최소 1개 이상의 전략을 선택해주세요.")
            return

        if not api:
            st.error("API 연결이 필요합니다.")
            return

        if total_scan == 0:
            st.warning("스캔할 종목 수를 1개 이상 설정해주세요.")
            return

        _run_chart_scan(
            api=api,
            strategies=selected_chart_strategies,
            market=scan_market,
            kospi_count=kospi_scan_count,
            kosdaq_count=kosdaq_scan_count,
            gc_short=gc_short,
            gc_long=gc_long,
            vol_mult=vol_mult,
            vol_min_change=vol_min_change / 100,
            box_days=box_days,
            box_threshold=box_threshold / 100,
            ma_periods=ma_periods,
            realtime_mode=realtime_mode
        )

    # 스캔 결과 표시
    if 'chart_scan_result' in st.session_state and st.session_state['chart_scan_result']:
        _display_chart_signals(st.session_state['chart_scan_result'], api)


def _run_chart_scan(api, strategies, market, kospi_count, kosdaq_count, **kwargs):
    """차트 시그널 스캔 실행"""
    from datetime import datetime, timedelta

    realtime_mode = kwargs.get('realtime_mode', False)

    # 종목 리스트 가져오기
    kospi_stocks = get_kospi_stocks()
    kosdaq_stocks = get_kosdaq_stocks()

    # 시장 선택에 따른 종목 리스트 구성
    stock_list = []
    if market == "KOSPI만":
        stock_list = kospi_stocks[:kospi_count]
    elif market == "KOSDAQ만":
        stock_list = kosdaq_stocks[:kosdaq_count]
    else:  # 전체
        stock_list = kospi_stocks[:kospi_count] + kosdaq_stocks[:kosdaq_count]

    # 전략 인스턴스 생성
    strategy_instances = []
    volume_strategy = None  # 실시간 모드용 거래량 전략 분리

    for strat_key in strategies:
        if strat_key == "golden_cross":
            strategy_instances.append(GoldenCrossStrategy(
                short_period=kwargs.get('gc_short', 5),
                long_period=kwargs.get('gc_long', 20)
            ))
        elif strat_key == "volume_breakout":
            volume_strategy = VolumeBreakoutStrategy(
                volume_mult=kwargs.get('vol_mult', 2.0),
                min_change=kwargs.get('vol_min_change', 0.02)
            )
            if not realtime_mode:
                strategy_instances.append(volume_strategy)
        elif strat_key == "accumulation":
            strategy_instances.append(AccumulationStrategy())
        elif strat_key == "ma_bounce":
            strategy_instances.append(MABounceStrategy(
                ma_periods=kwargs.get('ma_periods', [20, 60, 120])
            ))
        elif strat_key == "box_breakout":
            strategy_instances.append(BoxBreakoutStrategy(
                lookback_days=kwargs.get('box_days', 20),
                breakout_threshold=kwargs.get('box_threshold', 0.02)
            ))
        elif strat_key == "triple_ma":
            strategy_instances.append(TripleMAStrategy())

    signals = []
    progress = st.progress(0)
    status = st.empty()

    # 일봉 데이터 기간 설정 (120일)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")

    # 실시간 모드 안내
    if realtime_mode:
        st.info("⚡ 실시간 모드: 각 종목의 현재가/거래량을 API로 조회합니다...")

    for i, (code, name) in enumerate(stock_list):
        try:
            if realtime_mode:
                status.text(f"🔄 실시간 스캔... {name} ({code}) [{i+1}/{len(stock_list)}]")
            else:
                status.text(f"스캔 중... {name} ({code}) [{i+1}/{len(stock_list)}]")

            # 일봉 데이터 로드 (모든 전략에 필요)
            ohlcv = api.get_daily_price(code, start_date, end_date)
            if ohlcv is None or len(ohlcv) < 30:
                continue

            # 일반 전략 분석
            for strategy in strategy_instances:
                try:
                    signal = strategy.analyze(ohlcv, code, name)
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    continue

            # 실시간 모드: 거래량 급증 전략
            if realtime_mode and volume_strategy:
                try:
                    # 실시간 현재가 조회
                    realtime_info = api.get_stock_info(code)
                    if realtime_info:
                        rt_data = {
                            'price': realtime_info.get('price', 0),
                            'volume': realtime_info.get('volume', 0),
                            'change_rate': realtime_info.get('change_rate', 0),
                            'prev_close': realtime_info.get('prev_close', 0)
                        }
                        signal = volume_strategy.analyze_realtime(ohlcv, rt_data, code, name)
                        if signal:
                            signals.append(signal)
                except Exception as e:
                    continue

        except Exception as e:
            continue

        progress.progress((i + 1) / len(stock_list))

    progress.empty()
    status.empty()

    # 결과 저장
    st.session_state['chart_scan_result'] = signals

    if signals:
        buy_signals = [s for s in signals if s.signal_type == 'BUY']
        sell_signals = [s for s in signals if s.signal_type == 'SELL']
        realtime_count = sum(1 for s in signals if s.indicators and s.indicators.get('realtime'))
        mode_text = f" (실시간 {realtime_count}개 포함)" if realtime_mode and realtime_count > 0 else ""
        st.success(f"✅ 스캔 완료! 매수 시그널 {len(buy_signals)}개, 매도 시그널 {len(sell_signals)}개 발견{mode_text}")
    else:
        st.info("시그널을 발견하지 못했습니다. 설정을 조정해보세요.")


def _display_chart_signals(signals: list, api):
    """차트 시그널 결과 표시"""
    import plotly.graph_objects as go
    from datetime import datetime, timedelta

    if not signals:
        return

    st.markdown("### 📋 발견된 시그널")

    # 매수/매도 분리
    buy_signals = [s for s in signals if s.signal_type == 'BUY']
    sell_signals = [s for s in signals if s.signal_type == 'SELL']

    # 강도순 정렬
    buy_signals.sort(key=lambda x: x.signal_strength, reverse=True)
    sell_signals.sort(key=lambda x: x.signal_strength, reverse=True)

    # 탭으로 분리
    tab1, tab2 = st.tabs([f"🟢 매수 시그널 ({len(buy_signals)})", f"🔴 매도 시그널 ({len(sell_signals)})"])

    with tab1:
        if buy_signals:
            _render_signal_cards(buy_signals, "BUY", api)
        else:
            st.info("매수 시그널이 없습니다.")

    with tab2:
        if sell_signals:
            _render_signal_cards(sell_signals, "SELL", api)
        else:
            st.info("매도 시그널이 없습니다.")


def _render_signal_cards(signals: list, signal_type: str, api):
    """시그널 카드 렌더링"""
    import plotly.graph_objects as go
    from datetime import datetime, timedelta

    color = "#11998e" if signal_type == "BUY" else "#f5576c"
    icon = "🟢" if signal_type == "BUY" else "🔴"

    for idx, signal in enumerate(signals[:20]):  # 상위 20개만 표시
        with st.container():
            col1, col2, col3, col4 = st.columns([0.3, 2, 1.5, 1])

            with col1:
                # 강도 표시
                strength_color = "#38ef7d" if signal.signal_strength >= 70 else "#FFA500" if signal.signal_strength >= 50 else "#f5576c"
                st.markdown(f"""
                <div style='text-align: center;'>
                    <div style='font-size: 1.5rem;'>{icon}</div>
                    <div style='background: {strength_color}; color: white; border-radius: 12px;
                                padding: 0.25rem 0.5rem; font-size: 0.75rem; font-weight: 700;'>
                        {signal.signal_strength:.0f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div>
                    <strong style='font-size: 1.1rem;'>{signal.name}</strong>
                    <span style='color: #888;'>({signal.code})</span>
                    <br>
                    <span style='color: #666; font-size: 0.85rem;'>{signal.description}</span>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style='font-size: 0.9rem;'>
                    <div><span style='color: #888;'>현재가</span> <strong>{signal.price:,.0f}원</strong></div>
                    {'<div><span style="color: #888;">목표가</span> <strong style="color: #11998e;">' + f'{signal.target_price:,.0f}원</strong></div>' if signal.target_price else ''}
                    {'<div><span style="color: #888;">손절가</span> <strong style="color: #f5576c;">' + f'{signal.stop_loss:,.0f}원</strong></div>' if signal.stop_loss else ''}
                </div>
                """, unsafe_allow_html=True)

            with col4:
                if st.button("📈 차트", key=f"signal_chart_{signal_type}_{idx}_{signal.code}"):
                    st.session_state['signal_chart_code'] = signal.code
                    st.session_state['signal_chart_name'] = signal.name

            st.markdown("<hr style='margin: 0.5rem 0; border-color: #eee;'>", unsafe_allow_html=True)

    # 선택된 종목 차트 표시
    if 'signal_chart_code' in st.session_state and st.session_state.get('signal_chart_code'):
        code = st.session_state['signal_chart_code']
        name = st.session_state.get('signal_chart_name', code)

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    padding: 1.5rem; border-radius: 16px; margin: 1rem 0;
                    border: 1px solid #667eea30;'>
            <h3 style='margin: 0; color: #667eea;'>📈 {name} ({code}) 차트</h3>
        </div>
        """, unsafe_allow_html=True)

        # 차트 데이터 로드
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")

        with st.spinner("차트 로딩 중..."):
            chart_data = api.get_daily_price(code, start_date, end_date)

        if chart_data is not None and len(chart_data) > 0:
            from plotly.subplots import make_subplots

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                vertical_spacing=0.03, row_heights=[0.7, 0.3])

            # 캔들스틱
            fig.add_trace(go.Candlestick(
                x=chart_data['date'],
                open=chart_data['open'],
                high=chart_data['high'],
                low=chart_data['low'],
                close=chart_data['close'],
                name='주가',
                increasing_line_color='#FF3B30',
                decreasing_line_color='#007AFF',
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#007AFF'
            ), row=1, col=1)

            # 이동평균선
            for period, color, label in [(5, '#FF6B6B', '5일'), (20, '#FFE66D', '20일'), (60, '#95E1D3', '60일')]:
                if len(chart_data) >= period:
                    ma = chart_data['close'].rolling(window=period).mean()
                    fig.add_trace(go.Scatter(
                        x=chart_data['date'], y=ma,
                        mode='lines', name=label,
                        line=dict(color=color, width=1.5)
                    ), row=1, col=1)

            # 거래량
            colors = ['#FF3B30' if chart_data['close'].iloc[i] >= chart_data['open'].iloc[i] else '#007AFF'
                      for i in range(len(chart_data))]
            fig.add_trace(go.Bar(
                x=chart_data['date'], y=chart_data['volume'],
                marker_color=colors, name='거래량',
                showlegend=False, opacity=0.7
            ), row=2, col=1)

            fig.update_layout(
                height=500,
                margin=dict(t=30, b=30, l=60, r=30),
                xaxis_rangeslider_visible=False,
                plot_bgcolor='#FAFAFA',
                paper_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
            )

            st.plotly_chart(fig, use_container_width=True, key=f"signal_chart_{signal_type}_{code}")

        if st.button("❌ 차트 닫기", key=f"close_signal_chart_{signal_type}"):
            st.session_state['signal_chart_code'] = None
            st.rerun()
