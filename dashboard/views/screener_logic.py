"""
스크리너 로직 모듈 (screener.py에서 분리)
- 조건 검색, 시그널 스캐너, 고급 분석의 로직 및 표시 함수
- chart_strategy.py에서 import하여 사용
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 종목 리스트 import
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks

# 시총·상장주식수 일괄 캐시
from data.market_data_cache import (
    get_market_cap_dict,
    format_market_cap,
    format_shares,
)

# 피보나치 되돌림 + 200MA confluence
from utils.fibonacci import (
    fibonacci_retracement_levels,
    detect_ma200_fibonacci_confluence,
)

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection

# 공통 기술적 지표 모듈 import
from dashboard.utils.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger,
    calculate_volume_ratio,
    calculate_williams_r,
    get_rsi_signal,
    get_macd_signal,
    get_bollinger_signal,
    get_williams_r_signal,
    get_volume_signal,
    calculate_moving_averages,
    check_ma_alignment,
    calculate_52week_range,
    # 스윙매매 패턴 분석 함수
    detect_double_bottom,
    detect_inverse_head_shoulders,
    detect_pullback_buy,
    detect_accumulation,
    analyze_volume_profile,
    calculate_disparity,
    analyze_swing_patterns,
    detect_box_range,
    detect_box_breakout,
    detect_new_high_trend,
    # 다이버전스 분석 함수
    detect_rsi_divergence,
    detect_macd_divergence,
    analyze_divergence
)

# 공통 차트 유틸리티 import (중복 코드 제거)
from dashboard.utils.chart_utils import render_simple_chart, detect_swing_points, render_investor_trend


# ========== 업종 정보 캐시 및 헬퍼 ==========
def get_sector_info_cached(code: str) -> str:
    """
    업종 정보 조회 (캐시 사용)

    Args:
        code: 종목코드

    Returns:
        업종명
    """
    # 세션 캐시 초기화
    if 'sector_cache' not in st.session_state:
        st.session_state['sector_cache'] = {}

    # 캐시에 있으면 반환
    if code in st.session_state['sector_cache']:
        return st.session_state['sector_cache'][code]

    # API에서 조회
    try:
        api = get_api_connection(verbose=False)
        if api and hasattr(api, 'get_sector_info'):
            sector = api.get_sector_info(code)
            st.session_state['sector_cache'][code] = sector
            return sector
    except:
        pass

    # 테마 키워드 기반 분류 시도
    try:
        themes = classify_stock_theme(code, "")
        if themes and themes[0] != '기타':
            st.session_state['sector_cache'][code] = themes[0]
            return themes[0]
    except:
        pass

    st.session_state['sector_cache'][code] = "기타"
    return "기타"


def get_company_info_brief(code: str, name: str = "") -> dict:
    """
    종목의 간단한 회사 정보 조회 (pykrx 직접 사용)

    Args:
        code: 종목코드
        name: 종목명 (없으면 조회)

    Returns:
        회사 정보 딕셔너리
    """
    info = {
        'code': code,
        'name': name,
        'sector': '',
        'market': '',
        'market_cap': 0,
        'description': ''
    }

    try:
        from pykrx import stock
        import datetime

        # 종목명 조회
        if not name:
            try:
                info['name'] = stock.get_market_ticker_name(code)
            except:
                pass

        # KOSPI/KOSDAQ 구분
        try:
            kospi_tickers = stock.get_market_ticker_list(market="KOSPI")
            kosdaq_tickers = stock.get_market_ticker_list(market="KOSDAQ")

            if code in kospi_tickers:
                info['market'] = 'KOSPI'
            elif code in kosdaq_tickers:
                info['market'] = 'KOSDAQ'
            else:
                info['market'] = 'ETF/기타'
        except:
            pass

        # 시가총액 조회
        try:
            today = datetime.datetime.now().strftime("%Y%m%d")
            cap_df = stock.get_market_cap(today, today, code)
            if cap_df is not None and not cap_df.empty:
                info['market_cap'] = int(cap_df['시가총액'].iloc[-1])
        except:
            pass

        # 업종 정보 조회 - KOSPI/KOSDAQ 업종별 시세에서
        try:
            if info['market'] == 'KOSPI':
                sectors = stock.get_index_ticker_list(market="KOSPI")
            else:
                sectors = stock.get_index_ticker_list(market="KOSDAQ")

            # 업종 찾기 시도
            for sector_code in sectors[:20]:  # 주요 업종만
                try:
                    sector_name = stock.get_index_ticker_name(sector_code)
                    tickers = stock.get_index_portfolio_deposit_file(sector_code)
                    if code in tickers:
                        info['sector'] = sector_name
                        break
                except:
                    continue
        except:
            pass

        # 업종 정보가 없으면 테마 기반 분류
        if not info['sector']:
            try:
                themes = classify_stock_theme(code, name or info['name'])
                if themes and themes[0] != '기타':
                    info['sector'] = themes[0]
            except:
                info['sector'] = '기타'

        # 간단한 설명 생성
        if info['market'] or info['sector']:
            market_cap_text = ""
            if info['market_cap'] >= 1_000_000_000_000:
                market_cap_text = f"시가총액 {info['market_cap'] / 1_000_000_000_000:.1f}조원"
            elif info['market_cap'] >= 100_000_000:
                market_cap_text = f"시가총액 {info['market_cap'] / 100_000_000:,.0f}억원"

            info['description'] = f"{info['market']} 상장 {info['sector']} 기업. {market_cap_text}".strip()

    except Exception:
        # 테마 기반 분류만 시도
        try:
            themes = classify_stock_theme(code, name)
            if themes and themes[0] != '기타':
                info['sector'] = themes[0]
        except:
            pass

    return info


def analyze_stock_signals(df: pd.DataFrame) -> dict:
    """종목의 기술적 시그널 분석"""
    if df.empty or len(df) < 30:
        return None

    close = df['close']
    volume = df['volume']

    # 기술적 지표 계산
    rsi = calculate_rsi(close)
    macd = calculate_macd(close)
    bollinger = calculate_bollinger(close)
    volume_ratio = calculate_volume_ratio(volume)

    # 가격 변화
    current_price = close.iloc[-1]
    prev_price = close.iloc[-2] if len(close) >= 2 else current_price
    change_rate = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

    signals = []

    # RSI 시그널
    if rsi <= 30:
        signals.append(('buy', 'RSI 과매도 구간', '강함' if rsi <= 25 else '보통'))
    elif rsi >= 70:
        signals.append(('sell', 'RSI 과매수 구간', '강함' if rsi >= 75 else '보통'))

    # MACD 시그널
    if macd['cross'] == 'golden':
        signals.append(('buy', 'MACD 골든크로스', '강함'))
    elif macd['cross'] == 'dead':
        signals.append(('sell', 'MACD 데드크로스', '강함'))

    # 볼린저밴드 시그널
    if bollinger['position'] <= 0.1:
        signals.append(('buy', '볼린저밴드 하단 돌파', '강함' if bollinger['position'] <= 0.05 else '보통'))
    elif bollinger['position'] >= 0.9:
        signals.append(('sell', '볼린저밴드 상단 돌파', '강함' if bollinger['position'] >= 0.95 else '보통'))

    # 거래량 급증 시그널
    if volume_ratio >= 3:
        strength = '강함' if volume_ratio >= 5 else '보통'
        if change_rate > 0:
            signals.append(('buy', f'거래량 급증 ({volume_ratio:.1f}배)', strength))
        else:
            signals.append(('sell', f'거래량 급증 ({volume_ratio:.1f}배)', strength))

    return {
        'price': current_price,
        'change_rate': change_rate,
        'rsi': rsi,
        'macd': macd,
        'bollinger': bollinger,
        'volume_ratio': volume_ratio,
        'signals': signals
    }


def _render_condition_screener(api):
    """조건 검색 UI"""

    st.markdown("### 📋 검색 조건 설정")

    # 시장 선택
    col1, col2 = st.columns(2)
    with col1:
        market = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ"], key="screener_market")
    with col2:
        max_results = st.slider("최대 결과 수", 10, 100, 30, key="screener_max")

    st.markdown("---")

    # 조건 카테고리
    st.markdown("#### 🎯 기술적 지표 조건")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**RSI (14일)**")
        use_rsi = st.checkbox("RSI 조건 사용", key="use_rsi")
        if use_rsi:
            rsi_condition = st.selectbox(
                "조건",
                ["과매도 (< 30)", "과매수 (> 70)", "상승 반전 (30 돌파)", "하락 반전 (70 하회)", "커스텀"],
                key="rsi_condition"
            )
            if rsi_condition == "커스텀":
                rsi_min = st.number_input("RSI 최소", 0, 100, 20, key="rsi_min")
                rsi_max = st.number_input("RSI 최대", 0, 100, 40, key="rsi_max")

    with col2:
        st.markdown("**MACD**")
        use_macd = st.checkbox("MACD 조건 사용", key="use_macd")
        if use_macd:
            macd_condition = st.selectbox(
                "조건",
                ["골든크로스 (매수)", "데드크로스 (매도)", "히스토그램 상승", "히스토그램 하락", "0선 상향돌파"],
                key="macd_condition"
            )

    with col3:
        st.markdown("**볼린저밴드**")
        use_bb = st.checkbox("볼린저밴드 조건 사용", key="use_bb")
        if use_bb:
            bb_condition = st.selectbox(
                "조건",
                ["하단 터치 (매수)", "상단 터치 (매도)", "밴드 수축 (변동성 감소)", "밴드 확장 (변동성 증가)"],
                key="bb_condition"
            )

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("**Williams %R (81% 승률)**")
        use_williams = st.checkbox("Williams %R 조건 사용", key="use_williams")
        if use_williams:
            williams_condition = st.selectbox(
                "조건",
                ["과매도 (< -80)", "과매수 (> -20)", "과매도 반등 (-80 상향돌파)", "과매수 하락 (-20 하향돌파)", "커스텀"],
                key="williams_condition"
            )
            if williams_condition == "커스텀":
                williams_min = st.number_input("Williams %R 최소", -100, 0, -80, key="williams_min")
                williams_max = st.number_input("Williams %R 최대", -100, 0, -20, key="williams_max")

    with col2:
        st.markdown("**거래량**")
        use_volume = st.checkbox("거래량 조건 사용", key="use_volume")
        if use_volume:
            vol_condition = st.selectbox(
                "조건",
                ["급증 (20일 평균 2배 이상)", "급증 (20일 평균 3배 이상)", "급감 (20일 평균 50% 이하)", "커스텀"],
                key="vol_condition"
            )
            if vol_condition == "커스텀":
                vol_ratio = st.number_input("20일 평균 대비 비율", 0.1, 10.0, 2.0, key="vol_ratio")

    with col3:
        st.markdown("**이동평균선**")
        use_ma = st.checkbox("이동평균선 조건 사용", key="use_ma")
        if use_ma:
            ma_condition = st.selectbox(
                "조건",
                [
                    "골든크로스 (5일>20일)",
                    "데드크로스 (5일<20일)",
                    "정배열 (5>20>60)",
                    "역배열 (5<20<60)",
                    "20일선 돌파",
                    "장기 골든크로스 (50>200)",
                    "장기 데드크로스 (50<200)",
                    "완전 정배열 (5>10>20>50>100>200)",
                    "200일선 위 (장기 강세)",
                    "200MA·피보나치 confluence",
                ],
                key="ma_condition"
            )

    with col4:
        st.markdown("**가격 변동**")
        use_price = st.checkbox("가격 변동 조건 사용", key="use_price")
        if use_price:
            price_condition = st.selectbox(
                "조건",
                ["당일 3% 이상 상승", "당일 3% 이상 하락", "5일 연속 상승", "5일 연속 하락", "신고가 근접 (5% 이내)"],
                key="price_condition"
            )

    st.markdown("---")

    # 펀더멘털 필터
    st.markdown("#### 💰 펀더멘털 필터 (선택)")

    col1, col2, col3 = st.columns(3)

    with col1:
        use_per = st.checkbox("PER 필터", key="use_per")
        if use_per:
            per_max = st.number_input("PER 최대", 0.0, 100.0, 20.0, key="per_max")

    with col2:
        use_pbr = st.checkbox("PBR 필터", key="use_pbr")
        if use_pbr:
            pbr_max = st.number_input("PBR 최대", 0.0, 10.0, 2.0, key="pbr_max")

    with col3:
        use_cap = st.checkbox("시가총액 필터", key="use_cap")
        if use_cap:
            cap_min = st.number_input("시가총액 최소 (억원)", 0, 100000, 1000, key="cap_min")

    st.markdown("---")

    # 검색 실행 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_screener = st.button("🔍 조건 검색 실행", type="primary", use_container_width=True)

    if run_screener:
        with st.spinner("종목 검색 중..."):
            # 조건 수집
            conditions = _collect_conditions()

            # 검색 실행
            results = _run_screener(api, conditions, market, max_results)

            if results:
                st.session_state['screener_results'] = results
                st.success(f"✅ {len(results)}개 종목을 찾았습니다!")
            else:
                st.warning("조건에 맞는 종목이 없습니다.")

    # 결과 표시
    if 'screener_results' in st.session_state and st.session_state['screener_results']:
        _display_screener_results(st.session_state['screener_results'])


def _render_advanced_analysis(api):
    """고급 분석 - 테마분류, 52주 저점, 바닥 다지기, 턴어라운드"""

    st.markdown("### 🔬 고급 분석 스캐너")
    st.caption("테마별 분류, 52주 저점 대비 분석, 바닥 다지기 패턴, 실적 턴어라운드를 분석합니다")

    # ===== 개별 종목 분석 섹션 =====
    st.markdown("""
    <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;
                border: 1px solid rgba(255,255,255,0.1);'>
        <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;'>
            <span style='font-size: 1.5rem;'>🔍</span>
            <h4 style='margin: 0; color: white; font-weight: 700;'>개별 종목 분석</h4>
        </div>
        <p style='margin: 0; color: rgba(255,255,255,0.7); font-size: 0.9rem;'>
            시장을 선택하고 종목명을 검색하여 기술적 분석 결과를 확인하세요
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 종목 리스트 로드 (session_state에 캐시)
    if 'stock_list_cache' not in st.session_state:
        with st.spinner("종목 리스트 로딩 중..."):
            kospi_stocks = get_kospi_stocks()
            kosdaq_stocks = get_kosdaq_stocks()
            st.session_state['stock_list_cache'] = {
                'kospi': kospi_stocks,
                'kosdaq': kosdaq_stocks
            }

    kospi_stocks = st.session_state['stock_list_cache']['kospi']
    kosdaq_stocks = st.session_state['stock_list_cache']['kosdaq']

    # 시장 선택 및 종목 검색 UI (검정색 기반 스타일)
    st.markdown("""
    <style>
    .stock-search-container {
        background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
        padding: 1.25rem;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 1rem;
    }
    .search-label {
        color: rgba(255,255,255,0.9);
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col_market, col_search = st.columns([1, 3])

    with col_market:
        st.markdown("""
        <div class='search-label'>
            <span>🏛️</span> 시장 선택
        </div>
        """, unsafe_allow_html=True)
        search_market = st.selectbox(
            "시장",
            ["코스피", "코스닥"],
            key="single_stock_market",
            help="검색할 시장을 선택하세요",
            label_visibility="collapsed"
        )

    # 선택한 시장의 종목 리스트
    if search_market == "코스피":
        stock_options = kospi_stocks
        market_label = "KOSPI"
        market_color = "#e74c3c"
    else:
        stock_options = kosdaq_stocks
        market_label = "KOSDAQ"
        market_color = "#9b59b6"

    # 검색용 옵션 생성: "종목코드 - 종목명" 형식
    search_options = [f"{code} - {name}" for code, name in stock_options]

    with col_search:
        st.markdown(f"""
        <div class='search-label'>
            <span>🔎</span> 종목 검색
            <span style='background: {market_color}; color: white; padding: 0.15rem 0.5rem;
                        border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;'>
                {market_label}: {len(stock_options):,}개
            </span>
        </div>
        """, unsafe_allow_html=True)
        selected_stock = st.selectbox(
            "종목 검색",
            options=["직접 입력"] + search_options,
            key="single_stock_select",
            help="종목명 또는 종목코드로 검색하세요 (입력 시 자동 필터링)",
            label_visibility="collapsed"
        )

    # 직접 입력 선택 시 텍스트 입력 표시
    if selected_stock == "직접 입력":
        st.markdown("""
        <div class='search-label'>
            <span>✏️</span> 종목코드 직접 입력
        </div>
        """, unsafe_allow_html=True)
        single_stock_code = st.text_input(
            "종목코드 직접 입력",
            placeholder="예: 005930 (삼성전자)",
            key="single_stock_code_direct",
            help="6자리 종목코드를 직접 입력하세요",
            label_visibility="collapsed"
        )
    else:
        # selectbox에서 선택한 경우 코드 추출
        single_stock_code = selected_stock.split(" - ")[0] if selected_stock else ""

    # 버튼
    col_btn1, col_btn2, col_spacer = st.columns([1, 1, 2])

    with col_btn1:
        analyze_btn = st.button("📊 종목 분석", type="primary", use_container_width=True, key="analyze_single_stock")

    with col_btn2:
        clear_btn = st.button("🗑️ 결과 초기화", use_container_width=True, key="clear_single_result")

    if clear_btn:
        if 'single_stock_result' in st.session_state:
            del st.session_state['single_stock_result']
        st.rerun()

    if analyze_btn and single_stock_code:
        _analyze_and_display_single_stock(api, single_stock_code.strip())

    # 이전 분석 결과가 있으면 표시
    if 'single_stock_result' in st.session_state and st.session_state['single_stock_result']:
        _display_single_stock_analysis(st.session_state['single_stock_result'])

    st.markdown("---")

    # 분석 옵션
    st.markdown("#### ⚙️ 분석 설정")

    col1, col2, col3 = st.columns(3)

    with col1:
        adv_market = st.selectbox(
            "대상 시장",
            ["all", "kospi", "kosdaq"],
            format_func=lambda x: {"all": "전체 (KOSPI+KOSDAQ)", "kospi": "코스피", "kosdaq": "코스닥"}[x],
            key="adv_scan_market"
        )

    with col2:
        # 섹터/업종 필터
        SECTOR_LIST = [
            "전체",
            "IT/반도체", "2차전지/배터리", "바이오/제약", "자동차/부품",
            "금융/보험", "건설/인프라", "화학/소재", "유통/소비재",
            "엔터/미디어", "게임", "음식료", "철강/금속",
            "조선/해운", "항공/운송", "에너지/전력", "통신/인터넷",
            "기계/장비", "섬유/의류", "기타"
        ]
        sector_filter = st.selectbox(
            "섹터/업종",
            SECTOR_LIST,
            key="adv_sector_filter",
            help="특정 섹터만 필터링"
        )

    with col3:
        theme_filter = st.multiselect(
            "테마 필터",
            list(THEME_KEYWORDS.keys()),
            default=[],
            key="adv_theme_filter",
            help="특정 테마만 필터링 (비워두면 전체)"
        )

    st.markdown("---")

    # 분석 유형 선택
    st.markdown("#### 📋 분석 유형 선택")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>📊 패턴 분석</h5>
        </div>
        """, unsafe_allow_html=True)

        use_52w_low = st.checkbox("52주 저점 대비 분석", value=True, key="use_52w_low",
                                   help="52주 최저점 대비 20% 이내 종목")
        use_bottom = st.checkbox("바닥 다지기 패턴", value=True, key="use_bottom",
                                  help="거래량 감소 + 가격 횡보 패턴")
        use_large_bullish = st.checkbox("🔥 장대양봉 감지", value=True, key="use_large_bullish",
                                         help="5% 이상 상승 + 거래량 급증 (홍인기 매매법)")
        use_d1d2 = st.checkbox("📈 D+1/D+2 시그널", value=True, key="use_d1d2",
                                help="장대양봉 후 매매 타이밍")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>💰 펀더멘털/저항분석</h5>
        </div>
        """, unsafe_allow_html=True)

        use_turnaround = st.checkbox("실적 턴어라운드", value=False, key="use_turnaround",
                                      help="적자→흑자 전환 기업 (API 필요)")
        use_theme = st.checkbox("테마별 분류 표시", value=True, key="use_theme")
        use_prev_high = st.checkbox("🚀 전고점 돌파/저항", value=True, key="use_prev_high",
                                     help="60일 전고점 돌파 및 저항 분석")

    # 스윙매매 분석 섹션 추가
    st.markdown("---")
    st.markdown("#### 🎯 스윙매매 패턴 분석")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>📐 바닥 패턴</h5>
        </div>
        """, unsafe_allow_html=True)

        use_double_bottom = st.checkbox("쌍바닥(W패턴)", value=False, key="use_double_bottom",
                                         help="쌍바닥 패턴 + 넥라인 돌파 감지")
        use_inv_hs = st.checkbox("역헤드앤숄더", value=False, key="use_inv_hs",
                                  help="역헤드앤숄더 패턴 감지")
        use_pullback = st.checkbox("눌림목 매수", value=False, key="use_pullback",
                                    help="상승추세 중 이동평균선 지지")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>📊 수급/이격</h5>
        </div>
        """, unsafe_allow_html=True)

        use_accumulation = st.checkbox("세력 매집 패턴", value=False, key="use_accumulation",
                                        help="거래량 급증 + 가격 횡보 (매집 구간)")
        use_volume_profile = st.checkbox("매물대 분석", value=False, key="use_volume_profile",
                                          help="가격대별 거래량 분포 분석")
        use_disparity = st.checkbox("이격도 분석", value=False, key="use_disparity",
                                     help="이동평균 대비 이격도 과매수/과매도")

    # 태쏘 전략 필터 추가
    st.markdown("#### 📦 태쏘 스윙투자 전략 / 📊 다이버전스 분석")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>📦 박스권 전략</h5>
        </div>
        """, unsafe_allow_html=True)

        use_box_breakout_up = st.checkbox("박스권 상향 돌파", value=False, key="use_box_breakout_up",
                                           help="20일 박스권 상단 돌파 + 거래량 확인")
        use_box_buy = st.checkbox("박스권 하단 지지 매수", value=False, key="use_box_buy",
                                   help="박스권 하단 근처에서 지지 받는 종목")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>🚀 신고가 전략</h5>
        </div>
        """, unsafe_allow_html=True)

        use_new_high = st.checkbox("52주 신고가 돌파", value=False, key="use_new_high",
                                    help="52주 신고가 + 거래량 급증 + 정배열")
        use_new_high_approach = st.checkbox("신고가 근접 (95%+)", value=False, key="use_new_high_approach",
                                             help="52주 고가 95% 이상 근접 종목")

    with col3:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h5 style='color: white; margin: 0;'>📊 다이버전스 전략</h5>
        </div>
        """, unsafe_allow_html=True)

        use_divergence = st.checkbox("다이버전스 시그널", value=False, key="use_divergence",
                                      help="RSI/MACD 다이버전스 종목")
        use_rsi_divergence = st.checkbox("RSI 다이버전스", value=False, key="use_rsi_divergence",
                                          help="RSI 상승/하락 다이버전스")
        use_macd_divergence = st.checkbox("MACD 다이버전스", value=False, key="use_macd_divergence",
                                           help="MACD 상승/하락 다이버전스")

    st.markdown("---")

    # 스캔 실행
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 고급 분석 실행 (전체 종목)", type="primary", use_container_width=True, key="run_advanced"):
            _run_advanced_scan(api, adv_market, theme_filter, sector_filter)

    # 결과 표시
    if 'advanced_results' in st.session_state and st.session_state['advanced_results']:
        _display_advanced_results(st.session_state['advanced_results'])


