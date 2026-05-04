"""
차트 전략 페이지 - 기술적 분석 기법 해석법
neurotrader888 기반 기술적 차트 분석 전략 + 종목 검색
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import os
import sys

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection

# 공통 기술적 지표 모듈 import
from dashboard.utils.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger,
    calculate_volume_ratio,
    calculate_williams_r,
    calculate_williams_r_series,
    get_rsi_signal,
    get_macd_signal,
    get_bollinger_signal,
    get_williams_r_signal,
    calculate_moving_averages,
    detect_box_range,
    detect_box_breakout,
    calculate_volume_profile,  # 매물대 계산
    # 스크리너 분석용 추가 import
    analyze_swing_patterns,
    detect_new_high_trend,
    analyze_divergence,
)

# 공통 차트 유틸리티 import (중복 코드 제거)
from dashboard.utils.chart_utils import (
    render_candlestick_chart,
    detect_swing_points,  # chart_utils로 통합됨
    render_investor_trend,  # 투자자 매매동향 컴포넌트
)

# 홈 퀀트분석 함수 import (종목검색 결과에 퀀트분석 표시용)
from dashboard.views.home import (
    _render_quant_analysis_section,
    _get_chart_technical_analysis,
)

# 시총·상장주식수 일괄 캐시
from data.market_data_cache import (
    get_market_cap_for,
    format_market_cap,
    format_shares,
    get_sector_cached,
    get_detailed_sector_cached,
)
# 피보나치 + 200MA confluence + 매매 판단
from utils.fibonacci import detect_ma200_fibonacci_confluence, interpret_fib_ma200

# 스크리너 로직 모듈 import (screener.py → screener_logic.py로 이전됨)
from dashboard.views.screener_logic import (
    # 개별 종목 분석 표시 함수 (스윙/태쏘/다이버전스)
    _display_single_stock_indicators,
    _display_single_stock_swing,
    _display_single_stock_tasso,
    _display_single_stock_divergence,
    # 스크리너 탭 렌더링 함수
    _render_condition_screener,
    _render_signal_scanner,
    _render_advanced_analysis,
)

# 차트 매매 전략 로직 모듈 import (strategy.py → strategy_chart_logic.py로 이전됨)
from dashboard.views.strategy_chart_logic import (
    _render_chart_strategy_section,
)


def render_chart_strategy():
    """차트 전략 페이지 렌더링"""

    # 헤더
    st.markdown("""
    <div style='margin-bottom: 2rem;'>
        <h1 style='display: flex; align-items: center; gap: 0.75rem;'>
            <span style='font-size: 2rem;'>📊</span>
            <span style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>차트 전략 & 기술적 분석</span>
        </h1>
        <p style='color: #888;'>neurotrader888 기반 자동화된 기술적 분석 기법</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = get_api_connection()

    # 탭 생성 (스크리너 + 차트매매전략 통합)
    tabs = st.tabs([
        "🏆 종합 추천",
        "📈 추세선 분석",
        "🎯 조화 패턴",
        "👤 머리어깨",
        "🚩 깃발/페넌트",
        "📐 피보나치",
        "🔄 방향성 변화",
        "📊 지지/저항",
        "🧪 전략 검증",
        "🔍 조건 검색",
        "🎯 시그널 스캐너",
        "🔬 고급 분석",
        "📊 차트 매매",
    ])

    with tabs[0]:
        _render_comprehensive_recommendation_section(api)

    with tabs[1]:
        _render_trendline_section(api)

    with tabs[2]:
        _render_harmonic_section(api)

    with tabs[3]:
        _render_head_shoulders_section(api)

    with tabs[4]:
        _render_flags_pennants_section(api)

    with tabs[5]:
        _render_fibonacci_section(api)

    with tabs[6]:
        _render_directional_change_section(api)

    with tabs[7]:
        _render_support_resistance_section(api)

    with tabs[8]:
        _render_strategy_validation_section(api)

    with tabs[9]:
        _render_condition_screener(api)

    with tabs[10]:
        _render_signal_scanner(api)

    with tabs[11]:
        _render_advanced_analysis(api)

    with tabs[12]:
        _render_chart_strategy_section(api)


# _get_api_connection 함수는 dashboard/utils/api_helper.py로 통합됨
# 아래 호출부에서 get_api_connection() 사용


def _get_stock_data(api, code: str, days: int = 120):
    """종목 데이터 조회"""
    if api is None:
        return None
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = api.get_daily_price(code, start_date, end_date)
        if df is not None and not df.empty and 'date' in df.columns:
            df = df.set_index('date')
        return df
    except Exception as e:
        return None


def _get_stock_data_weekly(api, code: str, weeks: int = 52):
    """종목 주봉 데이터 조회"""
    if api is None:
        print(f"[주봉] {code}: API 없음")
        return None
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        # 주봉은 더 긴 기간 필요 (최소 2년치)
        start_date = (datetime.now() - timedelta(weeks=max(weeks, 104))).strftime("%Y%m%d")
        print(f"[주봉] {code}: 요청 기간 {start_date} ~ {end_date}")

        df = api.get_daily_price(code, start_date, end_date, period="W")

        # 데이터 유효성 검사
        if df is None or df.empty:
            print(f"[주봉] {code}: 데이터 없음 - API 반환값 확인 필요")
            return None

        print(f"[주봉] {code}: 데이터 {len(df)}개 로드됨")

        # 필수 컬럼 확인
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"[주봉] {code}: 필수 컬럼 누락 - {missing_cols}, 현재 컬럼: {list(df.columns)}")
            return None

        # date 컬럼 인덱스 설정
        if 'date' in df.columns:
            # 날짜 형식 확인 및 변환
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        elif df.index.name != 'date':
            # 인덱스가 이미 날짜형이 아니면 처리
            if not isinstance(df.index, pd.DatetimeIndex):
                print(f"[주봉] {code}: 날짜 인덱스 없음, 인덱스 타입: {type(df.index)}")
                return None

        # 정렬
        df = df.sort_index()

        # 데이터 개수 확인 (주봉은 2개 이상이면 표시)
        if len(df) < 2:
            print(f"[주봉] {code}: 데이터 부족 ({len(df)}개)")
            return None

        print(f"[주봉] {code}: 최종 {len(df)}개 데이터 반환")
        return df
    except Exception as e:
        import traceback
        print(f"[주봉] {code}: 오류 - {e}")
        traceback.print_exc()
        return None


def _render_stock_chart(api, code: str, name: str, key_prefix: str):
    """종목 차트 렌더링 (일봉/주봉 + 이동평균선 + 매물대)

    Note: 차트 렌더링은 chart_utils.render_candlestick_chart 사용
    """

    # API null 체크
    if api is None:
        st.error("API 연결이 필요합니다. 페이지를 새로고침 해주세요.")
        return

    # 세션 상태 키
    chart_type_key = f"{key_prefix}_chart_type_{code}"
    vp_key = f"{key_prefix}_vp_{code}"
    daily_data_key = f"{key_prefix}_daily_data_{code}"
    weekly_data_key = f"{key_prefix}_weekly_data_{code}"

    # 차트 옵션 - 라디오 버튼으로 변경 (rerun 안정성)
    opt_col1, opt_col2, opt_col3 = st.columns([2, 1, 1])

    # 현재 차트 타입 (세션에서 가져오기)
    if chart_type_key not in st.session_state:
        st.session_state[chart_type_key] = "일봉"

    # 라디오 버튼으로 일봉/주봉 선택 (rerun 안정적)
    with opt_col1:
        chart_type = st.radio(
            "차트 타입",
            ["일봉", "주봉"],
            index=0 if st.session_state[chart_type_key] == "일봉" else 1,
            key=f"{key_prefix}_chart_radio_{code}",
            horizontal=True,
            label_visibility="collapsed"
        )
        st.session_state[chart_type_key] = chart_type

    with opt_col2:
        show_volume_profile = st.checkbox("매물대", value=True, key=f"{key_prefix}_vp_{code}")

    with opt_col3:
        show_swing_points = st.checkbox("저점/고점", value=True, key=f"{key_prefix}_swing_{code}")

    # 박스권은 항상 표시 (체크박스 제거)
    show_box_range = True

    # 데이터 로드 (세션 캐싱)
    if chart_type == "일봉":
        # 일봉 데이터 캐싱
        if daily_data_key not in st.session_state or st.session_state[daily_data_key] is None:
            st.session_state[daily_data_key] = _get_stock_data(api, code, days=180)
        data = st.session_state[daily_data_key]
        period_label = "일봉"
    else:
        # 주봉 데이터 캐싱
        if weekly_data_key not in st.session_state or st.session_state[weekly_data_key] is None:
            st.session_state[weekly_data_key] = _get_stock_data_weekly(api, code, weeks=104)
        data = st.session_state[weekly_data_key]
        period_label = "주봉"

        # 주봉 데이터가 없으면 일봉으로 폴백
        if data is None or len(data) == 0:
            st.warning("주봉 데이터를 불러올 수 없어 일봉으로 표시합니다.")
            if daily_data_key not in st.session_state or st.session_state[daily_data_key] is None:
                st.session_state[daily_data_key] = _get_stock_data(api, code, days=365)
            data = st.session_state[daily_data_key]
            period_label = "일봉 (주봉 대체)"

    if data is None or len(data) == 0:
        st.warning("차트 데이터를 불러올 수 없습니다.")
        return

    # 공통 차트 유틸리티 사용 (중복 코드 제거)
    try:
        render_candlestick_chart(
            data=data,
            code=code,
            name=name,
            key_prefix=key_prefix,
            title=f"{name} ({code}) - {period_label}",
            height=500,
            show_ma=True,
            show_volume=True,
            show_volume_profile=show_volume_profile,
            show_swing_points=show_swing_points,
            show_box_range=show_box_range,
            ma_periods=[5, 20, 60, 120, 200]
        )
    except Exception as e:
        import traceback
        st.error(f"차트 렌더링 오류: {e}")
        print(f"[차트 오류] {code}: {e}")
        traceback.print_exc()
        # 박스권 비활성화 상태로 기본 차트 표시 시도
        try:
            render_candlestick_chart(
                data=data,
                code=code,
                name=name,
                key_prefix=f"{key_prefix}_fallback",
                title=f"{name} ({code}) - {period_label} (기본)",
                height=500,
                show_ma=True,
                show_volume=True,
                show_volume_profile=False,
                show_swing_points=False,
                show_box_range=False,
                ma_periods=[5, 20, 60, 120, 200]
            )
        except Exception as e2:
            st.error(f"기본 차트도 표시할 수 없습니다: {e2}")


def _render_stock_finder(api, strategy_name: str, find_func, key_prefix: str):
    """종목 검색 공통 컴포넌트"""
    st.markdown("---")
    st.subheader(f"🔍 {strategy_name} 종목 찾기")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key=f"{key_prefix}_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key=f"{key_prefix}_count")
    with col3:
        if st.button("🔎 검색", key=f"{key_prefix}_search", type="primary"):
            st.session_state[f'{key_prefix}_searching'] = True
            st.session_state[f'{key_prefix}_stock_count'] = stock_count

    if st.session_state.get(f'{key_prefix}_searching', False):
        count = st.session_state.get(f'{key_prefix}_stock_count', 100)
        with st.spinner(f"{strategy_name} 패턴 검색 중... ({count}개 종목)"):
            results = find_func(api, market, count)

        if results:
            st.success(f"✅ {len(results)}개 종목 발견!")
            # 페이지당 표시 개수 선택
            items_per_page = st.select_slider(
                "표시 개수",
                options=[15, 30, 50, 100, "전체"],
                value=15,
                key=f"{key_prefix}_items_per_page"
            )
            display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
            for i, stock in enumerate(results[:display_count]):
                _render_stock_card(stock, api=api, key_prefix=f"{key_prefix}_{i}")
            if display_count < len(results):
                st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
        else:
            st.info("조건에 맞는 종목이 없습니다.")

        st.session_state[f'{key_prefix}_searching'] = False


