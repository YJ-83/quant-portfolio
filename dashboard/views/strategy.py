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
# chart_strategies import는 strategy_chart_logic.py로 이동됨
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_sector
from data.theme_stocks import THEME_STOCKS, THEME_CATEGORIES, get_theme_stock_codes, get_all_theme_names

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection

# 스윙 포인트 감지 함수 import
from dashboard.utils.chart_utils import detect_swing_points


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
    api = get_api_connection()
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

    # 개별 종목 퀀트 점수 조회 섹션
    _render_individual_stock_quant_section(api)

    st.markdown("---")

    # 태쏘 분할 매수 계산기 섹션
    _render_division_calculator_section()

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

    # 테마/섹터 필터 설정
    with st.expander("🏷️ 테마/섹터 필터 (선택사항)", expanded=False):
        st.markdown("""
        <p style='color: #666; font-size: 0.85rem; margin-bottom: 1rem;'>
            특정 테마에 속한 종목만 필터링하여 분석할 수 있습니다.
        </p>
        """, unsafe_allow_html=True)

        # 테마 카테고리별 멀티셀렉트
        col_theme1, col_theme2 = st.columns(2)

        with col_theme1:
            # 산업/제조 테마
            st.markdown("**🏭 산업/제조**")
            industry_themes = st.multiselect(
                "산업/제조 테마 선택",
                options=THEME_CATEGORIES.get("산업/제조", []),
                default=[],
                key="industry_themes",
                label_visibility="collapsed"
            )

            # 신기술 테마
            st.markdown("**💡 신기술**")
            tech_themes = st.multiselect(
                "신기술 테마 선택",
                options=THEME_CATEGORIES.get("신기술", []),
                default=[],
                key="tech_themes",
                label_visibility="collapsed"
            )

        with col_theme2:
            # 기타 테마
            st.markdown("**📦 기타**")
            other_themes = st.multiselect(
                "기타 테마 선택",
                options=THEME_CATEGORIES.get("기타", []),
                default=[],
                key="other_themes",
                label_visibility="collapsed"
            )

        # 선택된 테마 합치기
        selected_themes = industry_themes + tech_themes + other_themes

        if selected_themes:
            # 선택된 테마에 해당하는 종목 코드 수집
            theme_stock_codes = set()
            for theme in selected_themes:
                theme_stock_codes.update(get_theme_stock_codes(theme))

            st.success(f"✅ 선택된 테마: {', '.join(selected_themes)} ({len(theme_stock_codes)}개 종목)")

            # 테마별 종목 수 표시
            theme_counts = []
            for theme in selected_themes:
                count = len(get_theme_stock_codes(theme))
                theme_counts.append(f"{theme}: {count}개")

            st.caption(" | ".join(theme_counts))
        else:
            theme_stock_codes = None
            st.info("테마를 선택하지 않으면 전체 종목을 대상으로 분석합니다.")

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

                # 테마 필터 적용
                if theme_stock_codes:
                    original_count = len(data)
                    data = data[data['code'].isin(theme_stock_codes)]
                    filtered_count = len(data)
                    st.info(f"🏷️ 테마 필터 적용: {original_count}개 → {filtered_count}개 종목")

                    if data.empty:
                        st.warning("선택한 테마에 해당하는 종목이 없습니다.")
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

                # 테마 정보 포함한 성공 메시지
                theme_info = f" (테마: {', '.join(selected_themes)})" if selected_themes else ""
                st.success(f"✅ 전략 실행 완료! **{result.selected_count}개** 종목 선정{theme_info}")

            except Exception as e:
                st.error(f"❌ 오류: {e}")
                import traceback
                st.code(traceback.format_exc())

    # 결과 표시
    if 'strategy_result' in st.session_state:
        result = st.session_state['strategy_result']
        _display_result(result)

    # 차트 매매 전략은 차트전략 페이지로 이동됨 (strategy_chart_logic.py)


# _get_api_connection 함수는 dashboard/utils/api_helper.py로 통합됨
# 아래 호출부에서 get_api_connection() 사용


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