def _analyze_single_stock_advanced(api, code: str, name: str, mkt: str, filter_options: dict) -> dict:
    """단일 종목 분석 (병렬 처리용)"""
    try:
        # 일봉 데이터 조회
        df = api.get_daily_price(code, period="D") if api else None

        # 고급 분석 실행
        analysis = analyze_advanced_signals(df, code, name)
        analysis['market'] = mkt

        if df is not None and not df.empty:
            analysis['current_price'] = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2] if len(df) >= 2 else analysis['current_price']
            analysis['change_rate'] = round(
                (analysis['current_price'] - prev_price) / prev_price * 100
                if prev_price > 0 else 0, 2
            )

            # 스윙매매 패턴 분석 추가
            swing_analysis = analyze_swing_patterns(df)
            if swing_analysis:
                analysis['swing_patterns'] = swing_analysis

            # 태쏘 전략 분석 추가
            try:
                box_result = detect_box_range(df, period=20, tolerance=0.05)
                if box_result:
                    analysis['box_range'] = box_result

                breakout_result = detect_box_breakout(df, period=20, volume_confirm=True)
                if breakout_result:
                    analysis['box_breakout'] = breakout_result

                new_high_result = detect_new_high_trend(df, lookback=60, breakout_days=3)
                if new_high_result:
                    analysis['new_high_trend'] = new_high_result
            except Exception:
                pass  # 태쏘 분석 실패 시 무시

            # 다이버전스 분석 추가
            try:
                divergence_result = analyze_divergence(df)
                if divergence_result:
                    analysis['divergence'] = divergence_result
            except Exception:
                pass  # 다이버전스 분석 실패 시 무시
        else:
            analysis['current_price'] = 0
            analysis['change_rate'] = 0

        # 필터링 조건 체크
        include = False

        if filter_options.get('use_52w_low') and analysis.get('low_52w_info'):
            if analysis['low_52w_info'].get('is_near_low'):
                include = True

        if filter_options.get('use_bottom') and analysis.get('bottom_pattern'):
            if analysis['bottom_pattern'].get('pattern_detected'):
                include = True

        if filter_options.get('use_theme'):
            if analysis.get('themes') and analysis['themes'] != ['기타']:
                include = True

        # 장대양봉 감지 (홍인기 매매법)
        if filter_options.get('use_large_bullish') and analysis.get('large_bullish'):
            if analysis['large_bullish'].get('detected'):
                include = True

        # D+1/D+2 시그널
        if filter_options.get('use_d1d2') and analysis.get('d1_d2_signal'):
            if analysis['d1_d2_signal'].get('has_recent_bullish'):
                include = True

        # 전고점 돌파/저항
        if filter_options.get('use_prev_high') and analysis.get('prev_high_breakout'):
            if analysis['prev_high_breakout'].get('is_breakout') or analysis['prev_high_breakout'].get('is_near_resistance'):
                include = True

        # ===== 스윙매매 패턴 필터 추가 =====
        swing = analysis.get('swing_patterns', {})

        # 쌍바닥(W패턴)
        if filter_options.get('use_double_bottom') and swing:
            for pattern in swing.get('patterns', []):
                if pattern.get('pattern') == 'double_bottom' and pattern.get('detected'):
                    include = True
                    break

        # 역헤드앤숄더
        if filter_options.get('use_inv_hs') and swing:
            for pattern in swing.get('patterns', []):
                if pattern.get('pattern') == 'inverse_head_shoulders' and pattern.get('detected'):
                    include = True
                    break

        # 눌림목 매수
        if filter_options.get('use_pullback') and swing:
            for pattern in swing.get('patterns', []):
                if pattern.get('pattern') == 'pullback' and pattern.get('detected'):
                    include = True
                    break

        # 세력 매집 패턴
        if filter_options.get('use_accumulation') and swing:
            for pattern in swing.get('patterns', []):
                if pattern.get('pattern') == 'accumulation' and pattern.get('detected'):
                    include = True
                    break

        # 매물대 분석 (지지선 근접)
        if filter_options.get('use_volume_profile') and swing:
            vp = swing.get('volume_profile', {})
            if vp.get('near_support'):
                include = True

        # 이격도 분석 (과매도)
        if filter_options.get('use_disparity') and swing:
            disp = swing.get('disparity', {})
            if disp.get('overall_signal') == 'oversold':
                include = True

        # ===== 태쏘 전략 필터 추가 =====
        # 박스권 상향 돌파
        if filter_options.get('use_box_breakout_up'):
            breakout = analysis.get('box_breakout', {})
            if breakout.get('direction') == 'up':
                # strength는 'strong'/'weak' 문자열 또는 숫자일 수 있음
                strength = breakout.get('strength', '')
                is_strong = strength == 'strong' or (isinstance(strength, (int, float)) and strength >= 0.7)
                if breakout.get('volume_confirmed') or is_strong:
                    include = True

        # 박스권 하단 지지 매수
        if filter_options.get('use_box_buy'):
            box = analysis.get('box_range', {})
            if box.get('signal') == 'box_buy':
                include = True

        # 52주 신고가 돌파
        if filter_options.get('use_new_high'):
            new_high = analysis.get('new_high_trend', {})
            new_high_strength = new_high.get('strength', '')
            is_new_high_strong = new_high_strength == 'strong' or (isinstance(new_high_strength, (int, float)) and new_high_strength >= 0.7)
            # is_52w_high 필드 사용 (indicators.py 반환값과 일치)
            if new_high.get('is_52w_high') and is_new_high_strong:
                include = True

        # 신고가 근접 (95%+)
        if filter_options.get('use_new_high_approach'):
            new_high = analysis.get('new_high_trend', {})
            if new_high.get('high_52w_pct', 0) >= 95:
                include = True

        # ===== 다이버전스 필터 =====
        divergence = analysis.get('divergence', {})
        if filter_options.get('use_divergence') and divergence:
            if divergence.get('signal') in ['strong_buy', 'buy', 'strong_sell', 'sell']:
                include = True

        if filter_options.get('use_rsi_divergence') and divergence:
            rsi_div = divergence.get('rsi_divergence', {})
            if rsi_div.get('detected'):
                include = True

        if filter_options.get('use_macd_divergence') and divergence:
            macd_div = divergence.get('macd_divergence', {})
            if macd_div.get('detected'):
                include = True

        # 아무 필터도 선택하지 않은 경우에만 시그널 기준으로 포함
        no_filter_selected = not any([
            filter_options.get('use_52w_low'),
            filter_options.get('use_bottom'),
            filter_options.get('use_theme'),
            filter_options.get('use_large_bullish'),
            filter_options.get('use_d1d2'),
            filter_options.get('use_prev_high'),
            filter_options.get('use_double_bottom'),
            filter_options.get('use_inv_hs'),
            filter_options.get('use_pullback'),
            filter_options.get('use_accumulation'),
            filter_options.get('use_volume_profile'),
            filter_options.get('use_disparity'),
            # 태쏘 전략 필터
            filter_options.get('use_box_breakout_up'),
            filter_options.get('use_box_buy'),
            filter_options.get('use_new_high'),
            filter_options.get('use_new_high_approach'),
            # 다이버전스 필터
            filter_options.get('use_divergence'),
            filter_options.get('use_rsi_divergence'),
            filter_options.get('use_macd_divergence')
        ])
        if no_filter_selected and analysis.get('signals'):
            include = True

        return analysis if include else None

    except Exception as e:
        return None


def _run_advanced_scan(api, market: str, theme_filter: list, sector_filter: str = "전체"):
    """고급 분석 스캔 실행 - 전체 종목 대상 (병렬 처리)"""

    # 섹터별 키워드 매핑 (종목명 기반 분류)
    SECTOR_KEYWORDS = {
        "IT/반도체": ["반도체", "전자", "디스플레이", "LED", "메모리", "파운드리", "칩", "IC", "PCB", "시스템반도체", "AI", "소프트웨어", "IT", "테크", "컴퓨터", "솔루션"],
        "2차전지/배터리": ["배터리", "2차전지", "리튬", "양극재", "음극재", "전해질", "분리막", "ESS", "에너지저장", "충전"],
        "바이오/제약": ["바이오", "제약", "신약", "의약", "헬스케어", "진단", "백신", "치료제", "항암", "임상", "메디", "팜", "셀", "젠"],
        "자동차/부품": ["자동차", "모터", "타이어", "부품", "전장", "현대", "기아", "모비스"],
        "금융/보험": ["은행", "증권", "보험", "금융", "캐피탈", "카드", "투자", "자산운용"],
        "건설/인프라": ["건설", "건축", "인프라", "토목", "플랜트", "엔지니어링", "개발"],
        "화학/소재": ["화학", "소재", "석유화학", "정유", "플라스틱", "고분자", "케미칼"],
        "유통/소비재": ["유통", "백화점", "마트", "리테일", "소비재", "식품", "음료", "화장품", "뷰티"],
        "엔터/미디어": ["엔터", "미디어", "방송", "콘텐츠", "영화", "드라마", "기획사", "음악"],
        "게임": ["게임", "온라인", "모바일게임", "넷마블", "엔씨", "넥슨", "크래프톤", "펄어비스"],
        "음식료": ["음식", "식품", "음료", "주류", "맥주", "우유", "제과", "라면", "커피"],
        "철강/금속": ["철강", "금속", "스틸", "알루미늄", "구리", "아연", "비철금속"],
        "조선/해운": ["조선", "해운", "선박", "해양", "컨테이너", "물류"],
        "항공/운송": ["항공", "운송", "물류", "택배", "배송", "철도", "버스"],
        "에너지/전력": ["에너지", "전력", "발전", "태양광", "풍력", "수소", "신재생", "원자력"],
        "통신/인터넷": ["통신", "인터넷", "네트워크", "5G", "텔레콤", "SK텔레콤", "KT", "LG유플"],
        "기계/장비": ["기계", "장비", "로봇", "자동화", "산업기계", "공작기계"],
        "섬유/의류": ["섬유", "의류", "패션", "스포츠", "신발", "아웃도어"],
    }

    def classify_stock_sector(name: str) -> str:
        """종목명으로 섹터 분류"""
        name_upper = name.upper()
        for sector, keywords in SECTOR_KEYWORDS.items():
            for kw in keywords:
                if kw.upper() in name_upper:
                    return sector
        return "기타"

    # 스캔할 종목 리스트 (전체 종목)
    stocks_to_scan = []

    if market in ['kospi', 'all']:
        kospi = get_kospi_stocks()
        stocks_to_scan.extend([(code, name, 'KOSPI') for code, name in kospi])

    if market in ['kosdaq', 'all']:
        kosdaq = get_kosdaq_stocks()
        stocks_to_scan.extend([(code, name, 'KOSDAQ') for code, name in kosdaq])

    # 섹터 필터 적용
    if sector_filter and sector_filter != "전체":
        filtered_stocks = []
        for code, name, mkt in stocks_to_scan:
            stock_sector = classify_stock_sector(name)
            if stock_sector == sector_filter:
                filtered_stocks.append((code, name, mkt))
        stocks_to_scan = filtered_stocks
        st.info(f"📂 **{sector_filter}** 섹터: {len(stocks_to_scan)}개 종목 대상")

    # 테마 필터 적용
    if theme_filter:
        filtered_stocks = []
        for code, name, mkt in stocks_to_scan:
            themes = classify_stock_theme(code, name)
            if any(t in theme_filter for t in themes):
                filtered_stocks.append((code, name, mkt))
        stocks_to_scan = filtered_stocks

    # 전체 종목 스캔 (제한 없음)

    if not stocks_to_scan:
        st.warning("스캔할 종목이 없습니다.")
        return

    # 필터 옵션 캡처 (병렬 처리 시 스레드 안전성)
    filter_options = {
        'use_52w_low': st.session_state.get('use_52w_low'),
        'use_bottom': st.session_state.get('use_bottom'),
        'use_theme': st.session_state.get('use_theme'),
        'use_large_bullish': st.session_state.get('use_large_bullish'),
        'use_d1d2': st.session_state.get('use_d1d2'),
        'use_prev_high': st.session_state.get('use_prev_high'),
        # 스윙매매 패턴 필터
        'use_double_bottom': st.session_state.get('use_double_bottom'),
        'use_inv_hs': st.session_state.get('use_inv_hs'),
        'use_pullback': st.session_state.get('use_pullback'),
        'use_accumulation': st.session_state.get('use_accumulation'),
        'use_volume_profile': st.session_state.get('use_volume_profile'),
        'use_disparity': st.session_state.get('use_disparity'),
        # 태쏘 전략 필터
        'use_box_breakout_up': st.session_state.get('use_box_breakout_up'),
        'use_box_buy': st.session_state.get('use_box_buy'),
        'use_new_high': st.session_state.get('use_new_high'),
        'use_new_high_approach': st.session_state.get('use_new_high_approach'),
        # 다이버전스 필터
        'use_divergence': st.session_state.get('use_divergence'),
        'use_rsi_divergence': st.session_state.get('use_rsi_divergence'),
        'use_macd_divergence': st.session_state.get('use_macd_divergence'),
    }

    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()

    results = []
    total = len(stocks_to_scan)
    completed = 0

    # 병렬 처리 설정 (동적 최적화)
    # CPU 코어 수 기반으로 workers 설정, 최소 4, 최대 12
    cpu_count = os.cpu_count() or 4
    max_workers = min(12, max(4, cpu_count))
    batch_size = 100  # 배치 단위로 처리 (API 부하 분산)

    status_text.text(f"🚀 병렬 스캔 시작 (동시 {max_workers}개 처리) - 총 {total}개 종목")

    # 배치 단위로 처리 (API 부하 분산)
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = stocks_to_scan[batch_start:batch_end]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_stock = {
                executor.submit(_analyze_single_stock_advanced, api, code, name, mkt, filter_options): (code, name)
                for code, name, mkt in batch
            }

            # 결과 수집
            for future in as_completed(future_to_stock):
                code, name = future_to_stock[future]
                completed += 1

                try:
                    analysis = future.result(timeout=30)  # 30초 타임아웃
                    if analysis:
                        results.append(analysis)
                except TimeoutError:
                    print(f"[스캔 타임아웃] {code} ({name})")
                except Exception as e:
                    print(f"[스캔 에러] {code} ({name}): {str(e)[:50]}")

                # 진행률 업데이트 (20개마다)
                if completed % 20 == 0 or completed == total:
                    progress_bar.progress(completed / total)
                    status_text.text(f"분석 중: {completed}/{total} 완료 ({len(results)}개 조건 충족)")

        # 배치 간 짧은 대기 (API 안정성)
        time.sleep(0.2)

    progress_bar.empty()
    status_text.empty()

    # 시총·상장주식수 일괄 조회 후 결과에 부착 (단 1회 pykrx 호출)
    try:
        cap_table = get_market_cap_dict("ALL")
        for r in results:
            cap_info = cap_table.get(str(r.get('code', '')), {})
            r['market_cap'] = int(cap_info.get('market_cap', 0))
            r['shares'] = int(cap_info.get('shares', 0))
    except Exception:
        pass

    st.session_state['advanced_results'] = results

    if results:
        st.success(f"✅ {len(results)}개 종목이 조건을 충족합니다!")
    else:
        st.info("조건에 맞는 종목이 없습니다.")


def _analyze_and_display_single_stock(api, stock_code: str):
    """개별 종목 분석 실행"""
    if not api:
        st.error("❌ API 연결이 필요합니다.")
        return

    # 종목코드 정리 (6자리)
    stock_code = stock_code.strip()
    if len(stock_code) < 6:
        stock_code = stock_code.zfill(6)

    with st.spinner(f"🔍 {stock_code} 종목 분석 중..."):
        try:
            # 일봉 데이터 조회
            df = api.get_daily_price(stock_code, period="D")

            if df is None or df.empty:
                st.error(f"❌ {stock_code} 종목의 데이터를 찾을 수 없습니다. 종목코드를 확인해주세요.")
                return

            # 종목명 조회 시도
            stock_name = stock_code
            try:
                kospi = get_kospi_stocks()
                kosdaq = get_kosdaq_stocks()
                all_stocks = {code: name for code, name in kospi + kosdaq}
                stock_name = all_stocks.get(stock_code, stock_code)
            except:
                pass

            # 분석 실행
            result = {
                'code': stock_code,
                'name': stock_name,
                'current_price': float(df['close'].iloc[-1]),
                'change_rate': 0
            }

            # 가격 변화율
            if len(df) >= 2:
                prev_price = df['close'].iloc[-2]
                result['change_rate'] = round((result['current_price'] - prev_price) / prev_price * 100, 2)

            # 스윙매매 패턴 분석
            swing_analysis = analyze_swing_patterns(df)
            if swing_analysis:
                result['swing_patterns'] = swing_analysis

            # 태쏘 전략 분석
            try:
                box_result = detect_box_range(df, period=20, tolerance=0.05)
                if box_result:
                    result['box_range'] = box_result

                breakout_result = detect_box_breakout(df, period=20, volume_confirm=True)
                if breakout_result:
                    result['box_breakout'] = breakout_result

                new_high_result = detect_new_high_trend(df, lookback=60, breakout_days=3)
                if new_high_result:
                    result['new_high_trend'] = new_high_result
            except Exception:
                pass

            # 다이버전스 분석
            try:
                divergence_result = analyze_divergence(df)
                if divergence_result:
                    result['divergence'] = divergence_result
            except Exception:
                pass

            # 기본 기술적 지표
            try:
                rsi = calculate_rsi(df['close'])
                macd = calculate_macd(df['close'])
                bollinger = calculate_bollinger(df['close'])
                volume_ratio = calculate_volume_ratio(df['volume'])

                result['rsi'] = round(rsi, 2)
                result['macd'] = macd
                result['bollinger'] = bollinger
                result['volume_ratio'] = round(volume_ratio, 2)
            except Exception:
                pass

            # 세션에 저장
            st.session_state['single_stock_result'] = result
            st.rerun()

        except Exception as e:
            st.error(f"❌ 분석 중 오류 발생: {str(e)}")


def _display_single_stock_analysis(result: dict):
    """개별 종목 분석 결과 표시"""
    if not result:
        return

    code = result.get('code', '')
    name = result.get('name', code)
    price = result.get('current_price', 0)
    change = result.get('change_rate', 0)

    # 기업 정보 조회
    company_info = None
    try:
        from dashboard.utils.api_helper import get_api_connection
        api = get_api_connection(verbose=False)
        if api and hasattr(api, 'get_company_overview'):
            company_info = api.get_company_overview(code)
            # 기업 정보가 없으면 기본 정보로 대체
            if not company_info:
                company_info = get_company_info_brief(code, name)
    except Exception as e:
        # 에러 시 기본 정보 사용
        company_info = get_company_info_brief(code, name)

    # 헤더 (검정색 기반) - 기업 정보 포함
    change_color = "#ff4757" if change > 0 else "#3498db" if change < 0 else "#95a5a6"
    change_icon = "▲" if change > 0 else "▼" if change < 0 else "─"

    # 업종/시장 정보 텍스트
    sector_text = ""
    market_cap_text = ""
    description_text = ""
    if company_info:
        if company_info.get('sector'):
            sector_text = f"<span style='background: rgba(255,255,255,0.15); padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; margin-right: 0.5rem;'>{company_info['sector']}</span>"
        if company_info.get('market'):
            sector_text += f"<span style='background: rgba(52,152,219,0.3); padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem;'>{company_info['market']}</span>"
        if company_info.get('market_cap') and company_info['market_cap'] > 0:
            if company_info['market_cap'] >= 1_000_000_000_000:
                market_cap_text = f"<span style='color: #f1c40f; font-size: 0.9rem; margin-left: 1rem;'>시총 {company_info['market_cap'] / 1_000_000_000_000:.1f}조</span>"
            else:
                market_cap_text = f"<span style='color: #f1c40f; font-size: 0.9rem; margin-left: 1rem;'>시총 {company_info['market_cap'] / 100_000_000:,.0f}억</span>"
        if company_info.get('description'):
            description_text = f"<p style='color: rgba(255,255,255,0.7); font-size: 0.85rem; margin-top: 0.8rem; margin-bottom: 0;'>{company_info['description']}</p>"

    html_content = f"<div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.5rem; border-radius: 12px; margin: 1rem 0; border: 1px solid rgba(255,255,255,0.1);'><div style='display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;'><div><h3 style='color: white; margin: 0; font-weight: 700;'>📈 {name} ({code})</h3><div style='margin-top: 0.5rem;'>{sector_text}</div></div><div style='text-align: right;'><p style='color: white; font-size: 1.5rem; margin: 0; font-weight: 600;'>{price:,.0f}원 <span style='font-size: 1rem; color: {change_color}; margin-left: 0.5rem;'>{change_icon} {abs(change):.2f}%</span></p>{market_cap_text}</div></div>{description_text}</div>"
    st.markdown(html_content, unsafe_allow_html=True)

    # 투자자별 매매동향 표시
    try:
        api = get_api_connection(verbose=False)
        if api:
            render_investor_trend(api, code, name, days=5, key_prefix=f"scr_inv_{code}")
    except:
        pass

    # 차트 표시 (매물대 포함)
    try:
        from dashboard.utils.api_helper import get_api_connection
        from dashboard.utils.chart_utils import render_candlestick_chart

        api = get_api_connection(verbose=False)
        if api:
            st.markdown("#### 📈 차트")
            df = api.get_daily_price(code, period="D")
            if df is not None and not df.empty:
                df = df.tail(120).copy()
                render_candlestick_chart(
                    data=df,
                    code=code,
                    name=name,
                    key_prefix="single_stock_chart",
                    height=500,
                    show_ma=True,
                    show_volume=True,
                    show_volume_profile=True,  # 매물대 표시
                    show_swing_points=True,
                    show_box_range=True,
                    ma_periods=[5, 20]
                )
    except Exception as e:
        st.warning(f"차트 로드 실패: {e}")

    # 탭으로 분류
    tab1, tab2, tab3, tab4 = st.tabs(["📊 기술적 지표", "🎯 스윙매매 패턴", "📦 태쏘 전략", "📉 다이버전스"])

    with tab1:
        _display_single_stock_indicators(result)

    with tab2:
        _display_single_stock_swing(result)

    with tab3:
        _display_single_stock_tasso(result)

    with tab4:
        _display_single_stock_divergence(result)