def _render_head_shoulders_stock_finder(api):
    """머리어깨 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 머리어깨 패턴 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="hs_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="hs_count")

    st.markdown("**패턴 선택** (복수 선택 가능)")
    col1, col2 = st.columns(2)
    with col1:
        head_shoulders = st.checkbox("📉 머리어깨 천장 (약세 반전)", value=True, key="hs_top")
    with col2:
        inv_head_shoulders = st.checkbox("📈 역머리어깨 (강세 반전)", value=True, key="hs_bottom")

    if st.button("🔎 패턴 검색 시작", key="hs_search", type="primary"):
        selected_patterns = []
        if head_shoulders:
            selected_patterns.append('head_shoulders')
        if inv_head_shoulders:
            selected_patterns.append('inv_head_shoulders')

        if not selected_patterns:
            st.warning("최소 1개 이상의 패턴을 선택해주세요.")
        else:
            with st.spinner(f"머리어깨 패턴 검색 중... (패턴: {len(selected_patterns)}개)"):
                results = _find_head_shoulders_by_pattern(api, market, stock_count, selected_patterns)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="hs_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_head_shoulders_card(stock, api=api, key_prefix=f"hs_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_harmonic_stock_finder(api):
    """조화 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 조화 패턴 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="harmonic_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="harmonic_count")

    st.markdown("**패턴 선택** (복수 선택 가능)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        gartley = st.checkbox("🦋 Gartley (78.6%)", value=True, key="harmonic_gartley")
    with col2:
        bat = st.checkbox("🦇 Bat (88.6%)", value=True, key="harmonic_bat")
    with col3:
        butterfly = st.checkbox("🦋 Butterfly (127%)", value=False, key="harmonic_butterfly")
    with col4:
        crab = st.checkbox("🦀 Crab (161.8%)", value=False, key="harmonic_crab")

    if st.button("🔎 패턴 검색 시작", key="harmonic_search", type="primary"):
        selected_patterns = []
        if gartley:
            selected_patterns.append('gartley')
        if bat:
            selected_patterns.append('bat')
        if butterfly:
            selected_patterns.append('butterfly')
        if crab:
            selected_patterns.append('crab')

        if not selected_patterns:
            st.warning("최소 1개 이상의 패턴을 선택해주세요.")
        else:
            with st.spinner(f"조화 패턴 검색 중... (패턴: {len(selected_patterns)}개)"):
                results = _find_harmonic_by_pattern(api, market, stock_count, selected_patterns)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="harmonic_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_harmonic_stock_card(stock, api=api, key_prefix=f"harmonic_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_card_addons(api, code: str):
    """모든 차트전략 카드에 공통으로 붙는 부가정보:
    - 섹터 / 주요분야 (네이버 금융 + 정적 매핑)
    - 시가총액 / 상장주식수 (pykrx 일괄 캐시)
    - 200MA + 피보나치 confluence 요약 (있을 때만)
    """
    try:
        cap_info = get_market_cap_for(code) or {}
        cap_val = int(cap_info.get('market_cap', 0))
        shares_val = int(cap_info.get('shares', 0))
    except Exception:
        cap_val = shares_val = 0

    # 섹터 / 주요분야
    try:
        sector_info = get_detailed_sector_cached(code) or {}
        sector_label = sector_info.get('sub_sector') or sector_info.get('sector') or get_sector_cached(code)
        industry_label = sector_info.get('industry')
    except Exception:
        sector_label = '기타'
        industry_label = None

    # 한 줄에 섹터 / 시총 / 상장주식수
    c1, c2, c3 = st.columns(3)
    with c1:
        if industry_label and industry_label != sector_label:
            st.markdown(f"🏷️ **섹터:** {sector_label} <span style='color:#888;'>· {industry_label}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"🏷️ **섹터:** {sector_label}")
    with c2:
        st.markdown(f"💰 **시가총액:** {format_market_cap(cap_val) if cap_val else '-'}")
    with c3:
        st.markdown(f"📊 **상장주식수:** {format_shares(shares_val) if shares_val else '-'}")

    # 200MA + 피보나치 confluence + 매매 판단 한 줄 결론
    if api is not None:
        try:
            df = api.get_daily_price(code, period="D")
            if df is not None and not df.empty and len(df) >= 60:
                close_s = df['close']
                # confluence
                if len(close_s) >= 200:
                    conf = detect_ma200_fibonacci_confluence(close_s, lookback=120, tolerance_pct=2.0)
                    if conf and conf.get('matched'):
                        best = conf['matched'][0]
                        zone = conf.get('price_zone', '중립')
                        zone_emoji = {'지지권':'🟢','저항권':'🔴','근접':'🟡','중립':'⚪'}.get(zone, '⚪')
                        st.caption(
                            f"{zone_emoji} **200MA·피보 {best['level']} confluence** "
                            f"({zone}) · 200MA {conf['ma200']:,.0f}원 · 레벨가 {best['price']:,.0f}원"
                        )
                # 매매 판단 (분할 매수 / 보유중 두 가지 결론만 압축 표시)
                interp = interpret_fib_ma200(close_s, lookback=120)
                if interp:
                    verdicts = {v['style']: v for v in interp.get('verdicts', [])}
                    split = verdicts.get('📦 분할매수 (중장기)')
                    hold = verdicts.get('🤝 보유중')
                    short = verdicts.get('⚡ 단기 트레이딩')
                    badge_color = {'🔴':'#ef4444','🟡':'#f59e0b','🟢':'#22c55e','⚪':'#888'}
                    pieces = []
                    for v in (split, hold, short):
                        if v:
                            emoji = v['badge'][0]
                            color = badge_color.get(emoji, '#888')
                            pieces.append(
                                f"<span style='background:#0d1421; padding:3px 8px; border-radius:6px; "
                                f"border-left:3px solid {color}; font-size:0.85rem;'>"
                                f"<b style='color:{color};'>{v['badge']}</b> "
                                f"<span style='color:#aaa;'>{v['style'].split(' ',1)[1] if ' ' in v['style'] else v['style']}</span></span>"
                            )
                    if pieces:
                        st.markdown(
                            "<div style='display:flex; gap:0.4rem; flex-wrap:wrap; margin:0.4rem 0;'>"
                            + "".join(pieces) + "</div>",
                            unsafe_allow_html=True
                        )
        except Exception:
            pass


def _render_stock_card(stock: dict, api=None, key_prefix: str = "stock"):
    """종목 카드 렌더링 (진입가, 손절가, 목표가 포함 + 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 매매 전략 정보 (있는 경우에만 표시)
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**현재가:** {current_price:,.0f}원")
            with col2:
                # 추천 진입가와 현재가 비교
                entry_diff = ((entry_price - current_price) / current_price) * 100 if current_price > 0 else 0
                if entry_diff > 0:
                    st.markdown(f"🎯 **추천진입:** {entry_price:,.0f}원 (+{entry_diff:.1f}%)")
                else:
                    st.markdown(f"🎯 **추천진입:** {entry_price:,.0f}원 ({entry_diff:.1f}%)")
            with col3:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:.1f}%)")
            with col4:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 (+{profit_pct:.1f}%)")

            # R:R 비율
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            st.caption(f"📊 R:R = 1:{rr_ratio:.1f} | {reason}")
        else:
            st.caption(f"{reason}")

        # 시총/상장주식수 + 200MA·피보 confluence
        _render_card_addons(api, code)

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _render_head_shoulders_card(stock: dict, api=None, key_prefix: str = "hs"):
    """머리어깨 패턴 종목 카드 렌더링 (어깨, 머리, 넥라인 정보 포함 + 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)

    # 머리어깨 패턴 정보
    left_shoulder = stock.get('left_shoulder', 0)
    head = stock.get('head', 0)
    right_shoulder = stock.get('right_shoulder', 0)
    neckline = stock.get('neckline', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        # 종목명 및 기본 정보
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 패턴 구조 표시 (왼쪽어깨 - 머리 - 오른쪽어깨)
        if left_shoulder > 0 and head > 0 and right_shoulder > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**현재가:** {current_price:,.0f}원")
            with col2:
                st.markdown(f"👈 **L어깨:** {left_shoulder:,.0f}")
            with col3:
                st.markdown(f"👤 **머리:** {head:,.0f}")
            with col4:
                st.markdown(f"👉 **R어깨:** {right_shoulder:,.0f}")

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"📍 **넥라인:** {neckline:,.0f}원")
            with col2:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col3:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col4:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")

            # R:R 비율
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            st.caption(f"📊 R:R = 1:{rr_ratio:.1f} | {reason}")
        else:
            st.caption(f"{reason}")

        # 시총/상장주식수 + 200MA·피보 confluence
        _render_card_addons(api, code)

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _render_harmonic_stock_card(stock: dict, api=None, key_prefix: str = "harmonic"):
    """조화 패턴 종목 카드 렌더링 (진입가, 손절가, 목표가 포함 + 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_a = stock.get('target_a', 0)
    target_c = stock.get('target_c', 0)
    d_point = stock.get('d_point', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        # 종목명 및 기본 정보
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 매매 전략 정보
        if entry_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**현재가:** {current_price:,.0f}원")
            with col2:
                # 진입가: D 포인트에서 반전 캔들 종가
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col3:
                # 손절: D 포인트 약간 아래/위
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:.1f}%)")
            with col4:
                # 목표가: A 또는 C 포인트
                profit_pct = ((target_a - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표가:** {target_a:,.0f}원 (+{profit_pct:.1f}%)")

            # 리스크/리워드 비율
            if stop_loss > 0 and target_a > 0 and entry_price > 0:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_a - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.caption(f"📊 R:R = 1:{rr_ratio:.1f} | D포인트: {d_point:,.0f}원 | 목표C: {target_c:,.0f}원")

        # 시총/상장주식수 + 200MA·피보 confluence
        _render_card_addons(api, code)

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_harmonic_by_pattern(api, market: str, stock_count, selected_patterns: list) -> list:
    """패턴별 조화 패턴 종목 찾기 - 진입가, 손절가, 목표가 계산 포함

    조화 패턴 매매 전략 (사용자 요청):
    1. 패턴 완성 대기: D 포인트가 형성될 때까지 관망
    2. 확인 캔들: D 포인트에서 반전 캔들 (망치형, 장악형) 확인
    3. 진입: 반전 캔들 종가에서 진입
    4. 손절: D 포인트 약간 아래/위
    5. 목표가: A 또는 C 포인트 수준
    """
    results = []
    stocks = _get_market_stocks(market)

    # 검색할 종목 수 결정
    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    # 패턴별 피보나치 수준 정의 (X-A-B-C-D 패턴)
    # D 포인트 = XA의 되돌림/확장 비율
    pattern_levels = {
        'gartley': {
            'name': 'Gartley',
            'd_level': 0.786,      # D = XA의 78.6% 되돌림
            'ab_level': 0.618,     # AB = XA의 61.8%
            'bc_range': (0.382, 0.886),  # BC = AB의 38.2~88.6%
            'tolerance': 0.03,
            'stop_buffer': 0.02    # 손절 버퍼 2%
        },
        'bat': {
            'name': 'Bat',
            'd_level': 0.886,      # D = XA의 88.6% 되돌림
            'ab_level': 0.50,      # AB = XA의 38.2~50%
            'bc_range': (0.382, 0.886),
            'tolerance': 0.03,
            'stop_buffer': 0.02
        },
        'butterfly': {
            'name': 'Butterfly',
            'd_level': 1.272,      # D = XA의 127.2% 확장
            'ab_level': 0.786,     # AB = XA의 78.6%
            'bc_range': (0.382, 0.886),
            'tolerance': 0.05,
            'stop_buffer': 0.03
        },
        'crab': {
            'name': 'Crab',
            'd_level': 1.618,      # D = XA의 161.8% 확장
            'ab_level': 0.618,     # AB = XA의 38.2~61.8%
            'bc_range': (0.382, 0.886),
            'tolerance': 0.05,
            'stop_buffer': 0.03
        },
    }

    progress = st.progress(0)
    total = len(search_stocks)

    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 90)
            if data is None or len(data) < 60:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            current = closes[-1]
            change_rate = (closes[-1] - closes[-2]) / closes[-2] * 100

            # X-A-B-C-D 포인트 식별 (간소화된 방식)
            # 최근 60일을 4구간으로 나눠서 고점/저점 탐색
            period = 15

            if len(highs) < 60:
                continue

            # 구간별 고점/저점 찾기
            seg1_high = np.max(highs[-60:-45])
            seg1_low = np.min(lows[-60:-45])
            seg2_high = np.max(highs[-45:-30])
            seg2_low = np.min(lows[-45:-30])
            seg3_high = np.max(highs[-30:-15])
            seg3_low = np.min(lows[-30:-15])
            seg4_high = np.max(highs[-15:])
            seg4_low = np.min(lows[-15:])

            # 강세 조화패턴 탐지 (X=저점, A=고점, B=저점, C=고점, D=저점)
            # 패턴: 상승 후 하락 조정, D에서 반등 기대
            x_point = seg1_low   # X: 시작 저점
            a_point = max(seg1_high, seg2_high)  # A: 첫 고점
            b_point = min(seg2_low, seg3_low)     # B: 조정 저점
            c_point = max(seg3_high, seg4_high)   # C: 반등 고점

            xa_range = a_point - x_point
            if xa_range <= 0:
                continue

            # 각 선택된 패턴에 대해 검사
            for pattern_key in selected_patterns:
                pattern_info = pattern_levels[pattern_key]
                d_level = pattern_info['d_level']
                tolerance = pattern_info['tolerance']
                pattern_name = pattern_info['name']
                stop_buffer = pattern_info['stop_buffer']

                if d_level < 1:  # 되돌림 패턴 (Gartley, Bat) - 강세 패턴
                    # D 포인트 예상 위치 (A에서 XA의 d_level% 만큼 하락한 지점)
                    d_point = a_point - xa_range * d_level

                    # 조건: 현재가가 D 포인트 근처이고, D 포인트 위에 있어야 함 (반등 시작)
                    # 현재가 >= D포인트 (이미 반등 시작) and 현재가 < D포인트 * 1.05 (너무 멀지 않음)
                    near_d_point = current >= d_point * 0.98 and current <= d_point * (1 + tolerance)

                    if near_d_point:
                        # 매매 전략: D 포인트에서 반등 매수
                        entry_price = current  # 진입: 현재가
                        stop_loss = d_point * (1 - stop_buffer)  # 손절: D 포인트 아래
                        target_a = a_point  # 목표가 1: A 포인트
                        target_c = c_point  # 목표가 2: C 포인트

                        # 유효성 검사: 손절 < 진입 < 목표
                        if stop_loss < entry_price < target_a:
                            # R:R 계산
                            risk = entry_price - stop_loss
                            reward = target_a - entry_price
                            if risk > 0 and reward / risk >= 1.5:  # 최소 R:R 1:1.5
                                results.append({
                                    'code': code,
                                    'name': name,
                                    'signal': f'{pattern_name} 패턴 (강세)',
                                    'reason': f'D포인트({d_point:,.0f}) 반등, A점({a_point:,.0f}) 목표',
                                    'change_rate': change_rate,
                                    'current_price': current,
                                    'entry_price': entry_price,
                                    'stop_loss': stop_loss,
                                    'target_a': target_a,
                                    'target_c': target_c,
                                    'd_point': d_point,
                                    'x_point': x_point,
                                    'a_point': a_point
                                })
                                break

                else:  # 확장 패턴 (Butterfly, Crab) - 하락 후 반전 매수
                    # 확장 패턴 구조: X=고점에서 시작, A=저점, D=A보다 더 아래 (확장)
                    # D 포인트에서 반등 기대 → 목표는 B 또는 C (고점)
                    x_point_ext = seg1_high  # X: 시작 고점
                    a_point_ext = min(seg1_low, seg2_low)  # A: 첫 저점
                    b_point_ext = max(seg2_high, seg3_high)  # B: 반등 고점
                    c_point_ext = min(seg3_low, seg4_low)  # C: 재하락 저점
                    xa_range_ext = x_point_ext - a_point_ext

                    if xa_range_ext <= 0:
                        continue

                    # D 포인트: XA의 161.8% 확장 (A보다 더 아래)
                    d_point = x_point_ext - xa_range_ext * d_level

                    if d_point > 0 and abs(current - d_point) / d_point < tolerance:
                        entry_price = current  # 진입: 현재가 (D 포인트 근처)
                        stop_loss = d_point * (1 - stop_buffer)  # 손절: D 포인트 아래
                        # 목표가: B 포인트 (반등 고점) - 확장 패턴에서 반등 목표
                        target_b = b_point_ext
                        target_a = a_point_ext  # 2차 목표: A 포인트

                        # R:R이 최소 1:1.5 이상인 경우만 추가
                        risk = entry_price - stop_loss
                        reward = target_b - entry_price
                        if risk > 0 and reward / risk >= 1.5:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': f'{pattern_name} 패턴 (반전)',
                                'reason': f'D포인트 {d_level*100:.1f}% 확장, B점 반등 목표',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'target_a': target_b,  # 1차 목표: B 포인트 (반등 고점)
                                'target_c': target_a,  # 2차 목표: A 포인트
                                'd_point': d_point,
                                'x_point': x_point_ext,
                                'a_point': a_point_ext
                            })
                            break
        except:
            continue

    progress.empty()
    return results


def _find_trendline_stocks(api, market: str, stock_count=100) -> list:
    """추세선 돌파/터치 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    # 검색할 종목 수 결정
    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 20:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            ma5 = data['close'].rolling(5).mean().values
            ma20 = data['close'].rolling(20).mean().values
            ma60 = data['close'].rolling(60).mean().values
            change_rate = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] != 0 else 0
            current = closes[-1]

            # 최근 고점/저점
            recent_high = np.max(highs[-20:])
            recent_low = np.min(lows[-20:])

            # 조건 1: 20일선 위에서 상승 중
            if len(ma20) > 1 and not np.isnan(ma20[-1]):
                if closes[-1] > ma20[-1] and closes[-1] > closes[-5]:
                    # 추천 진입가: 20일선 근처로 눌림목 대기 (20일선 + 1%)
                    entry = ma20[-1] * 1.01  # 20일선 1% 위에서 진입 추천
                    stop = ma20[-1] * 0.98
                    target = recent_high * 1.05  # 최근 고점 5% 위
                    # 유효성: 손절 < 진입 < 목표
                    if stop < entry < target:
                        risk = entry - stop
                        reward = target - entry
                        if risk > 0 and reward / risk >= 1.0:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '상승 추세',
                                'reason': f'20일선({ma20[-1]:,.0f}) 지지 상승',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
                # 조건 2: 20일선 근처 지지 (눌림목 매수)
                elif abs(closes[-1] - ma20[-1]) / ma20[-1] < 0.03:
                    # 추천 진입가: 20일선에서 지지 확인 후 진입
                    entry = ma20[-1] * 1.005  # 20일선 0.5% 위에서 반등 확인 후 진입
                    stop = ma20[-1] * 0.97  # 지지선 3% 아래
                    target = recent_high * 1.02
                    if stop < entry < target:
                        risk = entry - stop
                        reward = target - entry
                        if risk > 0 and reward / risk >= 1.0:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '지지선 테스트',
                                'reason': f'20일선({ma20[-1]:,.0f}) 눌림목',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
        except:
            continue

    progress.empty()
    return results


def _find_golden_cross_stocks(api, market: str, stock_count=100) -> list:
    """골든크로스 / 정배열 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 120)
            if data is None or len(data) < 60:
                continue

            ma5 = data['close'].rolling(5).mean()
            ma20 = data['close'].rolling(20).mean()
            ma60 = data['close'].rolling(60).mean()
            current = data['close'].iloc[-1]
            prev_close = data['close'].iloc[-2]
            change_rate = (current - prev_close) / prev_close * 100 if prev_close != 0 else 0
            recent_high = data['high'].max()
            recent_low = data['low'].iloc[-20:].min()

            # 조건 1: 골든크로스 (최근 5일 이내)
            for j in range(1, 6):
                if len(ma5) > j+1 and len(ma20) > j+1:
                    if ma5.iloc[-j-1] < ma20.iloc[-j-1] and ma5.iloc[-j] >= ma20.iloc[-j]:
                        entry = current
                        stop = ma20.iloc[-1] * 0.97  # 20일선 3% 아래
                        target = recent_high * 1.05  # 최근 고점 5% 위
                        # 유효성 검증: 손절 < 진입 < 목표
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '골든크로스',
                                'reason': f'{j}일 전 5일선이 20일선 돌파',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
                        break
            else:
                # 조건 2: 정배열 (5일 > 20일 > 60일)
                if (len(ma5) > 0 and len(ma20) > 0 and len(ma60) > 0 and
                    not np.isnan(ma5.iloc[-1]) and not np.isnan(ma20.iloc[-1]) and not np.isnan(ma60.iloc[-1])):
                    if ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]:
                        entry = current
                        stop = ma20.iloc[-1] * 0.98  # 20일선 2% 아래
                        target = recent_high * 1.03
                        # 유효성 검증: 손절 < 진입 < 목표
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '정배열',
                                'reason': 'MA5 > MA20 > MA60',
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target,
                                'change_rate': change_rate
                            })
        except:
            continue

    progress.empty()
    return results


def _find_oversold_stocks(api, market: str, stock_count=100) -> list:
    """과매도/과매수 종목 찾기 (RSI 기반) - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 20:
                continue

            # RSI 계산
            delta = data['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current = data['close'].iloc[-1]
            prev_close = data['close'].iloc[-2]
            change_rate = (current - prev_close) / prev_close * 100 if prev_close != 0 else 0

            # 최근 고점/저점
            recent_high = data['high'].iloc[-20:].max()
            recent_low = data['low'].iloc[-20:].min()

            if len(rsi) > 0 and not np.isnan(rsi.iloc[-1]):
                if rsi.iloc[-1] < 30:  # 과매도 - 매수 기회
                    entry = current
                    stop = recent_low * 0.97  # 최근 저점 3% 아래
                    target = recent_high * 0.95  # 최근 고점의 95%
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '과매도',
                            'reason': f'RSI {rsi.iloc[-1]:.1f} (30 미만) - 반등 기대',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
                elif rsi.iloc[-1] < 40:  # 약한 과매도
                    entry = current
                    stop = recent_low * 0.98
                    target = recent_high * 0.90
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '약한 과매도',
                            'reason': f'RSI {rsi.iloc[-1]:.1f} (30-40) - 반등 가능',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
                elif rsi.iloc[-1] > 70:  # 과매수 - 조정 후 재진입 관점 (롱 포지션)
                    # 과매수 구간에서는 조정을 기다린 후 지지선 반등 매수 전략
                    # 진입가: 최근 고점의 95% (조정 후 매수)
                    entry = recent_high * 0.95
                    stop = recent_low * 0.98  # 최근 저점 아래
                    target = recent_high * 1.05  # 전고점 돌파 목표
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '과매수 조정 대기',
                            'reason': f'RSI {rsi.iloc[-1]:.1f} (70 초과) - 조정 후 재진입 대기',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
        except:
            continue

    progress.empty()
    return results


def _find_fibonacci_stocks(api, market: str, stock_count=100) -> list:
    """피보나치 되돌림 종목 찾기 - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            high = data['high'].max()
            low = data['low'].min()
            current = data['close'].iloc[-1]
            prev_close = data['close'].iloc[-2]
            change_rate = (current - prev_close) / prev_close * 100 if prev_close != 0 else 0

            # 피보나치 수준 계산
            fib_236 = high - (high - low) * 0.236
            fib_382 = high - (high - low) * 0.382
            fib_500 = high - (high - low) * 0.500
            fib_618 = high - (high - low) * 0.618
            fib_786 = high - (high - low) * 0.786

            # 각 피보나치 수준 체크 (5% 오차 이내)
            if abs(current - fib_618) / fib_618 < 0.05:
                # 추천 진입가: 61.8% 레벨에서 지지 확인 후 진입
                entry = fib_618 * 1.01  # 61.8% 레벨 1% 위에서 반등 확인 후 진입
                stop = fib_786 * 0.98  # 78.6% 레벨 아래
                target = fib_382  # 38.2% 레벨까지 반등 기대
                # 유효성 검증: 손절 < 진입 < 목표
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '피보나치 61.8%',
                        'reason': f'황금비율 근처 (오차 {abs(current - fib_618) / fib_618 * 100:.1f}%)',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target
                    })
            elif abs(current - fib_500) / fib_500 < 0.05:
                # 추천 진입가: 50% 레벨에서 지지 확인 후 진입
                entry = fib_500 * 1.01  # 50% 레벨 1% 위에서 반등 확인 후 진입
                stop = fib_618 * 0.98  # 61.8% 레벨 아래
                target = fib_236  # 23.6% 레벨까지 반등 기대
                # 유효성 검증: 손절 < 진입 < 목표
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '피보나치 50%',
                        'reason': f'반값 되돌림 근처',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target
                    })
            elif abs(current - fib_382) / fib_382 < 0.05:
                # 추천 진입가: 38.2% 레벨에서 지지 확인 후 진입
                entry = fib_382 * 1.01  # 38.2% 레벨 1% 위에서 반등 확인 후 진입
                stop = fib_500 * 0.98  # 50% 레벨 아래
                target = high * 0.98  # 고점 근처까지 반등 기대
                # 유효성 검증: 손절 < 진입 < 목표
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '피보나치 38.2%',
                        'reason': f'1차 지지선 근처',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target
                    })
        except:
            continue

    progress.empty()
    return results


def _find_volume_breakout_stocks(api, market: str, stock_count=100) -> list:
    """거래량 돌파 종목 찾기 - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 30)
            if data is None or len(data) < 20:
                continue

            avg_volume = data['volume'].iloc[:-1].mean()
            today_volume = data['volume'].iloc[-1]
            current = data['close'].iloc[-1]
            prev_close = data['close'].iloc[-2]
            change_rate = (current - prev_close) / prev_close * 100 if prev_close != 0 else 0

            # 최근 고점/저점
            recent_high = data['high'].iloc[-10:].max()
            recent_low = data['low'].iloc[-10:].min()

            # 거래량 1.5배 이상
            if avg_volume > 0 and today_volume > avg_volume * 1.5:
                if change_rate > 0:  # 상승 + 거래량 급증 = 매수 신호
                    # 추천 진입가: 당일 저가 근처에서 눌림목 매수 대기
                    entry = data['low'].iloc[-1] * 1.02  # 당일 저가 2% 위에서 진입 추천
                    stop = data['low'].iloc[-1] * 0.98  # 당일 저가 2% 아래
                    target = recent_high * 1.05  # 최근 고점 5% 위
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '거래량 급증 상승',
                            'reason': f'평균 대비 {today_volume/avg_volume:.1f}배 + 상승',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
                else:  # 하락 + 거래량 급증 = 바닥 다지기 관점 (롱 포지션)
                    # 추천 진입가: 최근 저점에서 반등 확인 후 진입
                    entry = recent_low * 1.02  # 최근 저점 2% 위에서 반등 확인 후 진입
                    stop = recent_low * 0.97  # 최근 저점 3% 아래
                    target = recent_high  # 최근 고점까지 반등 기대
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '거래량 급증 하락',
                            'reason': f'평균 대비 {today_volume/avg_volume:.1f}배 + 하락 (반등 관찰)',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
        except:
            continue

    progress.empty()
    return results


def _find_bollinger_squeeze_stocks(api, market: str, stock_count=100) -> list:
    """볼린저밴드 수축 후 확장 종목 - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            # 볼린저밴드
            ma20 = data['close'].rolling(20).mean()
            std20 = data['close'].rolling(20).std()
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            bandwidth = (upper - lower) / ma20 * 100
            current = data['close'].iloc[-1]

            # 밴드폭 수축 후 확장
            if len(bandwidth) > 5:
                recent_bw = bandwidth.iloc[-5:].mean()
                prev_bw = bandwidth.iloc[-10:-5].mean()

                if not np.isnan(recent_bw) and not np.isnan(prev_bw):
                    change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

                    # 조건 완화: 15% 이상 확장 또는 상단밴드 근처
                    if recent_bw > prev_bw * 1.15:  # 15% 이상 확장
                        # 추천 진입가: 20일선과 현재가 사이 (눌림목 매수)
                        entry = ma20.iloc[-1] * 1.01  # 20일선 1% 위에서 진입 추천
                        stop = ma20.iloc[-1] * 0.97  # 20일선 3% 아래
                        target = upper.iloc[-1] * 1.02  # 상단밴드 2% 위
                        # 유효성 검증: 손절 < 진입 < 목표
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '볼린저 확장',
                                'reason': f'밴드폭 {((recent_bw/prev_bw)-1)*100:.0f}% 확장',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
                    # 상단밴드 돌파
                    elif current > upper.iloc[-1]:
                        # 추천 진입가: 상단밴드 돌파 후 눌림시 (상단밴드 가격)
                        entry = upper.iloc[-1]  # 상단밴드에서 지지 확인 후 진입
                        stop = ma20.iloc[-1]  # 20일선 (중심선)
                        target = upper.iloc[-1] * 1.05  # 상단밴드 5% 위
                        # 유효성 검증: 손절 < 진입 < 목표
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '상단밴드 돌파',
                                'reason': '볼린저 상단 돌파 - 추세 강화',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
                    # 하단밴드 근처 (반등 기대)
                    elif current < lower.iloc[-1] * 1.02:
                        # 추천 진입가: 하단밴드에서 지지 확인 후 진입
                        entry = lower.iloc[-1]  # 하단밴드에서 반등 확인 후 진입
                        stop = lower.iloc[-1] * 0.97  # 하단밴드 3% 아래
                        target = ma20.iloc[-1]  # 20일선 (중심선)까지 반등
                        # 유효성 검증: 손절 < 진입 < 목표
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '하단밴드 지지',
                                'reason': '볼린저 하단 근처 (반등 기대)',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target
                            })
        except:
            continue

    progress.empty()
    return results


def _get_market_stocks(market: str) -> list:
    """시장별 종목 리스트"""
    if market == "KOSPI":
        return get_kospi_stocks()
    elif market == "KOSDAQ":
        return get_kosdaq_stocks()
    else:
        return get_kospi_stocks() + get_kosdaq_stocks()


def _find_harmonic_pattern_stocks(api, market: str, stock_count=100) -> list:
    """조화 패턴 (피보나치 되돌림 기반) 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 90)
            if data is None or len(data) < 60:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            change_rate = (closes[-1] - closes[-2]) / closes[-2] * 100

            # 최근 60일 내 고점/저점 찾기
            high_idx = np.argmax(highs[-60:])
            low_idx = np.argmin(lows[-60:])
            high_price = highs[-60:][high_idx]
            low_price = lows[-60:][low_idx]
            current = closes[-1]

            # 피보나치 되돌림 수준
            fib_levels = {
                '38.2%': high_price - (high_price - low_price) * 0.382,
                '50.0%': high_price - (high_price - low_price) * 0.500,
                '61.8%': high_price - (high_price - low_price) * 0.618,
                '78.6%': high_price - (high_price - low_price) * 0.786,
            }

            # 하락 후 반등 패턴 (저점이 고점 이후)
            if low_idx > high_idx:
                for level_name, level_price in fib_levels.items():
                    if abs(current - level_price) / level_price < 0.03:  # 3% 오차
                        pattern = "Gartley" if level_name == '78.6%' else "Bat" if level_name == '61.8%' else "일반"
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': f'{pattern} 패턴 가능',
                            'reason': f'피보나치 {level_name} 되돌림 구간',
                            'change_rate': change_rate
                        })
                        break

            # 상승 후 조정 패턴 (고점이 저점 이후)
            elif high_idx > low_idx:
                for level_name, level_price in fib_levels.items():
                    if abs(current - level_price) / level_price < 0.03:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '조정 완료 가능',
                            'reason': f'상승 후 {level_name} 조정 구간',
                            'change_rate': change_rate
                        })
                        break
        except:
            continue

    progress.empty()
    return results