def _load_stock_data_by_market(api, market: str = "KOSPI") -> pd.DataFrame:
    """시장별 주식 데이터 로드 - 전체 종목 대상"""
    # 시장별 종목 가져오기
    if market == "KOSPI":
        stock_list = get_kospi_stocks()
    else:
        stock_list = get_kosdaq_stocks()

    total = len(stock_list)
    all_stocks = []
    api_codes = set()  # API로 가져온 종목 코드

    # 진행바
    progress = st.progress(0)
    status = st.empty()

    status.text(f"{market} 전체 {total}개 종목 데이터 로딩 중...")

    # API 사용 가능한 경우 일부 종목만 API로 조회 (속도 제한)
    if api:
        max_api_stocks = min(100, total)  # API는 100개만 조회 (속도)
        sample_list = stock_list[:max_api_stocks]

        for i, (code, name) in enumerate(sample_list):
            try:
                info = api.get_stock_info(code)
                if info and info.get('price', 0) > 0:
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
                    api_codes.add(code)
            except:
                continue

            if i % 20 == 0:
                progress.progress((i + 1) / total * 0.3)  # 30%까지 API
                status.text(f"{market} API 데이터 로딩 중... {i+1}/{len(sample_list)}")

    # 나머지 종목은 샘플 데이터로 채우기 (전체 종목 포함)
    status.text(f"{market} 전체 {total}개 종목 샘플 데이터 보완 중...")
    np.random.seed(42 if market == "KOSPI" else 123)

    for i, (code, name) in enumerate(stock_list):
        # API로 이미 가져온 종목은 스킵
        if code in api_codes:
            continue

        base_cap = 1e13 - (i * 2e9)
        base_cap = max(base_cap, 1e10)

        all_stocks.append({
            'code': code,
            'name': name,
            'market': market,
            'sector': get_sector(code),
            'market_cap': base_cap * np.random.uniform(0.8, 1.2),
            'price': np.random.uniform(10000, 500000),
            'per': np.random.uniform(5, 30),
            'pbr': np.random.uniform(0.5, 5),
            'roe': np.random.uniform(0.05, 0.25),
            'change_rate': np.random.uniform(-5, 5),
        })

        if i % 200 == 0:
            progress.progress(0.3 + (i + 1) / total * 0.7)  # 30~100%
            status.text(f"{market} 전체 종목 데이터 생성 중... {i+1}/{total}")

    progress.empty()
    status.empty()

    if not all_stocks:
        return pd.DataFrame()

    df = pd.DataFrame(all_stocks)

    # 추가 팩터
    n = len(df)
    np.random.seed(42 if market == "KOSPI" else 123)
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

    # code를 인덱스로 설정
    df = df.set_index('code')

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
    api = get_api_connection()
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
            decreasing_fillcolor='#007AFF',
            line=dict(width=1),
            whiskerwidth=0.8
        ), row=1, col=1)

        # 이동평균선 (5, 20, 60, 120, 200일 — 200일선은 진홍·두껍게 강조)
        ma_configs = [
            (5, '#FF6B6B', '5일', 1.5),
            (20, '#FFE66D', '20일', 1.5),
            (60, '#95E1D3', '60일', 1.5),
            (120, '#8B00FF', '120일', 1.5),
            (200, '#DC143C', '200일', 2.5),
        ]
        for period_val, color, label, width_val in ma_configs:
            if len(chart_data) >= period_val:
                ma = chart_data['close'].rolling(window=period_val).mean()
                fig.add_trace(go.Scatter(
                    x=chart_data['date'], y=ma,
                    mode='lines', name=label,
                    line=dict(color=color, width=width_val)
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

        # 스윙 포인트 (저점/고점 마커)
        if len(chart_data) >= 10:
            swing_order = 3 if len(chart_data) < 100 else 5
            swing_high_idx, swing_low_idx = detect_swing_points(chart_data, order=swing_order)

            price_range = chart_data['high'].max() - chart_data['low'].min()
            marker_offset = price_range * 0.02

            # 저점 마커
            if len(swing_low_idx) > 0:
                recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                low_dates = chart_data['date'].iloc[recent_low_idx]
                low_prices = chart_data['low'].iloc[recent_low_idx]

                fig.add_trace(go.Scatter(
                    x=low_dates,
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
                ), row=1, col=1)

            # 고점 마커
            if len(swing_high_idx) > 0:
                recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
                high_dates = chart_data['date'].iloc[recent_high_idx]
                high_prices = chart_data['high'].iloc[recent_high_idx]

                fig.add_trace(go.Scatter(
                    x=high_dates,
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
                ), row=1, col=1)

            # ========== 추세선 추가 (저점/고점 연결) ==========
            from scipy import stats

            # 가격 범위 계산 (Y축 클리핑용)
            price_high = chart_data['high'].max()
            price_low = chart_data['low'].min()
            price_margin = (price_high - price_low) * 0.1  # 10% 여유

            # 상승 추세선 (저점 연결)
            if len(swing_low_idx) >= 2:
                recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                tl_low_x = list(recent_lows)
                tl_low_y = [chart_data['low'].iloc[i] for i in recent_lows]
                slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

                if slope > 0:
                    tl_x_start = min(recent_lows)
                    tl_x_end = len(chart_data) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    fig.add_trace(go.Scatter(
                        x=[chart_data['date'].iloc[tl_x_start], chart_data['date'].iloc[tl_x_end]],
                        y=[tl_y_start, tl_y_end],
                        mode='lines',
                        name='상승 추세선',
                        line=dict(color='#00C853', width=2, dash='solid'),
                        hovertemplate='상승 추세선<extra></extra>',
                        showlegend=True
                    ), row=1, col=1)

            # 하락 추세선 (고점 연결)
            if len(swing_high_idx) >= 2:
                recent_highs = swing_high_idx[-5:] if len(swing_high_idx) >= 5 else swing_high_idx
                tl_high_x = list(recent_highs)
                tl_high_y = [chart_data['high'].iloc[i] for i in recent_highs]
                slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

                if slope < 0:
                    tl_x_start = min(recent_highs)
                    tl_x_end = len(chart_data) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    fig.add_trace(go.Scatter(
                        x=[chart_data['date'].iloc[tl_x_start], chart_data['date'].iloc[tl_x_end]],
                        y=[tl_y_start, tl_y_end],
                        mode='lines',
                        name='하락 추세선',
                        line=dict(color='#FF3B30', width=2, dash='solid'),
                        hovertemplate='하락 추세선<extra></extra>',
                        showlegend=True
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


# 차트 매매 전략 관련 함수들은 strategy_chart_logic.py로 이동됨
# _render_chart_strategy_section, _run_chart_scan, _display_chart_signals, _render_signal_cards


def _render_individual_stock_quant_section(api):
    """개별 종목 퀀트 점수 조회 섹션"""
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span class='step-badge'>🔎 개별 조회</span>
        <span style='font-size: 1.25rem; font-weight: 700;'>종목별 퀀트 점수 조회</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background: #f0f4ff; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
        <p style='margin: 0; font-size: 0.9rem; color: #555;'>
            📊 특정 종목의 <b>마법공식</b>, <b>멀티팩터</b>, <b>섹터중립</b> 점수와 순위를 확인할 수 있습니다.<br>
            시장(KOSPI/KOSDAQ)을 선택하면 해당 시장 내 순위를 확인할 수 있습니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 시장 선택
    market_col1, market_col2 = st.columns([1, 3])
    with market_col1:
        selected_market = st.radio(
            "시장 선택",
            ["KOSPI", "KOSDAQ"],
            horizontal=True,
            key="quant_market_select"
        )

    # 선택된 시장의 종목 리스트 로드
    @st.cache_data(ttl=3600)
    def _load_stocks_by_market(market: str):
        if market == "KOSPI":
            stocks = get_kospi_stocks()
        else:
            stocks = get_kosdaq_stocks()
        stock_options = ["-- 종목 선택 --"] + [f"{name} ({code})" for code, name in stocks]
        stock_map = {f"{name} ({code})": (code, name) for code, name in stocks}
        return stock_options, stock_map, len(stocks)

    stock_options, stock_map, total_stocks = _load_stocks_by_market(selected_market)

    with market_col2:
        st.info(f"📈 {selected_market} 총 **{total_stocks:,}개** 종목")

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_stock = st.selectbox(
            f"{selected_market} 종목 선택 (검색어 입력 시 자동완성)",
            options=stock_options,
            index=0,
            key="quant_stock_selectbox",
            help="종목명 또는 코드 일부를 입력하면 자동완성됩니다"
        )
    with col2:
        search_btn = st.button("📊 점수 조회", key="quant_score_btn", type="primary")

    if search_btn and selected_stock and selected_stock in stock_map:
        code, name = stock_map[selected_stock]
        _analyze_stock_quant_scores(api, code, name, selected_market)


def _analyze_stock_quant_scores(api, code: str, name: str, market: str = "KOSPI"):
    """개별 종목의 퀀트 점수 분석 (시장별) - 종목 정보 및 점수 표시"""
    with st.spinner(f"🔄 {name}({code}) {market} 내 퀀트 점수 분석 중..."):
        try:
            # 시장별 데이터 로드
            data = _load_stock_data_by_market(api, market)

            if data.empty:
                st.error("❌ 데이터 로딩 실패")
                return

            # 해당 종목이 데이터에 있는지 확인
            if code not in data.index:
                st.error(f"❌ {name}({code}) 데이터를 찾을 수 없습니다. {market} 종목이 맞는지 확인해주세요.")
                return

            stock_data = data.loc[code]
            total_market_stocks = len(data)

            # 종목 기본 점수 계산 (전략 실행 없이 직접 계산)
            results = _calculate_stock_scores(stock_data, code, market, total_market_stocks)

            # 결과 표시
            _display_quant_scores_simple(name, code, stock_data, results, market, total_market_stocks)

        except Exception as e:
            st.error(f"❌ 분석 오류: {e}")
            import traceback
            st.code(traceback.format_exc())


def _calculate_stock_scores(stock_data, code: str, market: str, total_stocks: int) -> dict:
    """종목의 퀀트 점수 직접 계산"""
    results = {}

    # 기본 지표 가져오기
    per = stock_data.get('per', 0) if hasattr(stock_data, 'get') else stock_data['per'] if 'per' in stock_data.index else 0
    pbr = stock_data.get('pbr', 0) if hasattr(stock_data, 'get') else stock_data['pbr'] if 'pbr' in stock_data.index else 0
    roe = stock_data.get('roe', 0) if hasattr(stock_data, 'get') else stock_data['roe'] if 'roe' in stock_data.index else 0
    roc = stock_data.get('roc', 0) if hasattr(stock_data, 'get') else stock_data['roc'] if 'roc' in stock_data.index else 0
    earnings_yield = stock_data.get('earnings_yield', 0) if hasattr(stock_data, 'get') else stock_data['earnings_yield'] if 'earnings_yield' in stock_data.index else 0
    momentum_3m = stock_data.get('momentum_3m', 0) if hasattr(stock_data, 'get') else stock_data['momentum_3m'] if 'momentum_3m' in stock_data.index else 0
    momentum_6m = stock_data.get('momentum_6m', 0) if hasattr(stock_data, 'get') else stock_data['momentum_6m'] if 'momentum_6m' in stock_data.index else 0
    gpa = stock_data.get('gpa', 0) if hasattr(stock_data, 'get') else stock_data['gpa'] if 'gpa' in stock_data.index else 0

    # 1. 마법공식 점수 (ROC + Earnings Yield 기반)
    # ROC 점수: 높을수록 좋음 (0~100)
    roc_score = min(100, max(0, roc * 500)) if roc > 0 else 0
    # EY 점수: 높을수록 좋음 (0~100)
    ey_score = min(100, max(0, earnings_yield * 500)) if earnings_yield > 0 else 0
    magic_score = (roc_score + ey_score) / 2

    results['magic'] = {
        'score': magic_score,
        'roc': roc * 100 if roc else 0,  # 백분율로 변환
        'earnings_yield': earnings_yield * 100 if earnings_yield else 0,
        'total_stocks': total_stocks
    }

    # 2. 멀티팩터 점수 (퀄리티 + 밸류 + 모멘텀)
    # 퀄리티: ROE, GPA
    quality_score = min(100, max(0, (roe * 200 + gpa * 200) / 2)) if roe > 0 else 0

    # 밸류: PER, PBR (낮을수록 좋음)
    per_score = max(0, 100 - per * 3) if per > 0 else 50
    pbr_score = max(0, 100 - pbr * 20) if pbr > 0 else 50
    value_score = (per_score + pbr_score) / 2

    # 모멘텀: 3개월, 6개월 수익률
    momentum_score = min(100, max(0, 50 + momentum_3m * 100 + momentum_6m * 50))

    multi_score = (quality_score * 0.33 + value_score * 0.33 + momentum_score * 0.34)

    results['multi'] = {
        'score': multi_score,
        'quality_score': quality_score,
        'value_score': value_score,
        'momentum_score': momentum_score,
        'total_stocks': total_stocks
    }

    # 3. 섹터중립 점수 (ROE 기반)
    sector = get_sector(code)
    sector_score = min(100, max(0, roe * 400)) if roe > 0 else 0

    results['sector'] = {
        'score': sector_score,
        'sector': sector,
        'roe': roe * 100 if roe else 0,
        'total_stocks': total_stocks
    }

    return results


def _display_quant_scores_simple(name: str, code: str, stock_data, results: dict, market: str = "KOSPI", total_market_stocks: int = 0):
    """퀀트 점수 결과 표시 (단순화 버전 - 점수만 표시)"""

    # 시장 배지 색상
    market_color = "#667eea" if market == "KOSPI" else "#11998e"
    market_icon = "🔵" if market == "KOSPI" else "🟢"

    # 종목 기본 정보
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {market_color} 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; margin-bottom: 1.5rem;'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <h2 style='color: white; margin: 0;'>{name}</h2>
                <p style='color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;'>종목코드: {code}</p>
            </div>
            <div style='background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 20px;'>
                <span style='color: white; font-weight: bold; font-size: 1.1rem;'>{market_icon} {market}</span>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.8rem;'>총 {total_market_stocks:,}개 종목</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 종합 점수 계산
    magic_score = results['magic'].get('score', 0)
    multi_score = results['multi'].get('score', 0)
    sector_score = results['sector'].get('score', 0)
    avg_score = (magic_score + multi_score + sector_score) / 3

    # 등급 결정 (점수 기준)
    if avg_score >= 80:
        grade = "A+"
        grade_color = "#00d26a"
    elif avg_score >= 70:
        grade = "A"
        grade_color = "#00d26a"
    elif avg_score >= 60:
        grade = "B+"
        grade_color = "#667eea"
    elif avg_score >= 50:
        grade = "B"
        grade_color = "#667eea"
    elif avg_score >= 40:
        grade = "C"
        grade_color = "#ffc107"
    else:
        grade = "D"
        grade_color = "#ff6b6b"

    # 종합 등급 표시
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <div style='display: inline-block; background: {grade_color}; color: white; font-size: 2.5rem; font-weight: bold;
                    width: 80px; height: 80px; line-height: 80px; border-radius: 50%;'>{grade}</div>
        <p style='margin: 0.5rem 0 0 0; color: #666;'>종합 등급 (평균 점수: {avg_score:.1f}점)</p>
    </div>
    """, unsafe_allow_html=True)

    # 전략별 점수 카드
    col1, col2, col3 = st.columns(3)

    # 마법공식
    with col1:
        magic = results['magic']
        score_display = f"{magic['score']:.1f}점"

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>🧙‍♂️</div>
            <h3 style='color: white; margin: 0;'>마법공식</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{score_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>ROC + Earnings Yield</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📊 상세 점수"):
            st.write(f"**ROC (자본수익률)**: {magic.get('roc', 0):.2f}%")
            st.write(f"**Earnings Yield**: {magic.get('earnings_yield', 0):.2f}%")

    # 멀티팩터
    with col2:
        multi = results['multi']
        score_display = f"{multi['score']:.1f}점"

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>📊</div>
            <h3 style='color: white; margin: 0;'>멀티팩터</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{score_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>퀄리티 + 밸류 + 모멘텀</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📊 상세 점수"):
            st.write(f"**퀄리티 점수**: {multi.get('quality_score', 0):.1f}")
            st.write(f"**밸류 점수**: {multi.get('value_score', 0):.1f}")
            st.write(f"**모멘텀 점수**: {multi.get('momentum_score', 0):.1f}")

    # 섹터중립
    with col3:
        sector = results['sector']
        score_display = f"{sector['score']:.1f}점"

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>⚖️</div>
            <h3 style='color: white; margin: 0;'>섹터중립</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{score_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>ROE 기반</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📊 상세 정보"):
            st.write(f"**섹터**: {sector.get('sector', 'N/A')}")
            st.write(f"**ROE**: {sector.get('roe', 0):.2f}%")

    # 종목 기본 지표 표시
    st.markdown("### 📈 기본 지표")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    # stock_data가 Series인 경우 처리
    def get_val(data, key, default=0):
        if hasattr(data, 'get'):
            return data.get(key, default)
        elif key in data.index:
            return data[key]
        return default

    with metric_col1:
        per = get_val(stock_data, 'per', 0)
        st.metric("PER", f"{per:.2f}" if per and not pd.isna(per) else "N/A")

    with metric_col2:
        pbr = get_val(stock_data, 'pbr', 0)
        st.metric("PBR", f"{pbr:.2f}" if pbr and not pd.isna(pbr) else "N/A")

    with metric_col3:
        roe = get_val(stock_data, 'roe', 0)
        st.metric("ROE", f"{roe*100:.2f}%" if roe and not pd.isna(roe) else "N/A")

    with metric_col4:
        market_cap = get_val(stock_data, 'market_cap', 0)
        if market_cap and not pd.isna(market_cap):
            cap_억 = market_cap / 1e8 if market_cap > 1e10 else market_cap
            st.metric("시가총액", f"{cap_억:,.0f}억")
        else:
            st.metric("시가총액", "N/A")


def _display_quant_scores(name: str, code: str, stock_data, results: dict, market: str = "KOSPI", total_market_stocks: int = 0):
    """퀀트 점수 결과 표시"""

    # 시장 배지 색상
    market_color = "#667eea" if market == "KOSPI" else "#11998e"
    market_icon = "🔵" if market == "KOSPI" else "🟢"

    # 종목 기본 정보
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {market_color} 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; margin-bottom: 1.5rem;'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <h2 style='color: white; margin: 0;'>{name}</h2>
                <p style='color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;'>종목코드: {code}</p>
            </div>
            <div style='background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 20px;'>
                <span style='color: white; font-weight: bold; font-size: 1.1rem;'>{market_icon} {market}</span>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.8rem;'>총 {total_market_stocks:,}개 종목</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 종합 등급 계산
    ranks = []
    for strategy in ['magic', 'multi', 'sector']:
        if results[strategy]['rank'] != 'N/A':
            ranks.append(results[strategy]['rank'])

    if ranks:
        avg_rank = sum(ranks) / len(ranks)
        total = results['magic'].get('total_stocks', total_market_stocks)

        # 등급 결정 (상위 %)
        pct = (avg_rank / total) * 100 if total > 0 else 100
        if pct <= 5:
            grade = "A+"
            grade_color = "#00d26a"
        elif pct <= 10:
            grade = "A"
            grade_color = "#00d26a"
        elif pct <= 20:
            grade = "B+"
            grade_color = "#667eea"
        elif pct <= 30:
            grade = "B"
            grade_color = "#667eea"
        elif pct <= 50:
            grade = "C"
            grade_color = "#ffc107"
        else:
            grade = "D"
            grade_color = "#ff6b6b"
    else:
        grade = "N/A"
        grade_color = "#999"
        pct = 100

    # 종합 등급 표시
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <div style='display: inline-block; background: {grade_color}; color: white; font-size: 2.5rem; font-weight: bold;
                    width: 80px; height: 80px; line-height: 80px; border-radius: 50%;'>{grade}</div>
        <p style='margin: 0.5rem 0 0 0; color: #666;'>{market} 내 종합 등급 (상위 {pct:.1f}%)</p>
    </div>
    """, unsafe_allow_html=True)

    # 전략별 점수 카드
    col1, col2, col3 = st.columns(3)

    # 마법공식
    with col1:
        magic = results['magic']
        rank_display = f"{magic['rank']}위" if magic['rank'] != 'N/A' else "N/A"
        rank_pct = f"(상위 {(magic['rank']/magic['total_stocks']*100):.1f}%)" if magic['rank'] != 'N/A' else ""

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>🧙‍♂️</div>
            <h3 style='color: white; margin: 0;'>마법공식</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{rank_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.9rem;'>{rank_pct}</p>
            <p style='color: rgba(255,255,255,0.7); margin: 0.5rem 0 0 0; font-size: 0.8rem;'>{market} {magic['total_stocks']}개 종목 중</p>
        </div>
        """, unsafe_allow_html=True)

        if magic['rank'] != 'N/A':
            with st.expander("📊 상세 점수"):
                st.write(f"**ROC 순위**: {magic.get('roc_rank', 'N/A')}")
                st.write(f"**EY 순위**: {magic.get('ey_rank', 'N/A')}")
                st.write(f"**종합 점수**: {magic.get('score', 0):.2f}")

    # 멀티팩터
    with col2:
        multi = results['multi']
        rank_display = f"{multi['rank']}위" if multi['rank'] != 'N/A' else "N/A"
        rank_pct = f"(상위 {(multi['rank']/multi['total_stocks']*100):.1f}%)" if multi['rank'] != 'N/A' else ""

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>📊</div>
            <h3 style='color: white; margin: 0;'>멀티팩터</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{rank_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.9rem;'>{rank_pct}</p>
            <p style='color: rgba(255,255,255,0.7); margin: 0.5rem 0 0 0; font-size: 0.8rem;'>{market} {multi['total_stocks']}개 종목 중</p>
        </div>
        """, unsafe_allow_html=True)

        if multi['rank'] != 'N/A':
            with st.expander("📊 상세 점수"):
                st.write(f"**퀄리티 점수**: {multi.get('quality_score', 0):.2f}")
                st.write(f"**밸류 점수**: {multi.get('value_score', 0):.2f}")
                st.write(f"**모멘텀 점수**: {multi.get('momentum_score', 0):.2f}")
                st.write(f"**종합 점수**: {multi.get('score', 0):.2f}")

    # 섹터중립
    with col3:
        sector = results['sector']
        rank_display = f"{sector['rank']}위" if sector['rank'] != 'N/A' else "N/A"
        rank_pct = f"(상위 {(sector['rank']/sector['total_stocks']*100):.1f}%)" if sector['rank'] != 'N/A' else ""

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); padding: 1.5rem; border-radius: 15px; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>⚖️</div>
            <h3 style='color: white; margin: 0;'>섹터중립</h3>
            <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{rank_display}</div>
            <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.9rem;'>{rank_pct}</p>
            <p style='color: rgba(255,255,255,0.7); margin: 0.5rem 0 0 0; font-size: 0.8rem;'>{market} {sector['total_stocks']}개 종목 중</p>
        </div>
        """, unsafe_allow_html=True)

        if sector['rank'] != 'N/A':
            with st.expander("📊 상세 정보"):
                st.write(f"**섹터**: {sector.get('sector', 'N/A')}")
                st.write(f"**섹터 내 순위**: {sector.get('sector_rank', 'N/A')}")
                st.write(f"**팩터 점수**: {sector.get('score', 0):.2f}")

    # 종목 기본 지표 표시
    st.markdown("### 📈 기본 지표")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        per = stock_data.get('PER', stock_data.get('per', 0))
        st.metric("PER", f"{per:.2f}" if per and not pd.isna(per) else "N/A")

    with metric_col2:
        pbr = stock_data.get('PBR', stock_data.get('pbr', 0))
        st.metric("PBR", f"{pbr:.2f}" if pbr and not pd.isna(pbr) else "N/A")

    with metric_col3:
        roe = stock_data.get('ROE', stock_data.get('roe', 0))
        st.metric("ROE", f"{roe:.2f}%" if roe and not pd.isna(roe) else "N/A")

    with metric_col4:
        market_cap = stock_data.get('market_cap', stock_data.get('시가총액', 0))
        if market_cap and not pd.isna(market_cap):
            cap_억 = market_cap / 1e8 if market_cap > 1e10 else market_cap
            st.metric("시가총액", f"{cap_억:,.0f}억")
        else:
            st.metric("시가총액", "N/A")


def _render_division_calculator_section():
    """태쏘 분할 매수/매도 계산기 섹션"""
    from dashboard.utils.indicators import (
        calculate_triangle_division,
        calculate_diamond_division,
        calculate_equal_division
    )

    st.markdown("""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span class='step-badge'>💎 분할 매수</span>
        <span style='font-size: 1.25rem; font-weight: 700;'>분할 매수/매도 계산기</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
        <p style='color: #333; margin: 0; font-size: 0.9rem;'>
            <b>태쏘 스윙투자 전략</b>의 분할 매수/매도 계산기입니다.<br>
            삼각분할(1:2:3)과 다이아몬드 분할(1:2:2:1) 방식을 지원합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📐 분할 매수 계산기", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 📊 기본 설정")
            total_amount = st.number_input(
                "총 투자금액 (원)",
                min_value=100000,
                max_value=1000000000,
                value=10000000,
                step=1000000,
                key="div_total_amount"
            )

            base_price = st.number_input(
                "기준 가격 (현재가)",
                min_value=100,
                max_value=10000000,
                value=10000,
                step=100,
                key="div_base_price"
            )

            direction = st.radio(
                "매매 방향",
                ["매수 (하락 시)", "매도 (상승 시)"],
                horizontal=True,
                key="div_direction"
            )
            dir_key = 'buy' if '매수' in direction else 'sell'

        with col2:
            st.markdown("##### 📈 분할 전략")
            division_type = st.selectbox(
                "분할 방식",
                ["삼각분할 (1:2:3)", "다이아몬드 (1:2:2:1)", "균등분할"],
                key="div_type"
            )

            if "삼각" in division_type:
                st.markdown("**분할 간격 (%)**")
                pct1 = st.slider("1차", 1, 10, 3, key="tri_pct1")
                pct2 = st.slider("2차", 2, 15, 5, key="tri_pct2")
                pct3 = st.slider("3차", 3, 20, 7, key="tri_pct3")
                division_pct = [pct1, pct2, pct3]
            elif "다이아몬드" in division_type:
                st.markdown("**분할 간격 (%)**")
                pct1 = st.slider("1차", 1, 10, 3, key="dia_pct1")
                pct2 = st.slider("2차", 2, 15, 5, key="dia_pct2")
                pct3 = st.slider("3차", 3, 20, 7, key="dia_pct3")
                pct4 = st.slider("4차", 5, 25, 10, key="dia_pct4")
                division_pct = [pct1, pct2, pct3, pct4]
            else:
                num_div = st.slider("분할 횟수", 2, 5, 3, key="eq_num")
                pct_step = st.slider("간격 (%)", 1, 10, 5, key="eq_pct")
                division_pct = pct_step

        # 계산 버튼
        if st.button("📊 분할 계획 계산", use_container_width=True, key="calc_division"):
            if "삼각" in division_type:
                result = calculate_triangle_division(total_amount, base_price, division_pct, dir_key)
            elif "다이아몬드" in division_type:
                result = calculate_diamond_division(total_amount, base_price, division_pct, dir_key)
            else:
                result = calculate_equal_division(total_amount, base_price, num_div, division_pct, dir_key)

            st.session_state['division_result'] = result

        # 결과 표시
        if 'division_result' in st.session_state:
            result = st.session_state['division_result']

            st.markdown("---")
            st.markdown("### 📋 분할 계획")

            # 요약 카드
            summary = result['summary']
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("총 수량", f"{summary['total_quantity']:,}주")
            with col2:
                st.metric("총 투자금", f"{summary['total_invested']:,.0f}원")
            with col3:
                st.metric("평균 단가", f"{summary['avg_price']:,.0f}원")
            with col4:
                diff = summary['vs_base_price']
                st.metric("기준가 대비", f"{diff:+.2f}%",
                         delta=f"{'유리' if (diff < 0 and dir_key == 'buy') or (diff > 0 and dir_key == 'sell') else '불리'}")

            # 상세 테이블
            st.markdown("#### 📊 단계별 상세")
            df_data = []
            for div in result['divisions']:
                df_data.append({
                    '단계': f"{div['step']}차",
                    '목표가': f"{div['target_price']:,.0f}원",
                    '변동': f"{div['change_pct']:+.0f}%",
                    '비중': f"{div['ratio']:.1f}%",
                    '금액': f"{div['amount']:,.0f}원",
                    '수량': f"{div['quantity']:,}주",
                    '누적수량': f"{div['cumulative_qty']:,}주",
                    '평균단가': f"{div['avg_price']:,.0f}원"
                })

            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 시각화
            st.markdown("#### 📈 분할 구조 시각화")
            fig = go.Figure()

            prices = [d['target_price'] for d in result['divisions']]
            ratios = [d['ratio'] for d in result['divisions']]
            steps = [f"{d['step']}차" for d in result['divisions']]

            # 가격 라인
            fig.add_trace(go.Scatter(
                x=steps,
                y=prices,
                mode='lines+markers+text',
                name='목표가',
                line=dict(color='#667eea', width=3),
                marker=dict(size=12),
                text=[f"{p:,.0f}" for p in prices],
                textposition='top center'
            ))

            # 비중 막대
            fig.add_trace(go.Bar(
                x=steps,
                y=[r * max(prices) / 100 for r in ratios],
                name='비중',
                marker_color='rgba(102, 126, 234, 0.3)',
                text=[f"{r:.1f}%" for r in ratios],
                textposition='auto',
                yaxis='y2'
            ))

            # 기준가 라인
            fig.add_hline(y=result['base_price'], line_dash="dash",
                         line_color="red", annotation_text=f"기준가: {result['base_price']:,.0f}원")

            fig.update_layout(
                title=f"{'삼각' if '삼각' in division_type else ('다이아몬드' if '다이아몬드' in division_type else '균등')} 분할 {'매수' if dir_key == 'buy' else '매도'} 계획",
                xaxis_title="단계",
                yaxis_title="가격 (원)",
                yaxis2=dict(overlaying='y', side='right', showticklabels=False),
                height=400,
                showlegend=True
            )

            st.plotly_chart(fig, use_container_width=True)

            # 메모 영역
            st.markdown("#### 📝 메모")
            memo = st.text_area(
                "분할 계획에 대한 메모를 입력하세요",
                placeholder="예: 삼성전자 분할 매수 계획, 1차 매수 완료 시 2차 대기...",
                key="division_memo"
            )