def _display_single_stock_indicators(result: dict):
    """기술적 지표 표시 (검정색 기반 카드)"""
    col1, col2, col3, col4, col5 = st.columns(5)

    # RSI
    with col1:
        rsi = result.get('rsi', 50)
        rsi_color = "#ff4757" if rsi >= 70 else "#2ed573" if rsi <= 30 else "#a4b0be"
        rsi_status = "과매수" if rsi >= 70 else "과매도" if rsi <= 30 else "중립"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
                    padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);'>
            <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>RSI (14)</p>
            <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{rsi:.1f}</p>
            <p style='color: {rsi_color}; font-size: 0.8rem; margin: 0;'>● {rsi_status}</p>
        </div>
        """, unsafe_allow_html=True)

    # MACD
    with col2:
        macd = result.get('macd', {})
        macd_value = macd.get('macd', 0)
        macd_signal = macd.get('signal', 0)
        cross = macd.get('cross', 'none')
        cross_text = "골든크로스" if cross == 'golden' else "데드크로스" if cross == 'dead' else "없음"
        cross_color = "#2ed573" if cross == 'golden' else "#ff4757" if cross == 'dead' else "#a4b0be"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
                    padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);'>
            <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>MACD</p>
            <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{macd_value:.1f}</p>
            <p style='color: {cross_color}; font-size: 0.8rem; margin: 0;'>● {cross_text}</p>
        </div>
        """, unsafe_allow_html=True)

    # 볼린저밴드
    with col3:
        bb = result.get('bollinger', {})
        bb_pos = bb.get('position', 0.5)
        bb_status = "상단 돌파" if bb_pos >= 0.9 else "하단 돌파" if bb_pos <= 0.1 else "중간"
        bb_color = "#ff4757" if bb_pos >= 0.9 else "#2ed573" if bb_pos <= 0.1 else "#a4b0be"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
                    padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);'>
            <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>볼린저 위치</p>
            <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{bb_pos*100:.0f}%</p>
            <p style='color: {bb_color}; font-size: 0.8rem; margin: 0;'>● {bb_status}</p>
        </div>
        """, unsafe_allow_html=True)

    # Williams %R (81% 승률 지표)
    with col4:
        williams_r = result.get('williams_r', -50)
        if williams_r >= -20:
            wr_status = "과매수"
            wr_color = "#ff4757"
        elif williams_r <= -80:
            wr_status = "과매도"
            wr_color = "#2ed573"
        elif williams_r >= -50:
            wr_status = "강세"
            wr_color = "#38ef7d"
        else:
            wr_status = "약세"
            wr_color = "#f39c12"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
                    padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);'>
            <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>Williams %R</p>
            <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{williams_r:.1f}</p>
            <p style='color: {wr_color}; font-size: 0.8rem; margin: 0;'>● {wr_status}</p>
        </div>
        """, unsafe_allow_html=True)

    # 거래량
    with col5:
        vol_ratio = result.get('volume_ratio', 1)
        vol_status = "급증" if vol_ratio >= 2 else "증가" if vol_ratio >= 1.5 else "보통"
        vol_color = "#ff4757" if vol_ratio >= 2 else "#f39c12" if vol_ratio >= 1.5 else "#a4b0be"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
                    padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);'>
            <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>거래량 비율</p>
            <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0;'>{vol_ratio:.1f}배</p>
            <p style='color: {vol_color}; font-size: 0.8rem; margin: 0;'>● {vol_status}</p>
        </div>
        """, unsafe_allow_html=True)


def _display_single_stock_swing(result: dict):
    """스윙매매 패턴 표시"""
    swing = result.get('swing_patterns', {})

    if not swing:
        st.info("스윙매매 패턴 분석 결과가 없습니다.")
        return

    # 종합 판단
    overall = swing.get('overall', 'neutral')
    overall_msg = swing.get('overall_message', '')

    if overall in ['strong_buy', 'buy']:
        st.success(f"🟢 **{overall_msg}**")
    elif overall == 'sell':
        st.error(f"🔴 **{overall_msg}**")
    elif overall == 'watch':
        st.warning(f"🟡 **{overall_msg}**")
    else:
        st.info(f"⚪ **{overall_msg}**")

    # 패턴 상세
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("##### 📐 감지된 패턴")
        patterns = swing.get('patterns', [])
        if patterns:
            for p in patterns:
                pattern_name = p.get('pattern', '')
                msg = p.get('message', '')
                st.markdown(f"- **{pattern_name}**: {msg}")
        else:
            st.caption("감지된 패턴 없음")

    with col2:
        st.markdown("##### 📊 매물대 분석")
        vp = swing.get('volume_profile', {})
        if vp.get('detected'):
            support = vp.get('support_zone')
            resist = vp.get('resistance_zone')
            if support:
                st.markdown(f"- 지지: **{support[0]:,.0f}원**")
            if resist:
                st.markdown(f"- 저항: **{resist[0]:,.0f}원**")
            if vp.get('near_support'):
                st.success("📍 지지 매물대 근접!")
            elif vp.get('near_resistance'):
                st.warning("📍 저항 매물대 근접!")
        else:
            st.caption("분석 결과 없음")

    with col3:
        st.markdown("##### 📈 이격도 분석")
        disparity = swing.get('disparity', {})
        if disparity.get('detected'):
            avg_disp = disparity.get('avg_disparity', 100)
            overall_sig = disparity.get('overall_signal', 'neutral')
            st.metric("평균 이격도", f"{avg_disp:.1f}%")
            if overall_sig == 'oversold':
                st.success("과매도 구간 (매수 기회)")
            elif overall_sig == 'overbought':
                st.error("과매수 구간 (조정 주의)")
            else:
                st.info("정상 범위")
        else:
            st.caption("분석 결과 없음")


def _display_single_stock_tasso(result: dict):
    """태쏘 전략 분석 표시"""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("##### 📦 박스권 분석")
        box = result.get('box_range', {})
        if box.get('detected'):
            upper = box.get('upper', 0)
            lower = box.get('lower', 0)
            pos = box.get('position_pct', 50)
            signal = box.get('signal', 'neutral')
            msg = box.get('message', '')

            st.markdown(f"- 상단: **{upper:,.0f}원**")
            st.markdown(f"- 하단: **{lower:,.0f}원**")
            st.markdown(f"- 위치: **{pos:.0f}%**")

            if signal == 'box_buy':
                st.success(f"🟢 {msg}")
            elif signal == 'breakout_buy':
                st.success(f"🔥 {msg}")
            elif signal == 'box_sell':
                st.warning(f"🟡 {msg}")
            elif signal == 'breakdown_sell':
                st.error(f"🔴 {msg}")
            else:
                st.info(f"⚪ {msg}")
        else:
            st.caption("박스권 분석 결과 없음")

    with col2:
        st.markdown("##### 🚀 박스권 돌파")
        breakout = result.get('box_breakout', {})
        if breakout.get('detected'):
            direction = breakout.get('direction', '')
            vol_ratio = breakout.get('volume_ratio', 1)
            vol_confirmed = breakout.get('volume_confirmed', False)
            msg = breakout.get('message', '')

            if direction == 'up':
                st.success(f"🔥 상향 돌파!")
            else:
                st.error(f"❄️ 하향 이탈!")

            st.markdown(f"- 거래량: **{vol_ratio:.1f}배**")
            if vol_confirmed:
                st.markdown("- ✅ 거래량 확인됨")
            st.caption(msg)
        else:
            st.caption("돌파 신호 없음")

    with col3:
        st.markdown("##### ⭐ 신고가 추세")
        new_high = result.get('new_high_trend', {})
        if new_high.get('detected'):
            is_52w = new_high.get('is_52w_high', False)
            vol_surge = new_high.get('volume_surge', False)
            is_bullish = new_high.get('is_bullish', False)
            signal = new_high.get('signal', 'watch')
            msg = new_high.get('message', '')

            if signal == 'strong_buy':
                st.success(f"🔥 {msg}")
            elif signal == 'buy':
                st.info(f"🟢 {msg}")
            else:
                st.warning(f"🟡 {msg}")

            st.markdown(f"- 52주 신고가: {'✅' if is_52w else '❌'}")
            st.markdown(f"- 거래량 급증: {'✅' if vol_surge else '❌'}")
            st.markdown(f"- 정배열: {'✅' if is_bullish else '❌'}")
        else:
            st.caption("신고가 추세 없음")


def _display_single_stock_divergence(result: dict):
    """다이버전스 분석 표시"""
    divergence = result.get('divergence', {})

    if not divergence or not divergence.get('detected'):
        st.info("다이버전스가 감지되지 않았습니다.")
        return

    overall = divergence.get('overall', 'neutral')
    overall_msg = divergence.get('overall_message', '')

    if overall == 'strong_buy':
        st.success(f"🔥 **{overall_msg}**")
    elif overall == 'buy':
        st.info(f"🟢 **{overall_msg}**")
    elif overall == 'strong_sell':
        st.error(f"⚠️ **{overall_msg}**")
    elif overall == 'sell':
        st.warning(f"🔴 **{overall_msg}**")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### RSI 다이버전스")
        rsi_div = divergence.get('rsi_divergence', {})
        if rsi_div and rsi_div.get('detected'):
            div_type = "상승" if rsi_div.get('type') == 'bullish' else "하락"
            strength = rsi_div.get('strength', 'moderate')
            strength_text = "강함" if strength == 'strong' else "보통"
            msg = rsi_div.get('message', '')

            if rsi_div.get('type') == 'bullish':
                st.success(f"🟢 **{div_type} 다이버전스** ({strength_text})")
            else:
                st.error(f"🔴 **{div_type} 다이버전스** ({strength_text})")
            st.caption(msg)
        else:
            st.caption("RSI 다이버전스 미감지")

    with col2:
        st.markdown("##### MACD 다이버전스")
        macd_div = divergence.get('macd_divergence', {})
        if macd_div and macd_div.get('detected'):
            div_type = "상승" if macd_div.get('type') == 'bullish' else "하락"
            strength = macd_div.get('strength', 'moderate')
            strength_text = "강함" if strength == 'strong' else "보통"
            msg = macd_div.get('message', '')

            if macd_div.get('type') == 'bullish':
                st.success(f"🟢 **{div_type} 다이버전스** ({strength_text})")
            else:
                st.error(f"🔴 **{div_type} 다이버전스** ({strength_text})")
            st.caption(msg)
        else:
            st.caption("MACD 다이버전스 미감지")


def _display_advanced_results(results: list):
    """고급 분석 결과 표시"""

    st.markdown("---")
    st.markdown("#### 📋 고급 분석 결과")

    # 통계 요약 - 6열로 확장
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("분석 종목", f"{len(results)}개")

    # 52주 저점 근접 종목 수
    near_low_count = sum(1 for r in results if (r.get('low_52w_info') or {}).get('is_near_low'))
    with col2:
        st.metric("52주 저점 근접", f"{near_low_count}개")

    # 바닥 다지기 패턴 종목 수
    bottom_count = sum(1 for r in results if (r.get('bottom_pattern') or {}).get('pattern_detected'))
    with col3:
        st.metric("바닥 다지기", f"{bottom_count}개")

    # 장대양봉 종목 수
    bullish_count = sum(1 for r in results if (r.get('large_bullish') or {}).get('detected'))
    with col4:
        st.metric("🔥 장대양봉", f"{bullish_count}개")

    # D+1, D+2 시그널 종목 수
    d1d2_count = sum(1 for r in results if (r.get('d1_d2_signal') or {}).get('has_recent_bullish'))
    with col5:
        st.metric("📈 D+1/D+2", f"{d1d2_count}개")

    # 전고점 돌파 종목 수
    breakout_count = sum(1 for r in results if (r.get('prev_high_breakout') or {}).get('is_breakout'))
    with col6:
        st.metric("🚀 전고점 돌파", f"{breakout_count}개")

    # 스윙매매 패턴 통계 (새 행)
    swing_stats = _calculate_swing_stats(results)

    if swing_stats['total'] > 0:
        st.markdown("##### 🎯 스윙매매 패턴 현황")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("쌍바닥", f"{swing_stats['double_bottom']}개")
        with col2:
            st.metric("역헤숄", f"{swing_stats['inv_hs']}개")
        with col3:
            st.metric("눌림목", f"{swing_stats['pullback']}개")
        with col4:
            st.metric("매집", f"{swing_stats['accumulation']}개")
        with col5:
            st.metric("지지 근접", f"{swing_stats['support']}개")
        with col6:
            st.metric("과매도", f"{swing_stats['oversold']}개")

    # 태쏘 전략 통계 계산
    tasso_stats = _calculate_tasso_stats(results)

    if tasso_stats['total'] > 0:
        st.markdown("##### 📦 태쏘 스윙투자 전략 현황")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("박스 상향돌파", f"{tasso_stats['box_breakout_up']}개")
        with col2:
            st.metric("박스 하단지지", f"{tasso_stats['box_buy']}개")
        with col3:
            st.metric("52주 신고가", f"{tasso_stats['new_high']}개")
        with col4:
            st.metric("신고가 근접", f"{tasso_stats['new_high_approach']}개")

    # 다이버전스 통계 계산
    divergence_stats = _calculate_divergence_stats(results)

    if divergence_stats['total'] > 0:
        st.markdown("##### 📉 다이버전스 시그널 현황")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("상승 다이버전스", f"{divergence_stats['bullish']}개")
        with col2:
            st.metric("하락 다이버전스", f"{divergence_stats['bearish']}개")
        with col3:
            st.metric("RSI 다이버전스", f"{divergence_stats['rsi']}개")
        with col4:
            st.metric("MACD 다이버전스", f"{divergence_stats['macd']}개")

    # 탭으로 분류 - 확장 (스윙매매 탭 + 태쏘 탭 + 다이버전스 탭 추가)
    tab_all, tab_bullish, tab_d1d2, tab_breakout, tab_swing, tab_tasso, tab_divergence, tab_low, tab_bottom, tab_theme = st.tabs([
        f"📊 전체 ({len(results)})",
        f"🔥 장대양봉 ({bullish_count})",
        f"📈 D+1/D+2 ({d1d2_count})",
        f"🚀 전고점 돌파 ({breakout_count})",
        f"🎯 스윙패턴 ({swing_stats['total']})",
        f"📦 태쏘전략 ({tasso_stats['total']})",
        f"📊 다이버전스 ({divergence_stats['total']})",
        f"📉 52주 저점 ({near_low_count})",
        f"🔄 바닥 다지기 ({bottom_count})",
        f"🏷️ 테마별"
    ])

    with tab_all:
        for r in results[:50]:  # 최대 50개
            _display_advanced_stock_card(r)

    with tab_bullish:
        # 장대양봉 종목
        bullish_stocks = [r for r in results if (r.get('large_bullish') or {}).get('detected')]
        if bullish_stocks:
            st.markdown("##### 🔥 오늘 장대양봉 발생 종목")
            st.caption("5% 이상 상승 + 거래량 급증 종목")
            for r in sorted(bullish_stocks, key=lambda x: (x.get('large_bullish') or {}).get('daily_change_pct', 0), reverse=True):
                _display_bullish_stock_card(r)
        else:
            st.info("오늘 장대양봉 패턴 종목이 없습니다.")

    with tab_d1d2:
        # D+1, D+2 시그널 종목
        d1d2_stocks = [r for r in results if (r.get('d1_d2_signal') or {}).get('has_recent_bullish')]
        if d1d2_stocks:
            st.markdown("##### 📈 D+1/D+2 매매 시그널")
            st.caption("최근 장대양봉 발생 후 매매 타이밍")

            # 시그널 유형별 분류
            buy_signals = [r for r in d1d2_stocks if (r.get('d1_d2_signal') or {}).get('signal_type') == 'buy']
            wait_signals = [r for r in d1d2_stocks if (r.get('d1_d2_signal') or {}).get('signal_type') in ['wait', 'caution']]

            if buy_signals:
                st.markdown("**🟢 매수 시그널**")
                for r in buy_signals:
                    _display_d1d2_stock_card(r)

            if wait_signals:
                st.markdown("**🟡 관망/신중**")
                for r in wait_signals:
                    _display_d1d2_stock_card(r)
        else:
            st.info("D+1/D+2 매매 시그널 종목이 없습니다.")

    with tab_breakout:
        # 전고점 돌파 종목
        breakout_stocks = [r for r in results if (r.get('prev_high_breakout') or {}).get('is_breakout')]
        near_resistance = [r for r in results if (r.get('prev_high_breakout') or {}).get('is_near_resistance') and not (r.get('prev_high_breakout') or {}).get('is_breakout')]

        if breakout_stocks:
            st.markdown("##### 🚀 전고점 돌파 종목")
            for r in breakout_stocks:
                _display_breakout_stock_card(r)

        if near_resistance:
            st.markdown("##### ⚡ 전고점 저항 근접 종목")
            st.caption("돌파 시 상승 모멘텀 기대")
            for r in near_resistance[:20]:
                _display_breakout_stock_card(r, is_resistance=True)

        if not breakout_stocks and not near_resistance:
            st.info("전고점 관련 시그널 종목이 없습니다.")

    with tab_swing:
        # 스윙매매 패턴 종목 - 개별 조건 선택 가능
        _display_swing_pattern_results_v2(results)

    with tab_tasso:
        # 태쏘 전략 종목
        _display_tasso_strategy_results(results)

    with tab_divergence:
        # 다이버전스 종목
        _display_divergence_results(results)

    with tab_low:
        low_stocks = [r for r in results if (r.get('low_52w_info') or {}).get('is_near_low')]
        if low_stocks:
            for r in sorted(low_stocks, key=lambda x: (x.get('low_52w_info') or {}).get('rise_from_low', 100)):
                _display_advanced_stock_card(r, highlight='52w_low')
        else:
            st.info("52주 저점 근접 종목이 없습니다.")

    with tab_bottom:
        bottom_stocks = [r for r in results if (r.get('bottom_pattern') or {}).get('pattern_detected')]
        if bottom_stocks:
            for r in sorted(bottom_stocks, key=lambda x: (x.get('bottom_pattern') or {}).get('strength', 0), reverse=True):
                _display_advanced_stock_card(r, highlight='bottom')
        else:
            st.info("바닥 다지기 패턴 종목이 없습니다.")

    with tab_theme:
        # 테마별 그룹핑
        theme_groups = {}
        for r in results:
            for theme in r.get('themes', ['기타']):
                if theme not in theme_groups:
                    theme_groups[theme] = []
                theme_groups[theme].append(r)

        # 기타 제외하고 표시
        for theme_name in THEME_KEYWORDS.keys():
            if theme_name in theme_groups:
                with st.expander(f"🏷️ {theme_name} ({len(theme_groups[theme_name])}개)", expanded=False):
                    for r in theme_groups[theme_name][:20]:
                        _display_advanced_stock_card(r, compact=True)


def _display_stock_chart(code: str, name: str, d1d2_info: dict = None):
    """종목 차트 표시 (캔들 + 거래량 + 매물대 + 박스권)

    Note: chart_utils.render_candlestick_chart 사용으로 매물대 포함
    """
    from dashboard.utils.chart_utils import render_candlestick_chart

    api = get_api_connection()
    if api is None:
        st.warning("API 연결이 필요합니다.")
        return

    try:
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty:
            st.warning("차트 데이터를 불러올 수 없습니다.")
            return

        df = df.tail(120).copy()
        render_candlestick_chart(
            data=df,
            code=code,
            name=name,
            key_prefix=f"screener_{code}",
            height=500,
            show_ma=True,
            show_volume=True,
            show_volume_profile=True,  # 매물대 표시
            show_swing_points=True,
            show_box_range=True,
            d1d2_info=d1d2_info,
            ma_periods=[5, 20]
        )
    except Exception as e:
        st.error(f"차트 로드 오류: {e}")


def _display_bullish_stock_card(result: dict):
    """장대양봉 종목 카드 표시 (차트 포함)"""
    name = result.get('name', '')
    code = result.get('code', '')
    current_price = result.get('current_price', 0)
    bullish = result.get('large_bullish') or {}

    col1, col2, col3, col4, col5, col6 = st.columns([2.5, 1.5, 1.5, 1.5, 1.5, 0.8])

    with col1:
        st.markdown(f"🔥 **{name}** ({code})")

    with col2:
        change = bullish.get('daily_change_pct', 0)
        st.markdown(f"<span style='color: #FF4444; font-weight: bold;'>+{change:.1f}%</span>", unsafe_allow_html=True)

    with col3:
        vol_ratio = bullish.get('volume_ratio', 1)
        st.markdown(f"거래량 **{vol_ratio:.1f}**배")

    with col4:
        body_ratio = bullish.get('body_ratio', 0)
        st.markdown(f"몸통 {body_ratio:.0f}%")

    with col5:
        strength = bullish.get('strength_text', '')
        st.markdown(f"강도: **{strength}**")

    with col6:
        # 차트 보기 버튼
        if st.button("📊", key=f"chart_bullish_{code}", help="차트 보기"):
            st.session_state[f'show_chart_bullish_{code}'] = not st.session_state.get(f'show_chart_bullish_{code}', False)

    # 차트 표시 영역
    if st.session_state.get(f'show_chart_bullish_{code}', False):
        _display_stock_chart(code, name)

    st.markdown("---")


def _display_d1d2_stock_card(result: dict):
    """D+1/D+2 시그널 종목 카드 표시 (차트 포함)"""
    name = result.get('name', '')
    code = result.get('code', '')
    current_price = result.get('current_price', 0)
    d1d2 = result.get('d1_d2_signal') or {}

    col1, col2, col3, col4, col5 = st.columns([2.5, 2.5, 2, 2, 1])

    with col1:
        days = d1d2.get('days_since_bullish', 0)
        icon = "📈" if d1d2.get('signal_type') == 'buy' else "⏳"
        st.markdown(f"{icon} **{name}** ({code})")

    with col2:
        signal = d1d2.get('signal', '')
        st.markdown(f"**{signal}**")

    with col3:
        if d1d2.get('entry_price'):
            st.markdown(f"진입가: {d1d2['entry_price']:,.0f}원")
        else:
            st.markdown(f"현재가: {current_price:,.0f}원")

    with col4:
        if d1d2.get('stop_loss') and d1d2.get('target_price'):
            st.caption(f"손절: {d1d2['stop_loss']:,.0f} / 목표: {d1d2['target_price']:,.0f}")

    with col5:
        # 차트 보기 버튼
        if st.button("📊", key=f"chart_d1d2_{code}", help="차트 보기"):
            st.session_state[f'show_chart_{code}'] = not st.session_state.get(f'show_chart_{code}', False)

    # 차트 표시 영역
    if st.session_state.get(f'show_chart_{code}', False):
        _display_stock_chart(code, name, d1d2)

    st.markdown("---")


def _display_breakout_stock_card(result: dict, is_resistance: bool = False):
    """전고점 돌파/저항 종목 카드 표시 (차트 포함)"""
    name = result.get('name', '')
    code = result.get('code', '')
    current_price = result.get('current_price', 0)
    phb = result.get('prev_high_breakout') or {}

    col1, col2, col3, col4, col5 = st.columns([2.5, 2, 2, 2, 0.8])

    with col1:
        icon = "🚀" if not is_resistance else "⚡"
        st.markdown(f"{icon} **{name}** ({code})")

    with col2:
        prev_high = phb.get('prev_high', 0)
        st.markdown(f"전고점: {prev_high:,.0f}원")

    with col3:
        st.markdown(f"현재가: {current_price:,.0f}원")

    with col4:
        distance = phb.get('distance_to_high_pct', 0)
        if is_resistance:
            st.markdown(f"<span style='color: #FF9800;'>저항까지 -{distance:.1f}%</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color: #4CAF50;'>돌파 완료!</span>", unsafe_allow_html=True)

    with col5:
        # 차트 보기 버튼
        if st.button("📊", key=f"chart_breakout_{code}", help="차트 보기"):
            st.session_state[f'show_chart_breakout_{code}'] = not st.session_state.get(f'show_chart_breakout_{code}', False)

    # 차트 표시 영역 (전고점 라인 포함)
    if st.session_state.get(f'show_chart_breakout_{code}', False):
        _display_stock_chart_with_resistance(code, name, phb)

    st.markdown("---")


def _display_stock_chart_with_resistance(code: str, name: str, phb_info: dict = None):
    """종목 차트 표시 (전고점 저항선 + 매물대 포함)

    Note: chart_utils.render_candlestick_chart 사용으로 매물대 포함
    """
    from dashboard.utils.chart_utils import render_candlestick_chart

    api = get_api_connection()
    if api is None:
        st.warning("API 연결이 필요합니다.")
        return

    # 전고점 저항선 정보 추출
    d1d2_info = {}
    if phb_info:
        prev_high = phb_info.get('prev_high')
        if prev_high:
            d1d2_info['resistance_line'] = prev_high
            d1d2_info['resistance_label'] = f"전고점: {prev_high:,.0f}"

    try:
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty:
            st.warning("차트 데이터를 불러올 수 없습니다.")
            return

        df = df.tail(120).copy()
        render_candlestick_chart(
            data=df,
            code=code,
            name=name,
            key_prefix=f"resistance_{code}",
            height=500,
            show_ma=True,
            show_volume=True,
            show_volume_profile=True,  # 매물대 표시
            show_swing_points=True,
            show_box_range=True,
            d1d2_info=d1d2_info if d1d2_info else None,
            ma_periods=[5, 20]
        )
    except Exception as e:
        st.error(f"차트 로드 오류: {e}")


def _display_advanced_stock_card(result: dict, highlight: str = None, compact: bool = False):
    """고급 분석 종목 카드 표시"""

    name = result.get('name', '')
    code = result.get('code', '')
    themes = result.get('themes', [])
    current_price = result.get('current_price', 0)
    change_rate = result.get('change_rate', 0)
    low_info = result.get('low_52w_info') or {}
    bottom = result.get('bottom_pattern') or {}
    signals = result.get('signals', [])

    # 업종 정보 가져오기
    sector = get_sector_info_cached(code)

    # 카드 배경색
    if highlight == '52w_low':
        bg_color = "rgba(76, 175, 80, 0.15)"
    elif highlight == 'bottom':
        bg_color = "rgba(33, 150, 243, 0.15)"
    else:
        bg_color = "rgba(100, 100, 100, 0.1)"

    change_color = "#FF4444" if change_rate > 0 else "#4444FF" if change_rate < 0 else "#888"
    change_sign = "+" if change_rate > 0 else ""

    if compact:
        # 간단한 표시 (컬럼 방식)
        col1, col2, col3 = st.columns([2.5, 1.5, 2])
        with col1:
            sector_tag = f" <span style='background: rgba(100,100,100,0.3); padding: 0.1rem 0.4rem; border-radius: 8px; font-size: 0.7rem;'>{sector}</span>" if sector and sector != '기타' else ""
            st.markdown(f"**{name}** ({code}){sector_tag}", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<span style='color: {change_color};'>{change_sign}{change_rate:.1f}%</span>", unsafe_allow_html=True)
        with col3:
            if low_info.get('is_near_low'):
                st.markdown(f"📉 저점대비 +{low_info.get('rise_from_low', 0):.1f}%")
    else:
        # 상세 표시 (컬럼 레이아웃 사용)
        # 테마 태그 생성 (업종 정보 포함)
        theme_tags = ""
        if sector and sector != '기타' and sector not in themes:
            theme_tags += f" `{sector}`"
        for t in themes:
            if t != '기타':
                theme_tags += f" `{t}`"

        # 메인 정보 컬럼
        col_name, col_price, col_rate = st.columns([3, 2, 1.5])

        with col_name:
            st.markdown(f"**{name}** ({code}){theme_tags}")

        with col_price:
            st.markdown(f"**{current_price:,.0f}**원")

        with col_rate:
            st.markdown(f"<span style='color: {change_color}; font-weight: bold;'>{change_sign}{change_rate:.1f}%</span>", unsafe_allow_html=True)

        # 추가 정보 컬럼
        info_cols = st.columns(4)

        with info_cols[0]:
            if low_info:
                rise = low_info.get('rise_from_low', 0)
                st.caption(f"📉 저점대비 +{rise:.1f}%")

        with info_cols[1]:
            if low_info:
                drop = low_info.get('drop_from_high', 0)
                st.caption(f"📈 고점대비 -{drop:.1f}%")

        with info_cols[2]:
            if bottom.get('pattern_detected'):
                strength = bottom.get('strength_text', '')
                st.caption(f"🔄 바닥: {strength}")

        with info_cols[3]:
            if signals:
                signal_texts = [s['signal'] for s in signals[:2]]
                st.caption(f"🎯 {', '.join(signal_texts)}")

        st.markdown("---")


def _render_signal_scanner(api):
    """시그널 스캐너 - 주요 매매 신호 자동 감지"""

    st.markdown("### 🎯 실시간 매매 시그널")
    st.caption("코스피/코스닥 종목에서 기술적 신호가 발생한 종목을 자동으로 감지합니다")

    # 스캔 옵션
    st.markdown("#### ⚙️ 스캔 설정")
    opt_col1, opt_col2, opt_col3 = st.columns(3)

    with opt_col1:
        scan_market = st.selectbox(
            "대상 시장",
            ["all", "kospi", "kosdaq"],
            format_func=lambda x: {"all": "전체 (코스피+코스닥)", "kospi": "코스피", "kosdaq": "코스닥"}[x],
            key="signal_scan_market"
        )

    with opt_col2:
        scan_count = st.selectbox(
            "스캔 종목 수",
            ["전체", 50, 100, 200, 500, 1000],
            index=0,  # 기본값: 전체
            format_func=lambda x: "전체 종목" if x == "전체" else f"{x}개 종목",
            key="signal_scan_count",
            help="종목 수가 많을수록 스캔 시간이 오래 걸립니다"
        )

    with opt_col3:
        # 예상 시간 표시 (전체일 경우 약 3000개 추정)
        count_for_time = 3000 if scan_count == "전체" else scan_count
        est_time = count_for_time * 0.1  # 병렬 처리로 종목당 약 0.1초
        st.metric("예상 소요 시간", f"약 {est_time/60:.1f}분" if est_time >= 60 else f"약 {est_time:.0f}초")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h4 style='color: white; margin: 0;'>📈 매수 시그널</h4>
        </div>
        """, unsafe_allow_html=True)

        st.checkbox("RSI 과매도 구간 (RSI ≤ 30)", value=True, key="signal_rsi_oversold")
        st.checkbox("MACD 골든크로스", value=True, key="signal_macd_golden")
        st.checkbox("볼린저밴드 하단 돌파", value=True, key="signal_bb_lower")
        st.checkbox("거래량 급증 (3배 이상)", value=True, key="signal_volume_surge")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
            <h4 style='color: white; margin: 0;'>📉 매도 시그널</h4>
        </div>
        """, unsafe_allow_html=True)

        st.checkbox("RSI 과매수 구간 (RSI ≥ 70)", value=True, key="signal_rsi_overbought")
        st.checkbox("MACD 데드크로스", value=True, key="signal_macd_dead")
        st.checkbox("볼린저밴드 상단 돌파", value=True, key="signal_bb_upper")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 시그널 스캔 실행", type="primary", use_container_width=True):
            # 스캔 실행
            signals = _scan_signals(api, market=scan_market, max_stocks=scan_count)

            if signals:
                st.session_state['signal_results'] = signals
                st.success(f"✅ {len(signals)}개 시그널을 감지했습니다!")
            else:
                st.info("현재 감지된 시그널이 없습니다.")

    # 시그널 결과 표시
    if 'signal_results' in st.session_state and st.session_state['signal_results']:
        _display_signal_results(st.session_state['signal_results'])


def _render_screener_results():
    """검색 결과 분석 탭"""

    st.markdown("### 📈 검색 결과 분석")

    if 'screener_results' not in st.session_state or not st.session_state['screener_results']:
        st.info("먼저 '조건 검색' 또는 '시그널 스캐너'를 실행해주세요.")
        return

    results = st.session_state['screener_results']

    # 결과 통계
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("검색된 종목", f"{len(results)}개")

    avg_rsi = np.mean([r.get('rsi', 50) for r in results if r.get('rsi')])
    with col2:
        st.metric("평균 RSI", f"{avg_rsi:.1f}")

    up_count = sum(1 for r in results if r.get('change_rate', 0) > 0)
    with col3:
        st.metric("상승 종목", f"{up_count}개")

    down_count = len(results) - up_count
    with col4:
        st.metric("하락 종목", f"{down_count}개")

    # 상세 결과 테이블
    st.markdown("---")
    st.markdown("#### 📋 상세 결과")

    df = pd.DataFrame(results)
    if not df.empty:
        # 컬럼 포맷팅
        if 'change_rate' in df.columns:
            df['등락률'] = df['change_rate'].apply(lambda x: f"{x:+.2f}%")
        if 'volume_ratio' in df.columns:
            df['거래량비'] = df['volume_ratio'].apply(lambda x: f"{x:.1f}배")
        if 'rsi' in df.columns:
            df['RSI'] = df['rsi'].apply(lambda x: f"{x:.1f}")
        if 'market_cap' in df.columns:
            df['시가총액'] = df['market_cap'].apply(format_market_cap)
        if 'shares' in df.columns:
            df['상장주식수'] = df['shares'].apply(format_shares)

        display_cols = ['code', 'name', '등락률', 'RSI', '거래량비', '시가총액', '상장주식수', 'signal']
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        # CSV 다운로드
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 결과 다운로드 (CSV)",
            csv,
            f"screener_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )


def _collect_conditions():
    """UI에서 설정된 조건 수집"""
    conditions = {}

    # RSI 조건
    if st.session_state.get('use_rsi'):
        rsi_cond = st.session_state.get('rsi_condition', '')
        if rsi_cond == "과매도 (< 30)":
            conditions['rsi'] = {'min': 0, 'max': 30}
        elif rsi_cond == "과매수 (> 70)":
            conditions['rsi'] = {'min': 70, 'max': 100}
        elif rsi_cond == "상승 반전 (30 돌파)":
            conditions['rsi_crossover'] = 30
        elif rsi_cond == "하락 반전 (70 하회)":
            conditions['rsi_crossunder'] = 70
        elif rsi_cond == "커스텀":
            conditions['rsi'] = {
                'min': st.session_state.get('rsi_min', 0),
                'max': st.session_state.get('rsi_max', 100)
            }

    # MACD 조건
    if st.session_state.get('use_macd'):
        macd_cond = st.session_state.get('macd_condition', '')
        if macd_cond == "골든크로스 (매수)":
            conditions['macd_golden_cross'] = True
        elif macd_cond == "데드크로스 (매도)":
            conditions['macd_dead_cross'] = True
        elif macd_cond == "히스토그램 상승":
            conditions['macd_hist_rising'] = True
        elif macd_cond == "히스토그램 하락":
            conditions['macd_hist_falling'] = True

    # 볼린저밴드 조건
    if st.session_state.get('use_bb'):
        bb_cond = st.session_state.get('bb_condition', '')
        if bb_cond == "하단 터치 (매수)":
            conditions['bb_lower_touch'] = True
        elif bb_cond == "상단 터치 (매도)":
            conditions['bb_upper_touch'] = True

    # Williams %R 조건 (81% 승률 지표)
    if st.session_state.get('use_williams'):
        williams_cond = st.session_state.get('williams_condition', '')
        if williams_cond == "과매도 (< -80)":
            conditions['williams_r'] = {'min': -100, 'max': -80}
        elif williams_cond == "과매수 (> -20)":
            conditions['williams_r'] = {'min': -20, 'max': 0}
        elif williams_cond == "과매도 반등 (-80 상향돌파)":
            conditions['williams_r_crossover'] = -80
        elif williams_cond == "과매수 하락 (-20 하향돌파)":
            conditions['williams_r_crossunder'] = -20
        elif williams_cond == "커스텀":
            conditions['williams_r'] = {
                'min': st.session_state.get('williams_min', -100),
                'max': st.session_state.get('williams_max', 0)
            }

    # 거래량 조건
    if st.session_state.get('use_volume'):
        vol_cond = st.session_state.get('vol_condition', '')
        if vol_cond == "급증 (20일 평균 2배 이상)":
            conditions['volume_ratio'] = 2.0
        elif vol_cond == "급증 (20일 평균 3배 이상)":
            conditions['volume_ratio'] = 3.0
        elif vol_cond == "급감 (20일 평균 50% 이하)":
            conditions['volume_ratio_max'] = 0.5

    # 이동평균선 조건
    if st.session_state.get('use_ma'):
        ma_cond = st.session_state.get('ma_condition', '')
        if ma_cond == "골든크로스 (5일>20일)":
            conditions['ma_golden_cross'] = True
        elif ma_cond == "데드크로스 (5일<20일)":
            conditions['ma_dead_cross'] = True
        elif ma_cond == "정배열 (5>20>60)":
            conditions['ma_aligned_up'] = True
        elif ma_cond == "역배열 (5<20<60)":
            conditions['ma_aligned_down'] = True
        elif ma_cond == "장기 골든크로스 (50>200)":
            conditions['ma_golden_cross_50_200'] = True
        elif ma_cond == "장기 데드크로스 (50<200)":
            conditions['ma_dead_cross_50_200'] = True
        elif ma_cond == "완전 정배열 (5>10>20>50>100>200)":
            conditions['ma_full_aligned_up'] = True
        elif ma_cond == "200일선 위 (장기 강세)":
            conditions['above_ma200'] = True
        elif ma_cond == "200MA·피보나치 confluence":
            conditions['ma200_fib_confluence'] = True

    # 펀더멘털 필터
    if st.session_state.get('use_per'):
        conditions['per_max'] = st.session_state.get('per_max', 20)
    if st.session_state.get('use_pbr'):
        conditions['pbr_max'] = st.session_state.get('pbr_max', 2)
    if st.session_state.get('use_cap'):
        conditions['cap_min'] = st.session_state.get('cap_min', 1000)

    return conditions


def _run_screener(api, conditions: dict, market: str, max_results: int) -> list:
    """
    코스피/코스닥 전종목 조건 스크리너 실행

    Args:
        api: KIS API 객체
        conditions: 검색 조건 딕셔너리
        market: 시장 ('전체', 'KOSPI', 'KOSDAQ')
        max_results: 최대 결과 수

    Returns:
        조건에 맞는 종목 리스트
    """
    results = []

    # 스캔할 종목 리스트 가져오기
    stocks_to_scan = []

    market_lower = market.lower() if market else 'all'
    if market_lower in ['전체', 'all', '']:
        market_lower = 'all'
    elif market_lower == 'kospi':
        market_lower = 'kospi'
    elif market_lower == 'kosdaq':
        market_lower = 'kosdaq'

    if market_lower in ['kospi', 'all']:
        kospi = get_kospi_stocks()
        stocks_to_scan.extend([(code, name, 'KOSPI') for code, name in kospi])

    if market_lower in ['kosdaq', 'all']:
        kosdaq = get_kosdaq_stocks()
        stocks_to_scan.extend([(code, name, 'KOSDAQ') for code, name in kosdaq])

    if not stocks_to_scan:
        st.warning("스캔할 종목이 없습니다.")
        return []

    # 스캔할 종목 수 제한 (최대 500개 - 속도 고려)
    max_scan = min(500, len(stocks_to_scan))
    stocks_to_scan = stocks_to_scan[:max_scan]

    # 시총·상장주식수 일괄 prefetch (전 종목 단 1회 pykrx 호출)
    try:
        _market_cap_table = get_market_cap_dict("ALL")
    except Exception:
        _market_cap_table = {}

    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(stocks_to_scan)
    scanned = 0
    found = 0

    for code, name, mkt in stocks_to_scan:
        scanned += 1
        progress = scanned / total
        progress_bar.progress(progress)
        status_text.text(f"스캔 중: {name} ({code}) - {scanned}/{total} 종목 완료, {found}개 조건 충족")

        try:
            # 60일 데이터 조회
            df = api.get_daily_price(code, period="D")

            if df is None or df.empty or len(df) < 30:
                continue

            # 기술적 지표 계산
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']

            rsi = calculate_rsi(close)
            macd = calculate_macd(close)
            bollinger = calculate_bollinger(close)
            volume_ratio = calculate_volume_ratio(volume)
            williams_r = calculate_williams_r(high, low, close)

            # 가격 변화
            current_price = close.iloc[-1]
            prev_price = close.iloc[-2] if len(close) >= 2 else current_price
            change_rate = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

            # 이동평균선 계산
            ma5 = close.rolling(5).mean().iloc[-1] if len(close) >= 5 else current_price
            ma10 = close.rolling(10).mean().iloc[-1] if len(close) >= 10 else current_price
            ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else current_price
            ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else current_price
            ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else current_price
            ma100 = close.rolling(100).mean().iloc[-1] if len(close) >= 100 else current_price
            ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else current_price

            # 조건 체크
            match = True
            matched_signals = []

            # RSI 조건
            if 'rsi' in conditions:
                if not (conditions['rsi']['min'] <= rsi <= conditions['rsi']['max']):
                    match = False
                else:
                    if rsi <= 30:
                        matched_signals.append("RSI 과매도")
                    elif rsi >= 70:
                        matched_signals.append("RSI 과매수")

            # RSI 크로스오버/크로스언더
            if 'rsi_crossover' in conditions and len(df) >= 2:
                prev_rsi = calculate_rsi(close.iloc[:-1])
                if not (prev_rsi < conditions['rsi_crossover'] <= rsi):
                    match = False
                else:
                    matched_signals.append(f"RSI {conditions['rsi_crossover']} 돌파")

            if 'rsi_crossunder' in conditions and len(df) >= 2:
                prev_rsi = calculate_rsi(close.iloc[:-1])
                if not (prev_rsi > conditions['rsi_crossunder'] >= rsi):
                    match = False
                else:
                    matched_signals.append(f"RSI {conditions['rsi_crossunder']} 하회")

            # MACD 조건
            if conditions.get('macd_golden_cross'):
                if macd['cross'] != 'golden':
                    match = False
                else:
                    matched_signals.append("MACD 골든크로스")

            if conditions.get('macd_dead_cross'):
                if macd['cross'] != 'dead':
                    match = False
                else:
                    matched_signals.append("MACD 데드크로스")

            # 볼린저밴드 조건
            if conditions.get('bb_lower_touch'):
                if bollinger['position'] > 0.1:
                    match = False
                else:
                    matched_signals.append("볼린저밴드 하단")

            if conditions.get('bb_upper_touch'):
                if bollinger['position'] < 0.9:
                    match = False
                else:
                    matched_signals.append("볼린저밴드 상단")

            # Williams %R 조건 (81% 승률 지표)
            if 'williams_r' in conditions:
                if not (conditions['williams_r']['min'] <= williams_r <= conditions['williams_r']['max']):
                    match = False
                else:
                    if williams_r <= -80:
                        matched_signals.append("Williams %R 과매도")
                    elif williams_r >= -20:
                        matched_signals.append("Williams %R 과매수")
                    else:
                        matched_signals.append(f"Williams %R {williams_r:.1f}")

            # Williams %R 크로스오버/크로스언더
            if 'williams_r_crossover' in conditions and len(df) >= 2:
                prev_williams = calculate_williams_r(high.iloc[:-1], low.iloc[:-1], close.iloc[:-1])
                if not (prev_williams < conditions['williams_r_crossover'] <= williams_r):
                    match = False
                else:
                    matched_signals.append(f"Williams %R {conditions['williams_r_crossover']} 상향돌파")

            if 'williams_r_crossunder' in conditions and len(df) >= 2:
                prev_williams = calculate_williams_r(high.iloc[:-1], low.iloc[:-1], close.iloc[:-1])
                if not (prev_williams > conditions['williams_r_crossunder'] >= williams_r):
                    match = False
                else:
                    matched_signals.append(f"Williams %R {conditions['williams_r_crossunder']} 하향돌파")

            # 거래량 조건
            if 'volume_ratio' in conditions:
                if volume_ratio < conditions['volume_ratio']:
                    match = False
                else:
                    matched_signals.append(f"거래량 {volume_ratio:.1f}배")

            if 'volume_ratio_max' in conditions:
                if volume_ratio > conditions['volume_ratio_max']:
                    match = False
                else:
                    matched_signals.append("거래량 급감")

            # 이동평균선 조건
            if conditions.get('ma_golden_cross'):
                # 5일선이 20일선 상향 돌파
                prev_ma5 = close.rolling(5).mean().iloc[-2] if len(close) >= 6 else ma5
                prev_ma20 = close.rolling(20).mean().iloc[-2] if len(close) >= 21 else ma20
                if not (prev_ma5 < prev_ma20 and ma5 > ma20):
                    match = False
                else:
                    matched_signals.append("MA 골든크로스")

            if conditions.get('ma_dead_cross'):
                prev_ma5 = close.rolling(5).mean().iloc[-2] if len(close) >= 6 else ma5
                prev_ma20 = close.rolling(20).mean().iloc[-2] if len(close) >= 21 else ma20
                if not (prev_ma5 > prev_ma20 and ma5 < ma20):
                    match = False
                else:
                    matched_signals.append("MA 데드크로스")

            if conditions.get('ma_aligned_up'):
                if not (ma5 > ma20 > ma60):
                    match = False
                else:
                    matched_signals.append("정배열")

            if conditions.get('ma_aligned_down'):
                if not (ma5 < ma20 < ma60):
                    match = False
                else:
                    matched_signals.append("역배열")

            # 50/200 골든·데드 크로스 (장기 추세 전환)
            if conditions.get('ma_golden_cross_50_200') and len(close) >= 201:
                prev_ma50 = close.rolling(50).mean().iloc[-2]
                prev_ma200 = close.rolling(200).mean().iloc[-2]
                if not (prev_ma50 < prev_ma200 and ma50 > ma200):
                    match = False
                else:
                    matched_signals.append("50/200 골든크로스")

            if conditions.get('ma_dead_cross_50_200') and len(close) >= 201:
                prev_ma50 = close.rolling(50).mean().iloc[-2]
                prev_ma200 = close.rolling(200).mean().iloc[-2]
                if not (prev_ma50 > prev_ma200 and ma50 < ma200):
                    match = False
                else:
                    matched_signals.append("50/200 데드크로스")

            # 완전 정배열 (5>10>20>50>100>200) - 강한 상승 추세
            if conditions.get('ma_full_aligned_up') and len(close) >= 200:
                if not (ma5 > ma10 > ma20 > ma50 > ma100 > ma200):
                    match = False
                else:
                    matched_signals.append("완전 정배열")

            # 200일선 위 (장기 강세 종목 필터)
            if conditions.get('above_ma200') and len(close) >= 200:
                if not (current_price > ma200):
                    match = False
                else:
                    pct_above = (current_price - ma200) / ma200 * 100
                    matched_signals.append(f"200MA 위 +{pct_above:.1f}%")

            # 200MA + 피보나치 confluence (강한 지지/저항)
            if conditions.get('ma200_fib_confluence') and len(close) >= 200:
                conf = detect_ma200_fibonacci_confluence(close, lookback=120, tolerance_pct=2.0)
                if not conf or not conf.get('matched'):
                    match = False
                else:
                    best = conf['matched'][0]  # 가장 가까운 매칭
                    matched_signals.append(
                        f"200MA·피보 {best['level']} confluence ({conf['price_zone']})"
                    )

            # 조건 충족 시 결과에 추가
            if match:
                cap_info = _market_cap_table.get(str(code), {}) if _market_cap_table else {}
                results.append({
                    "code": code,
                    "name": name,
                    "market": mkt,
                    "price": int(current_price),
                    "change_rate": round(change_rate, 2),
                    "rsi": round(rsi, 1),
                    "volume_ratio": round(volume_ratio, 1),
                    "market_cap": int(cap_info.get("market_cap", 0)),
                    "shares": int(cap_info.get("shares", 0)),
                    "signal": ", ".join(matched_signals) if matched_signals else "조건 충족"
                })
                found += 1

                if found >= max_results:
                    break

            # API 속도 제한 방지
            time.sleep(0.15)

        except Exception as e:
            continue

    # 진행률 표시 제거
    progress_bar.empty()
    status_text.empty()

    return results


def _scan_signals(api, market: str = "all", max_stocks = "전체") -> list:
    """
    코스피/코스닥 전종목 매매 시그널 스캔

    Args:
        api: KIS API 객체
        market: 시장 ('kospi', 'kosdaq', 'all')
        max_stocks: 스캔할 최대 종목 수 (숫자 또는 "전체")

    Returns:
        시그널이 발견된 종목 리스트
    """
    signals = []

    # 스캔할 종목 리스트 가져오기
    stocks_to_scan = []

    if market in ['kospi', 'all']:
        kospi = get_kospi_stocks()
        stocks_to_scan.extend([(code, name, 'KOSPI') for code, name in kospi])

    if market in ['kosdaq', 'all']:
        kosdaq = get_kosdaq_stocks()
        stocks_to_scan.extend([(code, name, 'KOSDAQ') for code, name in kosdaq])

    # 최대 종목 수 제한 ("전체"가 아닐 경우에만)
    if max_stocks != "전체":
        stocks_to_scan = stocks_to_scan[:int(max_stocks)]

    if not stocks_to_scan:
        st.warning("스캔할 종목이 없습니다.")
        return []

    # 진행률 표시
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(stocks_to_scan)
    scanned = 0
    found = 0

    for code, name, mkt in stocks_to_scan:
        scanned += 1
        progress = scanned / total
        progress_bar.progress(progress)
        status_text.text(f"스캔 중: {name} ({code}) - {scanned}/{total} 종목 완료, {found}개 시그널 발견")

        try:
            # 60일 데이터 조회 (기술적 지표 계산용)
            df = api.get_daily_price(code, period="D")

            if df is None or df.empty or len(df) < 30:
                continue

            # 기술적 시그널 분석
            analysis = analyze_stock_signals(df)

            if analysis is None:
                continue

            # 발견된 시그널 처리
            for signal_type, signal_name, strength in analysis['signals']:
                # 세션 상태에서 필터 조건 확인
                check_key = f"{'buy' if signal_type == 'buy' else 'sell'}_{signal_name.split()[0]}"

                # 시그널 추가
                signals.append({
                    "code": code,
                    "name": name,
                    "market": mkt,
                    "signal_type": signal_type,
                    "signal": signal_name,
                    "strength": strength,
                    "price": int(analysis['price']),
                    "change_rate": round(analysis['change_rate'], 2),
                    "rsi": round(analysis['rsi'], 1),
                    "volume_ratio": round(analysis['volume_ratio'], 1)
                })
                found += 1

            # API 속도 제한 방지
            time.sleep(0.15)

        except Exception as e:
            # 오류 발생 시 건너뛰기
            continue

    # 진행률 표시 제거
    progress_bar.empty()
    status_text.empty()

    # 시그널 필터링 (사용자가 선택한 시그널 유형만)
    filtered = _filter_signals_by_selection(signals)

    return filtered if filtered else signals


def _filter_signals_by_selection(signals: list) -> list:
    """사용자가 선택한 시그널 유형으로 필터링"""
    filtered = []

    # 매수 시그널 필터
    buy_filters = {
        'rsi': st.session_state.get('signal_rsi_oversold', True),
        'macd': st.session_state.get('signal_macd_golden', True),
        'bollinger': st.session_state.get('signal_bb_lower', True),
        'volume': st.session_state.get('signal_volume_surge', True)
    }

    # 매도 시그널 필터
    sell_filters = {
        'rsi': st.session_state.get('signal_rsi_overbought', True),
        'macd': st.session_state.get('signal_macd_dead', True),
        'bollinger': st.session_state.get('signal_bb_upper', True),
        'volume': st.session_state.get('signal_volume_surge', True)
    }

    for sig in signals:
        signal_name = sig['signal'].lower()
        signal_type = sig['signal_type']

        include = False

        if signal_type == 'buy':
            if 'rsi' in signal_name and buy_filters['rsi']:
                include = True
            elif 'macd' in signal_name and buy_filters['macd']:
                include = True
            elif '볼린저' in sig['signal'] and buy_filters['bollinger']:
                include = True
            elif '거래량' in sig['signal'] and buy_filters['volume']:
                include = True
        else:  # sell
            if 'rsi' in signal_name and sell_filters['rsi']:
                include = True
            elif 'macd' in signal_name and sell_filters['macd']:
                include = True
            elif '볼린저' in sig['signal'] and sell_filters['bollinger']:
                include = True
            elif '거래량' in sig['signal'] and sell_filters['volume']:
                include = True

        if include:
            filtered.append(sig)

    return filtered


def _display_screener_results(results: list):
    """스크리너 결과 표시"""
    st.markdown("---")
    st.markdown("#### 📋 검색 결과")

    for i, stock in enumerate(results):
        col1, col2, col3, col4, col5 = st.columns([2.5, 1.5, 1.5, 1.5, 2])

        with col1:
            # 종목명 + 업종 정보
            code = stock.get('code', '')
            name = stock.get('name', code)
            sector = stock.get('sector', '')
            if not sector:
                sector = get_sector_info_cached(code)
            sector_tag = f" <span style='background: rgba(100,100,100,0.3); padding: 0.1rem 0.4rem; border-radius: 8px; font-size: 0.75rem;'>{sector}</span>" if sector and sector != '기타' else ""
            st.markdown(f"**{name}** ({code}){sector_tag}", unsafe_allow_html=True)

        with col2:
            change = stock.get('change_rate', 0)
            color = "#FF4444" if change > 0 else "#4444FF" if change < 0 else "#888"
            st.markdown(f"<span style='color: {color}; font-weight: bold;'>{change:+.2f}%</span>", unsafe_allow_html=True)

        with col3:
            rsi = stock.get('rsi', '-')
            rsi_color = "#FF4444" if rsi > 70 else "#4444FF" if rsi < 30 else "#888"
            st.markdown(f"RSI: <span style='color: {rsi_color};'>{rsi}</span>", unsafe_allow_html=True)

        with col4:
            vol = stock.get('volume_ratio', 1)
            st.markdown(f"거래량: {vol:.1f}배")

        with col5:
            signal = stock.get('signal', '')
            st.markdown(f"🎯 {signal}")


def _display_signal_results(signals: list):
    """시그널 결과 표시"""
    st.markdown("---")
    st.markdown("#### 📋 발견된 시그널")

    buy_signals = [s for s in signals if s.get('signal_type') == 'buy']
    sell_signals = [s for s in signals if s.get('signal_type') == 'sell']

    # 탭으로 매수/매도 시그널 분리
    tab_buy, tab_sell = st.tabs([f"🟢 매수 시그널 ({len(buy_signals)})", f"🔴 매도 시그널 ({len(sell_signals)})"])

    with tab_buy:
        if buy_signals:
            # 시그널 유형 추출 및 필터 UI
            buy_signal_types = list(set(s['signal'] for s in buy_signals))
            buy_signal_types.sort()

            # 필터 및 표시 개수 선택
            col_filter, col_count = st.columns([3, 1])
            with col_filter:
                selected_buy_signals = st.multiselect(
                    "📊 시그널 필터",
                    options=buy_signal_types,
                    default=buy_signal_types,
                    key="buy_signal_filter",
                    help="표시할 시그널 유형을 선택하세요"
                )
            with col_count:
                items_per_page = st.selectbox(
                    "표시 개수",
                    [20, 50, 100, "전체"],
                    key="buy_items_per_page"
                )

            # 선택된 시그널 유형으로 필터링
            filtered_buy_signals = [s for s in buy_signals if s['signal'] in selected_buy_signals]

            # 전체 표시 또는 페이지네이션
            if items_per_page == "전체" or len(filtered_buy_signals) == 0:
                display_signals = filtered_buy_signals
                page = 1
                total_pages = 1
            else:
                # 페이지네이션
                total_pages = max(1, (len(filtered_buy_signals) - 1) // items_per_page + 1)
                if total_pages > 1:
                    page = st.selectbox(
                        f"페이지 (총 {total_pages})",
                        range(1, total_pages + 1),
                        key="buy_page"
                    )
                else:
                    page = 1
                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                display_signals = filtered_buy_signals[start_idx:end_idx]

            st.caption(f"표시: {len(display_signals)}개 / 필터된 전체: {len(filtered_buy_signals)}개 (원본: {len(buy_signals)}개)")

            # 시그널 목록 표시
            for sig in display_signals:
                col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1.5])
                with col1:
                    code = sig.get('code', '')
                    name = sig.get('name', code)
                    sector = get_sector_info_cached(code)
                    sector_tag = f" <span style='background: rgba(76,175,80,0.2); padding: 0.1rem 0.4rem; border-radius: 8px; font-size: 0.7rem;'>{sector}</span>" if sector and sector != '기타' else ""
                    st.markdown(f"🟢 **{name}** ({code}){sector_tag}", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"🎯 {sig['signal']}")
                with col3:
                    change_color = "#FF4444" if sig['change_rate'] > 0 else "#4444FF"
                    st.markdown(f"<span style='color: {change_color};'>{sig['change_rate']:+.1f}%</span>", unsafe_allow_html=True)
                with col4:
                    st.markdown(f"강도: {sig['strength']}")
        else:
            st.info("매수 시그널이 없습니다.")

    with tab_sell:
        if sell_signals:
            # 시그널 유형 추출 및 필터 UI
            sell_signal_types = list(set(s['signal'] for s in sell_signals))
            sell_signal_types.sort()

            # 필터 및 표시 개수 선택
            col_filter, col_count = st.columns([3, 1])
            with col_filter:
                selected_sell_signals = st.multiselect(
                    "📊 시그널 필터",
                    options=sell_signal_types,
                    default=sell_signal_types,
                    key="sell_signal_filter",
                    help="표시할 시그널 유형을 선택하세요"
                )
            with col_count:
                items_per_page_sell = st.selectbox(
                    "표시 개수",
                    [20, 50, 100, "전체"],
                    key="sell_items_per_page"
                )

            # 선택된 시그널 유형으로 필터링
            filtered_sell_signals = [s for s in sell_signals if s['signal'] in selected_sell_signals]

            # 전체 표시 또는 페이지네이션
            if items_per_page_sell == "전체" or len(filtered_sell_signals) == 0:
                display_signals_sell = filtered_sell_signals
                page_sell = 1
                total_pages_sell = 1
            else:
                # 페이지네이션
                total_pages_sell = max(1, (len(filtered_sell_signals) - 1) // items_per_page_sell + 1)
                if total_pages_sell > 1:
                    page_sell = st.selectbox(
                        f"페이지 (총 {total_pages_sell})",
                        range(1, total_pages_sell + 1),
                        key="sell_page"
                    )
                else:
                    page_sell = 1
                start_idx_sell = (page_sell - 1) * items_per_page_sell
                end_idx_sell = start_idx_sell + items_per_page_sell
                display_signals_sell = filtered_sell_signals[start_idx_sell:end_idx_sell]

            st.caption(f"표시: {len(display_signals_sell)}개 / 필터된 전체: {len(filtered_sell_signals)}개 (원본: {len(sell_signals)}개)")

            # 시그널 목록 표시
            for sig in display_signals_sell:
                col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1.5])
                with col1:
                    code = sig.get('code', '')
                    name = sig.get('name', code)
                    sector = get_sector_info_cached(code)
                    sector_tag = f" <span style='background: rgba(255,68,68,0.2); padding: 0.1rem 0.4rem; border-radius: 8px; font-size: 0.7rem;'>{sector}</span>" if sector and sector != '기타' else ""
                    st.markdown(f"🔴 **{name}** ({code}){sector_tag}", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"🎯 {sig['signal']}")
                with col3:
                    change_color = "#FF4444" if sig['change_rate'] > 0 else "#4444FF"
                    st.markdown(f"<span style='color: {change_color};'>{sig['change_rate']:+.1f}%</span>", unsafe_allow_html=True)
                with col4:
                    st.markdown(f"강도: {sig['strength']}")
        else:
            st.info("매도 시그널이 없습니다.")


# get_api_connection() 함수는 dashboard/utils/api_helper.py로 통합됨
# from dashboard.utils.api_helper import get_api_connection 사용

# ========== 추가 분석 기능 ==========
# 기술적 지표 계산 함수들은 dashboard/utils/indicators.py로 이동됨

# 테마 분류 데이터
THEME_KEYWORDS = {
    '원전': {
        'keywords': ['원전', '원자력', '핵', 'SMR', '소형모듈원자로', '우라늄', '두산에너빌리티', '한전기술', '한전KPS', '비에이치아이',
                    '우진', '보성파워텍', '일진파워', '태웅', '세아베스틸지주', '에너토크'],
        'codes': ['034020', '052690', '051600', '083650', '049800', '006910', '094820', '044490', '001430', '095910']
    },
    'AI/반도체': {
        'keywords': ['AI', '인공지능', '반도체', 'GPU', 'HBM', '엔비디아', '삼성전자', 'SK하이닉스', '한미반도체',
                    '리노공업', '솔브레인', '원익IPS', '파크시스템스', '티씨케이', '이오테크닉스'],
        'codes': ['005930', '000660', '042700', '058470', '357780', '240810', '140860', '140410', '064760']
    },
    '2차전지': {
        'keywords': ['2차전지', '배터리', '전기차', 'EV', '리튬', '양극재', '음극재', 'LG에너지솔루션', 'SK온', '삼성SDI',
                    '에코프로비엠', '포스코퓨처엠', '엘앤에프'],
        'codes': ['373220', '006400', '247540', '003670', '066970']
    },
    '바이오': {
        'keywords': ['바이오', '제약', '신약', '셀트리온', '삼성바이오로직스', '유한양행', '한미약품', '대웅제약',
                    '녹십자', '종근당', '알테오젠'],
        'codes': ['068270', '207940', '000100', '128940', '069620', '006280', '185750', '196170']
    },
    '핀테크/디지털금융': {
        'keywords': ['핀테크', '디지털', '가상자산', '비트코인', '블록체인', '간편결제', '카카오페이', '토스', '다날',
                    '갤럭시아머니트리', 'NHN한국사이버결제'],
        'codes': ['377300', '064260', '094480', '060250']
    },
    '엔터/콘텐츠': {
        'keywords': ['엔터', '게임', '드라마', 'OTT', '하이브', 'JYP', 'SM', '넷마블', '펄어비스', '엔씨소프트',
                    '크래프톤', '카카오엔터', '스튜디오드래곤'],
        'codes': ['352820', '035900', '041510', '251270', '263750', '036570', '259960', '253450']
    },
    '방산/우주항공': {
        'keywords': ['방산', '방위산업', '우주', '항공', '한화에어로스페이스', 'LIG넥스원', '한국항공우주',
                    '현대로템', '풍산', '두산퓨얼셀'],
        'codes': ['012450', '079550', '047810', '064350', '103140', '336260']
    },
    '로봇': {
        'keywords': ['로봇', '자동화', '삼성전자', '현대로보틱스', '두산로보틱스', '레인보우로보틱스',
                    'HL만도', '뉴로메카', '로보스타'],
        'codes': ['454910', '277810', '090460', '204270', '108860']
    }
}


def classify_stock_theme(stock_code: str, stock_name: str) -> list:
    """
    종목의 테마 자동 분류

    Args:
        stock_code: 종목코드
        stock_name: 종목명

    Returns:
        해당되는 테마 리스트
    """
    themes = []

    for theme_name, theme_data in THEME_KEYWORDS.items():
        # 종목코드로 확인
        if stock_code in theme_data.get('codes', []):
            themes.append(theme_name)
            continue

        # 종목명 키워드로 확인
        for keyword in theme_data.get('keywords', []):
            if keyword.lower() in stock_name.lower():
                if theme_name not in themes:
                    themes.append(theme_name)
                break

    return themes if themes else ['기타']


def calculate_52week_low_ratio(df: pd.DataFrame) -> dict:
    """
    52주 최저점 대비 상승률 계산

    Args:
        df: 일봉 데이터 (최소 250일 권장)

    Returns:
        52주 최저점 정보
    """
    if df is None or df.empty:
        return None

    # 52주 = 약 250 거래일
    period = min(250, len(df))
    recent_data = df.tail(period)

    low_52w = recent_data['low'].min()
    high_52w = recent_data['high'].max()
    current_price = df['close'].iloc[-1]

    # 최저점 날짜 찾기
    low_idx = recent_data['low'].idxmin()
    low_date = df.loc[low_idx, 'date'] if 'date' in df.columns else low_idx

    # 상승률 계산
    rise_from_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 0

    # 고점 대비 하락률
    drop_from_high = ((high_52w - current_price) / high_52w * 100) if high_52w > 0 else 0

    return {
        'low_52w': low_52w,
        'high_52w': high_52w,
        'current_price': current_price,
        'rise_from_low': round(rise_from_low, 2),
        'drop_from_high': round(drop_from_high, 2),
        'low_date': low_date,
        'is_near_low': rise_from_low < 20,  # 저점 대비 20% 이내
        'is_near_high': drop_from_high < 10  # 고점 대비 10% 이내
    }


def detect_bottom_consolidation(df: pd.DataFrame, period: int = 20) -> dict:
    """
    바닥 다지기 패턴 인식 (거래량 감소 + 횡보)

    Args:
        df: 일봉 데이터
        period: 패턴 인식 기간 (기본 20일)

    Returns:
        바닥 다지기 패턴 정보
    """
    if df is None or df.empty or len(df) < period + 10:
        return None

    recent = df.tail(period)
    prev = df.iloc[-(period*2):-(period)]  # 이전 기간

    # 1. 거래량 감소 체크
    recent_avg_vol = recent['volume'].mean()
    prev_avg_vol = prev['volume'].mean() if len(prev) > 0 else recent_avg_vol
    volume_decrease = (prev_avg_vol - recent_avg_vol) / prev_avg_vol * 100 if prev_avg_vol > 0 else 0

    # 2. 가격 횡보 체크 (변동성 감소)
    recent_volatility = (recent['high'].max() - recent['low'].min()) / recent['close'].mean() * 100
    prev_volatility = (prev['high'].max() - prev['low'].min()) / prev['close'].mean() * 100 if len(prev) > 0 else recent_volatility

    # 3. 이동평균선 수렴 체크
    ma5 = recent['close'].rolling(5).mean()
    ma20 = recent['close'].rolling(20).mean()
    ma_convergence = abs(ma5.iloc[-1] - ma20.iloc[-1]) / ma20.iloc[-1] * 100 if len(ma20) > 0 and pd.notna(ma20.iloc[-1]) and ma20.iloc[-1] > 0 else 10

    # 바닥 다지기 패턴 판단
    is_volume_decreasing = volume_decrease > 20  # 거래량 20% 이상 감소
    is_sideways = recent_volatility < 15  # 변동폭 15% 이내
    is_ma_converging = ma_convergence < 3  # 이평선 수렴 (3% 이내)

    # 패턴 강도 계산
    strength = 0
    if is_volume_decreasing:
        strength += 1
    if is_sideways:
        strength += 1
    if is_ma_converging:
        strength += 1

    pattern_detected = strength >= 2

    return {
        'pattern_detected': pattern_detected,
        'strength': strength,
        'strength_text': ['없음', '약함', '보통', '강함'][strength],
        'volume_decrease': round(volume_decrease, 1),
        'volatility': round(recent_volatility, 1),
        'ma_convergence': round(ma_convergence, 2),
        'is_volume_decreasing': is_volume_decreasing,
        'is_sideways': is_sideways,
        'is_ma_converging': is_ma_converging,
        'signal': '바닥 다지기 패턴 감지' if pattern_detected else None
    }


def detect_large_bullish_candle(df: pd.DataFrame, min_gain_pct: float = 5.0, volume_multiplier: float = 2.0) -> dict:
    """
    장대양봉 감지 (홍인기 매매법)

    조건:
    - 당일 종가가 시가 대비 5% 이상 상승
    - 거래량이 20일 평균 대비 200% 이상
    - 캔들 몸통이 전체 캔들의 70% 이상 (윗꼬리/아래꼬리 짧음)

    Args:
        df: 일봉 데이터 (OHLCV)
        min_gain_pct: 최소 상승률 (기본 5%)
        volume_multiplier: 거래량 배수 조건 (기본 2배)

    Returns:
        장대양봉 정보 dict
    """
    if df is None or df.empty or len(df) < 21:
        return None

    # 최근 거래일 데이터
    today = df.iloc[-1]
    open_price = today['open']
    close_price = today['close']
    high_price = today['high']
    low_price = today['low']
    volume = today['volume']

    # 전일 데이터
    yesterday = df.iloc[-2]
    prev_close = yesterday['close']

    # 1. 당일 등락률 계산 (전일 종가 대비)
    daily_change_pct = ((close_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

    # 2. 시가 대비 상승률
    intraday_gain_pct = ((close_price - open_price) / open_price * 100) if open_price > 0 else 0

    # 3. 20일 평균 거래량 대비 비율
    avg_volume_20d = df['volume'].iloc[-21:-1].mean()
    volume_ratio = (volume / avg_volume_20d) if avg_volume_20d > 0 else 1

    # 4. 캔들 몸통 비율 (양봉인 경우)
    candle_range = high_price - low_price
    body_size = abs(close_price - open_price)
    body_ratio = (body_size / candle_range * 100) if candle_range > 0 else 0

    # 5. 장대양봉 판정
    is_bullish = close_price > open_price  # 양봉
    is_large_gain = daily_change_pct >= min_gain_pct  # 5% 이상 상승
    is_volume_surge = volume_ratio >= volume_multiplier  # 거래량 2배 이상
    is_solid_body = body_ratio >= 60  # 몸통 60% 이상 (꼬리 짧음)

    # 장대양봉 강도 계산
    strength = 0
    if is_bullish and is_large_gain:
        strength += 1
    if is_volume_surge:
        strength += 1
    if is_solid_body:
        strength += 1
    if daily_change_pct >= 10:  # 10% 이상 급등
        strength += 1
    if volume_ratio >= 5:  # 거래량 5배 이상
        strength += 1

    is_large_bullish = is_bullish and is_large_gain and (is_volume_surge or is_solid_body)

    return {
        'detected': is_large_bullish,
        'daily_change_pct': round(daily_change_pct, 2),
        'intraday_gain_pct': round(intraday_gain_pct, 2),
        'volume_ratio': round(volume_ratio, 2),
        'body_ratio': round(body_ratio, 1),
        'strength': strength,
        'strength_text': ['없음', '약함', '보통', '강함', '매우강함', '폭발'][min(strength, 5)],
        'open': open_price,
        'close': close_price,
        'high': high_price,
        'low': low_price,
        'prev_close': prev_close,
        'volume': volume,
        'avg_volume_20d': avg_volume_20d
    }


def analyze_d1_d2_signal(df: pd.DataFrame, large_bullish_info: dict = None) -> dict:
    """
    D+1, D+2 매매 시그널 분석 (홍인기 매매법)

    장대양봉 발생 후:
    - D+1: 장대양봉 익일, 조정 또는 갭상승 확인
    - D+2: D+1 익일, 추세 지속 또는 돌파 확인

    매수 타이밍:
    - D+1 조정 시 장대양봉 몸통 중간(50%)~하단(시가) 지지 확인 후 매수
    - 손절: 장대양봉 시가 이탈
    - 목표: 장대양봉 고점 돌파

    Args:
        df: 일봉 데이터
        large_bullish_info: 장대양봉 정보 (없으면 자동 감지)

    Returns:
        D+1, D+2 시그널 분석 결과
    """
    if df is None or df.empty or len(df) < 5:
        return None

    # 과거 5일간 장대양봉 검색 (최근 장대양봉 발생일 찾기)
    bullish_days = []
    for i in range(2, min(6, len(df))):  # D-4 ~ D-1 검사
        temp_df = df.iloc[:-(i-1)] if i > 1 else df
        if len(temp_df) < 21:
            continue
        bullish_check = detect_large_bullish_candle(temp_df)
        if bullish_check and bullish_check.get('detected'):
            bullish_days.append({
                'days_ago': i - 1,  # 0 = 오늘, 1 = 어제, ...
                'info': bullish_check,
                'date_idx': len(df) - i
            })

    if not bullish_days:
        return {
            'has_recent_bullish': False,
            'signal': None,
            'message': '최근 5일 내 장대양봉 없음'
        }

    # 가장 최근 장대양봉 기준
    latest_bullish = bullish_days[0]
    days_since_bullish = latest_bullish['days_ago']
    bullish_info = latest_bullish['info']

    # 장대양봉 기준 가격
    bullish_open = bullish_info['open']
    bullish_close = bullish_info['close']
    bullish_high = bullish_info['high']
    bullish_low = bullish_info['low']
    bullish_mid = (bullish_open + bullish_close) / 2  # 몸통 중간

    # 현재가
    current_price = df['close'].iloc[-1]
    current_low = df['low'].iloc[-1]
    current_high = df['high'].iloc[-1]

    # D+1, D+2 시그널 분석
    signal = None
    signal_type = None
    entry_price = None
    stop_loss = None
    target_price = None

    if days_since_bullish == 1:
        # 오늘이 D+1 (장대양봉 익일)
        # 조정 시 매수 기회
        if current_low <= bullish_mid:
            # 몸통 중간까지 조정 → 매수 시그널
            signal = 'D+1 조정 매수 기회'
            signal_type = 'buy'
            entry_price = bullish_mid  # 진입가: 몸통 중간
            stop_loss = bullish_open * 0.98  # 손절: 장대양봉 시가 -2%
            target_price = bullish_high * 1.05  # 목표: 장대양봉 고점 +5%
        elif current_price > bullish_high:
            # 갭상승 돌파
            signal = 'D+1 갭상승 추격 (신중)'
            signal_type = 'caution'
            entry_price = current_price
            stop_loss = bullish_mid
            target_price = current_price * 1.10
        else:
            signal = 'D+1 관망 (조정 대기)'
            signal_type = 'wait'

    elif days_since_bullish == 2:
        # 오늘이 D+2
        d1_close = df['close'].iloc[-2]  # D+1 종가

        if current_price > bullish_high:
            # 장대양봉 고점 돌파
            signal = 'D+2 고점 돌파 매수'
            signal_type = 'buy'
            entry_price = bullish_high
            stop_loss = bullish_mid
            target_price = bullish_high * 1.10
        elif current_low < bullish_open:
            # 장대양봉 시가 이탈 → 손절/관망
            signal = 'D+2 시가 이탈 (손절)'
            signal_type = 'sell'
        else:
            signal = 'D+2 박스권 (관망)'
            signal_type = 'wait'

    elif days_since_bullish >= 3:
        # D+3 이후
        if current_price > bullish_high:
            signal = f'D+{days_since_bullish} 고점 돌파 추세'
            signal_type = 'buy'
        elif current_price < bullish_open:
            signal = f'D+{days_since_bullish} 추세 이탈'
            signal_type = 'sell'
        else:
            signal = f'D+{days_since_bullish} 박스권 횡보'
            signal_type = 'neutral'

    return {
        'has_recent_bullish': True,
        'days_since_bullish': days_since_bullish,
        'bullish_info': bullish_info,
        'signal': signal,
        'signal_type': signal_type,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'target_price': target_price,
        'bullish_open': bullish_open,
        'bullish_close': bullish_close,
        'bullish_high': bullish_high,
        'bullish_mid': bullish_mid,
        'current_price': current_price
    }


def detect_previous_high_breakout(df: pd.DataFrame, lookback_days: int = 60) -> dict:
    """
    전고점 돌파/저항 분석

    Args:
        df: 일봉 데이터
        lookback_days: 전고점 탐색 기간 (기본 60일)

    Returns:
        전고점 분석 결과
    """
    if df is None or df.empty or len(df) < lookback_days + 5:
        return None

    current_price = df['close'].iloc[-1]
    current_high = df['high'].iloc[-1]

    # 최근 lookback_days 기간의 고점들 (피크) 찾기
    highs = df['high'].iloc[-(lookback_days + 1):-1]  # 오늘 제외

    # 전고점 (최근 기간 최고가)
    prev_high = highs.max()
    prev_high_idx = highs.idxmax()
    prev_high_date = df.loc[prev_high_idx, 'date'] if 'date' in df.columns else prev_high_idx

    # 돌파 여부
    is_breakout = current_high > prev_high
    is_near_resistance = (prev_high - current_price) / prev_high * 100 < 3  # 3% 이내

    # 돌파 후 지지 전환 여부
    support_test = None
    if is_breakout:
        # 돌파 후 되돌림 시 전고점이 지지되는지
        recent_low = df['low'].iloc[-1]
        support_test = recent_low >= prev_high * 0.98  # 전고점 -2% 이상 지지

    # 저항/지지 강도 계산
    # 전고점 부근에서 며칠간 저항받았는지
    resistance_count = sum(1 for h in highs.tail(20) if abs(h - prev_high) / prev_high < 0.02)

    return {
        'prev_high': prev_high,
        'prev_high_date': prev_high_date,
        'current_price': current_price,
        'is_breakout': is_breakout,
        'is_near_resistance': is_near_resistance,
        'distance_to_high_pct': round((prev_high - current_price) / prev_high * 100, 2),
        'support_test': support_test,
        'resistance_strength': resistance_count,
        'signal': '전고점 돌파!' if is_breakout else ('저항 근접' if is_near_resistance else None)
    }


def detect_turnaround(eps_data: list) -> dict:
    """
    실적 턴어라운드 감지 (적자→흑자 전환)

    Args:
        eps_data: EPS 데이터 리스트 [{'period': '2024Q1', 'eps': 100}, ...]

    Returns:
        턴어라운드 정보
    """
    if not eps_data or len(eps_data) < 2:
        return {'is_turnaround': False, 'message': '데이터 부족'}

    # 최근 2개 분기 비교
    current = eps_data[-1]
    previous = eps_data[-2]

    current_eps = current.get('eps', 0) or 0
    previous_eps = previous.get('eps', 0) or 0

    # 적자에서 흑자 전환
    loss_to_profit = previous_eps < 0 and current_eps > 0

    # 흑자 지속 + 증가
    profit_increasing = previous_eps > 0 and current_eps > previous_eps

    # 적자 축소
    loss_decreasing = previous_eps < 0 and current_eps < 0 and current_eps > previous_eps

    # 턴어라운드 강도
    if loss_to_profit:
        turnaround_type = 'strong'
        message = f"적자→흑자 전환! (EPS: {previous_eps} → {current_eps})"
    elif loss_decreasing:
        turnaround_type = 'weak'
        message = f"적자 축소 중 (EPS: {previous_eps} → {current_eps})"
    elif profit_increasing:
        turnaround_type = 'improving'
        message = f"흑자 증가 (EPS: {previous_eps} → {current_eps})"
    else:
        turnaround_type = None
        message = "턴어라운드 신호 없음"

    return {
        'is_turnaround': turnaround_type in ['strong', 'weak'],
        'turnaround_type': turnaround_type,
        'message': message,
        'current_eps': current_eps,
        'previous_eps': previous_eps,
        'change_rate': ((current_eps - previous_eps) / abs(previous_eps) * 100) if previous_eps != 0 else 0
    }


def analyze_advanced_signals(df: pd.DataFrame, stock_code: str, stock_name: str, eps_data: list = None) -> dict:
    """
    고급 분석 시그널 통합 (홍인기 매매법 포함)

    Args:
        df: 일봉 데이터
        stock_code: 종목코드
        stock_name: 종목명
        eps_data: EPS 데이터 (선택)

    Returns:
        고급 분석 결과
    """
    result = {
        'code': stock_code,
        'name': stock_name,
        'themes': [],
        'low_52w_info': None,
        'bottom_pattern': None,
        'turnaround': None,
        'large_bullish': None,
        'd1_d2_signal': None,
        'prev_high_breakout': None,
        'signals': []
    }

    # 1. 테마 분류
    result['themes'] = classify_stock_theme(stock_code, stock_name)

    # 2. 52주 최저점 대비 분석
    if df is not None and not df.empty:
        result['low_52w_info'] = calculate_52week_low_ratio(df)
        if result['low_52w_info'] and result['low_52w_info'].get('is_near_low'):
            result['signals'].append({
                'type': 'buy',
                'signal': f"52주 저점 근접 (+{result['low_52w_info']['rise_from_low']:.1f}%)",
                'strength': '강함' if result['low_52w_info']['rise_from_low'] < 10 else '보통'
            })

    # 3. 바닥 다지기 패턴
    if df is not None and not df.empty:
        result['bottom_pattern'] = detect_bottom_consolidation(df)
        if result['bottom_pattern'] and result['bottom_pattern'].get('pattern_detected'):
            result['signals'].append({
                'type': 'buy',
                'signal': f"바닥 다지기 ({result['bottom_pattern']['strength_text']})",
                'strength': result['bottom_pattern']['strength_text']
            })

    # 4. 실적 턴어라운드
    if eps_data:
        result['turnaround'] = detect_turnaround(eps_data)
        if result['turnaround'] and result['turnaround'].get('is_turnaround'):
            result['signals'].append({
                'type': 'buy',
                'signal': result['turnaround']['message'],
                'strength': '강함' if result['turnaround']['turnaround_type'] == 'strong' else '보통'
            })

    # 5. 장대양봉 감지 (홍인기 매매법)
    if df is not None and not df.empty and len(df) >= 21:
        result['large_bullish'] = detect_large_bullish_candle(df)
        if result['large_bullish'] and result['large_bullish'].get('detected'):
            result['signals'].append({
                'type': 'buy',
                'signal': f"🔥 장대양봉 ({result['large_bullish']['daily_change_pct']:+.1f}%, 거래량 {result['large_bullish']['volume_ratio']:.1f}배)",
                'strength': result['large_bullish']['strength_text']
            })

    # 6. D+1, D+2 매매 시그널
    if df is not None and not df.empty:
        result['d1_d2_signal'] = analyze_d1_d2_signal(df)
        if result['d1_d2_signal'] and result['d1_d2_signal'].get('has_recent_bullish'):
            d1d2 = result['d1_d2_signal']
            if d1d2.get('signal_type') == 'buy':
                result['signals'].append({
                    'type': 'buy',
                    'signal': f"📈 {d1d2['signal']}",
                    'strength': '강함'
                })
            elif d1d2.get('signal_type') == 'sell':
                result['signals'].append({
                    'type': 'sell',
                    'signal': f"⚠️ {d1d2['signal']}",
                    'strength': '보통'
                })

    # 7. 전고점 돌파/저항 분석
    if df is not None and not df.empty:
        result['prev_high_breakout'] = detect_previous_high_breakout(df)
        if result['prev_high_breakout']:
            phb = result['prev_high_breakout']
            if phb.get('is_breakout'):
                result['signals'].append({
                    'type': 'buy',
                    'signal': f"🚀 전고점 돌파! (기준: {phb['prev_high']:,.0f}원)",
                    'strength': '강함'
                })
            elif phb.get('is_near_resistance'):
                result['signals'].append({
                    'type': 'caution',
                    'signal': f"⚡ 전고점 저항 근접 (-{phb['distance_to_high_pct']:.1f}%)",
                    'strength': '보통'
                })

    return result


# ========== 스윙매매 패턴 관련 헬퍼 함수 ==========

def _calculate_swing_stats(results: list) -> dict:
    """스윙매매 패턴 통계 계산"""
    stats = {
        'double_bottom': 0,
        'inv_hs': 0,
        'pullback': 0,
        'accumulation': 0,
        'support': 0,
        'oversold': 0,
        'total': 0
    }

    for r in results:
        swing = r.get('swing_patterns', {})
        if not swing:
            continue

        for pattern in swing.get('patterns', []):
            if pattern.get('detected'):
                if pattern.get('pattern') == 'double_bottom':
                    stats['double_bottom'] += 1
                elif pattern.get('pattern') == 'inverse_head_shoulders':
                    stats['inv_hs'] += 1
                elif pattern.get('pattern') == 'pullback':
                    stats['pullback'] += 1
                elif pattern.get('pattern') == 'accumulation':
                    stats['accumulation'] += 1

        vp = swing.get('volume_profile', {})
        if vp.get('near_support'):
            stats['support'] += 1

        disp = swing.get('disparity', {})
        if disp.get('overall_signal') == 'oversold':
            stats['oversold'] += 1

    stats['total'] = (stats['double_bottom'] + stats['inv_hs'] + stats['pullback'] +
                      stats['accumulation'] + stats['support'] + stats['oversold'])
    return stats


# ========== 태쏘 전략 관련 헬퍼 함수 ==========

def _calculate_tasso_stats(results: list) -> dict:
    """태쏘 스윙투자 전략 통계 계산"""
    stats = {
        'box_breakout_up': 0,
        'box_buy': 0,
        'new_high': 0,
        'new_high_approach': 0,
        'total': 0
    }

    for r in results:
        # 박스권 상향 돌파
        breakout = r.get('box_breakout', {})
        if breakout.get('direction') == 'up':
            # strength는 'strong'/'weak' 문자열 또는 숫자일 수 있음
            strength = breakout.get('strength', '')
            is_strong = strength == 'strong' or (isinstance(strength, (int, float)) and strength >= 0.7)
            if breakout.get('volume_confirmed') or is_strong:
                stats['box_breakout_up'] += 1

        # 박스권 하단 지지 매수
        box = r.get('box_range', {})
        if box.get('signal') == 'box_buy':
            stats['box_buy'] += 1

        # 52주 신고가 돌파
        new_high = r.get('new_high_trend', {})
        new_high_strength = new_high.get('strength', '')
        is_new_high_strong = new_high_strength == 'strong' or (isinstance(new_high_strength, (int, float)) and new_high_strength >= 0.7)
        # is_52w_high 필드 사용 (indicators.py 반환값과 일치)
        if new_high.get('is_52w_high') and is_new_high_strong:
            stats['new_high'] += 1
        elif new_high.get('high_52w_pct', 0) >= 95:
            stats['new_high_approach'] += 1

    stats['total'] = (stats['box_breakout_up'] + stats['box_buy'] +
                      stats['new_high'] + stats['new_high_approach'])
    return stats


def _calculate_divergence_stats(results: list) -> dict:
    """다이버전스 통계 계산"""
    stats = {
        'bullish': 0,  # 상승 다이버전스 (매수 신호)
        'bearish': 0,  # 하락 다이버전스 (매도 신호)
        'rsi': 0,      # RSI 다이버전스 종목 수
        'macd': 0,     # MACD 다이버전스 종목 수
        'total': 0
    }

    for r in results:
        divergence = r.get('divergence', {})
        if not divergence:
            continue

        rsi_div = divergence.get('rsi_divergence') or {}
        macd_div = divergence.get('macd_divergence') or {}

        # RSI 다이버전스 체크
        if rsi_div.get('detected'):
            stats['rsi'] += 1
            if rsi_div.get('type') == 'bullish':
                stats['bullish'] += 1
            elif rsi_div.get('type') == 'bearish':
                stats['bearish'] += 1

        # MACD 다이버전스 체크 (RSI와 중복 카운트 가능)
        if macd_div.get('detected'):
            stats['macd'] += 1
            # RSI에서 이미 bullish/bearish 카운트한 경우 제외
            if not rsi_div.get('detected'):
                if macd_div.get('type') == 'bullish':
                    stats['bullish'] += 1
                elif macd_div.get('type') == 'bearish':
                    stats['bearish'] += 1

    stats['total'] = stats['bullish'] + stats['bearish']
    return stats


def _display_divergence_results(results: list):
    """다이버전스 결과 표시"""

    # 종목 분류
    bullish_stocks = []   # 상승 다이버전스 (매수 신호)
    bearish_stocks = []   # 하락 다이버전스 (매도 신호)
    strong_buy_stocks = []  # RSI + MACD 동시 상승 다이버전스
    strong_sell_stocks = []  # RSI + MACD 동시 하락 다이버전스

    for r in results:
        divergence = r.get('divergence', {})
        if not divergence:
            continue

        signal = divergence.get('signal', '')
        rsi_div = divergence.get('rsi_divergence', {})
        macd_div = divergence.get('macd_divergence', {})

        # 강력 신호 (RSI + MACD 동시)
        if signal == 'strong_buy':
            strong_buy_stocks.append(r)
        elif signal == 'strong_sell':
            strong_sell_stocks.append(r)
        elif signal == 'buy':
            bullish_stocks.append(r)
        elif signal == 'sell':
            bearish_stocks.append(r)

    # 서브탭으로 표시
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        f"🔥 강력 매수 ({len(strong_buy_stocks)})",
        f"🟢 상승 다이버전스 ({len(bullish_stocks)})",
        f"⚠️ 강력 매도 ({len(strong_sell_stocks)})",
        f"🔴 하락 다이버전스 ({len(bearish_stocks)})"
    ])

    with sub_tab1:
        if strong_buy_stocks:
            st.markdown("##### 🔥 RSI + MACD 동시 상승 다이버전스")
            st.caption("가격은 저점 갱신, RSI/MACD 모두 저점 상승 → 강력 반등 신호")
            for r in strong_buy_stocks:
                _display_divergence_stock_card(r)
        else:
            st.info("강력 매수 다이버전스 종목이 없습니다.")

    with sub_tab2:
        if bullish_stocks:
            st.markdown("##### 🟢 상승 다이버전스 (매수 신호)")
            st.caption("가격은 저점 갱신, RSI 또는 MACD 저점 상승 → 반등 기대")
            for r in bullish_stocks:
                _display_divergence_stock_card(r)
        else:
            st.info("상승 다이버전스 종목이 없습니다.")

    with sub_tab3:
        if strong_sell_stocks:
            st.markdown("##### ⚠️ RSI + MACD 동시 하락 다이버전스")
            st.caption("가격은 고점 갱신, RSI/MACD 모두 고점 하락 → 강력 조정 신호")
            for r in strong_sell_stocks:
                _display_divergence_stock_card(r)
        else:
            st.info("강력 매도 다이버전스 종목이 없습니다.")

    with sub_tab4:
        if bearish_stocks:
            st.markdown("##### 🔴 하락 다이버전스 (매도 신호)")
            st.caption("가격은 고점 갱신, RSI 또는 MACD 고점 하락 → 조정 기대")
            for r in bearish_stocks:
                _display_divergence_stock_card(r)
        else:
            st.info("하락 다이버전스 종목이 없습니다.")


def _display_divergence_stock_card(r: dict):
    """다이버전스 종목 카드 표시"""
    divergence = r.get('divergence', {})
    rsi_div = divergence.get('rsi_divergence', {})
    macd_div = divergence.get('macd_divergence', {})
    code = r.get('code', '')
    sector = get_sector_info_cached(code)  # 업종 정보

    with st.container():
        col1, col2, col3 = st.columns([2.5, 3, 2])

        with col1:
            sector_tag = f" `{sector}`" if sector and sector != '기타' else ""
            st.markdown(f"**{r.get('name')}** ({code}){sector_tag}")
            price = r.get('current_price', 0)
            change = r.get('change_rate', 0)
            color = "🔴" if change < 0 else "🟢" if change > 0 else "⚪"
            st.markdown(f"{color} {price:,.0f}원 ({change:+.2f}%)")

        with col2:
            # RSI 다이버전스 정보
            if rsi_div.get('detected'):
                div_type = "상승" if rsi_div.get('type') == 'bullish' else "하락"
                strength = rsi_div.get('strength', 'moderate')
                strength_text = "강함" if strength == 'strong' else "보통"
                st.markdown(f"**RSI {div_type} 다이버전스** ({strength_text})")
                if rsi_div.get('signal'):
                    st.caption(rsi_div.get('signal'))

            # MACD 다이버전스 정보
            if macd_div.get('detected'):
                div_type = "상승" if macd_div.get('type') == 'bullish' else "하락"
                strength = macd_div.get('strength', 'moderate')
                strength_text = "강함" if strength == 'strong' else "보통"
                st.markdown(f"**MACD {div_type} 다이버전스** ({strength_text})")
                if macd_div.get('signal'):
                    st.caption(macd_div.get('signal'))

        with col3:
            signal = divergence.get('signal', '')
            if signal == 'strong_buy':
                st.success("🔥 강력 매수")
            elif signal == 'buy':
                st.info("🟢 매수 신호")
            elif signal == 'strong_sell':
                st.error("⚠️ 강력 매도")
            elif signal == 'sell':
                st.warning("🔴 매도 신호")

        st.divider()


def _display_tasso_strategy_results(results: list):
    """태쏘 전략 결과 표시"""

    # 전략별로 분류
    box_breakout_stocks = []
    box_buy_stocks = []
    new_high_stocks = []
    new_high_approach_stocks = []

    for r in results:
        # 박스권 상향 돌파
        breakout = r.get('box_breakout', {})
        if breakout.get('direction') == 'up':
            strength = breakout.get('strength', '')
            is_strong = strength == 'strong' or (isinstance(strength, (int, float)) and strength >= 0.7)
            if breakout.get('volume_confirmed') or is_strong:
                box_breakout_stocks.append(r)

        # 박스권 하단 지지 매수
        box = r.get('box_range', {})
        if box.get('signal') == 'box_buy':
            box_buy_stocks.append(r)

        # 52주 신고가 관련
        new_high = r.get('new_high_trend', {})
        new_high_strength = new_high.get('strength', '')
        is_new_high_strong = new_high_strength == 'strong' or (isinstance(new_high_strength, (int, float)) and new_high_strength >= 0.7)
        # is_52w_high 필드 사용 (indicators.py 반환값과 일치)
        if new_high.get('is_52w_high') and is_new_high_strong:
            new_high_stocks.append(r)
        elif new_high.get('high_52w_pct', 0) >= 95:
            new_high_approach_stocks.append(r)

    # 서브탭으로 표시
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        f"🚀 박스 상향돌파 ({len(box_breakout_stocks)})",
        f"📦 박스 하단지지 ({len(box_buy_stocks)})",
        f"⭐ 52주 신고가 ({len(new_high_stocks)})",
        f"📈 신고가 근접 ({len(new_high_approach_stocks)})"
    ])

    with sub_tab1:
        if box_breakout_stocks:
            st.markdown("##### 🚀 박스권 상향 돌파 종목")
            st.caption("20일 박스권 상단 돌파 + 거래량 확인")
            # strength가 문자열인 경우 정렬 처리
            def sort_key_breakout(x):
                s = x.get('box_breakout', {}).get('strength', '')
                if s == 'strong': return 2
                elif s == 'weak': return 1
                elif isinstance(s, (int, float)): return s
                return 0
            for r in sorted(box_breakout_stocks, key=sort_key_breakout, reverse=True):
                _display_tasso_stock_card(r, 'box_breakout')
        else:
            st.info("박스권 상향 돌파 종목이 없습니다.")

    with sub_tab2:
        if box_buy_stocks:
            st.markdown("##### 📦 박스권 하단 지지 매수 종목")
            st.caption("박스권 하단 근처에서 반등 가능성 높은 종목")
            for r in box_buy_stocks:
                _display_tasso_stock_card(r, 'box_buy')
        else:
            st.info("박스권 하단 지지 종목이 없습니다.")

    with sub_tab3:
        if new_high_stocks:
            st.markdown("##### ⭐ 52주 신고가 돌파 종목")
            st.caption("52주 신고가 + 거래량 급증 + 정배열 확인")
            # strength가 문자열인 경우 정렬 처리
            def sort_key_new_high(x):
                s = x.get('new_high_trend', {}).get('strength', '')
                if s == 'strong': return 3
                elif s == 'moderate': return 2
                elif s == 'weak': return 1
                elif isinstance(s, (int, float)): return s
                return 0
            for r in sorted(new_high_stocks, key=sort_key_new_high, reverse=True):
                _display_tasso_stock_card(r, 'new_high')
        else:
            st.info("52주 신고가 돌파 종목이 없습니다.")

    with sub_tab4:
        if new_high_approach_stocks:
            st.markdown("##### 📈 신고가 근접 종목 (95% 이상)")
            st.caption("52주 고가의 95% 이상 근접 - 돌파 가능성 주시")
            for r in sorted(new_high_approach_stocks,
                           key=lambda x: x.get('new_high_trend', {}).get('high_52w_pct', 0), reverse=True):
                _display_tasso_stock_card(r, 'new_high_approach')
        else:
            st.info("신고가 근접 종목이 없습니다.")


def _display_tasso_stock_card(result: dict, strategy_type: str):
    """태쏘 전략 종목 카드 표시 (차트 + 진입가/손절가/목표가 포함)"""
    code = result.get('code', '')
    name = result.get('name', '')
    price = result.get('current_price', 0)
    change_rate = result.get('change_rate', 0)
    market = result.get('market', '')
    sector = get_sector_info_cached(code)  # 업종 정보

    # 박스권 정보에서 진입가/손절가/목표가 계산
    box = result.get('box_range', {})
    breakout = result.get('box_breakout', {})
    new_high = result.get('new_high_trend', {})

    # 전략별 가격 계산
    if strategy_type == 'box_breakout':
        entry_price = breakout.get('breakout_price', box.get('upper', price))
        stop_loss = box.get('lower', entry_price * 0.95)
        target_price = entry_price * 1.10  # 10% 상승 목표
    elif strategy_type == 'box_buy':
        entry_price = box.get('lower', price) * 1.01  # 하단 +1%
        stop_loss = box.get('lower', price) * 0.97  # 하단 -3%
        target_price = box.get('upper', price)  # 상단이 목표
    elif strategy_type in ['new_high', 'new_high_approach']:
        entry_price = price
        high_52w = new_high.get('high_52w', price)
        stop_loss = price * 0.95  # -5%
        target_price = high_52w * 1.10  # 52주 고가 +10%
    else:
        entry_price = price
        stop_loss = price * 0.95
        target_price = price * 1.10

    # 전략별 아이콘
    strategy_icons = {
        'box_breakout': '🚀',
        'box_buy': '📦',
        'new_high': '⭐',
        'new_high_approach': '📈'
    }
    icon = strategy_icons.get(strategy_type, '📊')

    # 업종 태그 생성
    sector_display = f" [{sector}]" if sector and sector != '기타' else ""
    with st.expander(f"{icon} **{name}** ({code}){sector_display} | {price:,.0f}원 | {'🔴' if change_rate > 0 else '🔵'}{change_rate:+.2f}%", expanded=False):
        # 상단 정보 영역
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("##### 📊 기본 정보")
            st.markdown(f"**시장**: {market}")
            if sector and sector != '기타':
                st.markdown(f"**업종**: {sector}")
            st.markdown(f"**현재가**: {price:,.0f}원")

        with col2:
            st.markdown("##### 💰 매매 가격")
            st.markdown(f"🟢 **진입가**: {entry_price:,.0f}원")
            st.markdown(f"🔴 **손절가**: {stop_loss:,.0f}원")
            st.markdown(f"🎯 **목표가**: {target_price:,.0f}원")

        with col3:
            st.markdown("##### 📈 수익률 시뮬레이션")
            if entry_price > 0:
                potential_profit = ((target_price - entry_price) / entry_price) * 100
                potential_loss = ((stop_loss - entry_price) / entry_price) * 100
                risk_reward = abs(potential_profit / potential_loss) if potential_loss != 0 else 0
                st.markdown(f"📈 목표 수익률: **+{potential_profit:.1f}%**")
                st.markdown(f"📉 최대 손실률: **{potential_loss:.1f}%**")
                st.markdown(f"⚖️ 손익비: **{risk_reward:.1f}:1**")

        st.markdown("---")

        # 전략별 상세 정보
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 🎯 전략 상세")
            if strategy_type == 'box_breakout':
                strength_raw = breakout.get('strength', '')
                strength_display = "강함" if strength_raw == 'strong' else "약함"
                vol_ratio = breakout.get('volume_ratio', 1)
                vol_confirmed = "✅" if breakout.get('volume_confirmed') else "⚠️"
                st.markdown(f"**돌파 강도**: {strength_display}")
                st.markdown(f"**거래량 배수**: {vol_ratio:.1f}배 {vol_confirmed}")
                st.markdown(f"**돌파가**: {breakout.get('breakout_price', 0):,.0f}원")

            elif strategy_type == 'box_buy':
                position_pct = box.get('position_pct', 50)
                range_pct = box.get('range_pct', 0)
                st.markdown(f"**박스내 위치**: {position_pct:.0f}%")
                st.markdown(f"**박스 폭**: {range_pct:.1f}%")
                st.markdown(f"**박스 기간**: 20일")

            elif strategy_type == 'new_high':
                strength_raw = new_high.get('strength', '')
                strength_map = {'strong': '강함', 'moderate': '보통', 'weak': '약함'}
                strength_display = strength_map.get(strength_raw, strength_raw)
                vol_surge = "✅" if new_high.get('volume_surge') else "⚠️"
                ma_aligned = "✅" if new_high.get('is_bullish') else "⚠️"
                st.markdown(f"**추세 강도**: {strength_display}")
                st.markdown(f"**거래량 급증**: {vol_surge}")
                st.markdown(f"**정배열**: {ma_aligned}")

            elif strategy_type == 'new_high_approach':
                pct = new_high.get('high_52w_pct', 0)
                high_52w = new_high.get('high_52w', 0)
                st.markdown(f"**52주 고가 대비**: {pct:.1f}%")
                st.markdown(f"**52주 고가**: {high_52w:,.0f}원")

        with col2:
            st.markdown("##### 📦 박스권 정보")
            if box:
                upper = box.get('upper', 0)
                lower = box.get('lower', 0)
                mid = box.get('mid', 0)
                st.markdown(f"**상단**: {upper:,.0f}원")
                st.markdown(f"**중심**: {mid:,.0f}원")
                st.markdown(f"**하단**: {lower:,.0f}원")

        st.markdown("---")

        # 차트 표시
        _display_tasso_chart(code, name, box, breakout, new_high, entry_price, stop_loss, target_price)


def _display_tasso_chart(code: str, name: str, box: dict, breakout: dict, new_high: dict,
                         entry_price: float, stop_loss: float, target_price: float):
    """태쏘 전략 차트 표시 (박스권 + 진입/손절/목표가 라인)"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        api = get_api_connection()
        if not api:
            st.warning("API 연결이 필요합니다.")
            return

        # 일봉 데이터 조회
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty:
            st.warning("차트 데이터를 불러올 수 없습니다.")
            return

        # 최근 60일 데이터
        df = df.tail(120).copy()

        # 날짜 인덱스 처리
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            x_data = df['date']
        else:
            x_data = list(range(len(df)))

        # 서브플롯 생성 (캔들차트 + 거래량)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(f'{name} ({code}) - 태쏘 전략 분석', '거래량'),
            row_heights=[0.7, 0.3]
        )

        # 캔들스틱 차트
        fig.add_trace(
            go.Candlestick(
                x=x_data,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='가격',
                increasing_line_color='#FF3B30',
                decreasing_line_color='#007AFF',
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#007AFF',
                line=dict(width=1),
                whiskerwidth=0.8
            ),
            row=1, col=1
        )

        # 이동평균선
        if len(df) >= 20:
            ma20 = df['close'].rolling(20).mean()
            fig.add_trace(
                go.Scatter(x=x_data, y=ma20, name='MA20', line=dict(color='orange', width=1)),
                row=1, col=1
            )

        if len(df) >= 5:
            ma5 = df['close'].rolling(5).mean()
            fig.add_trace(
                go.Scatter(x=x_data, y=ma5, name='MA5', line=dict(color='purple', width=1)),
                row=1, col=1
            )

        # 스윙 포인트 (저점/고점 마커)
        if len(df) >= 10:
            swing_order = 3 if len(df) < 100 else 5
            swing_high_idx, swing_low_idx = detect_swing_points(df, order=swing_order)

            price_range = df['high'].max() - df['low'].min()
            marker_offset = price_range * 0.02

            # 저점 마커
            if len(swing_low_idx) > 0:
                recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                low_x = [x_data[i] for i in recent_low_idx] if isinstance(x_data, list) else x_data.iloc[recent_low_idx]
                low_prices = df['low'].iloc[recent_low_idx]

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
                ), row=1, col=1)

            # 고점 마커
            if len(swing_high_idx) > 0:
                recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
                high_x = [x_data[i] for i in recent_high_idx] if isinstance(x_data, list) else x_data.iloc[recent_high_idx]
                high_prices = df['high'].iloc[recent_high_idx]

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
                ), row=1, col=1)

            # ========== 추세선 추가 (저점/고점 연결) ==========
            from scipy import stats

            # 가격 범위 계산 (Y축 클리핑용)
            price_high = df['high'].max()
            price_low = df['low'].min()
            price_margin = (price_high - price_low) * 0.1  # 10% 여유

            # 상승 추세선 (저점 연결)
            if len(swing_low_idx) >= 2:
                recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                tl_low_x = list(recent_lows)
                tl_low_y = [df['low'].iloc[i] for i in recent_lows]
                slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

                if slope > 0:  # 상승 추세일 때만 표시
                    tl_x_start = min(recent_lows)
                    tl_x_end = len(df) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    tl_date_start = x_data[tl_x_start] if isinstance(x_data, list) else x_data.iloc[tl_x_start]
                    tl_date_end = x_data[tl_x_end] if isinstance(x_data, list) else x_data.iloc[tl_x_end]

                    fig.add_trace(go.Scatter(
                        x=[tl_date_start, tl_date_end],
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
                tl_high_y = [df['high'].iloc[i] for i in recent_highs]
                slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

                if slope < 0:  # 하락 추세일 때만 표시
                    tl_x_start = min(recent_highs)
                    tl_x_end = len(df) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    tl_date_start = x_data[tl_x_start] if isinstance(x_data, list) else x_data.iloc[tl_x_start]
                    tl_date_end = x_data[tl_x_end] if isinstance(x_data, list) else x_data.iloc[tl_x_end]

                    fig.add_trace(go.Scatter(
                        x=[tl_date_start, tl_date_end],
                        y=[tl_y_start, tl_y_end],
                        mode='lines',
                        name='하락 추세선',
                        line=dict(color='#FF3B30', width=2, dash='solid'),
                        hovertemplate='하락 추세선<extra></extra>',
                        showlegend=True
                    ), row=1, col=1)

        # 박스권 표시
        if box:
            upper = box.get('upper', 0)
            lower = box.get('lower', 0)
            mid = box.get('mid', 0)

            if upper > 0:
                fig.add_hline(y=upper, line_dash="solid", line_color="rgba(255,0,0,0.5)",
                             annotation_text=f"박스 상단: {upper:,.0f}", row=1, col=1)
            if lower > 0:
                fig.add_hline(y=lower, line_dash="solid", line_color="rgba(0,0,255,0.5)",
                             annotation_text=f"박스 하단: {lower:,.0f}", row=1, col=1)
            if mid > 0:
                fig.add_hline(y=mid, line_dash="dot", line_color="rgba(128,128,128,0.5)",
                             annotation_text=f"중심: {mid:,.0f}", row=1, col=1)

        # 진입가/손절가/목표가 라인
        if entry_price > 0:
            fig.add_hline(y=entry_price, line_dash="dash", line_color="green", line_width=2,
                         annotation_text=f"🟢 진입가: {entry_price:,.0f}", row=1, col=1)
        if stop_loss > 0:
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", line_width=2,
                         annotation_text=f"🔴 손절가: {stop_loss:,.0f}", row=1, col=1)
        if target_price > 0:
            fig.add_hline(y=target_price, line_dash="dash", line_color="gold", line_width=2,
                         annotation_text=f"🎯 목표가: {target_price:,.0f}", row=1, col=1)

        # 거래량 바 차트
        colors = ['#FF4444' if df['close'].iloc[i] >= df['open'].iloc[i] else '#4444FF'
                  for i in range(len(df))]
        fig.add_trace(
            go.Bar(x=x_data, y=df['volume'], name='거래량', marker_color=colors),
            row=2, col=1
        )

        # 레이아웃 설정
        fig.update_layout(
            height=500,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=50, t=50, b=30)
        )

        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')

        st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        st.warning("Plotly가 설치되어 있지 않습니다. `pip install plotly`를 실행해주세요.")
    except Exception as e:
        st.error(f"차트 로드 오류: {e}")