def _find_head_shoulders_by_pattern(api, market: str, stock_count, selected_patterns: list) -> list:
    """패턴별 머리어깨 종목 찾기 - 진입가, 손절가, 목표가 포함

    머리어깨 패턴 구조:
    - 왼쪽어깨(LS): 첫 번째 고점
    - 머리(H): 가장 높은 고점 (LS, RS보다 높음)
    - 오른쪽어깨(RS): 두 번째 고점 (LS와 비슷한 높이)
    - 넥라인(NL): LS-H 사이 저점과 H-RS 사이 저점을 연결

    매매 전략:
    - 머리어깨 천장: 넥라인 이탈 확인 후 매도, 목표 = 넥라인 - (머리-넥라인)
    - 역머리어깨: 넥라인 돌파 확인 후 매수, 목표 = 넥라인 + (넥라인-머리)
    """
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)

    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 90)
            if data is None or len(data) < 60:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            current = closes[-1]
            change_rate = (current - closes[-2]) / closes[-2] * 100

            if len(highs) < 60:
                continue

            # ===== 머리어깨 천장 패턴 (Head & Shoulders Top) =====
            # 하락 반전 신호: 상승 추세 후 천장에서 형성
            if 'head_shoulders' in selected_patterns:
                # 3구간으로 나눠 고점 찾기 (각 20일)
                # 구간1: 왼쪽어깨 [-60:-40], 구간2: 머리 [-40:-20], 구간3: 오른쪽어깨 [-20:]
                ls_idx = np.argmax(highs[-60:-40]) + len(highs) - 60  # 왼쪽어깨 고점 인덱스
                h_idx = np.argmax(highs[-40:-20]) + len(highs) - 40   # 머리 고점 인덱스
                rs_idx = np.argmax(highs[-20:]) + len(highs) - 20     # 오른쪽어깨 고점 인덱스

                left_shoulder = highs[ls_idx]    # 왼쪽어깨 가격
                head = highs[h_idx]              # 머리 가격
                right_shoulder = highs[rs_idx]   # 오른쪽어깨 가격

                # 넥라인: 왼쪽어깨~머리 사이 저점, 머리~오른쪽어깨 사이 저점
                neckline_left = np.min(lows[ls_idx:h_idx]) if h_idx > ls_idx else np.min(lows[-50:-30])
                neckline_right = np.min(lows[h_idx:rs_idx]) if rs_idx > h_idx else np.min(lows[-30:-10])
                neckline = (neckline_left + neckline_right) / 2

                # 패턴 조건 검사
                # 1) 머리가 양 어깨보다 높아야 함 (최소 2% 이상)
                # 2) 양 어깨가 비슷한 높이 (10% 오차 허용)
                # 3) 현재가가 넥라인 근처 또는 아래
                head_higher = head > left_shoulder * 1.02 and head > right_shoulder * 1.02
                shoulders_similar = abs(left_shoulder - right_shoulder) / left_shoulder < 0.10
                near_neckline = current < neckline * 1.05  # 넥라인 5% 위까지

                if head_higher and shoulders_similar and near_neckline:
                    pattern_height = head - neckline  # 패턴 높이
                    drop_target = neckline - pattern_height  # 넥라인 이탈시 하락 목표

                    # 매매 전략: 일반 투자자 (롱 포지션) 관점
                    if current > neckline:  # 아직 넥라인 위 - 넥라인 지지 반등 매수 전략
                        entry = neckline  # 진입: 넥라인까지 하락시 매수
                        stop = neckline * 0.97  # 손절: 넥라인 3% 이탈시
                        target = right_shoulder  # 목표: 오른쪽어깨까지 반등
                        signal_msg = f'머리어깨 형성 중 ⚠️'
                        reason_msg = f'넥라인({neckline:,.0f}) 지지 반등 기대, 이탈시 {drop_target:,.0f} 하락 주의'
                    else:  # 넥라인 이탈 - 하락 목표 도달시 반등 매수 전략
                        entry = drop_target  # 진입: 하락 목표가 도달시 반등 매수
                        stop = drop_target * 0.95  # 손절: 목표가 5% 추가 하락시
                        target = neckline  # 목표: 넥라인까지 반등
                        signal_msg = f'머리어깨 이탈 🔻'
                        reason_msg = f'넥라인 이탈! {drop_target:,.0f} 도달시 반등 매수 검토'

                    results.append({
                        'code': code,
                        'name': name,
                        'signal': signal_msg,
                        'reason': reason_msg,
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'left_shoulder': left_shoulder,
                        'head': head,
                        'right_shoulder': right_shoulder,
                        'neckline': neckline
                    })
                    continue

            # ===== 역머리어깨 패턴 (Inverse Head & Shoulders) =====
            # 상승 반전 신호: 하락 추세 후 바닥에서 형성
            if 'inv_head_shoulders' in selected_patterns:
                # 3구간으로 나눠 저점 찾기
                ls_idx = np.argmin(lows[-60:-40]) + len(lows) - 60
                h_idx = np.argmin(lows[-40:-20]) + len(lows) - 40
                rs_idx = np.argmin(lows[-20:]) + len(lows) - 20

                left_shoulder = lows[ls_idx]     # 왼쪽어깨 (저점)
                head = lows[h_idx]               # 머리 (가장 낮은 저점)
                right_shoulder = lows[rs_idx]    # 오른쪽어깨 (저점)

                # 넥라인: 왼쪽어깨~머리 사이 고점, 머리~오른쪽어깨 사이 고점
                neckline_left = np.max(highs[ls_idx:h_idx]) if h_idx > ls_idx else np.max(highs[-50:-30])
                neckline_right = np.max(highs[h_idx:rs_idx]) if rs_idx > h_idx else np.max(highs[-30:-10])
                neckline = (neckline_left + neckline_right) / 2

                # 패턴 조건 검사
                # 1) 머리가 양 어깨보다 낮아야 함 (최소 2% 이상)
                # 2) 양 어깨가 비슷한 높이 (10% 오차 허용)
                # 3) 현재가가 넥라인 근처 또는 위
                head_lower = head < left_shoulder * 0.98 and head < right_shoulder * 0.98
                shoulders_similar = abs(left_shoulder - right_shoulder) / left_shoulder < 0.10
                near_neckline = current > neckline * 0.95  # 넥라인 5% 아래까지

                if head_lower and shoulders_similar and near_neckline:
                    pattern_height = neckline - head  # 패턴 높이
                    target_price = neckline + pattern_height  # 상승 목표

                    # 매매 전략
                    if current < neckline:  # 아직 넥라인 아래 (돌파 대기)
                        entry = current
                        stop = right_shoulder * 0.97  # 오른쪽어깨 아래 손절
                        target = neckline  # 1차 목표: 넥라인 돌파
                        signal_msg = f'역머리어깨 형성 중 📈'
                        reason_msg = f'넥라인({neckline:,.0f}) 돌파시 → {target_price:,.0f} 상승 기대'
                    else:  # 넥라인 돌파
                        entry = current
                        stop = neckline * 0.97  # 넥라인 아래로 복귀시 손절
                        target = target_price
                        signal_msg = f'역머리어깨 돌파 🚀'
                        reason_msg = f'넥라인({neckline:,.0f}) 돌파! 목표 {target_price:,.0f}'

                    results.append({
                        'code': code,
                        'name': name,
                        'signal': signal_msg,
                        'reason': reason_msg,
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'left_shoulder': left_shoulder,
                        'head': head,
                        'right_shoulder': right_shoulder,
                        'neckline': neckline
                    })
        except:
            continue

    progress.empty()
    return results


def _find_flag_pennant_stocks(api, market: str, stock_count=100) -> list:
    """깃발/페넌트 패턴 종목 찾기 - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            volumes = data['volume'].values
            current = closes[-1]
            change_rate = (current - closes[-2]) / closes[-2] * 100

            # 깃발 패턴: 급등 후 횡보/조정
            # 1. 15일 전~10일 전 급등 (10% 이상)
            if len(closes) >= 30:
                pole_start = closes[-30]
                pole_end = closes[-15]
                pole_change = (pole_end - pole_start) / pole_start * 100
                pole_height = abs(pole_end - pole_start)

                # 최근 10일 변동폭
                recent_high = np.max(highs[-10:])
                recent_low = np.min(lows[-10:])
                recent_range = (recent_high - recent_low) / recent_low * 100

                # 급등 후 좁은 횡보 (깃발 패턴) - 상승 돌파 기대
                if pole_change > 10 and recent_range < 8:
                    # 추천 진입가: 깃발 상단 돌파 시점 (최근 고점)
                    entry = recent_high * 1.005  # 최근 고점 0.5% 돌파 시 진입
                    stop = recent_low * 0.98  # 깃발 하단 2% 아래
                    target = recent_high + pole_height  # 깃발 상단 + 깃대 높이
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '상승 깃발',
                            'reason': f'급등({pole_change:.1f}%) 후 횡보 → 돌파 대기',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })

                # 급락 후 횡보 (하락 깃발) - 롱 포지션 관점: 반등 매수 전략
                elif pole_change < -10 and recent_range < 8:
                    # 추천 진입가: 횡보 상단 돌파 시점 (반등 확인 후)
                    entry = recent_high * 1.005  # 최근 고점 돌파 시 반등 확인
                    stop = recent_low * 0.97  # 최근 저점 아래
                    target = pole_start  # 급락 전 고점까지 반등 기대
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '하락 후 횡보',
                            'reason': f'급락({pole_change:.1f}%) 후 횡보 → 바닥 다지기 가능',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })

                # 페넌트: 거래량 감소와 함께 수렴
                avg_vol_early = np.mean(volumes[-30:-15])
                avg_vol_late = np.mean(volumes[-10:])
                if avg_vol_late < avg_vol_early * 0.6 and recent_range < 5:
                    # 추천 진입가: 수렴 상단 돌파 시점
                    entry = recent_high * 1.005  # 수렴 상단 돌파 시 진입
                    stop = recent_low * 0.97  # 수렴 하단 3% 아래
                    # 직전 추세 방향으로 돌파 예상
                    if pole_change > 0:  # 상승 추세였다면 상승 돌파
                        target = recent_high + pole_height * 0.5
                    else:
                        target = recent_high * 1.05  # 최소 5% 상승
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '페넌트 수렴',
                            'reason': f'거래량 감소 + 가격 수렴 → 돌파 임박',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
        except:
            continue

    progress.empty()
    return results


def _find_directional_change_stocks(api, market: str, stock_count=100) -> list:
    """방향성 변화 종목 찾기 (ATR 기반) - 진입가, 손절가, 목표가 포함"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            high = data['high'].values
            low = data['low'].values
            close = data['close'].values
            current = close[-1]
            change_rate = (current - close[-2]) / close[-2] * 100

            # ATR 계산
            tr = np.maximum(high[1:] - low[1:],
                          np.abs(high[1:] - close[:-1]),
                          np.abs(low[1:] - close[:-1]))
            atr = np.mean(tr[-14:])

            # 최근 고점/저점
            recent_high = np.max(high[-10:])
            recent_low = np.min(low[-10:])

            # 최근 가격 변화가 ATR의 2배 이상 (강한 방향성 변화)
            recent_change = abs(current - close[-5])
            if recent_change > atr * 2:
                direction = "상승" if current > close[-5] else "하락"
                if direction == "상승":  # 상승 전환 - 매수
                    entry = current
                    stop = recent_low * 0.98  # 최근 저점 2% 아래
                    target = current + atr * 3  # ATR 3배 상승 목표
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': f'강한 상승 전환',
                            'reason': f'ATR 대비 {recent_change/atr:.1f}배 상승',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })
                else:  # 하락 전환 - 롱 포지션 관점: 반등 매수 기회
                    # 급락 후 반등 가능성, 지지선 반등 매수 전략
                    entry = current
                    stop = recent_low * 0.97  # 최근 저점 아래
                    target = current + atr * 2  # ATR 2배 반등 목표
                    # 유효성 검증: 손절 < 진입 < 목표
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': f'급락 후 반등 대기',
                            'reason': f'ATR 대비 {recent_change/atr:.1f}배 하락 → 반등 기대',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target
                        })

            # 변동성 확대 (ATR 급증)
            atr_prev = np.mean(tr[-28:-14])
            if atr > atr_prev * 1.5:
                entry = current
                stop = current - atr * 1.5  # ATR 1.5배 손절
                target = current + atr * 2  # ATR 2배 목표
                # 유효성 검증: 손절 < 진입 < 목표
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '변동성 확대',
                        'reason': f'ATR {((atr/atr_prev)-1)*100:.0f}% 증가 → 큰 움직임 예고',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target
                    })
        except:
            continue

    progress.empty()
    return results


