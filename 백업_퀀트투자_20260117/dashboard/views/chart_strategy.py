"""
차트 전략 페이지 - 기술적 분석 기법 해석법
neurotrader888 기반 기술적 차트 분석 전략 + 종목 검색
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name


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
    api = _get_api_connection()

    # 탭 생성
    tabs = st.tabs([
        "📈 추세선 분석",
        "🎯 조화 패턴",
        "👤 머리어깨",
        "🚩 깃발/페넌트",
        "📐 피보나치",
        "🔄 방향성 변화",
        "📊 지지/저항",
        "🧪 전략 검증"
    ])

    with tabs[0]:
        _render_trendline_section(api)

    with tabs[1]:
        _render_harmonic_section(api)

    with tabs[2]:
        _render_head_shoulders_section(api)

    with tabs[3]:
        _render_flags_pennants_section(api)

    with tabs[4]:
        _render_fibonacci_section(api)

    with tabs[5]:
        _render_directional_change_section(api)

    with tabs[6]:
        _render_support_resistance_section(api)

    with tabs[7]:
        _render_strategy_validation_section(api)


def _get_api_connection():
    """API 연결"""
    try:
        from data.kis_api import KoreaInvestmentAPI
        api = KoreaInvestmentAPI()
        return api
    except Exception as e:
        return None


def _get_stock_data(api, code: str, days: int = 120):
    """종목 데이터 조회"""
    if api is None:
        return None
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        return api.get_daily_price(code, start_date, end_date)
    except Exception as e:
        return None


def _render_stock_finder(api, strategy_name: str, find_func, key_prefix: str):
    """종목 검색 공통 컴포넌트"""
    st.markdown("---")
    st.subheader(f"🔍 {strategy_name} 종목 찾기")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        market = st.radio("시장", ["KOSPI", "KOSDAQ", "전체"], horizontal=True, key=f"{key_prefix}_market")
    with col2:
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key=f"{key_prefix}_count")
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
            for stock in results[:15]:
                _render_stock_card(stock)
            if len(results) > 15:
                st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="hs_count")

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
                for stock in results[:15]:
                    _render_head_shoulders_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="harmonic_count")

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
                for stock in results[:15]:
                    _render_harmonic_stock_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_stock_card(stock: dict):
    """종목 카드 렌더링 (진입가, 손절가, 목표가 포함)"""
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
                st.markdown(f"🎯 **진입가:** {entry_price:,.0f}원")
            with col3:
                loss_pct = ((stop_loss - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🛑 **손절:** {stop_loss:,.0f}원 ({loss_pct:.1f}%)")
            with col4:
                profit_pct = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                st.markdown(f"🎁 **목표가:** {target_price:,.0f}원 (+{profit_pct:.1f}%)")

            # R:R 비율
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            st.caption(f"📊 R:R = 1:{rr_ratio:.1f} | {reason}")
        else:
            st.caption(f"{reason}")

        st.divider()


def _render_head_shoulders_card(stock: dict):
    """머리어깨 패턴 종목 카드 렌더링 (어깨, 머리, 넥라인 정보 포함)"""
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

        st.divider()


def _render_harmonic_stock_card(stock: dict):
    """조화 패턴 종목 카드 렌더링 (진입가, 손절가, 목표가 포함)"""
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
            change_rate = (closes[-1] - closes[-2]) / closes[-2] * 100
            current = closes[-1]

            # 최근 고점/저점
            recent_high = np.max(highs[-20:])
            recent_low = np.min(lows[-20:])

            # 조건 1: 20일선 위에서 상승 중
            if len(ma20) > 1 and not np.isnan(ma20[-1]):
                if closes[-1] > ma20[-1] and closes[-1] > closes[-5]:
                    # 진입: 현재가, 손절: 20일선 아래 2%, 목표: 최근 고점 돌파
                    entry = current
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
                    entry = current
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
            change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100
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
            change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

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
            change_rate = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

            # 피보나치 수준 계산
            fib_236 = high - (high - low) * 0.236
            fib_382 = high - (high - low) * 0.382
            fib_500 = high - (high - low) * 0.500
            fib_618 = high - (high - low) * 0.618
            fib_786 = high - (high - low) * 0.786

            # 각 피보나치 수준 체크 (5% 오차 이내)
            if abs(current - fib_618) / fib_618 < 0.05:
                entry = current
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
                entry = current
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
                entry = current
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
            change_rate = (current - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100

            # 최근 고점/저점
            recent_high = data['high'].iloc[-10:].max()
            recent_low = data['low'].iloc[-10:].min()

            # 거래량 1.5배 이상
            if today_volume > avg_volume * 1.5:
                if change_rate > 0:  # 상승 + 거래량 급증 = 매수 신호
                    entry = current
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
                    # 거래량 급증 하락은 매집 또는 세력 이탈 가능성
                    # 저점 매수 관점으로 반등 기대
                    entry = current
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
                        entry = current
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
                        entry = current
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
                        entry = current
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
                    entry = current
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
                    # 급락 후 횡보는 바닥 다지기일 수 있음 - 반등 매수 관점
                    entry = current
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
                    entry = current
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="flag_count")

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
                for stock in results[:15]:
                    _render_flag_pennant_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_flag_pennant_card(stock: dict):
    """깃발/페넌트 종목 카드 렌더링"""
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="fib_count")

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
                for stock in results[:15]:
                    _render_fibonacci_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_fibonacci_card(stock: dict):
    """피보나치 종목 카드 렌더링"""
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="dc_count")

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
                for stock in results[:15]:
                    _render_directional_change_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_directional_change_card(stock: dict):
    """방향성 변화 종목 카드 렌더링"""
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="sr_count")

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
                for stock in results[:15]:
                    _render_support_resistance_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_support_resistance_card(stock: dict):
    """지지/저항 종목 카드 렌더링"""
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
        stock_count = st.select_slider("검색 종목 수", options=[50, 100, 200, 500, "전체"], value=100, key="sv_count")

    st.markdown("**전략 유형 선택** (복수 선택 가능)")
    col1, col2, col3 = st.columns(3)
    with col1:
        golden_cross = st.checkbox("✨ 골든크로스", value=True, key="sv_golden")
    with col2:
        alignment = st.checkbox("📊 정배열 (MA5>MA20>MA60)", value=True, key="sv_alignment")
    with col3:
        volume_surge = st.checkbox("📈 거래량 급증", value=True, key="sv_volume")

    if st.button("🔎 전략 검색 시작", key="sv_search", type="primary"):
        selected_strategies = []
        if golden_cross:
            selected_strategies.append('golden_cross')
        if alignment:
            selected_strategies.append('alignment')
        if volume_surge:
            selected_strategies.append('volume_surge')

        if not selected_strategies:
            st.warning("최소 1개 이상의 전략을 선택해주세요.")
        else:
            with st.spinner(f"전략 검색 중... (전략: {len(selected_strategies)}개)"):
                results = _find_strategy_validation_stocks(api, market, stock_count, selected_strategies)

            if results:
                st.success(f"✅ {len(results)}개 종목 발견!")
                for stock in results[:15]:
                    _render_strategy_validation_card(stock)
                if len(results) > 15:
                    st.info(f"... 외 {len(results) - 15}개 종목 더 있음")
            else:
                st.info("조건에 맞는 종목이 없습니다.")


def _render_strategy_validation_card(stock: dict):
    """전략 검증 종목 카드 렌더링"""
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
        except:
            continue

    progress.empty()
    return results