def _display_swing_pattern_results_v2(results: list):
    """스윙매매 패턴 결과 표시 (개별 조건 선택 가능, 성능 개선)"""

    # 패턴별로 분류 (한 번만 수행)
    double_bottom_stocks = []
    inv_hs_stocks = []
    pullback_stocks = []
    accumulation_stocks = []
    support_stocks = []
    oversold_stocks = []

    for r in results:
        swing = r.get('swing_patterns', {})
        if not swing:
            continue

        for pattern in swing.get('patterns', []):
            if pattern.get('detected'):
                if pattern.get('pattern') == 'double_bottom':
                    double_bottom_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'inverse_head_shoulders':
                    inv_hs_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'pullback':
                    pullback_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'accumulation':
                    accumulation_stocks.append((r, pattern))

        vp = swing.get('volume_profile', {})
        if vp.get('near_support'):
            support_stocks.append((r, vp))

        disp = swing.get('disparity', {})
        if disp.get('overall_signal') == 'oversold':
            oversold_stocks.append((r, disp))

    # 패턴별 개수 계산
    pattern_counts = {
        'double_bottom': len(double_bottom_stocks),
        'inv_hs': len(inv_hs_stocks),
        'pullback': len(pullback_stocks),
        'accumulation': len(accumulation_stocks),
        'support': len(support_stocks),
        'oversold': len(oversold_stocks)
    }

    total_count = sum(pattern_counts.values())

    if total_count == 0:
        st.info("스윙매매 패턴 시그널 종목이 없습니다.")
        return

    # 조건 선택 UI
    st.markdown("#### 🎯 스윙 패턴 조건 선택")

    # 패턴 옵션
    pattern_options = {
        '📐 쌍바닥(W패턴)': ('double_bottom', pattern_counts['double_bottom']),
        '📐 역헤드앤숄더': ('inv_hs', pattern_counts['inv_hs']),
        '📈 눌림목 매수': ('pullback', pattern_counts['pullback']),
        '🔍 세력 매집': ('accumulation', pattern_counts['accumulation']),
        '💪 지지 매물대': ('support', pattern_counts['support']),
        '📉 이격도 과매도': ('oversold', pattern_counts['oversold'])
    }

    # 선택 박스 생성
    col1, col2 = st.columns([3, 1])

    with col1:
        # 조건이 있는 것만 표시
        available_options = [f"{name} ({count}개)" for name, (key, count) in pattern_options.items() if count > 0]
        option_map = {f"{name} ({count}개)": key for name, (key, count) in pattern_options.items() if count > 0}

        if available_options:
            selected_option = st.selectbox(
                "패턴 유형 선택",
                ["전체 보기"] + available_options,
                key="swing_pattern_selector",
                label_visibility="collapsed"
            )
        else:
            selected_option = "전체 보기"

    with col2:
        max_display = st.number_input("표시 개수", min_value=5, max_value=50, value=20, step=5, key="swing_max_display")

    st.markdown("---")

    # 선택된 패턴만 표시 (성능 개선)
    if selected_option == "전체 보기":
        # 전체 표시 (각 패턴별 최대 10개)
        if double_bottom_stocks:
            st.markdown("##### 📐 쌍바닥(W패턴) 종목")
            st.caption("두 번의 저점을 형성 후 반등하는 패턴")
            for r, pattern in double_bottom_stocks[:10]:
                _display_swing_stock_card(r, pattern, 'double_bottom')

        if inv_hs_stocks:
            st.markdown("##### 📐 역헤드앤숄더 종목")
            st.caption("머리-어깨 패턴의 반전형")
            for r, pattern in inv_hs_stocks[:10]:
                _display_swing_stock_card(r, pattern, 'inv_hs')

        if pullback_stocks:
            st.markdown("##### 📈 눌림목 매수 타이밍")
            st.caption("상승 추세 중 이동평균선 지지 확인")
            for r, pattern in pullback_stocks[:10]:
                _display_swing_stock_card(r, pattern, 'pullback')

        if accumulation_stocks:
            st.markdown("##### 🔍 세력 매집 패턴")
            st.caption("거래량 증가 + 가격 횡보 (매집 구간)")
            for r, pattern in accumulation_stocks[:10]:
                _display_swing_stock_card(r, pattern, 'accumulation')

        if support_stocks:
            st.markdown("##### 💪 지지 매물대 근접")
            st.caption("주요 거래량 밀집 구간 지지 근접")
            for r, vp in support_stocks[:10]:
                _display_volume_profile_card(r, vp)

        if oversold_stocks:
            st.markdown("##### 📉 이격도 과매도")
            st.caption("이동평균 대비 과도한 하락")
            for r, disp in oversold_stocks[:10]:
                _display_disparity_card(r, disp)
    else:
        # 선택된 패턴만 표시
        selected_key = option_map.get(selected_option, '')

        if selected_key == 'double_bottom':
            st.markdown("##### 📐 쌍바닥(W패턴) 종목")
            st.caption("두 번의 저점을 형성 후 반등하는 패턴")
            for r, pattern in double_bottom_stocks[:max_display]:
                _display_swing_stock_card(r, pattern, 'double_bottom')

        elif selected_key == 'inv_hs':
            st.markdown("##### 📐 역헤드앤숄더 종목")
            st.caption("머리-어깨 패턴의 반전형")
            for r, pattern in inv_hs_stocks[:max_display]:
                _display_swing_stock_card(r, pattern, 'inv_hs')

        elif selected_key == 'pullback':
            st.markdown("##### 📈 눌림목 매수 타이밍")
            st.caption("상승 추세 중 이동평균선 지지 확인")
            for r, pattern in pullback_stocks[:max_display]:
                _display_swing_stock_card(r, pattern, 'pullback')

        elif selected_key == 'accumulation':
            st.markdown("##### 🔍 세력 매집 패턴")
            st.caption("거래량 증가 + 가격 횡보 (매집 구간)")
            for r, pattern in accumulation_stocks[:max_display]:
                _display_swing_stock_card(r, pattern, 'accumulation')

        elif selected_key == 'support':
            st.markdown("##### 💪 지지 매물대 근접")
            st.caption("주요 거래량 밀집 구간 지지 근접")
            for r, vp in support_stocks[:max_display]:
                _display_volume_profile_card(r, vp)

        elif selected_key == 'oversold':
            st.markdown("##### 📉 이격도 과매도")
            st.caption("이동평균 대비 과도한 하락")
            for r, disp in oversold_stocks[:max_display]:
                _display_disparity_card(r, disp)