def _render_trendline_section(api):
    """추세선 분석 섹션"""
    st.markdown("### 📈 추세선 자동화 (Trendline Automation)")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 🔍 개념")
        st.info("""
        그래디언트 하강법(Gradient Descent)을 사용하여 가격 데이터에서
        **지지선과 저항선을 자동으로 탐지**하는 알고리즘입니다.
        """)

        st.markdown("**⚙️ 작동 원리**")
        st.markdown("""
        1. 로컬 고점/저점 식별
        2. 최적화 알고리즘으로 직선 피팅
        3. 터치 횟수 및 각도로 유효성 판단
        """)

    with col2:
        st.markdown("#### 📖 해석법")

        st.markdown("**🔺 상승 추세선 (지지선)**")
        st.markdown("""
        - 저점들을 연결한 상향 직선
        - 가격이 추세선에 닿으면 → **매수 신호**
        - 추세선 하향 이탈 시 → **추세 전환 경고**
        """)

        st.markdown("**🔻 하락 추세선 (저항선)**")
        st.markdown("""
        - 고점들을 연결한 하향 직선
        - 가격이 추세선 돌파 시 → **매수 신호**
        - 돌파 실패 시 하락 지속
        """)

    # 매매 전략
    st.markdown("#### 💡 매매 전략")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.error("**매수 시점**\n\n상승 추세선 터치 + 반등 캔들 확인")
    with col2:
        st.warning("**매도 시점**\n\n하락 추세선 터치 + 저항 확인")
    with col3:
        st.info("**손절 기준**\n\n추세선 이탈 후 되돌림 실패 시")

    # 종목 찾기
    _render_stock_finder(api, "추세선 지지 반등", _find_trendline_stocks, "trendline")


def _render_harmonic_section(api):
    """조화 패턴 섹션"""
    st.markdown("### 🎯 조화 패턴 (Harmonic Patterns)")

    st.info("""
    피보나치 비율을 기반으로 한 **예측 가능한 가격 패턴**입니다.
    특정 비율의 되돌림과 확장이 반복되는 구조를 찾습니다.
    """)

    # 패턴 종류
    col1, col2 = st.columns(2)

    with col1:
        with st.expander("🦋 Gartley 패턴", expanded=True):
            st.markdown("""
            **구조:** X-A-B-C-D 5개 포인트
            - AB = XA의 61.8% 되돌림
            - BC = AB의 38.2~88.6% 되돌림
            - CD = BC의 127.2~161.8% 확장
            - D = XA의 78.6% 되돌림

            🎯 **D 포인트에서 반전 매매**
            """)

        with st.expander("🦇 Bat 패턴"):
            st.markdown("""
            **구조:** 더 깊은 되돌림
            - AB = XA의 38.2~50% 되돌림
            - CD = AB의 161.8~261.8% 확장
            - D = XA의 88.6% 되돌림

            🎯 **높은 정확도의 반전 신호**
            """)

    with col2:
        with st.expander("🦋 Butterfly 패턴", expanded=True):
            st.markdown("""
            **구조:** 확장형 패턴
            - AB = XA의 78.6% 되돌림
            - CD = AB의 161.8~261.8% 확장
            - D = XA의 127.2~161.8% 확장

            🎯 **강력한 반전 구간**
            """)

        with st.expander("🦀 Crab 패턴"):
            st.markdown("""
            **구조:** 극단적 확장
            - AB = XA의 38.2~61.8% 되돌림
            - D = XA의 161.8% 확장

            🎯 **가장 극단적인 반전 지점**
            """)

    # 매매 전략
    st.markdown("#### 💡 조화 패턴 매매 전략")
    st.markdown("""
    1. **패턴 완성 대기:** D 포인트가 형성될 때까지 관망
    2. **확인 캔들:** D 포인트에서 반전 캔들 (망치형, 장악형) 확인
    3. **진입:** 반전 캔들 종가에서 진입
    4. **손절:** D 포인트 약간 아래/위
    5. **목표가:** A 또는 C 포인트 수준
    """)

    # 종목 찾기 - 조화 패턴별 선택 검색
    _render_harmonic_stock_finder(api)


def _render_head_shoulders_section(api):
    """머리어깨 패턴 섹션"""
    st.markdown("### 👤 머리어깨 패턴 (Head & Shoulders)")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 📉 머리어깨 천장 (약세 반전)")
        st.error("""
        **구조:**
        - **왼쪽 어깨:** 첫 번째 고점 형성 후 하락
        - **머리:** 더 높은 고점 형성 후 하락
        - **오른쪽 어깨:** 머리보다 낮은 고점
        - **넥라인:** 두 저점을 연결한 선

        ⚠️ **넥라인 하향 이탈 시 매도 신호**

        **목표가:** 넥라인 - (머리 ~ 넥라인 높이)
        """)

    with col2:
        st.markdown("#### 📈 역 머리어깨 (강세 반전)")
        st.success("""
        **구조:**
        - **왼쪽 어깨:** 첫 번째 저점 형성 후 상승
        - **머리:** 더 낮은 저점 형성 후 상승
        - **오른쪽 어깨:** 머리보다 높은 저점
        - **넥라인:** 두 고점을 연결한 선

        ✅ **넥라인 상향 돌파 시 매수 신호**

        **목표가:** 넥라인 + (넥라인 ~ 머리 깊이)
        """)

    # 신뢰도 판단
    st.markdown("#### ✅ 신뢰도 높은 패턴 조건")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 거래량", "머리↓ 돌파↑")
    with col2:
        st.metric("⚖️ 대칭성", "양 어깨 유사")
    with col3:
        st.metric("📏 넥라인", "수평/약경사")
    with col4:
        st.metric("⏱️ 기간", "장기 = 신뢰↑")

    # 종목 찾기 - 머리어깨 패턴 (패턴 선택 가능)
    _render_head_shoulders_stock_finder(api)


def _render_flags_pennants_section(api):
    """깃발/페넌트 패턴 섹션"""
    st.markdown("### 🚩 깃발 & 페넌트 패턴 (Flags & Pennants)")

    st.info("""
    **지속형 패턴**: 강한 추세 움직임(깃대) 후 짧은 조정(깃발/페넌트)을 거쳐
    **기존 추세가 지속**됩니다.
    """)

    col1, col2 = st.columns(2)

    with col1:
        with st.expander("🏳️ 깃발 패턴 (Flag)", expanded=True):
            st.markdown("""
            **특징:**
            - 평행한 두 추세선으로 형성
            - 기존 추세의 **반대 방향**으로 기울어짐
            - 상승 추세 → 하향 깃발
            - 하락 추세 → 상향 깃발

            **목표가:** 깃대 높이만큼 돌파 방향으로
            """)

    with col2:
        with st.expander("🔺 페넌트 패턴 (Pennant)", expanded=True):
            st.markdown("""
            **특징:**
            - 수렴하는 두 추세선으로 형성
            - 작은 **대칭 삼각형** 모양
            - 깃발보다 짧은 기간 형성
            - 거래량 감소 후 돌파 시 증가

            **목표가:** 깃대 높이만큼 돌파 방향으로
            """)

    # 매매 전략
    st.markdown("#### 💡 매매 전략")
    col1, col2 = st.columns(2)
    with col1:
        st.success("""
        **🔺 상승 깃발/페넌트 (강세)**
        - 상단 추세선 돌파 시 매수
        - 손절: 패턴 하단
        - 목표: 진입가 + 깃대 높이
        """)
    with col2:
        st.error("""
        **🔻 하락 깃발/페넌트 (약세)**
        - 하단 추세선 이탈 시 매도
        - 손절: 패턴 상단
        - 목표: 진입가 - 깃대 높이
        """)

    # 종목 찾기 - 깃발/페넌트 패턴 (패턴 선택 가능)
    _render_flag_pennant_stock_finder(api)


def _render_flag_pennant_stock_finder(api):
    """깃발/페넌트 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 깃발/페넌트 패턴 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="flag_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="flag_count")

    st.markdown("**패턴 선택** (복수 선택 가능)")
    col1, col2, col3 = st.columns(3)
    with col1:
        bull_flag = st.checkbox("🚩 상승 깃발 (강세)", value=True, key="flag_bull")
    with col2:
        bear_flag = st.checkbox("🏳️ 하락 후 횡보 (반등 기대)", value=True, key="flag_bear")
    with col3:
        pennant = st.checkbox("🔺 페넌트 수렴", value=True, key="flag_pennant")

    if st.button("🔎 패턴 검색 시작", key="flag_search", type="primary"):
        selected_patterns = []
        if bull_flag:
            selected_patterns.append('bull_flag')
        if bear_flag:
            selected_patterns.append('bear_flag')
        if pennant:
            selected_patterns.append('pennant')

        if not selected_patterns:
            st.warning("최소 1개 이상의 패턴을 선택해주세요.")
        else:
            with st.spinner(f"깃발/페넌트 패턴 검색 중... (패턴: {len(selected_patterns)}개)"):
                results = _find_flag_pennant_by_pattern(api, market, stock_count, selected_patterns)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="flag_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_flag_pennant_card(stock, api=api, key_prefix=f"flag_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_flag_pennant_card(stock: dict, api=None, key_prefix: str = "flag"):
    """깃발/페넌트 종목 카드 렌더링 (+ 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    pole_height = stock.get('pole_height', 0)
    pattern_range = stock.get('pattern_range', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 패턴 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**현재가:** {current_price:,.0f}원")
        with col2:
            st.markdown(f"📏 **깃대높이:** {pole_height:,.0f}원")
        with col3:
            st.markdown(f"📐 **패턴폭:** {pattern_range:.1f}%")
        with col4:
            pass

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col2:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col3:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")
            with col4:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.markdown(f"📊 **R:R** = 1:{rr_ratio:.1f}")

            st.caption(f"{reason}")
        else:
            st.caption(f"{reason}")

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_flag_pennant_by_pattern(api, market: str, stock_count, selected_patterns: list) -> list:
    """패턴별 깃발/페넌트 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values
            volumes = data['volume'].values
            current = closes[-1]
            change_rate = (current - closes[-2]) / closes[-2] * 100

            if len(closes) >= 30:
                pole_start = closes[-30]
                pole_end = closes[-15]
                pole_change = (pole_end - pole_start) / pole_start * 100
                pole_height = abs(pole_end - pole_start)

                recent_high = np.max(highs[-10:])
                recent_low = np.min(lows[-10:])
                recent_range = (recent_high - recent_low) / recent_low * 100

                # 상승 깃발
                if 'bull_flag' in selected_patterns and pole_change > 10 and recent_range < 8:
                    entry = current
                    stop = recent_low * 0.98
                    target = recent_high + pole_height
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '🚩 상승 깃발',
                            'reason': f'급등({pole_change:.1f}%) 후 횡보 → 돌파 대기',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'pole_height': pole_height,
                            'pattern_range': recent_range
                        })

                # 하락 후 횡보 (반등 기대)
                if 'bear_flag' in selected_patterns and pole_change < -10 and recent_range < 8:
                    entry = current
                    stop = recent_low * 0.97
                    target = pole_start
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '🏳️ 하락 후 횡보',
                            'reason': f'급락({pole_change:.1f}%) 후 횡보 → 바닥 다지기 가능',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'pole_height': pole_height,
                            'pattern_range': recent_range
                        })

                # 페넌트 수렴
                avg_vol_early = np.mean(volumes[-30:-15])
                avg_vol_late = np.mean(volumes[-10:])
                if 'pennant' in selected_patterns and avg_vol_late < avg_vol_early * 0.6 and recent_range < 5:
                    entry = current
                    stop = recent_low * 0.97
                    if pole_change > 0:
                        target = recent_high + pole_height * 0.5
                    else:
                        target = recent_high * 1.05
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '🔺 페넌트 수렴',
                            'reason': f'거래량 감소 + 가격 수렴 → 돌파 임박',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'pole_height': pole_height,
                            'pattern_range': recent_range
                        })
        except:
            continue

    progress.empty()
    return results


def _render_fibonacci_section(api):
    """피보나치 섹션"""
    st.markdown("### 📐 피보나치 되돌림 (Fibonacci Retracement)")

    st.info("피보나치 수열에서 파생된 비율로, 자연계와 금융시장에서 반복적으로 나타나는 패턴입니다.")

    # 비율 테이블
    st.markdown("#### 🔢 핵심 피보나치 비율")

    fib_data = {
        "비율": ["23.6%", "38.2%", "50.0%", "61.8%", "78.6%"],
        "의미": ["얕은 되돌림", "황금 비율 1", "반값 되돌림", "황금 비율 (Golden)", "깊은 되돌림"],
        "매매 활용": ["강한 추세 짧은 조정", "첫 번째 주요 지지/저항", "심리적 중요 수준", "가장 중요한 되돌림", "마지막 방어선"]
    }
    st.dataframe(pd.DataFrame(fib_data), hide_index=True, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.success("""
        #### 📈 상승 추세 활용
        1. 스윙 저점 → 스윙 고점 선택
        2. 되돌림 수준에서 매수 대기
        3. 38.2%, 50%, 61.8% 순으로 관찰
        4. 반등 캔들 확인 후 진입
        """)

    with col2:
        st.error("""
        #### 📉 하락 추세 활용
        1. 스윙 고점 → 스윙 저점 선택
        2. 되돌림 수준에서 매도 대기
        3. 38.2%, 50%, 61.8% 순으로 관찰
        4. 저항 확인 후 진입
        """)

    # 종목 찾기 - 피보나치 (패턴 선택 가능)
    _render_fibonacci_stock_finder(api)


def _render_fibonacci_stock_finder(api):
    """피보나치 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 피보나치 되돌림 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="fib_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="fib_count")

    st.markdown("**피보나치 레벨 선택** (복수 선택 가능)")
    col1, col2, col3 = st.columns(3)
    with col1:
        fib_382 = st.checkbox("📐 38.2% (1차 지지)", value=True, key="fib_382")
    with col2:
        fib_500 = st.checkbox("📐 50.0% (반값)", value=True, key="fib_500")
    with col3:
        fib_618 = st.checkbox("📐 61.8% (황금비율)", value=True, key="fib_618")

    if st.button("🔎 패턴 검색 시작", key="fib_search", type="primary"):
        selected_levels = []
        if fib_382:
            selected_levels.append('38.2')
        if fib_500:
            selected_levels.append('50.0')
        if fib_618:
            selected_levels.append('61.8')

        if not selected_levels:
            st.warning("최소 1개 이상의 레벨을 선택해주세요.")
        else:
            with st.spinner(f"피보나치 패턴 검색 중... (레벨: {len(selected_levels)}개)"):
                results = _find_fibonacci_by_level(api, market, stock_count, selected_levels)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="fib_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_fibonacci_card(stock, api=api, key_prefix=f"fib_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_fibonacci_card(stock: dict, api=None, key_prefix: str = "fib"):
    """피보나치 종목 카드 렌더링 (+ 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    fib_level = stock.get('fib_level', 0)
    swing_high = stock.get('swing_high', 0)
    swing_low = stock.get('swing_low', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 피보나치 레벨 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**현재가:** {current_price:,.0f}원")
        with col2:
            st.markdown(f"📈 **스윙고점:** {swing_high:,.0f}원")
        with col3:
            st.markdown(f"📉 **스윙저점:** {swing_low:,.0f}원")
        with col4:
            st.markdown(f"📐 **피보레벨:** {fib_level:,.0f}원")

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col2:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col3:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")
            with col4:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.markdown(f"📊 **R:R** = 1:{rr_ratio:.1f}")

            st.caption(f"{reason}")
        else:
            st.caption(f"{reason}")

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_fibonacci_by_level(api, market: str, stock_count, selected_levels: list) -> list:
    """피보나치 레벨별 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            high = data['high'].max()
            low = data['low'].min()
            current = data['close'].iloc[-1]
            change_rate = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

            # 피보나치 수준 계산
            fib_236 = high - (high - low) * 0.236
            fib_382 = high - (high - low) * 0.382
            fib_500 = high - (high - low) * 0.500
            fib_618 = high - (high - low) * 0.618
            fib_786 = high - (high - low) * 0.786

            # 61.8% 레벨
            if '61.8' in selected_levels and abs(current - fib_618) / fib_618 < 0.05:
                entry = current
                stop = fib_786 * 0.98
                target = fib_382
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '📐 피보나치 61.8%',
                        'reason': f'황금비율 근처 (오차 {abs(current - fib_618) / fib_618 * 100:.1f}%)',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'fib_level': fib_618,
                        'swing_high': high,
                        'swing_low': low
                    })

            # 50% 레벨
            if '50.0' in selected_levels and abs(current - fib_500) / fib_500 < 0.05:
                entry = current
                stop = fib_618 * 0.98
                target = fib_236
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '📐 피보나치 50%',
                        'reason': f'반값 되돌림 근처',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'fib_level': fib_500,
                        'swing_high': high,
                        'swing_low': low
                    })

            # 38.2% 레벨
            if '38.2' in selected_levels and abs(current - fib_382) / fib_382 < 0.05:
                entry = current
                stop = fib_500 * 0.98
                target = high * 0.98
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '📐 피보나치 38.2%',
                        'reason': f'1차 지지선 근처',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'fib_level': fib_382,
                        'swing_high': high,
                        'swing_low': low
                    })
        except:
            continue

    progress.empty()
    return results