def _display_swing_pattern_results(results: list):
    """스윙매매 패턴 결과 표시 (레거시 - 하위 호환용)"""

    # 패턴별로 분류
    double_bottom_stocks = []
    inv_hs_stocks = []
    pullback_stocks = []
    accumulation_stocks = []
    support_stocks = []
    oversold_stocks = []

    for r in results:
        swing = r.get('swing_patterns', {})
        if not swing:
            continue

        for pattern in swing.get('patterns', []):
            if pattern.get('detected'):
                if pattern.get('pattern') == 'double_bottom':
                    double_bottom_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'inverse_head_shoulders':
                    inv_hs_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'pullback':
                    pullback_stocks.append((r, pattern))
                elif pattern.get('pattern') == 'accumulation':
                    accumulation_stocks.append((r, pattern))

        vp = swing.get('volume_profile', {})
        if vp.get('near_support'):
            support_stocks.append((r, vp))

        disp = swing.get('disparity', {})
        if disp.get('overall_signal') == 'oversold':
            oversold_stocks.append((r, disp))

    # 결과 표시
    if double_bottom_stocks:
        st.markdown("##### 📐 쌍바닥(W패턴) 종목")
        st.caption("두 번의 저점을 형성 후 반등하는 패턴")
        for r, pattern in double_bottom_stocks:
            _display_swing_stock_card(r, pattern, 'double_bottom')

    if inv_hs_stocks:
        st.markdown("##### 📐 역헤드앤숄더 종목")
        st.caption("머리-어깨 패턴의 반전형")
        for r, pattern in inv_hs_stocks:
            _display_swing_stock_card(r, pattern, 'inv_hs')

    if pullback_stocks:
        st.markdown("##### 📈 눌림목 매수 타이밍")
        st.caption("상승 추세 중 이동평균선 지지 확인")
        for r, pattern in pullback_stocks:
            _display_swing_stock_card(r, pattern, 'pullback')

    if accumulation_stocks:
        st.markdown("##### 🔍 세력 매집 패턴")
        st.caption("거래량 증가 + 가격 횡보 (매집 구간)")
        for r, pattern in accumulation_stocks:
            _display_swing_stock_card(r, pattern, 'accumulation')

    if support_stocks:
        st.markdown("##### 💪 지지 매물대 근접")
        st.caption("주요 거래량 밀집 구간 지지 근접")
        for r, vp in support_stocks:
            _display_volume_profile_card(r, vp)

    if oversold_stocks:
        st.markdown("##### 📉 이격도 과매도")
        st.caption("이동평균 대비 과도한 하락")
        for r, disp in oversold_stocks:
            _display_disparity_card(r, disp)

    if not any([double_bottom_stocks, inv_hs_stocks, pullback_stocks,
                accumulation_stocks, support_stocks, oversold_stocks]):
        st.info("스윙매매 패턴 시그널 종목이 없습니다.")


def _display_swing_stock_card(result: dict, pattern: dict, pattern_type: str):
    """스윙매매 패턴 종목 카드 표시 (차트 + 진입가/손절가/목표가 포함)"""
    code = result.get('code', '')
    name = result.get('name', '')
    price = result.get('current_price', 0)
    change = result.get('change_rate', 0)
    market = result.get('market', '')
    sector = get_sector_info_cached(code)  # 업종 정보

    # 패턴별 아이콘 및 정보
    pattern_info = {
        'double_bottom': {'icon': '📐', 'color': '#11998e', 'name': '쌍바닥'},
        'inv_hs': {'icon': '📐', 'color': '#38ef7d', 'name': '역헤숄'},
        'pullback': {'icon': '📈', 'color': '#667eea', 'name': '눌림목'},
        'accumulation': {'icon': '🔍', 'color': '#fc4a1a', 'name': '매집'}
    }
    info = pattern_info.get(pattern_type, {'icon': '📊', 'color': '#666', 'name': '패턴'})

    # 패턴별 진입가/손절가/목표가 계산
    if pattern_type == 'double_bottom':
        neckline = pattern.get('neckline', price)
        bottom = pattern.get('bottom', price * 0.95)
        entry_price = neckline  # 넥라인 돌파시 진입
        stop_loss = bottom * 0.97  # 저점 -3%
        target_price = neckline + (neckline - bottom)  # 넥라인 + (넥라인-저점)
    elif pattern_type == 'inv_hs':
        neckline = pattern.get('neckline', price)
        head_low = pattern.get('head_low', price * 0.90)
        entry_price = neckline
        stop_loss = head_low * 0.97
        target_price = neckline + (neckline - head_low)
    elif pattern_type == 'pullback':
        ma_support = pattern.get('ma_support', price * 0.97)
        entry_price = price
        stop_loss = ma_support * 0.97  # 이평선 지지 -3%
        target_price = price * 1.10  # 10% 상승 목표
    elif pattern_type == 'accumulation':
        entry_price = price
        stop_loss = price * 0.95  # -5%
        target_price = price * 1.15  # 15% 상승 목표 (매집 후 급등 기대)
    else:
        entry_price = price
        stop_loss = price * 0.95
        target_price = price * 1.10

    # 강도 정보
    strength = pattern.get('strength', 'moderate')
    strength_display = "강함" if strength == 'strong' else ("보통" if strength == 'moderate' else "약함")
    signal = pattern.get('signal', 'watch')

    # 업종 태그 생성
    sector_display = f" [{sector}]" if sector and sector != '기타' else ""
    with st.expander(f"{info['icon']} **{name}** ({code}){sector_display} | {price:,.0f}원 | {'🔴' if change > 0 else '🔵'}{change:+.2f}%", expanded=False):
        # 상단 정보 영역
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("##### 📊 기본 정보")
            st.markdown(f"**시장**: {market}")
            st.markdown(f"**현재가**: {price:,.0f}원")
            st.markdown(f"**패턴**: {info['name']} ({strength_display})")

        with col2:
            st.markdown("##### 💰 매매 가격")
            st.markdown(f"🟢 **진입가**: {entry_price:,.0f}원")
            st.markdown(f"🔴 **손절가**: {stop_loss:,.0f}원")
            st.markdown(f"🎯 **목표가**: {target_price:,.0f}원")

        with col3:
            st.markdown("##### 📈 수익률 시뮬레이션")
            if entry_price > 0:
                potential_profit = ((target_price - entry_price) / entry_price) * 100
                potential_loss = ((stop_loss - entry_price) / entry_price) * 100
                risk_reward = abs(potential_profit / potential_loss) if potential_loss != 0 else 0
                st.markdown(f"📈 목표 수익률: **+{potential_profit:.1f}%**")
                st.markdown(f"📉 최대 손실률: **{potential_loss:.1f}%**")
                st.markdown(f"⚖️ 손익비: **{risk_reward:.1f}:1**")

        st.markdown("---")

        # 패턴 상세 정보
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 🎯 패턴 상세")
            message = pattern.get('message', '')
            if message:
                st.caption(message)

            if pattern_type == 'double_bottom':
                st.markdown(f"**넥라인**: {pattern.get('neckline', 0):,.0f}원")
                st.markdown(f"**저점**: {pattern.get('bottom', 0):,.0f}원")
            elif pattern_type == 'inv_hs':
                st.markdown(f"**넥라인**: {pattern.get('neckline', 0):,.0f}원")
                st.markdown(f"**헤드 저점**: {pattern.get('head_low', 0):,.0f}원")
            elif pattern_type == 'pullback':
                st.markdown(f"**MA 지지선**: {pattern.get('ma_support', 0):,.0f}원")
            elif pattern_type == 'accumulation':
                vol_ratio = pattern.get('volume_ratio', 1)
                st.markdown(f"**거래량 배수**: {vol_ratio:.1f}배")

        with col2:
            st.markdown("##### 📌 매매 신호")
            if signal == 'buy':
                st.markdown("🟢 **매수 신호**")
            elif signal == 'watch':
                st.markdown("🟡 **관망**")
            else:
                st.markdown(f"**{signal}**")

        st.markdown("---")

        # 차트 표시
        _display_swing_chart(code, name, pattern, pattern_type, entry_price, stop_loss, target_price)