def _render_directional_change_section(api):
    """방향성 변화 섹션"""
    st.markdown("### 🔄 방향성 변화 (Directional Change)")

    st.info("""
    가격이 특정 **임계값(threshold)**만큼 반대 방향으로 움직일 때
    **추세 전환**으로 인식하는 알고리즘입니다.
    ATR(Average True Range)을 기반으로 동적 임계값을 설정하여 변동성에 적응합니다.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ⚙️ 알고리즘")
        st.markdown("""
        1. **ATR 계산:** 14일 평균 변동폭
        2. **임계값 설정:** ATR × 배수 (예: 2배)
        3. **방향 전환 감지:**
           - 상승 중 고점 대비 임계값 이상 하락 → 하락 전환
           - 하락 중 저점 대비 임계값 이상 상승 → 상승 전환
        """)

    with col2:
        st.markdown("#### 📖 해석법")
        st.success("**Upturn (상승 전환)**\n\n저점에서 임계값 이상 상승 → 매수 신호")
        st.error("**Downturn (하락 전환)**\n\n고점에서 임계값 이상 하락 → 매도 신호")

    # 활용 전략
    st.markdown("#### 💡 활용 전략")
    st.markdown("""
    - **추세 추종:** 방향 전환 시 해당 방향으로 진입
    - **다중 시간대:** 상위 시간대 방향과 일치할 때만 진입
    - **필터링:** 거래량 증가와 함께 전환 시 신뢰도 증가
    """)

    # 종목 찾기 - 방향성 변화 (패턴 선택 가능)
    _render_directional_change_stock_finder(api)


def _render_directional_change_stock_finder(api):
    """방향성 변화 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 방향성 변화 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="dc_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="dc_count")

    st.markdown("**신호 유형 선택** (복수 선택 가능)")
    col1, col2, col3 = st.columns(3)
    with col1:
        upturn = st.checkbox("📈 상승 전환", value=True, key="dc_upturn")
    with col2:
        downturn = st.checkbox("📉 급락 후 반등 대기", value=True, key="dc_downturn")
    with col3:
        volatility = st.checkbox("📊 변동성 확대", value=True, key="dc_volatility")

    if st.button("🔎 패턴 검색 시작", key="dc_search", type="primary"):
        selected_signals = []
        if upturn:
            selected_signals.append('upturn')
        if downturn:
            selected_signals.append('downturn')
        if volatility:
            selected_signals.append('volatility')

        if not selected_signals:
            st.warning("최소 1개 이상의 신호를 선택해주세요.")
        else:
            with st.spinner(f"방향성 변화 검색 중... (신호: {len(selected_signals)}개)"):
                results = _find_directional_change_by_signal(api, market, stock_count, selected_signals)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="dc_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_directional_change_card(stock, api=api, key_prefix=f"dc_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_directional_change_card(stock: dict, api=None, key_prefix: str = "dc"):
    """방향성 변화 종목 카드 렌더링 (+ 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    atr = stock.get('atr', 0)
    atr_multiple = stock.get('atr_multiple', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # ATR 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**현재가:** {current_price:,.0f}원")
        with col2:
            st.markdown(f"📊 **ATR:** {atr:,.0f}원")
        with col3:
            st.markdown(f"⚡ **ATR배수:** {atr_multiple:.1f}배")
        with col4:
            pass

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col2:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col3:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")
            with col4:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.markdown(f"📊 **R:R** = 1:{rr_ratio:.1f}")

            st.caption(f"{reason}")
        else:
            st.caption(f"{reason}")

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_directional_change_by_signal(api, market: str, stock_count, selected_signals: list) -> list:
    """방향성 변화 신호별 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            high = data['high'].values
            low = data['low'].values
            close = data['close'].values
            current = close[-1]
            change_rate = (current - close[-2]) / close[-2] * 100

            # ATR 계산
            tr = np.maximum(high[1:] - low[1:],
                          np.abs(high[1:] - close[:-1]),
                          np.abs(low[1:] - close[:-1]))
            atr = np.mean(tr[-14:])

            recent_high = np.max(high[-10:])
            recent_low = np.min(low[-10:])

            # 최근 가격 변화가 ATR의 2배 이상
            recent_change = abs(current - close[-5])
            if recent_change > atr * 2:
                direction = "상승" if current > close[-5] else "하락"
                atr_multiple = recent_change / atr

                # 상승 전환
                if 'upturn' in selected_signals and direction == "상승":
                    entry = current
                    stop = recent_low * 0.98
                    target = current + atr * 3
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '📈 강한 상승 전환',
                            'reason': f'ATR 대비 {atr_multiple:.1f}배 상승',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'atr': atr,
                            'atr_multiple': atr_multiple
                        })

                # 급락 후 반등 대기
                if 'downturn' in selected_signals and direction == "하락":
                    entry = current
                    stop = recent_low * 0.97
                    target = current + atr * 2
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '📉 급락 후 반등 대기',
                            'reason': f'ATR 대비 {atr_multiple:.1f}배 하락 → 반등 기대',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'atr': atr,
                            'atr_multiple': atr_multiple
                        })

            # 변동성 확대
            atr_prev = np.mean(tr[-28:-14]) if len(tr) >= 28 else atr
            if 'volatility' in selected_signals and atr > atr_prev * 1.5:
                atr_increase = ((atr / atr_prev) - 1) * 100
                entry = current
                stop = current - atr * 1.5
                target = current + atr * 2
                if stop < entry < target:
                    results.append({
                        'code': code,
                        'name': name,
                        'signal': '📊 변동성 확대',
                        'reason': f'ATR {atr_increase:.0f}% 증가 → 큰 움직임 예고',
                        'change_rate': change_rate,
                        'current_price': current,
                        'entry_price': entry,
                        'stop_loss': stop,
                        'target_price': target,
                        'atr': atr,
                        'atr_multiple': atr / atr_prev if atr_prev > 0 else 0
                    })
        except:
            continue

    progress.empty()
    return results


def _render_support_resistance_section(api):
    """지지/저항선 섹션"""
    st.markdown("### 📊 지지/저항선 (Support & Resistance)")

    st.info("""
    가격대별 **거래량 분포**를 분석하여 의미 있는 가격 수준을 찾습니다.
    거래가 많이 일어난 가격대가 지지/저항으로 작용합니다.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.success("""
        #### 🟢 지지선
        - 가격 하락을 막는 수준
        - 매수세가 집중되는 구간
        - 터치 횟수가 많을수록 강력

        **지지선 터치 시 매수 고려**
        """)

    with col2:
        st.error("""
        #### 🔴 저항선
        - 가격 상승을 막는 수준
        - 매도세가 집중되는 구간
        - 돌파 시 강한 상승 모멘텀

        **저항선 터치 시 매도 고려**
        """)

    with col3:
        st.warning("""
        #### 🔄 역할 전환
        - 지지선 이탈 → 저항선
        - 저항선 돌파 → 지지선
        - 돌파/이탈 후 리테스트 확인

        **역할 전환 확인 후 진입**
        """)

    # POC
    st.markdown("#### 🎯 POC (Point of Control)")
    st.markdown("""
    특정 기간 내 **가장 거래량이 많은 가격대**입니다.
    - **가격 > POC:** 강세 구간, 하락 시 POC가 지지선
    - **가격 < POC:** 약세 구간, 상승 시 POC가 저항선
    """)

    # 종목 찾기 - 지지/저항 (패턴 선택 가능)
    _render_support_resistance_stock_finder(api)


def _render_support_resistance_stock_finder(api):
    """지지/저항 패턴 전용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 지지/저항 패턴 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="sr_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="sr_count")

    st.markdown("**신호 유형 선택** (복수 선택 가능)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bb_expand = st.checkbox("📊 볼린저 확장", value=True, key="sr_bb_expand")
    with col2:
        bb_upper = st.checkbox("📈 상단밴드 돌파", value=True, key="sr_bb_upper")
    with col3:
        bb_lower = st.checkbox("📉 하단밴드 지지", value=True, key="sr_bb_lower")
    with col4:
        rsi_signal = st.checkbox("📊 RSI 과매도", value=True, key="sr_rsi")

    if st.button("🔎 패턴 검색 시작", key="sr_search", type="primary"):
        selected_signals = []
        if bb_expand:
            selected_signals.append('bb_expand')
        if bb_upper:
            selected_signals.append('bb_upper')
        if bb_lower:
            selected_signals.append('bb_lower')
        if rsi_signal:
            selected_signals.append('rsi')

        if not selected_signals:
            st.warning("최소 1개 이상의 신호를 선택해주세요.")
        else:
            with st.spinner(f"지지/저항 패턴 검색 중... (신호: {len(selected_signals)}개)"):
                results = _find_support_resistance_by_signal(api, market, stock_count, selected_signals)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="sr_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_support_resistance_card(stock, api=api, key_prefix=f"sr_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_support_resistance_card(stock: dict, api=None, key_prefix: str = "sr"):
    """지지/저항 종목 카드 렌더링 (+ 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    indicator_value = stock.get('indicator_value', 0)
    indicator_name = stock.get('indicator_name', '')

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 지표 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**현재가:** {current_price:,.0f}원")
        with col2:
            if indicator_name:
                if 'RSI' in indicator_name:
                    st.markdown(f"📊 **{indicator_name}:** {indicator_value:.1f}")
                else:
                    st.markdown(f"📊 **{indicator_name}:** {indicator_value:,.0f}원")
        with col3:
            pass
        with col4:
            pass

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col2:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col3:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")
            with col4:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.markdown(f"📊 **R:R** = 1:{rr_ratio:.1f}")

            st.caption(f"{reason}")
        else:
            st.caption(f"{reason}")

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_support_resistance_by_signal(api, market: str, stock_count, selected_signals: list) -> list:
    """지지/저항 신호별 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 60)
            if data is None or len(data) < 30:
                continue

            current = data['close'].iloc[-1]
            change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

            # 볼린저밴드 계산
            ma20 = data['close'].rolling(20).mean()
            std20 = data['close'].rolling(20).std()
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            bandwidth = (upper - lower) / ma20 * 100

            if len(bandwidth) > 5:
                recent_bw = bandwidth.iloc[-5:].mean()
                prev_bw = bandwidth.iloc[-10:-5].mean()

                if not np.isnan(recent_bw) and not np.isnan(prev_bw):
                    # 볼린저 확장
                    if 'bb_expand' in selected_signals and recent_bw > prev_bw * 1.15:
                        entry = current
                        stop = ma20.iloc[-1] * 0.97
                        target = upper.iloc[-1] * 1.02
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '📊 볼린저 확장',
                                'reason': f'밴드폭 {((recent_bw/prev_bw)-1)*100:.0f}% 확장',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target,
                                'indicator_name': '상단밴드',
                                'indicator_value': upper.iloc[-1]
                            })

                    # 상단밴드 돌파
                    if 'bb_upper' in selected_signals and current > upper.iloc[-1]:
                        entry = current
                        stop = ma20.iloc[-1]
                        target = upper.iloc[-1] * 1.05
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '📈 상단밴드 돌파',
                                'reason': '볼린저 상단 돌파 - 추세 강화',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target,
                                'indicator_name': '상단밴드',
                                'indicator_value': upper.iloc[-1]
                            })

                    # 하단밴드 지지
                    if 'bb_lower' in selected_signals and current < lower.iloc[-1] * 1.02:
                        entry = current
                        stop = lower.iloc[-1] * 0.97
                        target = ma20.iloc[-1]
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '📉 하단밴드 지지',
                                'reason': '볼린저 하단 근처 (반등 기대)',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target,
                                'indicator_name': '하단밴드',
                                'indicator_value': lower.iloc[-1]
                            })

            # RSI 과매도
            if 'rsi' in selected_signals:
                delta = data['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                recent_high = data['high'].iloc[-20:].max()
                recent_low = data['low'].iloc[-20:].min()

                if len(rsi) > 0 and not np.isnan(rsi.iloc[-1]) and rsi.iloc[-1] < 30:
                    entry = current
                    stop = recent_low * 0.97
                    target = recent_high * 0.95
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '📊 RSI 과매도',
                            'reason': f'RSI {rsi.iloc[-1]:.1f} (30 미만) - 반등 기대',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'indicator_name': 'RSI',
                            'indicator_value': rsi.iloc[-1]
                        })
        except:
            continue

    progress.empty()
    return results