def _display_swing_chart(code: str, name: str, pattern: dict, pattern_type: str,
                         entry_price: float, stop_loss: float, target_price: float):
    """스윙 패턴 차트 표시 (패턴 라인 + 진입/손절/목표가 라인)"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        api = get_api_connection()
        if not api:
            st.warning("API 연결이 필요합니다.")
            return

        # 일봉 데이터 조회
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty:
            st.warning("차트 데이터를 불러올 수 없습니다.")
            return

        # 최근 60일 데이터
        df = df.tail(120).copy()

        # 날짜 인덱스 처리
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            x_data = df['date']
        else:
            x_data = list(range(len(df)))

        # 서브플롯 생성 (캔들차트 + 거래량)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.03,
                           row_heights=[0.7, 0.3])

        # 캔들스틱 차트
        fig.add_trace(
            go.Candlestick(
                x=x_data,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='가격',
                increasing_line_color='#FF3B30',
                decreasing_line_color='#007AFF',
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#007AFF',
                line=dict(width=1),
                whiskerwidth=0.8
            ),
            row=1, col=1
        )

        # 이동평균선
        if len(df) >= 20:
            ma20 = df['close'].rolling(20).mean()
            fig.add_trace(
                go.Scatter(x=x_data, y=ma20, name='MA20', line=dict(color='orange', width=1)),
                row=1, col=1
            )

        if len(df) >= 5:
            ma5 = df['close'].rolling(5).mean()
            fig.add_trace(
                go.Scatter(x=x_data, y=ma5, name='MA5', line=dict(color='purple', width=1)),
                row=1, col=1
            )

        # 스윙 포인트 (저점/고점 마커)
        if len(df) >= 10:
            swing_order = 3 if len(df) < 100 else 5
            swing_high_idx, swing_low_idx = detect_swing_points(df, order=swing_order)

            price_range = df['high'].max() - df['low'].min()
            marker_offset = price_range * 0.02

            # 저점 마커
            if len(swing_low_idx) > 0:
                recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                low_x = [x_data[i] for i in recent_low_idx] if isinstance(x_data, list) else x_data.iloc[recent_low_idx]
                low_prices = df['low'].iloc[recent_low_idx]

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
                ), row=1, col=1)

            # 고점 마커
            if len(swing_high_idx) > 0:
                recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
                high_x = [x_data[i] for i in recent_high_idx] if isinstance(x_data, list) else x_data.iloc[recent_high_idx]
                high_prices = df['high'].iloc[recent_high_idx]

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
                ), row=1, col=1)

            # ========== 추세선 추가 (저점/고점 연결) ==========
            from scipy import stats

            # 가격 범위 계산 (Y축 클리핑용)
            price_high = df['high'].max()
            price_low = df['low'].min()
            price_margin = (price_high - price_low) * 0.1  # 10% 여유

            # 상승 추세선 (저점 연결)
            if len(swing_low_idx) >= 2:
                recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                tl_low_x = list(recent_lows)
                tl_low_y = [df['low'].iloc[i] for i in recent_lows]
                slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

                if slope > 0:
                    tl_x_start = min(recent_lows)
                    tl_x_end = len(df) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    tl_date_start = x_data[tl_x_start] if isinstance(x_data, list) else x_data.iloc[tl_x_start]
                    tl_date_end = x_data[tl_x_end] if isinstance(x_data, list) else x_data.iloc[tl_x_end]

                    fig.add_trace(go.Scatter(
                        x=[tl_date_start, tl_date_end],
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
                tl_high_y = [df['high'].iloc[i] for i in recent_highs]
                slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

                if slope < 0:
                    tl_x_start = min(recent_highs)
                    tl_x_end = len(df) - 1
                    tl_y_start = slope * tl_x_start + intercept
                    tl_y_end = slope * tl_x_end + intercept

                    # Y값 클리핑 (차트 범위 내로 제한)
                    tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                    tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                    tl_date_start = x_data[tl_x_start] if isinstance(x_data, list) else x_data.iloc[tl_x_start]
                    tl_date_end = x_data[tl_x_end] if isinstance(x_data, list) else x_data.iloc[tl_x_end]

                    fig.add_trace(go.Scatter(
                        x=[tl_date_start, tl_date_end],
                        y=[tl_y_start, tl_y_end],
                        mode='lines',
                        name='하락 추세선',
                        line=dict(color='#FF3B30', width=2, dash='solid'),
                        hovertemplate='하락 추세선<extra></extra>',
                        showlegend=True
                    ), row=1, col=1)

        # 패턴별 특수 라인
        if pattern_type == 'double_bottom':
            neckline = pattern.get('neckline', 0)
            bottom = pattern.get('bottom', 0)
            if neckline > 0:
                fig.add_hline(y=neckline, line_dash="dot", line_color="rgba(17,153,142,0.7)",
                             annotation_text=f"넥라인: {neckline:,.0f}", row=1, col=1)
            if bottom > 0:
                fig.add_hline(y=bottom, line_dash="dot", line_color="rgba(100,100,100,0.5)",
                             annotation_text=f"저점: {bottom:,.0f}", row=1, col=1)

        elif pattern_type == 'inv_hs':
            neckline = pattern.get('neckline', 0)
            if neckline > 0:
                fig.add_hline(y=neckline, line_dash="dot", line_color="rgba(56,239,125,0.7)",
                             annotation_text=f"넥라인: {neckline:,.0f}", row=1, col=1)

        elif pattern_type == 'pullback':
            ma_support = pattern.get('ma_support', 0)
            if ma_support > 0:
                fig.add_hline(y=ma_support, line_dash="dot", line_color="rgba(102,126,234,0.7)",
                             annotation_text=f"MA지지: {ma_support:,.0f}", row=1, col=1)

        elif pattern_type == 'volume_profile':
            support = pattern.get('support', 0)
            resistance = pattern.get('resistance', 0)
            if support > 0:
                fig.add_hline(y=support, line_dash="dot", line_color="rgba(34,139,34,0.7)",
                             annotation_text=f"지지선: {support:,.0f}", row=1, col=1)
            if resistance > 0:
                fig.add_hline(y=resistance, line_dash="dot", line_color="rgba(220,20,60,0.7)",
                             annotation_text=f"저항선: {resistance:,.0f}", row=1, col=1)

        elif pattern_type == 'disparity':
            # 이격도 차트에서는 추가 라인 없이 진입/손절/목표가만 표시
            pass

        # 진입가/손절가/목표가 라인
        if entry_price > 0:
            fig.add_hline(y=entry_price, line_dash="dash", line_color="green", line_width=2,
                         annotation_text=f"🟢 진입가: {entry_price:,.0f}", row=1, col=1)
        if stop_loss > 0:
            fig.add_hline(y=stop_loss, line_dash="dash", line_color="red", line_width=2,
                         annotation_text=f"🔴 손절가: {stop_loss:,.0f}", row=1, col=1)
        if target_price > 0:
            fig.add_hline(y=target_price, line_dash="dash", line_color="gold", line_width=2,
                         annotation_text=f"🎯 목표가: {target_price:,.0f}", row=1, col=1)

        # 거래량 바 차트
        colors = ['#FF4444' if df['close'].iloc[i] >= df['open'].iloc[i] else '#4444FF'
                  for i in range(len(df))]
        fig.add_trace(
            go.Bar(x=x_data, y=df['volume'], name='거래량', marker_color=colors),
            row=2, col=1
        )

        # 레이아웃 설정
        fig.update_layout(
            height=500,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=50, t=50, b=30)
        )

        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')

        st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        st.warning("Plotly가 설치되어 있지 않습니다. `pip install plotly`를 실행해주세요.")
    except Exception as e:
        st.error(f"차트 로드 오류: {e}")


def _display_volume_profile_card(result: dict, vp: dict):
    """매물대 분석 카드 표시 (차트 + 진입가/손절가/목표가 포함)"""
    code = result.get('code', '')
    name = result.get('name', '')
    price = result.get('current_price', 0)
    change = result.get('change_rate', 0)
    market = result.get('market', '')
    sector = get_sector_info_cached(code)  # 업종 정보

    support = vp.get('support_zone')
    resistance = vp.get('resistance_zone')

    # 진입가/손절가/목표가 계산 (지지선 기반)
    support_price = support[0] if support else price * 0.95
    resistance_price = resistance[0] if resistance else price * 1.10
    entry_price = support_price * 1.01  # 지지선 +1%
    stop_loss = support_price * 0.97  # 지지선 -3%
    target_price = resistance_price  # 저항선이 목표

    # 업종 태그 생성
    sector_display = f" [{sector}]" if sector and sector != '기타' else ""
    with st.expander(f"💪 **{name}** ({code}){sector_display} | {price:,.0f}원 | {'🔴' if change > 0 else '🔵'}{change:+.2f}%", expanded=False):
        # 상단 정보 영역
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("##### 📊 기본 정보")
            st.markdown(f"**시장**: {market}")
            if sector and sector != '기타':
                st.markdown(f"**업종**: {sector}")
            st.markdown(f"**현재가**: {price:,.0f}원")
            st.markdown(f"**분석**: 지지 매물대 근접")

        with col2:
            st.markdown("##### 💰 매매 가격")
            st.markdown(f"🟢 **진입가**: {entry_price:,.0f}원")
            st.markdown(f"🔴 **손절가**: {stop_loss:,.0f}원")
            st.markdown(f"🎯 **목표가**: {target_price:,.0f}원")

        with col3:
            st.markdown("##### 📈 수익률 시뮬레이션")
            if entry_price > 0:
                potential_profit = ((target_price - entry_price) / entry_price) * 100
                potential_loss = ((stop_loss - entry_price) / entry_price) * 100
                risk_reward = abs(potential_profit / potential_loss) if potential_loss != 0 else 0
                st.markdown(f"📈 목표 수익률: **+{potential_profit:.1f}%**")
                st.markdown(f"📉 최대 손실률: **{potential_loss:.1f}%**")
                st.markdown(f"⚖️ 손익비: **{risk_reward:.1f}:1**")

        st.markdown("---")

        # 매물대 상세 정보
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 📊 매물대 분석")
            if support:
                st.markdown(f"🟢 **지지선**: {support[0]:,.0f}원")
            if resistance:
                st.markdown(f"🔴 **저항선**: {resistance[0]:,.0f}원")

        with col2:
            st.markdown("##### 📌 매매 신호")
            st.markdown("🟢 **지지 매물대 근접**")
            st.caption("지지선 근처에서 반등 가능성")

        st.markdown("---")

        # 차트 표시
        _display_swing_chart(code, name, {'support': support_price, 'resistance': resistance_price},
                            'volume_profile', entry_price, stop_loss, target_price)


def _display_disparity_card(result: dict, disp: dict):
    """이격도 카드 표시 (차트 + 진입가/손절가/목표가 포함)"""
    code = result.get('code', '')
    name = result.get('name', '')
    price = result.get('current_price', 0)
    change = result.get('change_rate', 0)
    market = result.get('market', '')
    sector = get_sector_info_cached(code)  # 업종 정보

    disparities = disp.get('disparities', {})
    avg_disp = disp.get('avg_disparity', 100)

    # 과매도 종목 진입가/손절가/목표가 계산
    entry_price = price
    stop_loss = price * 0.95  # -5%
    # 이격도 기준으로 목표가 설정 (평균 100%로 회귀)
    if avg_disp < 100:
        target_pct = (100 - avg_disp) / 100  # 예: 이격도 90% -> 10% 상승 목표
        target_price = price * (1 + target_pct)
    else:
        target_price = price * 1.10

    # 업종 태그 생성
    sector_display = f" [{sector}]" if sector and sector != '기타' else ""
    with st.expander(f"📉 **{name}** ({code}){sector_display} | {price:,.0f}원 | {'🔴' if change > 0 else '🔵'}{change:+.2f}%", expanded=False):
        # 상단 정보 영역
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("##### 📊 기본 정보")
            st.markdown(f"**시장**: {market}")
            if sector and sector != '기타':
                st.markdown(f"**업종**: {sector}")
            st.markdown(f"**현재가**: {price:,.0f}원")
            st.markdown(f"**분석**: 과매도 상태")

        with col2:
            st.markdown("##### 💰 매매 가격")
            st.markdown(f"🟢 **진입가**: {entry_price:,.0f}원")
            st.markdown(f"🔴 **손절가**: {stop_loss:,.0f}원")
            st.markdown(f"🎯 **목표가**: {target_price:,.0f}원")

        with col3:
            st.markdown("##### 📈 수익률 시뮬레이션")
            if entry_price > 0:
                potential_profit = ((target_price - entry_price) / entry_price) * 100
                potential_loss = ((stop_loss - entry_price) / entry_price) * 100
                risk_reward = abs(potential_profit / potential_loss) if potential_loss != 0 else 0
                st.markdown(f"📈 목표 수익률: **+{potential_profit:.1f}%**")
                st.markdown(f"📉 최대 손실률: **{potential_loss:.1f}%**")
                st.markdown(f"⚖️ 손익비: **{risk_reward:.1f}:1**")

        st.markdown("---")

        # 이격도 상세 정보
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 📊 이격도 분석")
            for period, value in disparities.items():
                status = "🟢 과매도" if value < 95 else ("🔴 과매수" if value > 105 else "⚪ 정상")
                st.markdown(f"**{period}일**: {value:.1f}% {status}")
            st.markdown(f"**평균**: {avg_disp:.1f}%")

        with col2:
            st.markdown("##### 📌 매매 신호")
            st.markdown("🟢 **과매도 반등 기대**")
            st.caption("이격도 평균 100% 회귀 전략")

        st.markdown("---")

        # 차트 표시
        _display_swing_chart(code, name, {'avg_disparity': avg_disp}, 'disparity',
                            entry_price, stop_loss, target_price)