def _render_strategy_validation_section(api):
    """전략 검증 섹션"""
    st.markdown("### 🧪 전략 검증 (MCPT - Monte Carlo Permutation Test)")

    st.info("""
    트레이딩 전략의 수익이 **실제 예측력**에 의한 것인지,
    단순한 **우연**인지를 통계적으로 검증하는 방법입니다.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ⚙️ 검증 방법")
        st.markdown("""
        1. **원본 성과 계산:** 실제 데이터로 전략 수익률 측정
        2. **순열 생성:** 가격 데이터의 순서를 무작위로 섞음 (1000회 이상)
        3. **순열 성과 계산:** 각 순열에서 전략 수익률 측정
        4. **p-value 계산:** 원본보다 좋은 순열 비율
        """)

    with col2:
        st.markdown("#### 📖 결과 해석")
        st.success("**p-value < 0.05**\n\n통계적으로 유의미 → 전략에 실제 예측력 있음")
        st.error("**p-value > 0.05**\n\n우연일 가능성 높음 → 과최적화 의심")

    # 과최적화 경고
    st.markdown("#### ⚠️ 과최적화(Overfitting) 방지")

    col1, col2 = st.columns(2)
    with col1:
        st.warning("""
        **과최적화 징후:**
        - 백테스트 성과 >> 실전 성과
        - 파라미터에 민감하게 반응
        - 특정 기간에만 잘 작동
        """)
    with col2:
        st.success("""
        **방지 방법:**
        - Walk-forward 분석 적용
        - Out-of-sample 테스트
        - MCPT로 통계적 유의성 검증
        - 단순한 전략 선호
        """)

    # 워크포워드 설명
    st.markdown("#### 📊 Walk-Forward 분석")
    st.markdown("""
    데이터를 여러 구간으로 나누어 **순차적으로 최적화 → 테스트**를 반복합니다.
    """)
    st.code("[최적화 1] → [테스트 1] → [최적화 2] → [테스트 2] → ...\n├── In-sample ──┤├─ Out-of-sample ─┤")
    st.markdown("**장점:** 실제 거래 환경을 시뮬레이션하여 과최적화 방지")

    # 종목 찾기 - 전략 검증용 (골든크로스/정배열/거래량)
    _render_strategy_validation_stock_finder(api)


def _render_strategy_validation_stock_finder(api):
    """전략 검증용 종목 검색 컴포넌트 (패턴 선택 가능)"""
    st.markdown("---")
    st.subheader("🔍 전략 검증용 종목 찾기")

    col1, col2 = st.columns(2)
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key="sv_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value="전체", key="sv_count")

    st.markdown("**전략 유형 선택** (복수 선택 가능)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        golden_cross = st.checkbox("✨ 골든크로스", value=True, key="sv_golden")
    with col2:
        alignment = st.checkbox("📊 정배열 (MA5>MA20>MA60)", value=True, key="sv_alignment")
    with col3:
        volume_surge = st.checkbox("📈 거래량 급증", value=True, key="sv_volume")
    with col4:
        ma120_weekly = st.checkbox("📈 주봉 120일선 돌파/지지", value=False, key="sv_ma120_weekly")

    if st.button("🔎 전략 검색 시작", key="sv_search", type="primary"):
        selected_strategies = []
        if golden_cross:
            selected_strategies.append('golden_cross')
        if alignment:
            selected_strategies.append('alignment')
        if volume_surge:
            selected_strategies.append('volume_surge')
        if ma120_weekly:
            selected_strategies.append('ma120_weekly')

        if not selected_strategies:
            st.warning("최소 1개 이상의 전략을 선택해주세요.")
        else:
            with st.spinner(f"전략 검색 중... (전략: {len(selected_strategies)}개)"):
                results = _find_strategy_validation_stocks(api, market, stock_count, selected_strategies)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                items_per_page = st.select_slider(
                    "표시 개수", options=[15, 30, 50, 100, "전체"], value=15, key="sv_items_per_page"
                )
                display_count = len(results) if items_per_page == "전체" else min(int(items_per_page), len(results))
                for i, stock in enumerate(results[:display_count]):
                    _render_strategy_validation_card(stock, api=api, key_prefix=f"sv_{i}")
                if display_count < len(results):
                    st.info(f"... 외 {len(results) - display_count}개 종목 더 있음 (위 슬라이더로 더 보기)")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_strategy_validation_card(stock: dict, api=None, key_prefix: str = "sv"):
    """전략 검증 종목 카드 렌더링 (+ 차트 보기)"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    signal = stock.get('signal', '')
    reason = stock.get('reason', '')
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    ma5 = stock.get('ma5', 0)
    ma20 = stock.get('ma20', 0)
    ma60 = stock.get('ma60', 0)

    color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{name}** ({code})")
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:bold;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col3:
            st.caption(f"{signal}")

        # 이동평균선 정보
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**현재가:** {current_price:,.0f}원")
        with col2:
            if ma5 > 0:
                st.markdown(f"📊 **MA5:** {ma5:,.0f}원")
        with col3:
            if ma20 > 0:
                st.markdown(f"📊 **MA20:** {ma20:,.0f}원")
        with col4:
            if ma60 > 0:
                st.markdown(f"📊 **MA60:** {ma60:,.0f}원")

        # 매매 전략 정보
        if entry_price > 0 and stop_loss > 0 and target_price > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col2:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:+.1f}%)")
            with col3:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표:** {target_price:,.0f}원 ({profit_pct:+.1f}%)")
            with col4:
                risk = abs(entry_price - stop_loss)
                reward = abs(target_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                st.markdown(f"📊 **R:R** = 1:{rr_ratio:.1f}")

            st.caption(f"{reason}")
        else:
            st.caption(f"{reason}")

        # 차트 보기 버튼 (expander) - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"{key_prefix}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"{key_prefix}_{code}")

        st.divider()


def _find_strategy_validation_stocks(api, market: str, stock_count, selected_strategies: list) -> list:
    """전략 검증용 종목 찾기"""
    results = []
    stocks = _get_market_stocks(market)

    if stock_count == "전체":
        search_stocks = stocks
    else:
        search_stocks = stocks[:int(stock_count)]

    progress = st.progress(0)
    total = len(search_stocks)
    for i, (code, name) in enumerate(search_stocks):
        progress.progress((i + 1) / total)
        try:
            data = _get_stock_data(api, code, 120)
            if data is None or len(data) < 60:
                continue

            ma5 = data['close'].rolling(5).mean()
            ma20 = data['close'].rolling(20).mean()
            ma60 = data['close'].rolling(60).mean()
            current = data['close'].iloc[-1]
            change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100
            recent_high = data['high'].max()
            recent_low = data['low'].iloc[-20:].min()

            # 골든크로스 (최근 5일 이내)
            if 'golden_cross' in selected_strategies:
                for j in range(1, 6):
                    if len(ma5) > j+1 and len(ma20) > j+1:
                        if ma5.iloc[-j-1] < ma20.iloc[-j-1] and ma5.iloc[-j] >= ma20.iloc[-j]:
                            entry = current
                            stop = ma20.iloc[-1] * 0.97
                            target = recent_high * 1.05
                            if stop < entry < target:
                                results.append({
                                    'code': code,
                                    'name': name,
                                    'signal': '✨ 골든크로스',
                                    'reason': f'{j}일 전 5일선이 20일선 돌파',
                                    'change_rate': change_rate,
                                    'current_price': current,
                                    'entry_price': entry,
                                    'stop_loss': stop,
                                    'target_price': target,
                                    'ma5': ma5.iloc[-1],
                                    'ma20': ma20.iloc[-1],
                                    'ma60': ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0
                                })
                            break

            # 정배열
            if 'alignment' in selected_strategies:
                if (len(ma5) > 0 and len(ma20) > 0 and len(ma60) > 0 and
                    not np.isnan(ma5.iloc[-1]) and not np.isnan(ma20.iloc[-1]) and not np.isnan(ma60.iloc[-1])):
                    if ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]:
                        entry = current
                        stop = ma20.iloc[-1] * 0.98
                        target = recent_high * 1.03
                        if stop < entry < target:
                            results.append({
                                'code': code,
                                'name': name,
                                'signal': '📊 정배열',
                                'reason': 'MA5 > MA20 > MA60',
                                'change_rate': change_rate,
                                'current_price': current,
                                'entry_price': entry,
                                'stop_loss': stop,
                                'target_price': target,
                                'ma5': ma5.iloc[-1],
                                'ma20': ma20.iloc[-1],
                                'ma60': ma60.iloc[-1]
                            })

            # 거래량 급증
            if 'volume_surge' in selected_strategies:
                avg_volume = data['volume'].iloc[:-1].mean()
                today_volume = data['volume'].iloc[-1]
                if today_volume > avg_volume * 1.5 and change_rate > 0:
                    entry = current
                    stop = data['low'].iloc[-1] * 0.98
                    target = recent_high * 1.05
                    if stop < entry < target:
                        results.append({
                            'code': code,
                            'name': name,
                            'signal': '📈 거래량 급증',
                            'reason': f'평균 대비 {today_volume/avg_volume:.1f}배 + 상승',
                            'change_rate': change_rate,
                            'current_price': current,
                            'entry_price': entry,
                            'stop_loss': stop,
                            'target_price': target,
                            'ma5': ma5.iloc[-1] if not np.isnan(ma5.iloc[-1]) else 0,
                            'ma20': ma20.iloc[-1] if not np.isnan(ma20.iloc[-1]) else 0,
                            'ma60': ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0
                        })

            # 주봉 120일선 돌파/지지
            if 'ma120_weekly' in selected_strategies:
                try:
                    # 주봉 데이터 조회 (약 2년)
                    weekly_data = _get_stock_data_weekly(api, code, 104)
                    if weekly_data is not None and len(weekly_data) >= 30:
                        # 주봉 기준 120일선 (약 24주 = 120일/5)
                        weekly_ma120 = weekly_data['close'].rolling(24).mean()
                        weekly_current = weekly_data['close'].iloc[-1]
                        weekly_prev = weekly_data['close'].iloc[-2]
                        weekly_ma120_now = weekly_ma120.iloc[-1]
                        weekly_ma120_prev = weekly_ma120.iloc[-2]
                        weekly_volume = weekly_data['volume'].iloc[-1]
                        weekly_avg_volume = weekly_data['volume'].iloc[-10:-1].mean()

                        if not np.isnan(weekly_ma120_now) and not np.isnan(weekly_ma120_prev):
                            # 조건 1: 120일선 돌파 (이전 주 아래, 이번 주 위 + 거래량 급증)
                            is_breakout = (weekly_prev < weekly_ma120_prev and weekly_current > weekly_ma120_now)
                            volume_surge_weekly = (weekly_volume > weekly_avg_volume * 1.3) if weekly_avg_volume > 0 else False

                            # 조건 2: 120일선 지지 (현재가가 120일선 근처 ±3% 내에서 반등)
                            ma120_proximity = abs(weekly_current - weekly_ma120_now) / weekly_ma120_now * 100
                            is_support = (ma120_proximity < 3 and weekly_current > weekly_prev and weekly_current >= weekly_ma120_now)

                            if is_breakout and volume_surge_weekly:
                                entry = current
                                stop = weekly_ma120_now * 0.95
                                target = current * 1.10
                                vol_ratio = weekly_volume / weekly_avg_volume if weekly_avg_volume > 0 else 1
                                results.append({
                                    'code': code,
                                    'name': name,
                                    'signal': '🚀 주봉 120일선 돌파',
                                    'reason': f'거래량 {vol_ratio:.1f}배 동반 돌파',
                                    'change_rate': change_rate,
                                    'current_price': current,
                                    'entry_price': entry,
                                    'stop_loss': stop,
                                    'target_price': target,
                                    'ma5': ma5.iloc[-1] if not np.isnan(ma5.iloc[-1]) else 0,
                                    'ma20': ma20.iloc[-1] if not np.isnan(ma20.iloc[-1]) else 0,
                                    'ma60': ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0
                                })
                            elif is_support:
                                entry = current
                                stop = weekly_ma120_now * 0.97
                                target = current * 1.08
                                results.append({
                                    'code': code,
                                    'name': name,
                                    'signal': '💎 주봉 120일선 지지',
                                    'reason': f'120일선 근처 ({ma120_proximity:.1f}%) 반등',
                                    'change_rate': change_rate,
                                    'current_price': current,
                                    'entry_price': entry,
                                    'stop_loss': stop,
                                    'target_price': target,
                                    'ma5': ma5.iloc[-1] if not np.isnan(ma5.iloc[-1]) else 0,
                                    'ma20': ma20.iloc[-1] if not np.isnan(ma20.iloc[-1]) else 0,
                                    'ma60': ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0
                                })
                except:
                    pass
        except:
            continue

    progress.empty()
    return results


# =====================================================
# 종합 추천 섹션
# =====================================================

def _render_comprehensive_recommendation_section(api):
    """종합 추천 섹션 - 모든 전략 기반 최고 수익 예상 종목"""
    st.subheader("🏆 종합 추천 (AI 기반 전략 통합)")

    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
        <p style='color: white; margin: 0; font-size: 0.9rem;'>
            📊 <b>8가지 차트 전략을 종합 분석</b>하여 가장 높은 수익이 예상되는 종목을 추천합니다.<br>
            각 전략별 신호를 점수화하고, R:R 비율을 고려하여 최적의 매수 기회를 제시합니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ========== 개별 종목 검색 섹션 ==========
    st.markdown("### 🔎 개별 종목 점수 조회")

    # 전체 종목 리스트 로드 (매번 새로 로드 - stock_list.py에서 자체 캐싱됨)
    kospi = get_kospi_stocks()
    kosdaq = get_kosdaq_stocks()
    all_stocks = kospi + kosdaq

    # 디버깅: 종목 수 출력
    print(f"[chart_strategy] 종목 로드: KOSPI {len(kospi)}개, KOSDAQ {len(kosdaq)}개, 전체 {len(all_stocks)}개")

    # "종목명 (종목코드)" 형식으로 변환
    stock_options = ["-- 종목 선택 --"] + [f"{name} ({code})" for code, name in all_stocks]
    stock_map = {f"{name} ({code})": (code, name) for code, name in all_stocks}

    # selectbox로 자동완성 검색 (Streamlit의 selectbox는 검색 기능 내장)
    # 모바일 모드 확인
    is_mobile = st.session_state.get('mobile_mode', False)

    if is_mobile:
        # 모바일: 전체 너비 사용
        selected_stock = st.selectbox(
            "종목 선택",
            options=stock_options,
            index=0,
            key="single_stock_selectbox",
            help="종목명 또는 코드 일부를 입력하면 자동완성됩니다"
        )
        search_btn = st.button("📊 점수 조회", key="single_stock_btn", type="primary", use_container_width=True)
    else:
        # 데스크톱: 기존 레이아웃
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_stock = st.selectbox(
                "종목 선택 (검색어 입력 시 자동완성)",
                options=stock_options,
                index=0,
                key="single_stock_selectbox",
                help="종목명 또는 코드 일부를 입력하면 자동완성됩니다"
            )
        with col2:
            search_btn = st.button("📊 점수 조회", key="single_stock_btn", type="primary")

    # 검색 실행 - 종목이 선택되고 버튼 클릭 시
    if search_btn and selected_stock and selected_stock in stock_map:
        code, name = stock_map[selected_stock]
        _analyze_single_stock(api, code)

    st.markdown("---")

    # ========== 시장 전체 분석 섹션 ==========
    st.markdown("### 📈 시장 전체 종합 분석")

    # 시장 선택
    col1, col2 = st.columns(2)
    with col1:
        market = st.radio(
            "시장 선택",
            ["KOSPI", "KOSDAQ"],
            horizontal=True,
            key="comprehensive_market"
        )
    with col2:
        top_n = st.select_slider(
            "추천 종목 수",
            options=[10, 20, 30, 50],
            value=20,
            key="comprehensive_top_n"
        )

    # 분석 옵션
    st.markdown("**분석 전략 선택**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        use_trendline = st.checkbox("추세선 지지", value=True, key="comp_trendline")
        use_harmonic = st.checkbox("조화 패턴", value=True, key="comp_harmonic")
    with col2:
        use_head_shoulders = st.checkbox("머리어깨", value=True, key="comp_hs")
        use_flag_pennant = st.checkbox("깃발/페넌트", value=True, key="comp_flag")
    with col3:
        use_fibonacci = st.checkbox("피보나치", value=True, key="comp_fib")
        use_directional = st.checkbox("방향성 변화", value=True, key="comp_dc")
    with col4:
        use_support_resistance = st.checkbox("지지/저항", value=True, key="comp_sr")
        use_ma_alignment = st.checkbox("이평선 정배열", value=True, key="comp_ma")

    if st.button("🔍 종합 분석 시작", key="comprehensive_search", type="primary"):
        strategies = {
            'trendline': use_trendline,
            'harmonic': use_harmonic,
            'head_shoulders': use_head_shoulders,
            'flag_pennant': use_flag_pennant,
            'fibonacci': use_fibonacci,
            'directional': use_directional,
            'support_resistance': use_support_resistance,
            'ma_alignment': use_ma_alignment
        }

        with st.spinner(f"🔄 {market} 전 종목 종합 분석 중... (시간이 소요될 수 있습니다)"):
            results = _analyze_comprehensive_stocks(api, market, strategies)

        if results:
            # 점수 기준 정렬
            results.sort(key=lambda x: x['total_score'], reverse=True)
            top_results = results[:top_n]

            st.success(f"✅ {len(results)}개 종목 분석 완료! 상위 {len(top_results)}개 추천")

            # 요약 통계
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                avg_score = sum(r['total_score'] for r in top_results) / len(top_results)
                st.metric("평균 점수", f"{avg_score:.1f}점")
            with col2:
                avg_rr = sum(r['rr_ratio'] for r in top_results if r['rr_ratio'] > 0) / max(1, len([r for r in top_results if r['rr_ratio'] > 0]))
                st.metric("평균 R:R", f"1:{avg_rr:.1f}")
            with col3:
                bullish = len([r for r in top_results if '매수' in r['signal'] or '강세' in r['signal'] or '상승' in r['signal']])
                st.metric("매수 신호", f"{bullish}개")
            with col4:
                high_score = len([r for r in top_results if r['total_score'] >= 70])
                st.metric("고점수(70+)", f"{high_score}개")

            st.markdown("---")

            # 결과 표시
            for i, stock in enumerate(top_results):
                _render_comprehensive_card(stock, api, i)

        else:
            st.info("분석 결과가 없습니다. 전략을 다시 선택해주세요.")


def _analyze_comprehensive_stocks(api, market: str, strategies: dict) -> list:
    """종합 분석 - 모든 전략을 적용하여 점수화"""
    results = []
    stocks = _get_market_stocks(market)

    progress = st.progress(0)
    total = len(stocks)

    for i, (code, name) in enumerate(stocks):
        progress.progress((i + 1) / total)

        try:
            data = _get_stock_data(api, code, 120)
            if data is None or len(data) < 60:
                continue

            data = data.sort_index()
            current = data['close'].iloc[-1]
            prev_close = data['close'].iloc[-2] if len(data) > 1 else current
            change_rate = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0

            # 기본 지표 계산
            ma5 = data['close'].rolling(window=5).mean()
            ma20 = data['close'].rolling(window=20).mean()
            ma60 = data['close'].rolling(window=60).mean()
            ma120 = data['close'].rolling(window=120).mean()

            # ATR 계산
            high_low = data['high'] - data['low']
            high_close = np.abs(data['high'] - data['close'].shift())
            low_close = np.abs(data['low'] - data['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]

            # 점수 및 신호 수집
            total_score = 0
            signals = []
            entry_prices = []
            stop_losses = []
            target_prices = []

            # 1. 추세선 지지 분석
            if strategies.get('trendline', False):
                score, signal, entry, stop, target = _check_trendline_signal(data, ma20, current, atr)
                if score > 0:
                    total_score += score
                    signals.append(signal)
                    if entry: entry_prices.append(entry)
                    if stop: stop_losses.append(stop)
                    if target: target_prices.append(target)

            # 2. 이평선 정배열 분석
            if strategies.get('ma_alignment', False):
                score, signal, entry, stop, target = _check_ma_alignment_signal(data, ma5, ma20, ma60, current, atr)
                if score > 0:
                    total_score += score
                    signals.append(signal)
                    if entry: entry_prices.append(entry)
                    if stop: stop_losses.append(stop)
                    if target: target_prices.append(target)

            # 3. 피보나치 분석
            if strategies.get('fibonacci', False):
                score, signal, entry, stop, target = _check_fibonacci_signal(data, current, atr)
                if score > 0:
                    total_score += score
                    signals.append(signal)
                    if entry: entry_prices.append(entry)
                    if stop: stop_losses.append(stop)
                    if target: target_prices.append(target)

            # 4. 볼린저 밴드 분석 (지지/저항 대용)
            if strategies.get('support_resistance', False):
                score, signal, entry, stop, target = _check_bollinger_signal(data, ma20, current, atr)
                if score > 0:
                    total_score += score
                    signals.append(signal)
                    if entry: entry_prices.append(entry)
                    if stop: stop_losses.append(stop)
                    if target: target_prices.append(target)

            # 5. 거래량 분석
            if strategies.get('directional', False):
                score, signal, entry, stop, target = _check_volume_signal(data, current, atr)
                if score > 0:
                    total_score += score
                    signals.append(signal)
                    if entry: entry_prices.append(entry)
                    if stop: stop_losses.append(stop)
                    if target: target_prices.append(target)

            # 6. RSI 분석
            score, signal = _check_rsi_signal(data)
            if score > 0:
                total_score += score
                signals.append(signal)

            # 7. MACD 분석
            score, signal = _check_macd_signal(data)
            if score > 0:
                total_score += score
                signals.append(signal)

            # 최소 점수 이상일 때만 결과에 추가
            if total_score >= 20 and len(signals) >= 2:
                # 진입가, 손절, 목표가 결정
                if entry_prices:
                    entry = np.mean(entry_prices)
                else:
                    entry = ma20.iloc[-1] * 1.01 if not np.isnan(ma20.iloc[-1]) else current

                if stop_losses:
                    stop = np.mean(stop_losses)
                else:
                    stop = entry - (atr * 1.5) if atr > 0 else entry * 0.95

                if target_prices:
                    target = np.mean(target_prices)
                else:
                    # ATR 기반 목표가 (2.5배 ATR)
                    target = entry + (atr * 2.5) if atr > 0 else entry * 1.10

                # R:R 비율 계산
                risk = abs(entry - stop)
                reward = abs(target - entry)
                rr_ratio = reward / risk if risk > 0 else 0

                # R:R 비율이 좋을수록 점수 추가
                if rr_ratio >= 2:
                    total_score += 15
                elif rr_ratio >= 1.5:
                    total_score += 10
                elif rr_ratio >= 1:
                    total_score += 5

                results.append({
                    'code': code,
                    'name': name,
                    'total_score': total_score,
                    'signals': signals,
                    'signal': ' | '.join(signals[:3]),
                    'signal_count': len(signals),
                    'change_rate': change_rate,
                    'current_price': current,
                    'entry_price': entry,
                    'stop_loss': stop,
                    'target_price': target,
                    'rr_ratio': rr_ratio,
                    'ma5': ma5.iloc[-1] if not np.isnan(ma5.iloc[-1]) else 0,
                    'ma20': ma20.iloc[-1] if not np.isnan(ma20.iloc[-1]) else 0,
                    'ma60': ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0,
                    'ma120': ma120.iloc[-1] if not np.isnan(ma120.iloc[-1]) else 0,
                    'atr': atr
                })

        except Exception as e:
            continue

    progress.empty()
    return results


def _check_trendline_signal(data, ma20, current, atr):
    """추세선 지지 신호 확인 (조건 완화)"""
    score = 0
    signal = ""
    entry = stop = target = None

    try:
        ma20_val = ma20.iloc[-1]
        if np.isnan(ma20_val):
            return 0, "", None, None, None

        # MA20 대비 현재가 위치 계산
        ma20_ratio = (current - ma20_val) / ma20_val * 100

        # 20일선 돌파 (전일 대비)
        if len(data) > 1 and current > ma20_val and data['close'].iloc[-2] < ma20.iloc[-2]:
            score = 20
            signal = "🚀 MA20 돌파"
            entry = current
            stop = ma20_val * 0.98
            target = entry + (atr * 2.5) if atr > 0 else current * 1.10

        # 20일선 위에서 지지 (0~5% 범위 확대)
        elif 0 < ma20_ratio < 5:
            score = 15
            signal = "📈 추세 지지"
            entry = ma20_val * 1.01
            stop = ma20_val * 0.97
            target = entry + (atr * 2) if atr > 0 else current * 1.08

        # 20일선 근처에서 반등 시도 (-2% ~ +2%)
        elif -2 < ma20_ratio < 2:
            score = 10
            signal = "📉 MA20 근접"
            entry = ma20_val * 1.01
            stop = ma20_val * 0.95
            target = entry + (atr * 1.5) if atr > 0 else current * 1.05

    except:
        pass

    return score, signal, entry, stop, target


def _check_ma_alignment_signal(data, ma5, ma20, ma60, current, atr):
    """이평선 정배열 신호 확인 (조건 완화)"""
    score = 0
    signal = ""
    entry = stop = target = None

    try:
        ma5_val = ma5.iloc[-1]
        ma20_val = ma20.iloc[-1]
        ma60_val = ma60.iloc[-1]

        if np.isnan(ma5_val) or np.isnan(ma20_val) or np.isnan(ma60_val):
            return 0, "", None, None, None

        # 정배열: MA5 > MA20 > MA60
        if ma5_val > ma20_val > ma60_val:
            # 현재가가 5일선 위
            if current > ma5_val:
                score = 25
                signal = "📊 정배열 강세"
                entry = ma5_val * 1.01
                stop = ma20_val * 0.98
                target = entry + (atr * 3) if atr > 0 else current * 1.12
            # 현재가가 5일선에서 지지
            elif current > ma20_val:
                score = 15
                signal = "📊 정배열"
                entry = ma20_val * 1.01
                stop = ma60_val * 0.98
                target = entry + (atr * 2) if atr > 0 else ma5_val * 1.05

        # 준정배열: MA5 > MA20 (60일선 무시) - 추가 조건
        elif ma5_val > ma20_val and current > ma20_val:
            score = 10
            signal = "📊 준정배열"
            entry = ma20_val * 1.01
            stop = ma20_val * 0.95
            target = entry + (atr * 1.5) if atr > 0 else ma5_val * 1.03

        # 역배열에서 회복 시도: 현재가 > MA5 > MA20 (60일선 위에 있음)
        elif current > ma5_val > ma20_val:
            score = 8
            signal = "📊 이평 회복"
            entry = ma5_val * 1.01
            stop = ma20_val * 0.97
            target = entry + (atr * 1.5) if atr > 0 else current * 1.05

    except:
        pass

    return score, signal, entry, stop, target


def _check_fibonacci_signal(data, current, atr):
    """피보나치 신호 확인 (조건 완화: 5% 오차)"""
    score = 0
    signal = ""
    entry = stop = target = None

    try:
        recent_high = data['high'].iloc[-30:].max()  # 30일로 확대
        recent_low = data['low'].iloc[-30:].min()
        fib_range = recent_high - recent_low

        if fib_range <= 0:
            return 0, "", None, None, None

        fib_236 = recent_high - fib_range * 0.236
        fib_382 = recent_high - fib_range * 0.382
        fib_50 = recent_high - fib_range * 0.5
        fib_618 = recent_high - fib_range * 0.618

        # 피보나치 레벨 근처 (5% 오차로 확대)
        tolerance = fib_range * 0.05

        if abs(current - fib_236) < tolerance:
            score = 12
            signal = "📐 Fib 23.6%"
            entry = fib_236 * 1.01
            stop = fib_382 * 0.98
            target = recent_high * 0.98
        elif abs(current - fib_382) < tolerance:
            score = 15
            signal = "📐 Fib 38.2%"
            entry = fib_382 * 1.01
            stop = fib_50 * 0.98
            target = recent_high * 0.95
        elif abs(current - fib_50) < tolerance:
            score = 18
            signal = "📐 Fib 50%"
            entry = fib_50 * 1.01
            stop = fib_618 * 0.98
            target = fib_382 * 1.02
        elif abs(current - fib_618) < tolerance:
            score = 20
            signal = "📐 Fib 61.8%"
            entry = fib_618 * 1.01
            stop = recent_low * 0.98
            target = fib_50 * 1.02

    except:
        pass

    return score, signal, entry, stop, target


def _check_bollinger_signal(data, ma20, current, atr):
    """볼린저 밴드 신호 확인 (조건 완화)"""
    score = 0
    signal = ""
    entry = stop = target = None

    try:
        std20 = data['close'].rolling(window=20).std()
        ma20_val = ma20.iloc[-1]
        std_val = std20.iloc[-1]

        if np.isnan(ma20_val) or np.isnan(std_val) or std_val <= 0:
            return 0, "", None, None, None

        upper = ma20_val + 2 * std_val
        lower = ma20_val - 2 * std_val

        # 밴드폭 계산
        bandwidth = (upper - lower) / ma20_val * 100

        # 현재가의 밴드 내 위치 (0=하단, 1=상단)
        bb_position = (current - lower) / (upper - lower) if upper != lower else 0.5

        # 하단 밴드 근처 (하위 20%)
        if bb_position < 0.2:
            score = 15
            signal = "🔵 BB 하단"
            entry = lower * 1.01
            stop = lower * 0.97
            target = ma20_val

        # 하단~중심 (20%~40% 구간)
        elif bb_position < 0.4:
            score = 12
            signal = "🔵 BB 하단 반등"
            entry = current
            stop = lower * 0.98
            target = ma20_val * 1.02

        # 중심선 지지 (40%~60% 구간)
        elif 0.4 < bb_position < 0.6:
            score = 10
            signal = "🟡 BB 중심"
            entry = ma20_val * 1.01
            stop = lower * 0.98
            target = upper * 0.95

        # 상단 밴드 근처 (상위 20%) - 주의 신호
        elif bb_position > 0.8:
            score = 5
            signal = "🔴 BB 상단 (과열)"
            entry = None
            stop = ma20_val * 0.98
            target = None

    except:
        pass

    return score, signal, entry, stop, target


def _check_volume_signal(data, current, atr):
    """거래량 신호 확인 (조건 완화)"""
    score = 0
    signal = ""
    entry = stop = target = None

    try:
        avg_volume = data['volume'].iloc[-20:-1].mean()
        today_volume = data['volume'].iloc[-1]
        change = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

        if avg_volume <= 0:
            return 0, "", None, None, None

        vol_ratio = today_volume / avg_volume

        # 거래량 급증 + 상승
        if vol_ratio > 2 and change > 0:
            score = 20
            signal = "📊 거래량 폭발"
            entry = current
            stop = data['low'].iloc[-1] * 0.97
            target = entry + (atr * 3) if atr > 0 else current * 1.12
        elif vol_ratio > 1.5 and change > 0:
            score = 12
            signal = "📊 거래량 증가"
            entry = current
            stop = data['low'].iloc[-1] * 0.98
            target = entry + (atr * 2) if atr > 0 else current * 1.08
        # 거래량 평균 이상 + 상승 (조건 완화)
        elif vol_ratio > 1.0 and change > 1:
            score = 8
            signal = "📊 거래량 양호"
            entry = current
            stop = data['low'].iloc[-1] * 0.98
            target = entry + (atr * 1.5) if atr > 0 else current * 1.05
        # 거래량 감소 중 (관망 신호)
        elif vol_ratio < 0.5:
            score = 3
            signal = "📉 거래량 감소"
            entry = None
            stop = None
            target = None

    except:
        pass

    return score, signal, entry, stop, target


def _check_rsi_signal(data):
    """RSI 신호 확인"""
    score = 0
    signal = ""

    try:
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]

        if rsi_val < 30:
            score = 15
            signal = "🔴 RSI 과매도"
        elif rsi_val < 40:
            score = 10
            signal = "🟠 RSI 저점"
        elif 40 <= rsi_val <= 60:
            score = 5
            signal = "🟢 RSI 중립"

    except:
        pass

    return score, signal


def _check_macd_signal(data):
    """MACD 신호 확인"""
    score = 0
    signal = ""

    try:
        ema12 = data['close'].ewm(span=12).mean()
        ema26 = data['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        signal_line = macd.ewm(span=9).mean()

        macd_val = macd.iloc[-1]
        signal_val = signal_line.iloc[-1]
        macd_prev = macd.iloc[-2]
        signal_prev = signal_line.iloc[-2]

        # MACD 골든크로스
        if macd_prev < signal_prev and macd_val > signal_val:
            score = 20
            signal = "🌟 MACD 골든크로스"
        # MACD 상승 중
        elif macd_val > signal_val and macd_val > macd_prev:
            score = 10
            signal = "📈 MACD 상승"
        # MACD 바닥 반등
        elif macd_val < 0 and macd_val > macd_prev:
            score = 8
            signal = "🔄 MACD 반등"

    except:
        pass

    return score, signal


def _render_comprehensive_card(stock: dict, api=None, index: int = 0):
    """종합 추천 종목 카드 렌더링"""
    code = stock.get('code', '')
    name = stock.get('name', '')
    total_score = stock.get('total_score', 0)
    signals = stock.get('signals', [])
    signal_count = stock.get('signal_count', 0)
    change_rate = stock.get('change_rate', 0)
    current_price = stock.get('current_price', 0)
    entry_price = stock.get('entry_price', 0)
    stop_loss = stock.get('stop_loss', 0)
    target_price = stock.get('target_price', 0)
    rr_ratio = stock.get('rr_ratio', 0)

    # 점수에 따른 색상
    if total_score >= 70:
        score_color = "#00C851"
        grade = "A+"
    elif total_score >= 55:
        score_color = "#33b5e5"
        grade = "A"
    elif total_score >= 40:
        score_color = "#ffbb33"
        grade = "B"
    else:
        score_color = "#888"
        grade = "C"

    change_color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    with st.container():
        # 헤더: 순위, 종목명, 점수
        col1, col2, col3, col4 = st.columns([0.5, 2, 1.5, 1])
        with col1:
            st.markdown(f"<h2 style='margin:0; color:{score_color};'>#{index + 1}</h2>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{name}** ({code})")
            st.caption(f"신호 {signal_count}개 감지")
        with col3:
            st.markdown(f"<span style='color:{change_color};font-weight:bold;font-size:1.2rem;'>{sign}{change_rate:.2f}%</span>", unsafe_allow_html=True)
        with col4:
            st.markdown(f"<div style='background:{score_color};color:white;padding:0.5rem;border-radius:5px;text-align:center;'><b>{grade}</b><br>{total_score:.0f}점</div>", unsafe_allow_html=True)

        # 신호 목록
        st.markdown("**감지된 신호:** " + " | ".join(signals[:5]))

        # 매매 전략 (개선된 카드 UI)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.8rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>현재가</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{current_price:,.0f}원</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            entry_diff = ((entry_price - current_price) / current_price) * 100 if current_price > 0 else 0
            entry_badge = "#FF4444" if entry_diff >= 0 else "#4444FF"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.8rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🎯 진입가</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{entry_price:,.0f}원</div>
                <span style='background: {entry_badge}; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.75rem; font-weight: bold;'>{entry_diff:+.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.8rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🛑 손절</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{stop_loss:,.0f}원</div>
                <span style='background: #4444FF; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.75rem; font-weight: bold;'>{loss_pct:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.8rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🎁 목표</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{target_price:,.0f}원</div>
                <span style='background: #FF4444; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.75rem; font-weight: bold;'>+{profit_pct:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
        with col5:
            rr_badge = "#22c55e" if rr_ratio >= 2 else "#f59e0b" if rr_ratio >= 1 else "#ef4444"
            rr_text = "좋음" if rr_ratio >= 2 else "보통" if rr_ratio >= 1 else "위험"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.8rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>📊 R:R</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>1:{rr_ratio:.1f}</div>
                <span style='background: {rr_badge}; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.75rem; font-weight: bold;'>{rr_text}</span>
            </div>
            """, unsafe_allow_html=True)

        # 차트 보기 - 세션 상태로 열림 유지
        if api is not None:
            expander_key = f"comp_{index}_expander_{code}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False
            with st.expander(f"📈 차트 보기 - {name}", expanded=st.session_state[expander_key]):
                st.session_state[expander_key] = True  # 열리면 상태 유지
                _render_stock_chart(api, code, name, f"comp_{index}_{code}")

        st.divider()


def _analyze_single_stock(api, stock_code: str):
    """개별 종목 종합 점수 분석

    Args:
        api: KIS API 인스턴스
        stock_code: 6자리 종목코드
    """
    # 종목코드 정규화
    code = stock_code.zfill(6)
    name = get_stock_name(code)

    if not name:
        st.error(f"❌ 종목코드 '{code}'를 찾을 수 없습니다.")
        return

    # ========== 섹터 조회 V5 (2026-02-01 21:15) - UTF-8 ==========
    sector_info = "기타"
    sector_source = "fallback"

    try:
        import requests
        from bs4 import BeautifulSoup

        # 네이버 금융에서 직접 조회 (UTF-8 인코딩)
        naver_url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        }
        resp = requests.get(naver_url, headers=headers, timeout=10)

        if resp.status_code == 200:
            # 네이버 금융은 UTF-8 (resp.text가 자동으로 처리)
            soup = BeautifulSoup(resp.text, 'lxml')

            # 업종 링크에서 추출
            sector_link = soup.find('a', href=lambda x: x and 'sise_group_detail' in x and 'upjong' in x)

            if sector_link:
                raw_sector = sector_link.get_text(strip=True)

                # 섹터명 정제 매핑
                sector_mapping = {
                    '반도체와반도체장비': '반도체', '전자장비와기기': '반도체장비',
                    '소프트웨어': 'AI/소프트웨어', 'IT서비스': 'AI/IT서비스', '인터넷': 'AI/플랫폼',
                    '전기장비': '2차전지', '에너지장비': '2차전지장비',
                    '자동차': '자동차', '자동차부품': '자동차부품',
                    '제약': '제약', '바이오': '바이오', '생물공학': '바이오',
                    '건강관리장비와용품': '헬스케어', '건강관리업체및서비스': '헬스케어',
                    '화학': '화학', '석유와가스': '석유화학',
                    '은행': '은행', '보험': '보험', '증권': '증권',
                    '건설': '건설', '부동산': '부동산',
                    '백화점과일반상점': '유통', '식품': '식품', '음식료품': '식품',
                    '조선': '조선', '해운': '해운', '항공': '항공',
                    '항공우주와국방': '우주항공', '국방': '방산',
                    '철강': '철강', '기계': '기계',
                    '무선통신서비스': '통신/5G', '다각화된통신서비스': '통신/5G',
                    '엔터테인먼트': '엔터', '방송과엔터테인먼트': '엔터',
                    '전기유틸리티': '전력',
                }
                sector_info = sector_mapping.get(raw_sector, raw_sector)
                sector_source = 'naver'

        # 네이버에서 못 찾으면 KIS API fallback
        if sector_info == '기타' and hasattr(api, 'get_company_overview'):
            try:
                overview = api.get_company_overview(code)
                if overview and overview.get('sector'):
                    sector_info = overview['sector']
                    sector_source = 'kis'
            except Exception:
                pass

    except Exception:
        sector_info = "기타"
        sector_source = "error"

    # 종목 데이터 가져오기
    with st.spinner(f"🔄 {name}({code}) 분석 중..."):
        data = _get_stock_data(api, code, 120)

    if data is None or len(data) < 60:
        st.error(f"❌ {name}({code}) 데이터를 가져올 수 없습니다.")
        return

    # 분석 수행
    data = data.sort_index()
    current = data['close'].iloc[-1]
    prev_close = data['close'].iloc[-2] if len(data) > 1 else current
    change_rate = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0

    # 기본 지표 계산
    ma5 = data['close'].rolling(window=5).mean()
    ma20 = data['close'].rolling(window=20).mean()
    ma60 = data['close'].rolling(window=60).mean()
    ma120 = data['close'].rolling(window=120).mean()

    # ATR 계산
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean().iloc[-1]

    # 점수 및 신호 수집
    total_score = 0
    signals = []
    signal_details = []
    entry_prices = []
    stop_losses = []
    target_prices = []

    # 1. 추세선 지지 분석
    score, signal, entry, stop, target = _check_trendline_signal(data, ma20, current, atr)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('추세선 지지', signal, score))
        if entry: entry_prices.append(entry)
        if stop: stop_losses.append(stop)
        if target: target_prices.append(target)
    else:
        signal_details.append(('추세선 지지', '미감지', 0))

    # 2. 이평선 정배열 분석
    score, signal, entry, stop, target = _check_ma_alignment_signal(data, ma5, ma20, ma60, current, atr)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('이평선 정배열', signal, score))
        if entry: entry_prices.append(entry)
        if stop: stop_losses.append(stop)
        if target: target_prices.append(target)
    else:
        signal_details.append(('이평선 정배열', '미감지', 0))

    # 3. 피보나치 분석
    score, signal, entry, stop, target = _check_fibonacci_signal(data, current, atr)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('피보나치', signal, score))
        if entry: entry_prices.append(entry)
        if stop: stop_losses.append(stop)
        if target: target_prices.append(target)
    else:
        signal_details.append(('피보나치', '미감지', 0))

    # 4. 볼린저 밴드 분석
    score, signal, entry, stop, target = _check_bollinger_signal(data, ma20, current, atr)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('볼린저밴드', signal, score))
        if entry: entry_prices.append(entry)
        if stop: stop_losses.append(stop)
        if target: target_prices.append(target)
    else:
        signal_details.append(('볼린저밴드', '미감지', 0))

    # 5. 거래량 분석
    score, signal, entry, stop, target = _check_volume_signal(data, current, atr)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('거래량', signal, score))
        if entry: entry_prices.append(entry)
        if stop: stop_losses.append(stop)
        if target: target_prices.append(target)
    else:
        signal_details.append(('거래량', '미감지', 0))

    # 6. RSI 분석
    score, signal = _check_rsi_signal(data)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('RSI', signal, score))
    else:
        signal_details.append(('RSI', '미감지', 0))

    # 7. MACD 분석
    score, signal = _check_macd_signal(data)
    if score > 0:
        total_score += score
        signals.append(signal)
        signal_details.append(('MACD', signal, score))
    else:
        signal_details.append(('MACD', '미감지', 0))

    # 진입가, 손절, 목표가 결정
    if entry_prices:
        entry = np.mean(entry_prices)
    else:
        entry = ma20.iloc[-1] * 1.01 if not np.isnan(ma20.iloc[-1]) else current

    if stop_losses:
        stop = np.mean(stop_losses)
    else:
        stop = entry - (atr * 1.5) if atr > 0 else entry * 0.95

    if target_prices:
        target = np.mean(target_prices)
    else:
        # ATR 기반 목표가 (2.5배 ATR)
        target = entry + (atr * 2.5) if atr > 0 else entry * 1.10

    # R:R 비율 계산
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr_ratio = reward / risk if risk > 0 else 0

    # R:R 비율이 좋을수록 점수 추가
    rr_bonus = 0
    if rr_ratio >= 2:
        rr_bonus = 15
    elif rr_ratio >= 1.5:
        rr_bonus = 10
    elif rr_ratio >= 1:
        rr_bonus = 5
    total_score += rr_bonus

    # 등급 결정
    if total_score >= 70:
        grade = "A+"
        grade_color = "#00C851"
        grade_desc = "매우 강력한 매수 신호"
    elif total_score >= 55:
        grade = "A"
        grade_color = "#33b5e5"
        grade_desc = "강력한 매수 신호"
    elif total_score >= 40:
        grade = "B"
        grade_color = "#ffbb33"
        grade_desc = "보통 매수 신호"
    elif total_score >= 25:
        grade = "C"
        grade_color = "#ff8800"
        grade_desc = "약한 매수 신호"
    else:
        grade = "D"
        grade_color = "#CC0000"
        grade_desc = "매수 비추천"

    change_color = "#FF3B30" if change_rate > 0 else "#007AFF" if change_rate < 0 else "#888"
    sign = "+" if change_rate > 0 else ""

    # 모바일 모드 확인
    is_mobile = st.session_state.get('mobile_mode', False)

    # 섹터 배지 색상 설정 (세부 섹터별)
    sector_colors = {
        # 반도체/IT (파란색 계열)
        '반도체': '#1565C0', '반도체장비': '#1976D2', '반도체소재': '#2196F3',
        'AI반도체': '#0D47A1', 'AI': '#1A237E', 'AI/플랫폼': '#283593',
        'AI/게임': '#303F9F', 'AI/SaaS': '#3949AB', 'AI인프라': '#3F51B5',
        'AI소프트웨어': '#5C6BC0', 'AI로봇': '#7986CB', 'AI클라우드': '#9FA8DA',
        'IT': '#2196F3', '인터넷': '#42A5F5', '게임': '#9C27B0',

        # 2차전지/배터리 (녹색-청록 계열)
        '2차전지': '#00897B', '2차전지소재': '#00ACC1', '2차전지장비': '#26C6DA',

        # 우주항공/방산 (진한 남색-회색)
        '우주항공': '#37474F', '방산': '#455A64', '방산전자': '#546E7A',
        '조선방산': '#607D8B', '조선': '#78909C',

        # 자동차 (회색-금속 계열)
        '자동차': '#546E7A', '자동차부품': '#607D8B', '전기차부품': '#00838F',
        '타이어': '#78909C',

        # 바이오/헬스케어 (녹색 계열)
        '바이오': '#2E7D32', '바이오CMO': '#388E3C', '제약': '#43A047',
        '헬스케어': '#4CAF50', '진단키트': '#66BB6A', '화장품': '#81C784',

        # 금융 (빨간색 계열)
        '금융': '#C62828', '은행': '#D32F2F', '보험': '#E53935',
        '카드/캐피탈': '#F44336', '증권': '#EF5350', '금융지주': '#E57373',

        # 에너지/화학 (주황색 계열)
        '에너지': '#E65100', '석유화학': '#EF6C00', '정유': '#F57C00',
        '화학': '#FF9800', '가스': '#FFA726', '에너지솔루션': '#FFB74D',
        '에너지장비': '#FFCC80',

        # 건설/철강 (갈색 계열)
        '건설': '#5D4037', '건자재': '#6D4C41', '철강': '#795548',
        '철강/건자재': '#8D6E63',

        # 통신 (청록 계열)
        '통신': '#00695C', '통신/5G': '#00796B',

        # 엔터/미디어 (핑크-보라 계열)
        '엔터': '#AD1457', 'K-POP': '#C2185B', '미디어': '#D81B60',
        '엔터테인먼트': '#E91E63',

        # 로봇/자동화 (보라 계열)
        '로봇': '#6A1B9A', '로봇부품': '#7B1FA2', '자동화장비': '#8E24AA',

        # 유통/식품 (노란색 계열)
        '유통': '#F9A825', '식품': '#FBC02D', '소비재': '#FFEB3B',

        # 기타
        '산업재': '#827717', '전력설비': '#9E9D24', '화학/섬유': '#AFB42B',
        'SK그룹': '#00BCD4', '해운': '#0097A7', 'IoT': '#00ACC1',
    }
    sector_color = sector_colors.get(sector_info, '#9E9E9E')

    # 결과 표시 - 모바일/데스크톱 분기
    if is_mobile:
        # 모바일: 세로 배치, 작은 폰트
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, {grade_color}22 0%, {grade_color}11 100%);
                    padding: 1rem; border-radius: 12px; border: 2px solid {grade_color}; margin: 0.5rem 0;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;'>
                <div style='flex: 1; min-width: 150px;'>
                    <h3 style='margin: 0; color: #333; font-size: 1.1rem;'>{name}</h3>
                    <p style='margin: 0.2rem 0; color: #666; font-size: 0.85rem;'>{code}
                        <span style='background: {sector_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-left: 5px;'>{sector_info}</span>
                    </p>
                    <p style='margin: 0.3rem 0; color: {change_color}; font-size: 1rem; font-weight: bold;'>
                        {current:,.0f}원 ({sign}{change_rate:.2f}%)
                    </p>
                </div>
                <div style='text-align: center; background: {grade_color}; padding: 0.5rem 1rem; border-radius: 8px;'>
                    <div style='color: white; font-size: 1.8rem; font-weight: bold;'>{grade}</div>
                    <div style='color: white; font-size: 1rem;'>{total_score}점</div>
                </div>
            </div>
            <p style='margin-top: 0.5rem; color: #666; font-size: 0.9rem;'>📊 {grade_desc}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # 데스크톱: 기존 레이아웃
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, {grade_color}22 0%, {grade_color}11 100%);
                    padding: 1.5rem; border-radius: 15px; border: 2px solid {grade_color}; margin: 1rem 0;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h2 style='margin: 0; color: #333;'>{name} ({code})</h2>
                    <p style='margin: 0.3rem 0;'>
                        <span style='background: {sector_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.9rem;'>{sector_info}</span>
                    </p>
                    <p style='margin: 0.5rem 0; color: {change_color}; font-size: 1.3rem; font-weight: bold;'>
                        현재가: {current:,.0f}원 ({sign}{change_rate:.2f}%)
                    </p>
                </div>
                <div style='text-align: center; background: {grade_color}; padding: 1rem 2rem; border-radius: 10px;'>
                    <h1 style='margin: 0; color: white; font-size: 2.5rem;'>{grade}</h1>
                    <p style='margin: 0; color: white; font-size: 1.5rem;'>{total_score}점</p>
                </div>
            </div>
            <p style='margin-top: 1rem; color: #666; font-size: 1.1rem;'>📊 {grade_desc}</p>
        </div>
        """, unsafe_allow_html=True)

    # 투자자 매매동향 표시
    render_investor_trend(api, code, name, days=5, key_prefix=f"inv_{code}")

    # 신호 상세 분석
    st.markdown("#### 📋 전략별 분석 결과")
    is_mobile = st.session_state.get('mobile_mode', False)

    if is_mobile:
        # 모바일: 1열로 표시
        for strategy_name, signal_text, score in signal_details:
            if score > 0:
                st.markdown(f"""
                <div style='background: #e8f5e9; padding: 0.5rem 0.8rem; border-radius: 8px; margin: 0.2rem 0; border-left: 4px solid #4CAF50; font-size: 0.9rem;'>
                    <b>{strategy_name}</b>: {signal_text} <span style='color: #4CAF50; float: right;'>+{score}점</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='background: #f5f5f5; padding: 0.5rem 0.8rem; border-radius: 8px; margin: 0.2rem 0; border-left: 4px solid #999; font-size: 0.9rem;'>
                    <b>{strategy_name}</b>: {signal_text} <span style='color: #999; float: right;'>0점</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        # 데스크톱: 2열로 표시
        col1, col2 = st.columns(2)
        for i, (strategy_name, signal_text, score) in enumerate(signal_details):
            col = col1 if i % 2 == 0 else col2
            with col:
                if score > 0:
                    st.markdown(f"""
                    <div style='background: #e8f5e9; padding: 0.8rem; border-radius: 8px; margin: 0.3rem 0; border-left: 4px solid #4CAF50;'>
                        <b>{strategy_name}</b>: {signal_text} <span style='color: #4CAF50; float: right;'>+{score}점</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                <div style='background: #f5f5f5; padding: 0.8rem; border-radius: 8px; margin: 0.3rem 0; border-left: 4px solid #999;'>
                    <b>{strategy_name}</b>: {signal_text} <span style='color: #999; float: right;'>0점</span>
                </div>
                """, unsafe_allow_html=True)

    # R:R 보너스
    if rr_bonus > 0:
        st.markdown(f"""
        <div style='background: #fff3e0; padding: 0.8rem; border-radius: 8px; margin: 0.3rem 0; border-left: 4px solid #FF9800;'>
            <b>R:R 비율 보너스</b>: 1:{rr_ratio:.1f} <span style='color: #FF9800; float: right;'>+{rr_bonus}점</span>
        </div>
        """, unsafe_allow_html=True)

    # 매매 전략
    st.markdown("#### 💰 추천 매매 전략")

    # 미리 계산
    entry_diff = ((entry - current) / current) * 100 if current > 0 else 0
    entry_color = "#FF4444" if entry_diff >= 0 else "#4444FF"
    loss_pct = ((stop - entry) / entry) * 100 if entry > 0 else 0
    profit_pct = ((target - entry) / entry) * 100 if entry > 0 else 0
    rr_color = "#22c55e" if rr_ratio >= 1.5 else "#f59e0b"

    # 모바일 vs 데스크톱 레이아웃
    if is_mobile:
        # 모바일: 2열 2행
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🎯 진입가</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{entry:,.0f}</div>
                <div style='background: {entry_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.8rem;'>{entry_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with row1_col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🛑 손절가</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{stop:,.0f}</div>
                <div style='background: #4444FF; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.8rem;'>{loss_pct:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>🎁 목표가</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{target:,.0f}</div>
                <div style='background: #FF4444; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.8rem;'>+{profit_pct:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with row2_col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>📊 R:R</div>
                <div style='color: #fff; font-size: 1.1rem; font-weight: bold;'>1:{rr_ratio:.1f}</div>
                <div style='background: {rr_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.8rem;'>{"좋음" if rr_ratio >= 1.5 else "보통"}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # 데스크톱: 4열
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>🎯 추천 진입가</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{entry:,.0f}원</div>
                <div style='background: {entry_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{entry_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>🛑 손절가</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{stop:,.0f}원</div>
                <div style='background: #4444FF; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{loss_pct:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>🎁 목표가</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{target:,.0f}원</div>
                <div style='background: #FF4444; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>+{profit_pct:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>📊 R:R 비율</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>1:{rr_ratio:.1f}</div>
                <div style='background: {rr_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{"좋음" if rr_ratio >= 1.5 else "보통"}</div>
            </div>
            """, unsafe_allow_html=True)

    # 이동평균선 정보
    st.markdown("#### 📈 이동평균선 현황")

    # 미리 계산
    ma5_val = ma5.iloc[-1] if not np.isnan(ma5.iloc[-1]) else 0
    ma5_diff = ((current - ma5_val) / ma5_val * 100) if ma5_val > 0 else 0
    ma5_color = "#FF4444" if ma5_diff >= 0 else "#4444FF"

    ma20_val = ma20.iloc[-1] if not np.isnan(ma20.iloc[-1]) else 0
    ma20_diff = ((current - ma20_val) / ma20_val * 100) if ma20_val > 0 else 0
    ma20_color = "#FF4444" if ma20_diff >= 0 else "#4444FF"

    ma60_val = ma60.iloc[-1] if not np.isnan(ma60.iloc[-1]) else 0
    ma60_diff = ((current - ma60_val) / ma60_val * 100) if ma60_val > 0 else 0
    ma60_color = "#FF4444" if ma60_diff >= 0 else "#4444FF"

    ma120_val = ma120.iloc[-1] if not np.isnan(ma120.iloc[-1]) else 0
    ma120_diff = ((current - ma120_val) / ma120_val * 100) if ma120_val > 0 else 0
    ma120_color = "#FF4444" if ma120_diff >= 0 else "#4444FF"

    if is_mobile:
        # 모바일: 2열 2행
        ma_row1_col1, ma_row1_col2 = st.columns(2)
        with ma_row1_col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>MA5</div>
                <div style='color: #fff; font-size: 1rem; font-weight: bold;'>{ma5_val:,.0f}</div>
                <div style='background: {ma5_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.75rem;'>{ma5_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with ma_row1_col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>MA20</div>
                <div style='color: #fff; font-size: 1rem; font-weight: bold;'>{ma20_val:,.0f}</div>
                <div style='background: {ma20_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.75rem;'>{ma20_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        ma_row2_col1, ma_row2_col2 = st.columns(2)
        with ma_row2_col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>MA60</div>
                <div style='color: #fff; font-size: 1rem; font-weight: bold;'>{ma60_val:,.0f}</div>
                <div style='background: {ma60_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.75rem;'>{ma60_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with ma_row2_col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.7rem; border-radius: 8px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.75rem;'>MA120</div>
                <div style='color: #fff; font-size: 1rem; font-weight: bold;'>{ma120_val:,.0f}</div>
                <div style='background: {ma120_color}; color: white; padding: 0.1rem 0.3rem; border-radius: 4px; display: inline-block; font-size: 0.75rem;'>{ma120_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # 데스크톱: 4열
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>MA5</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{ma5_val:,.0f}원</div>
                <div style='background: {ma5_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{ma5_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>MA20</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{ma20_val:,.0f}원</div>
                <div style='background: {ma20_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{ma20_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>MA60</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{ma60_val:,.0f}원</div>
                <div style='background: {ma60_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{ma60_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
                <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>MA120</div>
                <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{ma120_val:,.0f}원</div>
                <div style='background: {ma120_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; font-weight: bold;'>{ma120_diff:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 차트 표시 (expander 제거 - 디버깅용)
    # expander 내부 체크박스 문제 확인을 위해 임시로 직접 렌더링
    st.markdown(f"### 📈 차트 - {name}")
    _render_stock_chart(api, code, name, f"single_{code}")

    # 퀀트 전략 분석 (마법공식, 멀티팩터, 차트기술분석)
    try:
        info = api.get_stock_info(code)
        if info:
            _render_quant_analysis_section(api, info, code, name)
    except Exception as e:
        st.caption(f"⚠️ 퀀트 분석 로드 실패: {e}")

    # 스크리너 통합 분석 (스윙매매, 태쏘전략, 다이버전스, 기술지표)
    st.markdown("---")
    st.markdown("#### 🔬 스크리너 통합 분석")
    try:
        screener_result = {
            'code': code,
            'name': name,
            'current_price': float(data['close'].iloc[-1]),
            'change_rate': change_rate,
        }

        # 스윙매매 패턴 분석
        try:
            swing_analysis = analyze_swing_patterns(data)
            if swing_analysis:
                screener_result['swing_patterns'] = swing_analysis
        except Exception:
            pass

        # 태쏘 전략 분석
        try:
            box_result = detect_box_range(data, period=20, tolerance=0.05)
            if box_result:
                screener_result['box_range'] = box_result

            breakout_result = detect_box_breakout(data, period=20, volume_confirm=True)
            if breakout_result:
                screener_result['box_breakout'] = breakout_result

            new_high_result = detect_new_high_trend(data, lookback=60, breakout_days=3)
            if new_high_result:
                screener_result['new_high_trend'] = new_high_result
        except Exception:
            pass

        # 다이버전스 분석
        try:
            divergence_result = analyze_divergence(data)
            if divergence_result:
                screener_result['divergence'] = divergence_result
        except Exception:
            pass

        # 기본 기술적 지표
        try:
            rsi_val = calculate_rsi(data['close'])
            macd_val = calculate_macd(data['close'])
            bollinger_val = calculate_bollinger(data['close'])
            volume_ratio_val = calculate_volume_ratio(data['volume'])
            williams_r_val = calculate_williams_r(data['high'], data['low'], data['close'])

            screener_result['rsi'] = round(rsi_val, 2)
            screener_result['macd'] = macd_val
            screener_result['bollinger'] = bollinger_val
            screener_result['volume_ratio'] = round(volume_ratio_val, 2)
            screener_result['williams_r'] = round(williams_r_val, 2)
        except Exception:
            pass

        # 탭으로 표시
        sc_tab1, sc_tab2, sc_tab3, sc_tab4 = st.tabs([
            "📊 기술적 지표", "🎯 스윙매매 패턴", "📦 태쏘 전략", "📉 다이버전스"
        ])

        with sc_tab1:
            _display_single_stock_indicators(screener_result)
        with sc_tab2:
            _display_single_stock_swing(screener_result)
        with sc_tab3:
            _display_single_stock_tasso(screener_result)
        with sc_tab4:
            _display_single_stock_divergence(screener_result)

    except Exception as e:
        st.caption(f"⚠️ 스크리너 분석 로드 실패: {e}")
