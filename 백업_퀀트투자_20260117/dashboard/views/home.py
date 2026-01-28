"""
홈 대시보드 페이지 - 한국투자증권 API 연동 + 종목 상세 분석
KOSPI/KOSDAQ 전체 종목 + 보조지표 선택 + 분봉 차트
+ WebSocket 실시간 시세 지원
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys
import time

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# .env 파일 로드 (override=True로 기존 환경변수 덮어쓰기)
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

# 종목 리스트 import (KRX에서 동적으로 가져옴)
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name
from data.market_theme import MarketThemeService

# 이동평균선 옵션
MA_OPTIONS = {
    'MA5': (5, '#FF6B6B', '5일선'),
    'MA10': (10, '#4ECDC4', '10일선'),
    'MA20': (20, '#FFE66D', '20일선'),
    'MA60': (60, '#95E1D3', '60일선'),
    'MA120': (120, '#8B00FF', '120일선'),  # 보라색
    'MA200': (200, '#1A1A1A', '200일선'),  # 검정색
}

# 차트 타입 옵션
CHART_TYPE_OPTIONS = {
    '일봉': ('D', 0),    # (period_type, minute_value)
    '주봉': ('W', 0),
    '월봉': ('M', 0),
    '1분봉': ('D', 1),
    '5분봉': ('D', 5),
    '15분봉': ('D', 15),
    '30분봉': ('D', 30),
    '60분봉': ('D', 60),
}

# 기존 분봉 옵션 (하위 호환성)
MINUTE_OPTIONS = {
    '일봉': 0,
    '1분봉': 1,
    '5분봉': 5,
    '15분봉': 15,
    '30분봉': 30,
    '60분봉': 60,
}

# 보조지표 옵션
INDICATOR_OPTIONS = {
    'bollinger': '볼린저밴드',
    'macd': 'MACD',
    'rsi': 'RSI',
    'stochastic': '스토캐스틱',
}


def render_home():
    """홈 대시보드 렌더링"""

    # CSS
    st.markdown("""
    <style>
        .market-card {
            background: white;
            padding: 1.25rem;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }
        .stock-detail-card {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            padding: 1.5rem;
            border-radius: 16px;
            border: 1px solid #667eea30;
            margin: 1rem 0;
        }
        /* 종목 버튼 스타일 - KOSPI */
        div[data-testid="column"]:has(button[key^="btn_KOSPI"]) button {
            border: 2px solid #667eea !important;
            border-radius: 10px !important;
        }
        /* 종목 버튼 스타일 - KOSDAQ */
        div[data-testid="column"]:has(button[key^="btn_KOSDAQ"]) button {
            border: 2px solid #f5576c !important;
            border-radius: 10px !important;
        }
        /* 상승률 색상 - 더 선명하게 */
        [data-testid="stMetricDelta"] > div {
            font-weight: 700 !important;
            font-size: 1rem !important;
        }
        [data-testid="stMetricDelta"] svg {
            display: none !important;
        }
        [data-testid="stMetricDelta"][style*="color: rgb(9, 171, 59)"] > div,
        [data-testid="stMetricDelta"]:has(svg[color="#09AB3B"]) > div {
            color: #00FF88 !important;
            text-shadow: 0 0 10px rgba(0,255,136,0.5);
        }
        [data-testid="stMetricDelta"][style*="color: rgb(255, 43, 43)"] > div,
        [data-testid="stMetricDelta"]:has(svg[color="#FF2B2B"]) > div {
            color: #FF6B6B !important;
            text-shadow: 0 0 10px rgba(255,107,107,0.5);
        }
        /* 메트릭 값 색상 */
        [data-testid="stMetricValue"] {
            font-weight: 700 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 헤더
    st.markdown(f"""
    <div style='margin-bottom: 2rem;'>
        <h1 style='display: flex; align-items: center; gap: 0.75rem;'>
            <span style='font-size: 2rem;'>📊</span>
            <span style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>시장 현황 & 종목 분석</span>
        </h1>
        <p style='color: #888;'>{datetime.now().strftime("%Y년 %m월 %d일 %H:%M")} | 한국투자증권 API 연동</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = _get_api_connection()
    if api is None:
        st.warning("⚠️ API 연결 실패. 일부 기능이 제한됩니다.")
    else:
        st.success("✅ 한국투자증권 API 연결 성공")

    # 실시간 지수 & 환율 표시
    _render_market_indices(api)

    st.markdown("---")

    # 주도 테마/섹터 섹션
    _render_market_theme_section()

    st.markdown("---")

    # 종목 검색
    st.markdown("### 🔍 종목 검색 & 상세 분석")

    col1, col2 = st.columns([3, 1])

    with col1:
        all_stocks = [(c, n, 'KOSPI') for c, n in get_kospi_stocks()] + [(c, n, 'KOSDAQ') for c, n in get_kosdaq_stocks()]
        options = [f"{n} ({c}) - {m}" for c, n, m in all_stocks]
        selected = st.selectbox("종목 선택", ["선택하세요..."] + options, key="stock_select")

    with col2:
        direct_code = st.text_input("종목코드 직접입력", placeholder="005930")

    selected_code = None
    if direct_code and len(direct_code) == 6:
        selected_code = direct_code
    elif selected != "선택하세요...":
        selected_code = selected.split("(")[1].split(")")[0]

    if selected_code:
        _render_stock_detail_section(api, selected_code)

    st.markdown("---")

    # 주요 종목
    st.markdown("### 💰 주요 종목 바로가기")

    # 종목 등락률 캐시 로드
    stock_changes = _get_top_stocks_changes(api)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 0.75rem 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <span style='color: white; font-weight: 700; font-size: 1.1rem;'>🏢 KOSPI TOP 10</span>
        </div>
        """, unsafe_allow_html=True)
        _render_stock_buttons(get_kospi_stocks()[:10], stock_changes, 'KOSPI', api)

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
                    padding: 0.75rem 1rem; border-radius: 12px; margin-bottom: 1rem;'>
            <span style='color: white; font-weight: 700; font-size: 1.1rem;'>🚀 KOSDAQ TOP 10</span>
        </div>
        """, unsafe_allow_html=True)
        _render_stock_buttons(get_kosdaq_stocks()[:10], stock_changes, 'KOSDAQ', api)

    if 'quick_code' in st.session_state:
        st.markdown("---")
        _render_stock_detail_section(api, st.session_state['quick_code'])

    st.markdown("---")

    # 관심종목 실시간 모니터링 섹션
    _render_watchlist_section(api)


def _get_api_connection():
    """API 연결"""
    if 'kis_api' not in st.session_state:
        try:
            from data.kis_api import KoreaInvestmentAPI
            api = KoreaInvestmentAPI()
            if api.connect():
                st.session_state['kis_api'] = api
            else:
                return None
        except Exception as e:
            return None
    return st.session_state.get('kis_api')


@st.cache_data(ttl=60)
def _get_top_stocks_changes(_api) -> dict:
    """주요 종목들의 등락률 조회 (캐시)"""
    changes = {}
    if _api is None:
        return changes

    # KOSPI + KOSDAQ TOP 10 종목들의 등락률 조회
    all_codes = [code for code, _ in get_kospi_stocks()[:10]] + [code for code, _ in get_kosdaq_stocks()[:10]]

    for code in all_codes:
        try:
            info = _api.get_stock_info(code)
            if info:
                changes[code] = info.get('change_rate', 0)
        except:
            changes[code] = 0

    return changes


def _render_stock_buttons(stocks: list, changes: dict, market: str, api):
    """종목 버튼들 렌더링 (등락률 포함, 상승=빨강, 하락=파랑) - 클릭 가능한 심플 버튼"""

    # 5개씩 한 줄에 표시
    for row_start in range(0, len(stocks), 5):
        cols = st.columns(5)
        for i, (code, name) in enumerate(stocks[row_start:row_start+5]):
            with cols[i]:
                change = changes.get(code, 0)

                # 등락에 따른 색상 (상승=빨강, 하락=파랑)
                if change > 0:
                    arrow = '▲'
                    btn_type = 'primary'
                elif change < 0:
                    arrow = '▼'
                    btn_type = 'secondary'
                else:
                    arrow = '-'
                    btn_type = 'secondary'

                # 버튼 레이블
                btn_label = f"{name} {arrow}{abs(change):.1f}%"

                # 클릭 가능한 버튼 (type에 따라 색상 다름)
                if change > 0:
                    # 상승 - 빨간 버튼
                    clicked = st.button(btn_label, key=f"btn_{market}_{code}", type="primary", help=f"{code}")
                else:
                    # 하락/보합 - 파란 버튼
                    clicked = st.button(btn_label, key=f"btn_{market}_{code}", help=f"{code}")

                if clicked:
                    st.session_state['quick_code'] = code
                    st.rerun()


def _render_stock_card(name: str, price: int, change: float, icon: str):
    """종목 카드"""
    color = "#38ef7d" if change >= 0 else "#f5576c"
    arrow = "▲" if change >= 0 else "▼"

    st.markdown(f"""
    <div class='market-card'>
        <div style='display: flex; justify-content: space-between;'>
            <span style='font-size: 1.5rem;'>{icon}</span>
            <span style='color: {color}; font-weight: 600;'>{arrow} {abs(change):.2f}%</span>
        </div>
        <p style='font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0 0 0;'>{price:,}원</p>
        <p style='color: #888; margin: 0;'>{name}</p>
    </div>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=30)
def _get_stock_info_cached(_api, code: str) -> dict:
    """종목 정보 캐시"""
    try:
        return _api.get_stock_info(code)
    except:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def _get_chart_technical_analysis(_api, code: str) -> dict:
    """차트 기술적 분석 데이터 조회"""
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")

        df = _api.get_daily_price(code, start, end)
        if df is None or len(df) < 60:
            return None

        result = {}

        # 1. 이동평균선 분석 (5, 20, 60일)
        ma5 = df['close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['close'].rolling(window=20).mean().iloc[-1]
        ma60 = df['close'].rolling(window=60).mean().iloc[-1]
        current_price = df['close'].iloc[-1]

        # 정배열 (5 > 20 > 60) / 역배열 (5 < 20 < 60)
        if ma5 > ma20 > ma60:
            result['ma_status'] = '정배열 ↑'
            result['ma_color'] = '#38ef7d'
            ma_score = 80
        elif ma5 > ma20 and ma20 < ma60:
            result['ma_status'] = '회복중'
            result['ma_color'] = '#FFD700'
            ma_score = 60
        elif ma5 < ma20 < ma60:
            result['ma_status'] = '역배열 ↓'
            result['ma_color'] = '#FF6B6B'
            ma_score = 20
        elif ma5 < ma20 and ma20 > ma60:
            result['ma_status'] = '하락중'
            result['ma_color'] = '#FFA500'
            ma_score = 40
        else:
            result['ma_status'] = '혼조'
            result['ma_color'] = '#888'
            ma_score = 50

        # 2. 거래량 분석
        vol_ma20 = df['volume'].rolling(window=20).mean().iloc[-1]
        current_vol = df['volume'].iloc[-1]
        vol_ratio = current_vol / vol_ma20 if vol_ma20 > 0 else 0
        result['vol_ratio'] = vol_ratio

        if vol_ratio >= 2.0:
            result['vol_status'] = '급증'
            result['vol_color'] = '#FF3B30'
            vol_score = 70 if df['close'].iloc[-1] > df['open'].iloc[-1] else 30
        elif vol_ratio >= 1.5:
            result['vol_status'] = '증가'
            result['vol_color'] = '#FFD700'
            vol_score = 60
        elif vol_ratio >= 0.5:
            result['vol_status'] = '보통'
            result['vol_color'] = '#888'
            vol_score = 50
        else:
            result['vol_status'] = '침체'
            result['vol_color'] = '#007AFF'
            vol_score = 40

        # 3. RSI 분석 (14일)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        result['rsi'] = current_rsi

        if current_rsi >= 70:
            result['rsi_status'] = '과매수'
            result['rsi_color'] = '#FF6B6B'
            rsi_score = 30
        elif current_rsi >= 50:
            result['rsi_status'] = '강세'
            result['rsi_color'] = '#38ef7d'
            rsi_score = 70
        elif current_rsi >= 30:
            result['rsi_status'] = '약세'
            result['rsi_color'] = '#FFA500'
            rsi_score = 40
        else:
            result['rsi_status'] = '과매도'
            result['rsi_color'] = '#007AFF'
            rsi_score = 60  # 반등 기대

        # 4. 볼린저밴드 분석 (20일, 2σ)
        bb_mid = df['close'].rolling(window=20).mean().iloc[-1]
        bb_std = df['close'].rolling(window=20).std().iloc[-1]
        bb_upper = bb_mid + (bb_std * 2)
        bb_lower = bb_mid - (bb_std * 2)

        if current_price >= bb_upper:
            result['bb_status'] = '상단 돌파'
            result['bb_color'] = '#FF6B6B'
            bb_score = 40  # 과열
        elif current_price >= bb_mid:
            result['bb_status'] = '상단 구간'
            result['bb_color'] = '#38ef7d'
            bb_score = 70
        elif current_price >= bb_lower:
            result['bb_status'] = '하단 구간'
            result['bb_color'] = '#FFA500'
            bb_score = 40
        else:
            result['bb_status'] = '하단 이탈'
            result['bb_color'] = '#007AFF'
            bb_score = 50  # 반등 기대

        # 종합 차트 점수
        result['chart_score'] = (ma_score + vol_score + rsi_score + bb_score) / 4

        return result

    except Exception as e:
        return None


def _render_quant_analysis_section(api, info: dict, code: str, stock_name: str):
    """마법공식 & 멀티팩터 & 차트 기술적 분석 섹션"""
    import html

    st.markdown("---")
    st.markdown("#### 🎯 퀀트 전략 분석")

    col1, col2, col3 = st.columns(3)

    with col1:
        # 마법공식 분석
        st.markdown("""<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'><span style='color: white; font-weight: 700;'>📊 마법공식 (Magic Formula)</span></div>""", unsafe_allow_html=True)

        per = info.get('per', 0)
        eps = info.get('eps', 0)
        price = info.get('price', 0)
        pbr = info.get('pbr', 0)
        bps = info.get('bps', 0)

        # 이익수익률 (Earnings Yield) = EPS / Price = 1/PER
        if per > 0:
            earnings_yield = (1 / per) * 100
        elif eps > 0 and price > 0:
            earnings_yield = (eps / price) * 100
        else:
            earnings_yield = 0

        # ROE 추정 (= EPS / BPS)
        if bps > 0 and eps > 0:
            roe = (eps / bps) * 100
        else:
            roe = 0

        # 점수 계산 (간소화 버전)
        # 이익수익률: 높을수록 좋음 (일반적으로 5% 이상이면 양호)
        ey_score = min(earnings_yield / 10 * 100, 100) if earnings_yield > 0 else 0
        # ROE: 높을수록 좋음 (일반적으로 15% 이상이면 양호)
        roe_score = min(roe / 20 * 100, 100) if roe > 0 else 0

        # 마법공식 종합 점수
        magic_score = (ey_score + roe_score) / 2 if (ey_score > 0 or roe_score > 0) else 0

        # 등급 결정
        if magic_score >= 70:
            grade = "A"
            grade_color = "#38ef7d"
            grade_desc = "매우 우수"
        elif magic_score >= 50:
            grade = "B"
            grade_color = "#FFD700"
            grade_desc = "양호"
        elif magic_score >= 30:
            grade = "C"
            grade_color = "#FFA500"
            grade_desc = "보통"
        else:
            grade = "D"
            grade_color = "#FF6B6B"
            grade_desc = "미흡"

        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 10px; border: 1px solid #e0e0e0;'>
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                <span style='font-weight: 700; font-size: 1.1rem;'>종합 등급</span>
                <div style='background: {grade_color}30; padding: 0.3rem 0.8rem; border-radius: 20px;'>
                    <span style='color: {grade_color}; font-weight: 700; font-size: 1.2rem;'>{grade}</span>
                    <span style='color: #666; font-size: 0.85rem; margin-left: 0.3rem;'>{grade_desc}</span>
                </div>
            </div>
            <div style='margin-bottom: 0.5rem;'>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>이익수익률 (EY)</span>
                    <span style='font-weight: 600;'>{earnings_yield:.2f}%</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: #667eea; height: 100%; width: {ey_score:.0f}%;'></div>
                </div>
            </div>
            <div>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>자본수익률 (ROE)</span>
                    <span style='font-weight: 600;'>{roe:.2f}%</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: #764ba2; height: 100%; width: {roe_score:.0f}%;'></div>
                </div>
            </div>
            <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                <span style='color: #888; font-size: 0.8rem;'>💡 마법공식: 저평가 우량주 (EY↑, ROE↑)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # 멀티팩터 분석
        st.markdown("""<div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'><span style='color: white; font-weight: 700;'>📈 멀티팩터 분석</span></div>""", unsafe_allow_html=True)

        # 밸류 점수 (PER, PBR 기반)
        # PER: 낮을수록 좋음 (10 이하면 만점, 30 이상이면 0점)
        if per > 0:
            value_per_score = max(0, min(100, (30 - per) / 20 * 100))
        else:
            value_per_score = 0

        # PBR: 낮을수록 좋음 (1 이하면 만점, 3 이상이면 0점)
        if pbr > 0:
            value_pbr_score = max(0, min(100, (3 - pbr) / 2 * 100))
        else:
            value_pbr_score = 0

        value_score = (value_per_score + value_pbr_score) / 2 if (value_per_score > 0 or value_pbr_score > 0) else 0

        # 퀄리티 점수 (ROE 기반)
        quality_score = roe_score  # 마법공식에서 계산한 ROE 점수 재사용

        # 전체 멀티팩터 점수 (밸류 50% + 퀄리티 50%)
        multi_score = (value_score * 0.5 + quality_score * 0.5) if (value_score > 0 or quality_score > 0) else 0

        # 등급 결정
        if multi_score >= 70:
            m_grade = "A"
            m_grade_color = "#38ef7d"
            m_grade_desc = "매우 우수"
        elif multi_score >= 50:
            m_grade = "B"
            m_grade_color = "#FFD700"
            m_grade_desc = "양호"
        elif multi_score >= 30:
            m_grade = "C"
            m_grade_color = "#FFA500"
            m_grade_desc = "보통"
        else:
            m_grade = "D"
            m_grade_color = "#FF6B6B"
            m_grade_desc = "미흡"

        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 10px; border: 1px solid #e0e0e0;'>
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                <span style='font-weight: 700; font-size: 1.1rem;'>종합 등급</span>
                <div style='background: {m_grade_color}30; padding: 0.3rem 0.8rem; border-radius: 20px;'>
                    <span style='color: {m_grade_color}; font-weight: 700; font-size: 1.2rem;'>{m_grade}</span>
                    <span style='color: #666; font-size: 0.85rem; margin-left: 0.3rem;'>{m_grade_desc}</span>
                </div>
            </div>
            <div style='margin-bottom: 0.5rem;'>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>밸류 팩터</span>
                    <span style='font-weight: 600;'>{value_score:.0f}점</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: #f5576c; height: 100%; width: {value_score:.0f}%;'></div>
                </div>
                <div style='color: #888; font-size: 0.75rem; margin-top: 0.2rem;'>PER {per:.1f} | PBR {pbr:.2f}</div>
            </div>
            <div>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>퀄리티 팩터</span>
                    <span style='font-weight: 600;'>{quality_score:.0f}점</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: #f093fb; height: 100%; width: {quality_score:.0f}%;'></div>
                </div>
                <div style='color: #888; font-size: 0.75rem; margin-top: 0.2rem;'>ROE {roe:.1f}%</div>
            </div>
            <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                <span style='color: #888; font-size: 0.8rem;'>💡 멀티팩터: 밸류(저PER,저PBR) + 퀄리티(고ROE)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        # 차트 기술적 분석
        st.markdown("""<div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'><span style='color: white; font-weight: 700;'>📈 차트 기술분석</span></div>""", unsafe_allow_html=True)

        # 차트 데이터 로드
        chart_analysis = _get_chart_technical_analysis(api, code)

        if chart_analysis:
            ma_status = chart_analysis.get('ma_status', '-')
            ma_color = chart_analysis.get('ma_color', '#888')
            vol_ratio = chart_analysis.get('vol_ratio', 0)
            vol_status = chart_analysis.get('vol_status', '-')
            vol_color = chart_analysis.get('vol_color', '#888')
            rsi = chart_analysis.get('rsi', 0)
            rsi_status = chart_analysis.get('rsi_status', '-')
            rsi_color = chart_analysis.get('rsi_color', '#888')
            bb_status = chart_analysis.get('bb_status', '-')
            bb_color = chart_analysis.get('bb_color', '#888')
            chart_score = chart_analysis.get('chart_score', 0)

            # 등급 결정
            if chart_score >= 70:
                c_grade = "A"
                c_grade_color = "#38ef7d"
                c_grade_desc = "강세"
            elif chart_score >= 50:
                c_grade = "B"
                c_grade_color = "#FFD700"
                c_grade_desc = "중립"
            elif chart_score >= 30:
                c_grade = "C"
                c_grade_color = "#FFA500"
                c_grade_desc = "약세"
            else:
                c_grade = "D"
                c_grade_color = "#FF6B6B"
                c_grade_desc = "매우약세"

            st.markdown(f"""
            <div style='background: white; padding: 1rem; border-radius: 10px; border: 1px solid #e0e0e0;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                    <span style='font-weight: 700; font-size: 1.1rem;'>종합 등급</span>
                    <div style='background: {c_grade_color}30; padding: 0.3rem 0.8rem; border-radius: 20px;'>
                        <span style='color: {c_grade_color}; font-weight: 700; font-size: 1.2rem;'>{c_grade}</span>
                        <span style='color: #666; font-size: 0.85rem; margin-left: 0.3rem;'>{c_grade_desc}</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>이평선 배열</span>
                        <span style='font-weight: 600; color: {ma_color}; font-size: 0.85rem;'>{ma_status}</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>거래량</span>
                        <span style='font-weight: 600; color: {vol_color}; font-size: 0.85rem;'>{vol_status} ({vol_ratio:.1f}배)</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>RSI(14)</span>
                        <span style='font-weight: 600; color: {rsi_color}; font-size: 0.85rem;'>{rsi:.1f} ({rsi_status})</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>볼린저밴드</span>
                        <span style='font-weight: 600; color: {bb_color}; font-size: 0.85rem;'>{bb_status}</span>
                    </div>
                </div>
                <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                    <span style='color: #888; font-size: 0.8rem;'>💡 기술분석: 이평선, 거래량, RSI, BB</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background: white; padding: 1rem; border-radius: 10px; border: 1px solid #e0e0e0;'>
                <div style='text-align: center; color: #888; padding: 1rem;'>
                    <div style='font-size: 1.5rem; margin-bottom: 0.5rem;'>📊</div>
                    <div>차트 데이터 로딩 중...</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 투자 의견 (펀더멘털 + 기술적 분석 종합)
    chart_score_val = chart_analysis.get('chart_score', 50) if chart_analysis else 50
    avg_score = (magic_score + multi_score + chart_score_val) / 3

    if avg_score >= 60:
        opinion = "✅ 종합 관점 긍정적 - 펀더멘털 + 기술적 분석 양호"
        opinion_color = "#38ef7d"
    elif avg_score >= 40:
        opinion = "⚠️ 종합 관점 중립적 - 추가 분석 필요"
        opinion_color = "#FFD700"
    else:
        opinion = "❌ 종합 관점 부정적 - 펀더멘털 또는 기술적 분석 미흡"
        opinion_color = "#FF6B6B"

    st.markdown(f"""
    <div style='background: {opinion_color}15; padding: 0.75rem 1rem; border-radius: 8px; margin-top: 0.75rem; border-left: 4px solid {opinion_color};'>
        <span style='font-weight: 600;'>{opinion}</span>
    </div>
    """, unsafe_allow_html=True)

    # 주의사항
    st.caption("⚠️ 본 분석은 PER, PBR, EPS, BPS 및 차트 지표 기반의 간소화된 분석이며, 실제 투자 판단 시 재무제표, 성장성, 시장 상황 등을 종합적으로 고려해야 합니다.")


def _get_websocket_connection():
    """WebSocket 연결 (HTS_ID가 있을 때만)"""
    # .env 다시 로드 (Streamlit 세션에서 환경변수 갱신)
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

    hts_id = os.getenv("KIS_HTS_ID")
    if not hts_id:
        return None

    if 'kis_websocket' not in st.session_state:
        try:
            from data.kis_api import KoreaInvestmentWebSocket
            ws = KoreaInvestmentWebSocket()
            if ws.connect():
                st.session_state['kis_websocket'] = ws
            else:
                st.session_state['kis_websocket'] = None
        except Exception as e:
            print(f"WebSocket 연결 실패: {e}")
            st.session_state['kis_websocket'] = None

    return st.session_state.get('kis_websocket')


def _render_realtime_price_widget(ws, code: str, stock_name: str, rest_info: dict):
    """실시간 시세 위젯 렌더링"""
    if ws is None:
        return False

    # 구독 시도
    if code not in ws.get_subscribed_codes():
        if ws.get_subscription_count() >= 20:
            # 가장 오래된 구독 해제
            oldest = ws.get_subscribed_codes()[0] if ws.get_subscribed_codes() else None
            if oldest:
                ws.unsubscribe([oldest])
        ws.subscribe([code])
        time.sleep(0.3)  # 데이터 수신 대기

    # 실시간 데이터 조회
    realtime = ws.get_realtime_price(code)

    if realtime:
        price = realtime.get('price', 0)
        change = realtime.get('change', 0)
        change_rate = realtime.get('change_rate', 0)
        volume = realtime.get('volume', 0)
        trade_time = realtime.get('time', '')
        updated_at = realtime.get('updated_at')

        # 색상 결정
        if change_rate > 0:
            color = "#FF3B30"
            arrow = "▲"
            sign = "+"
        elif change_rate < 0:
            color = "#007AFF"
            arrow = "▼"
            sign = ""
        else:
            color = "#888"
            arrow = "-"
            sign = ""

        # 체결 시간 포맷팅
        if trade_time and len(trade_time) >= 6:
            formatted_time = f"{trade_time[:2]}:{trade_time[2:4]}:{trade_time[4:6]}"
        else:
            formatted_time = "-"

        # 실시간 배지
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #FF416C 0%, #FF4B2B 100%);
                    padding: 0.4rem 0.8rem; border-radius: 20px; display: inline-block; margin-bottom: 0.5rem;'>
            <span style='color: white; font-weight: 600; font-size: 0.8rem;'>
                🔴 실시간 | 체결 {formatted_time}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # 실시간 시세 카드
        st.markdown(f"""
        <div style='background: white; padding: 1.25rem; border-radius: 16px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1); border-left: 5px solid {color};
                    margin-bottom: 1rem;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <div style='font-size: 2rem; font-weight: 700; color: #333;'>
                        {price:,}원
                    </div>
                    <div style='color: {color}; font-size: 1.1rem; font-weight: 600; margin-top: 0.25rem;'>
                        {arrow} {sign}{change:,}원 ({sign}{change_rate:.2f}%)
                    </div>
                </div>
                <div style='text-align: right;'>
                    <div style='color: #888; font-size: 0.85rem;'>거래량</div>
                    <div style='font-weight: 600; font-size: 1.1rem;'>{volume:,}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # REST API 데이터로 추가 정보 표시
        if rest_info:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                cap = rest_info.get('market_cap', 0)
                st.metric("시가총액", f"{cap/1e12:.1f}조" if cap >= 1e12 else f"{cap/1e8:.0f}억")
            with col2:
                st.metric("PER", f"{rest_info.get('per', 0):.2f}" if rest_info.get('per', 0) > 0 else "-")
            with col3:
                st.metric("PBR", f"{rest_info.get('pbr', 0):.2f}" if rest_info.get('pbr', 0) > 0 else "-")
            with col4:
                st.metric("EPS", f"{rest_info.get('eps', 0):,.0f}원" if rest_info.get('eps', 0) > 0 else "-")

        return True

    return False


def _render_stock_detail_section(api, code: str):
    """종목 상세 정보"""

    stock_name = get_stock_name(code)

    st.markdown(f"""
    <div class='stock-detail-card'>
        <h2 style='margin: 0;'>{stock_name}</h2>
        <p style='color: #888; margin: 0.25rem 0;'>종목코드: {code}</p>
    </div>
    """, unsafe_allow_html=True)

    # API 없는 경우
    if api is None:
        st.warning("API 연결이 필요합니다. 종목 상세 정보를 볼 수 없습니다.")
        return

    # REST API로 기본 정보 조회 (PER, PBR 등)
    with st.spinner(f"{stock_name} 정보 로딩..."):
        info = api.get_stock_info(code)

    # WebSocket 실시간 시세 시도
    ws = _get_websocket_connection()
    realtime_displayed = False

    if ws and ws.is_connected:
        realtime_displayed = _render_realtime_price_widget(ws, code, stock_name, info)

    if info and not realtime_displayed:
        # REST API 기반 표시 (WebSocket 미연결 또는 실패 시)
        # 상승/하락 색상 설정
        change_rate = info['change_rate']
        if change_rate > 0:
            rate_color = "#FF3B30"  # 빨간색 (상승)
            rate_text = f"▲ +{change_rate:.2f}%"
        elif change_rate < 0:
            rate_color = "#007AFF"  # 파란색 (하락)
            rate_text = f"▼ {change_rate:.2f}%"
        else:
            rate_color = "#888888"
            rate_text = "0.00%"

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>현재가</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{info['price']:,}원</p>
                <p style='color: {rate_color}; font-weight: 700; margin: 0; font-size: 1rem; text-shadow: 0 0 8px {rate_color}80;'>{rate_text}</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            cap = info['market_cap']
            cap_str = f"{cap/1e12:.1f}조" if cap >= 1e12 else f"{cap/1e8:.0f}억"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>시가총액</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{cap_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            per_str = f"{info['per']:.2f}" if info['per'] > 0 else "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>PER</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{per_str}</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            eps_str = f"{info['eps']:,.0f}원" if info['eps'] > 0 else "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>EPS</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{eps_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            bps_str = f"{info['bps']:,.0f}원" if info['bps'] > 0 else "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>BPS</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{bps_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.2rem; border-radius: 16px;'>
                <p style='color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;'>거래량</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{info['volume']:,}</p>
            </div>
            """, unsafe_allow_html=True)
    elif not realtime_displayed:
        # REST API도 실패하고 WebSocket도 없는 경우
        st.warning("종목 정보를 불러올 수 없습니다.")
        return

    # info가 없어도 realtime이 있으면 계속 진행
    if not info:
        info = {}

    # 마법공식 & 멀티팩터 분석 섹션
    _render_quant_analysis_section(api, info, code, stock_name)

    st.markdown("---")

    # 차트 설정 - 네이버/구글 스타일
    st.markdown("#### ⚙️ 차트 설정")

    # 장중 여부 확인 - 분봉은 장중에만 가능
    from datetime import time as dt_time
    now = datetime.now()
    is_market_open = (
        now.weekday() < 5 and  # 평일
        dt_time(9, 0) <= now.time() <= dt_time(15, 30)  # 09:00 ~ 15:30
    )

    # 장중이면 모든 옵션, 아니면 일봉/주봉/월봉만
    if is_market_open:
        available_chart_types = ['일봉', '주봉', '월봉', '1분봉', '5분봉', '15분봉', '30분봉', '60분봉']
    else:
        available_chart_types = ['일봉', '주봉', '월봉']

    col1, col2, col3 = st.columns(3)
    with col1:
        chart_type = st.selectbox("차트 타입", available_chart_types, key=f"ct_{code}")
        if not is_market_open and chart_type in ['일봉', '주봉', '월봉']:
            st.caption("⏰ 분봉은 장중(09:00~15:30)에만 가능")
    with col2:
        if chart_type in ['일봉', '주봉', '월봉']:
            period = st.selectbox("기간", ['1개월', '3개월', '6개월', '1년', '2년', '3년'], index=2, key=f"pd_{code}")
        else:
            st.info(f"📊 {chart_type} (당일)")
            period = '1개월'
    with col3:
        chart_style = st.selectbox("차트 스타일", ['캔들차트', '라인차트', '영역차트'], key=f"style_{code}")

    # 이동평균선 & 보조지표
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📈 이동평균선**")
        ma_cols = st.columns(6)
        selected_mas = []
        for i, (ma_key, (_, _, label)) in enumerate(MA_OPTIONS.items()):
            with ma_cols[i]:
                if st.checkbox(label, value=(ma_key in ['MA5', 'MA20', 'MA60']), key=f"{ma_key}_{code}"):
                    selected_mas.append(ma_key)

    with col2:
        st.markdown("**📊 보조지표**")
        indicator_cols = st.columns(4)
        selected_indicators = []
        for i, (ind_key, ind_name) in enumerate(INDICATOR_OPTIONS.items()):
            with indicator_cols[i]:
                if st.checkbox(ind_name, value=(ind_key == 'bollinger'), key=f"{ind_key}_{code}"):
                    selected_indicators.append(ind_key)

    # 차트
    st.markdown(f"#### 📈 {stock_name} 차트")

    # 차트 타입별 처리
    period_type, minute_val = CHART_TYPE_OPTIONS.get(chart_type, ('D', 0))

    with st.spinner("차트 로딩..."):
        if chart_type in ['일봉', '주봉', '월봉']:
            # 일봉/주봉/월봉
            base_days = {'1개월': 30, '3개월': 90, '6개월': 180, '1년': 365, '2년': 730, '3년': 1095}.get(period, 180)

            # 주봉/월봉은 더 많은 데이터 필요
            if chart_type == '주봉':
                base_days = max(base_days * 2, 365)  # 최소 1년
            elif chart_type == '월봉':
                base_days = max(base_days * 3, 730)  # 최소 2년

            # 이동평균선 계산을 위해 추가 데이터 필요
            # 선택된 MA 중 가장 긴 기간 찾기
            max_ma_period = 0
            for ma_key in selected_mas:
                ma_period = MA_OPTIONS[ma_key][0]
                if ma_period > max_ma_period:
                    max_ma_period = ma_period

            # 보조지표를 위한 추가 데이터 (MACD=26, RSI/Stochastic=14, Bollinger=20)
            indicator_extra = 0
            if 'macd' in selected_indicators:
                indicator_extra = max(indicator_extra, 26)
            if any(ind in selected_indicators for ind in ['rsi', 'stochastic', 'bollinger']):
                indicator_extra = max(indicator_extra, 20)

            # 총 필요 일수 = 기본 기간 + MA 기간 + 보조지표 기간 (거래일 기준으로 1.5배)
            extra_days = int((max_ma_period + indicator_extra) * 1.5)
            days = base_days + extra_days

            chart_data = _get_daily_chart_data(api, code, days, period=period_type)
            time_col = 'date'

            # 차트 표시용 시작 날짜 계산 (기본 기간만큼만 표시)
            if not chart_data.empty:
                display_start_date = datetime.now() - timedelta(days=int(base_days * 1.5))
        else:
            # 분봉
            chart_data = _get_minute_chart_data(api, code, minute_val)
            time_col = 'datetime' if 'datetime' in chart_data.columns else 'time'
            display_start_date = None

    if not chart_data.empty and len(chart_data) > 0:
        # 보조지표에 따라 서브플롯 수 결정
        num_indicator_rows = sum([1 for ind in selected_indicators if ind in ['macd', 'rsi', 'stochastic']])
        total_rows = 2 + num_indicator_rows  # 가격 + 거래량 + 보조지표들

        row_heights = [0.5] + [0.15] + [0.35 / max(num_indicator_rows, 1)] * num_indicator_rows if num_indicator_rows > 0 else [0.7, 0.3]

        fig = make_subplots(
            rows=total_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=row_heights
        )

        # 메인 차트 (가격)
        if chart_style == '캔들차트':
            fig.add_trace(go.Candlestick(
                x=chart_data[time_col],
                open=chart_data['open'], high=chart_data['high'],
                low=chart_data['low'], close=chart_data['close'],
                name='주가',
                increasing_line_color='#FF3B30',  # 상승 빨간색 (한국식)
                decreasing_line_color='#007AFF',  # 하락 파란색 (한국식)
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#007AFF',
            ), row=1, col=1)
        elif chart_style == '라인차트':
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=chart_data['close'],
                mode='lines', name='종가',
                line=dict(color='#667eea', width=2)
            ), row=1, col=1)
        else:  # 영역차트
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=chart_data['close'],
                mode='lines', name='종가', fill='tozeroy',
                line=dict(color='#667eea', width=1),
                fillcolor='rgba(102, 126, 234, 0.3)'
            ), row=1, col=1)

        # 이동평균선
        for ma_key in selected_mas:
            period_val, color, label = MA_OPTIONS[ma_key]
            if len(chart_data) >= period_val:
                ma_values = chart_data['close'].rolling(window=period_val).mean()
                fig.add_trace(go.Scatter(
                    x=chart_data[time_col], y=ma_values,
                    mode='lines', name=label,
                    line=dict(color=color, width=1.5)
                ), row=1, col=1)

        # 볼린저 밴드
        if 'bollinger' in selected_indicators and len(chart_data) >= 20:
            bb_mid = chart_data['close'].rolling(window=20).mean()
            bb_std = chart_data['close'].rolling(window=20).std()
            bb_upper = bb_mid + (bb_std * 2)
            bb_lower = bb_mid - (bb_std * 2)

            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=bb_upper,
                mode='lines', name='BB상단',
                line=dict(color='rgba(255, 99, 132, 0.5)', width=1, dash='dot')
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=bb_lower,
                mode='lines', name='BB하단', fill='tonexty',
                line=dict(color='rgba(255, 99, 132, 0.5)', width=1, dash='dot'),
                fillcolor='rgba(255, 99, 132, 0.1)'
            ), row=1, col=1)

        # 거래량 차트 (Row 2)
        vol_colors = ['#FF3B30' if chart_data['close'].iloc[i] >= chart_data['open'].iloc[i] else '#007AFF'
                      for i in range(len(chart_data))]
        # 거래량 이동평균
        vol_ma = chart_data['volume'].rolling(window=20).mean()

        fig.add_trace(go.Bar(
            x=chart_data[time_col], y=chart_data['volume'],
            name='거래량', marker_color=vol_colors, opacity=0.85,
            showlegend=False,
            marker_line_width=0  # 바 테두리 제거로 더 깔끔하게
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=chart_data[time_col], y=vol_ma,
            mode='lines', name='거래량MA20',
            line=dict(color='#FFA500', width=1.5)
        ), row=2, col=1)

        current_row = 3

        # MACD
        if 'macd' in selected_indicators and len(chart_data) >= 26:
            ema12 = chart_data['close'].ewm(span=12, adjust=False).mean()
            ema26 = chart_data['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            hist_colors = ['#FF3B30' if v >= 0 else '#007AFF' for v in macd_hist]

            fig.add_trace(go.Bar(
                x=chart_data[time_col], y=macd_hist,
                name='MACD Hist', marker_color=hist_colors, opacity=0.5
            ), row=current_row, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=macd_line,
                mode='lines', name='MACD',
                line=dict(color='#667eea', width=1.5)
            ), row=current_row, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=signal_line,
                mode='lines', name='Signal',
                line=dict(color='#f5576c', width=1.5)
            ), row=current_row, col=1)
            fig.update_yaxes(title_text="MACD", row=current_row, col=1)
            current_row += 1

        # RSI
        if 'rsi' in selected_indicators and len(chart_data) >= 14:
            delta = chart_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=rsi,
                mode='lines', name='RSI(14)',
                line=dict(color='#9B59B6', width=1.5)
            ), row=current_row, col=1)
            # 과매수/과매도 라인
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=current_row, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)
            current_row += 1

        # 스토캐스틱
        if 'stochastic' in selected_indicators and len(chart_data) >= 14:
            low_14 = chart_data['low'].rolling(window=14).min()
            high_14 = chart_data['high'].rolling(window=14).max()
            stoch_k = 100 * (chart_data['close'] - low_14) / (high_14 - low_14)
            stoch_d = stoch_k.rolling(window=3).mean()

            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=stoch_k,
                mode='lines', name='%K',
                line=dict(color='#3498DB', width=1.5)
            ), row=current_row, col=1)
            fig.add_trace(go.Scatter(
                x=chart_data[time_col], y=stoch_d,
                mode='lines', name='%D',
                line=dict(color='#E74C3C', width=1.5)
            ), row=current_row, col=1)
            fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=current_row, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=current_row, col=1)
            fig.update_yaxes(title_text="Stoch", range=[0, 100], row=current_row, col=1)

        # 레이아웃 업데이트
        layout_config = dict(
            height=600 + (num_indicator_rows * 100),
            margin=dict(t=30, b=30, l=60, r=30),
            xaxis_rangeslider_visible=False,
            plot_bgcolor='#FAFAFA',
            paper_bgcolor='white',
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="center", x=0.5,
                font=dict(size=10)
            ),
            hovermode='x unified',
            font=dict(family="Arial, sans-serif")
        )

        # x축 범위 설정 (일봉인 경우 기본 기간만 표시)
        if minute_val == 0 and display_start_date is not None:
            layout_config['xaxis'] = dict(
                range=[display_start_date, datetime.now() + timedelta(days=1)]
            )

        fig.update_layout(**layout_config)

        fig.update_yaxes(title_text="가격", row=1, col=1, gridcolor='#E5E5E5')
        fig.update_yaxes(title_text="거래량", row=2, col=1, gridcolor='#E5E5E5')
        fig.update_xaxes(gridcolor='#E5E5E5')

        st.plotly_chart(fig, use_container_width=True)

        # 통계 - 네이버 스타일
        st.markdown("#### 📋 기간 통계")
        col1, col2, col3, col4, col5 = st.columns(5)

        current_price = int(chart_data['close'].iloc[-1])
        high_price = int(chart_data['high'].max())
        low_price = int(chart_data['low'].min())
        avg_volume = int(chart_data['volume'].mean())

        with col1:
            st.metric("기간 최고가", f"{high_price:,}원",
                     f"{((high_price - current_price) / current_price * 100):+.1f}%")
        with col2:
            st.metric("기간 최저가", f"{low_price:,}원",
                     f"{((current_price - low_price) / low_price * 100):+.1f}%")
        with col3:
            st.metric("평균 거래량", f"{avg_volume:,}")
        with col4:
            if len(chart_data) > 1:
                ret = (chart_data['close'].iloc[-1] / chart_data['close'].iloc[0] - 1) * 100
                st.metric("기간 수익률", f"{ret:+.1f}%")
        with col5:
            # 변동성 (표준편차)
            volatility = chart_data['close'].pct_change().std() * 100 * (252 ** 0.5)  # 연환산
            st.metric("연 변동성", f"{volatility:.1f}%")

    else:
        if minute_val > 0:
            # 분봉 데이터 로드 실패 (장중인데도 실패한 경우)
            st.warning("""
            ⚠️ **분봉 데이터를 불러올 수 없습니다.**

            **가능한 원인:**
            - 공휴일 (휴장일)
            - API 연결 오류
            - 종목 데이터 없음

            **해결 방법:** 새로고침 하거나 일봉 차트를 사용해주세요.
            """)
        else:
            st.warning("차트 데이터를 불러올 수 없습니다. API 연결을 확인해주세요.")


def _get_daily_chart_data(_api, code: str, days: int, period: str = "D") -> pd.DataFrame:
    """일봉/주봉/월봉 데이터 조회 (캐시 없이 직접 호출)

    Args:
        _api: API 인스턴스
        code: 종목코드
        days: 조회 일수
        period: D(일봉), W(주봉), M(월봉)
    """
    import sys
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        period_name = {'D': '일봉', 'W': '주봉', 'M': '월봉'}.get(period, '일봉')
        print(f"[DEBUG] {period_name} 요청: {code}, {start}~{end}, {days}일", file=sys.stderr)
        df = _api.get_daily_price(code, start, end, period=period)
        if df is None or df.empty:
            print(f"[DEBUG] {period_name} 데이터 없음: {code}", file=sys.stderr)
            return pd.DataFrame()
        print(f"[DEBUG] {period_name} 데이터 {len(df)}개 로드: {code}", file=sys.stderr)
        return df
    except Exception as e:
        print(f"[DEBUG] {period_name} 데이터 로드 오류: {code}, {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def _get_minute_chart_data(_api, code: str, minute: int) -> pd.DataFrame:
    """분봉 데이터 조회"""
    import sys
    try:
        df = _api.get_minute_price(code, minute)
        if df is None or df.empty:
            print(f"[DEBUG] 분봉 데이터 없음: {code}, {minute}분", file=sys.stderr)
            return pd.DataFrame()
        print(f"[DEBUG] 분봉 데이터 {len(df)}개 로드: {code}", file=sys.stderr)
        return df
    except Exception as e:
        print(f"[DEBUG] 분봉 데이터 로드 오류: {code}, {e}", file=sys.stderr)
        return pd.DataFrame()


# ===== 주도 테마/섹터 섹션 =====

def _render_market_theme_section():
    """주도 테마/섹터 섹션 렌더링"""

    st.markdown("### 🔥 실시간 주도 테마 & 섹터")

    # 버전 선택
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        theme_version = st.radio(
            "버전 선택",
            ["간단 버전", "풀 버전"],
            horizontal=True,
            key="theme_version",
            help="간단: TOP 5 테마/섹터 | 풀: 급등락 종목 + 뉴스 + 자동갱신"
        )

    with col2:
        if st.button("🔄 새로고침", key="refresh_theme"):
            # 캐시 무효화
            if 'theme_service' in st.session_state:
                st.session_state['theme_service'].refresh_cache()
            st.rerun()

    with col3:
        # 시장 상태 표시
        service = _get_theme_service()
        status = service.get_market_status()
        status_color = "#38ef7d" if service.is_market_open() else "#f5576c"
        st.markdown(f"""
        <div style='background: {status_color}20; padding: 0.5rem 1rem; border-radius: 8px; text-align: center;'>
            <span style='color: {status_color}; font-weight: 600;'>{status}</span>
        </div>
        """, unsafe_allow_html=True)

    # 풀 버전 - 자동 갱신 (장중에만)
    if theme_version == "풀 버전" and service.is_market_open():
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=30000, limit=None, key="theme_autorefresh")
            st.caption("⏱️ 장중 30초마다 자동 갱신")
        except ImportError:
            st.caption("💡 자동 갱신을 위해: `pip install streamlit-autorefresh`")

    # 버전에 따른 렌더링
    if theme_version == "간단 버전":
        _render_theme_simple(service)
    else:
        _render_theme_full(service)


def _get_theme_service() -> MarketThemeService:
    """테마 서비스 싱글톤"""
    if 'theme_service' not in st.session_state:
        st.session_state['theme_service'] = MarketThemeService()
    return st.session_state['theme_service']


def _render_theme_simple(service: MarketThemeService):
    """간단 버전: TOP 5 테마 + 섹터"""
    import html

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%);
                    padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'>
            <span style='color: white; font-weight: 700;'>🚀 상승 테마 TOP 5</span>
        </div>
        """, unsafe_allow_html=True)

        hot_themes = service.get_hot_themes(5)
        if hot_themes:
            for theme in hot_themes:
                # HTML escape 처리
                theme_name = html.escape(theme.name)
                leader_stock = html.escape(theme.leader_stock) if theme.leader_stock else ""
                leader_display = f"대장주: {leader_stock}" if leader_stock else ""
                change_rate = theme.change_rate

                st.markdown(f"""<div style='background: white; padding: 0.6rem 0.8rem; border-radius: 8px; margin-bottom: 0.4rem; border-left: 4px solid #FF6B6B; display: flex; justify-content: space-between; align-items: center;'><div><span style='font-weight: 600;'>{theme_name}</span><span style='color: #888; font-size: 0.85rem; margin-left: 0.5rem;'>{leader_display}</span></div><span style='color: #FF3B30; font-weight: 700;'>+{change_rate:.2f}%</span></div>""", unsafe_allow_html=True)
        else:
            st.info("테마 데이터를 불러오는 중...")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'>
            <span style='color: white; font-weight: 700;'>📊 상승 섹터 TOP 5</span>
        </div>
        """, unsafe_allow_html=True)

        rising_sectors = service.get_sector_ranking(5, rising=True)
        if rising_sectors:
            for sector in rising_sectors:
                sector_name = html.escape(sector.name)
                change_rate = sector.change_rate
                st.markdown(f"""<div style='background: white; padding: 0.6rem 0.8rem; border-radius: 8px; margin-bottom: 0.4rem; border-left: 4px solid #667eea; display: flex; justify-content: space-between; align-items: center;'><span style='font-weight: 600;'>{sector_name}</span><span style='color: #FF3B30; font-weight: 700;'>+{change_rate:.2f}%</span></div>""", unsafe_allow_html=True)
        else:
            st.info("섹터 데이터를 불러오는 중...")


def _render_theme_full(service: MarketThemeService):
    """풀 버전: 테마 + 섹터 + 급등락 + 뉴스"""
    import html

    # 상단: 테마 & 섹터
    col1, col2 = st.columns(2)

    with col1:
        # 상승 테마
        st.markdown("""<div style='background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>🚀 상승 테마</span></div>""", unsafe_allow_html=True)

        hot_themes = service.get_hot_themes(5)
        for theme in hot_themes:
            name = html.escape(theme.name)
            rate = theme.change_rate
            st.markdown(f"""<div style='background: #fff; padding: 0.4rem 0.6rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #FF6B6B; font-size: 0.85rem;'><span style='font-weight: 600;'>{name}</span><span style='color: #FF3B30; font-weight: 700; float: right;'>+{rate:.2f}%</span></div>""", unsafe_allow_html=True)

        # 하락 테마
        st.markdown("""<div style='background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin: 0.75rem 0 0.5rem 0;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>📉 하락 테마</span></div>""", unsafe_allow_html=True)

        falling_themes = service.get_falling_themes(5)
        for theme in falling_themes:
            name = html.escape(theme.name)
            rate = theme.change_rate
            st.markdown(f"""<div style='background: #fff; padding: 0.4rem 0.6rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #007AFF; font-size: 0.85rem;'><span style='font-weight: 600;'>{name}</span><span style='color: #007AFF; font-weight: 700; float: right;'>{rate:.2f}%</span></div>""", unsafe_allow_html=True)

    with col2:
        # 상승 섹터
        st.markdown("""<div style='background: linear-gradient(135deg, #38ef7d 0%, #11998e 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>📊 상승 섹터</span></div>""", unsafe_allow_html=True)

        rising_sectors = service.get_sector_ranking(5, rising=True)
        for sector in rising_sectors:
            name = html.escape(sector.name)
            rate = sector.change_rate
            st.markdown(f"""<div style='background: #fff; padding: 0.4rem 0.6rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #38ef7d; font-size: 0.85rem;'><span style='font-weight: 600;'>{name}</span><span style='color: #FF3B30; font-weight: 700; float: right;'>+{rate:.2f}%</span></div>""", unsafe_allow_html=True)

        # 하락 섹터
        st.markdown("""<div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin: 0.75rem 0 0.5rem 0;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>📉 하락 섹터</span></div>""", unsafe_allow_html=True)

        falling_sectors = service.get_sector_ranking(5, rising=False)
        for sector in falling_sectors:
            name = html.escape(sector.name)
            rate = sector.change_rate
            st.markdown(f"""<div style='background: #fff; padding: 0.4rem 0.6rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #f5576c; font-size: 0.85rem;'><span style='font-weight: 600;'>{name}</span><span style='color: #007AFF; font-weight: 700; float: right;'>{rate:.2f}%</span></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 중단: 급등/급락 종목
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""<div style='background: linear-gradient(135deg, #FF3B30 0%, #FF6B6B 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>🔥 급등 종목 TOP 5</span></div>""", unsafe_allow_html=True)

        gainers = service.get_top_gainers(5)
        for stock in gainers:
            name = html.escape(stock.name)
            rate = stock.change_rate
            price = stock.price
            volume = stock.volume
            st.markdown(f"""<div style='background: #fff; padding: 0.5rem 0.7rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #FF3B30; font-size: 0.85rem;'><div style='display: flex; justify-content: space-between;'><span style='font-weight: 600;'>{name}</span><span style='color: #FF3B30; font-weight: 700;'>+{rate:.2f}%</span></div><div style='color: #888; font-size: 0.75rem;'>{price:,}원 | 거래량 {volume:,}</div></div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("""<div style='background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>💧 급락 종목 TOP 5</span></div>""", unsafe_allow_html=True)

        losers = service.get_top_losers(5)
        for stock in losers:
            name = html.escape(stock.name)
            rate = stock.change_rate
            price = stock.price
            volume = stock.volume
            st.markdown(f"""<div style='background: #fff; padding: 0.5rem 0.7rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #007AFF; font-size: 0.85rem;'><div style='display: flex; justify-content: space-between;'><span style='font-weight: 600;'>{name}</span><span style='color: #007AFF; font-weight: 700;'>{rate:.2f}%</span></div><div style='color: #888; font-size: 0.75rem;'>{price:,}원 | 거래량 {volume:,}</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 하단: 뉴스 헤드라인
    st.markdown("""<div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;'><span style='color: white; font-weight: 700; font-size: 0.9rem;'>📰 주요 경제 뉴스</span></div>""", unsafe_allow_html=True)

    news = service.get_market_news(5)
    if news:
        for item in news:
            title = html.escape(item['title'])
            news_time = html.escape(item['time'])
            st.markdown(f"""<div style='background: #fff; padding: 0.5rem 0.7rem; border-radius: 6px; margin-bottom: 0.3rem; border-left: 3px solid #1a1a2e;'><div style='font-size: 0.85rem;'>• {title}</div><div style='color: #888; font-size: 0.7rem;'>{news_time}</div></div>""", unsafe_allow_html=True)
    else:
        st.info("뉴스 데이터를 불러오는 중...")

    # 업데이트 시간 표시
    st.caption(f"🕐 데이터 갱신: {datetime.now().strftime('%H:%M:%S')}")


# ===== 실시간 지수 & 환율 섹션 =====

@st.cache_data(ttl=60, show_spinner=False)  # 1분 캐시
def _get_market_indices_direct() -> dict:
    """시장 지수 직접 조회 (네이버 크롤링)"""
    import requests
    from bs4 import BeautifulSoup
    import re

    result = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    def get_index_from_naver(code: str) -> dict:
        """네이버에서 지수 조회"""
        url = f'https://finance.naver.com/sise/sise_index.naver?code={code}'
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')

        # subtop_sise_detail 영역에서 정보 추출
        detail = soup.select_one('.subtop_sise_detail')
        if not detail:
            return None

        text = detail.get_text(separator=' ').strip()

        # 숫자 추출 (첫번째: 현재가, 두번째: 변동)
        numbers = re.findall(r'[0-9,]+\.?[0-9]*', text)
        if len(numbers) < 2:
            return None

        price = float(numbers[0].replace(',', ''))
        change = float(numbers[1].replace(',', ''))

        # 등락률 찾기 (+0.65% 형태)
        rate_match = re.search(r'([+-]?[0-9.]+)%', text)
        change_rate = float(rate_match.group(1)) if rate_match else 0

        # 상승/하락 판단 - 등락률에서 부호 확인
        # 등락률 패턴: +1.15% 또는 -0.65%
        rate_with_sign = re.search(r'([+-])([0-9.]+)%', text)
        if rate_with_sign:
            sign = rate_with_sign.group(1)
            if sign == '-':
                change = -abs(change)
                change_rate = -abs(change_rate)
            else:
                change = abs(change)
                change_rate = abs(change_rate)
        elif '하락' in text:
            change = -abs(change)
            change_rate = -abs(change_rate)
        elif '상승' in text:
            change = abs(change)
            change_rate = abs(change_rate)

        return {'price': price, 'change': change, 'change_rate': change_rate}

    try:
        # 코스피 지수
        kospi_data = get_index_from_naver('KOSPI')
        if kospi_data:
            result['kospi'] = {
                "name": "코스피",
                "price": kospi_data['price'],
                "change": kospi_data['change'],
                "change_rate": kospi_data['change_rate']
            }
    except Exception as e:
        print(f"코스피 조회 오류: {e}")

    try:
        # 코스닥 지수
        kosdaq_data = get_index_from_naver('KOSDAQ')
        if kosdaq_data:
            result['kosdaq'] = {
                "name": "코스닥",
                "price": kosdaq_data['price'],
                "change": kosdaq_data['change'],
                "change_rate": kosdaq_data['change_rate']
            }
    except Exception as e:
        print(f"코스닥 조회 오류: {e}")

    try:
        # 환율 (USD)
        response = requests.get("https://finance.naver.com/marketindex/", headers=headers, timeout=10)
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')

        # USD 환율 찾기 (첫번째 li 또는 .on 클래스)
        usd_area = soup.select_one("#exchangeList li.on") or soup.select_one("#exchangeList li:first-child")
        if usd_area:
            rate_elem = usd_area.select_one(".value")
            change_elem = usd_area.select_one(".change")
            head_info = usd_area.select_one(".head_info")

            if rate_elem:
                rate = float(rate_elem.text.strip().replace(",", ""))
                change = 0
                if change_elem:
                    change_text = change_elem.text.strip().replace(",", "")
                    try:
                        change = float(change_text)
                    except:
                        pass

                # 상승/하락 확인 (point_dn = 하락, point_up = 상승)
                if head_info:
                    if 'point_dn' in head_info.get('class', []):
                        change = -abs(change)
                    elif 'point_up' in head_info.get('class', []):
                        change = abs(change)

                result['usd'] = {
                    "currency": "USD",
                    "name": "미국 USD",
                    "rate": rate,
                    "change": change,
                    "change_rate": (change / rate * 100) if rate else 0
                }
    except Exception as e:
        print(f"환율 조회 오류: {e}")

    return result


def _render_market_indices(api):
    """실시간 지수 & 환율 섹션 렌더링"""

    # 지수 데이터 직접 조회 (API 없이도 동작)
    indices = _get_market_indices_direct()

    # 새로고침 버튼
    col_refresh, col_time = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 지수 새로고침", key="refresh_indices"):
            _get_market_indices_direct.clear()
            st.rerun()
    with col_time:
        st.caption(f"📊 시세 기준: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 지수 카드 4개 표시
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _render_index_card("KOSPI", indices.get('kospi'), "📈")

    with col2:
        _render_index_card("KOSDAQ", indices.get('kosdaq'), "📊")

    with col3:
        _render_exchange_card("USD/KRW", indices.get('usd'), "💵")

    with col4:
        # 대표 종목 (삼성전자)
        samsung = _get_stock_info_cached(api, '005930') if api else None
        if samsung:
            _render_stock_card("삼성전자", samsung['price'], samsung['change_rate'], "🏢")
        else:
            st.metric("삼성전자", "-", "-")


def _render_index_card(name: str, data: dict, icon: str):
    """지수 카드 렌더링"""
    if data:
        price = data.get('price', 0)
        change = data.get('change', 0)
        change_rate = data.get('change_rate', 0)

        # 색상 결정
        if change_rate > 0:
            color = "#FF3B30"
            arrow = "▲"
            sign = "+"
        elif change_rate < 0:
            color = "#007AFF"
            arrow = "▼"
            sign = ""
        else:
            color = "#888"
            arrow = "-"
            sign = ""

        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
                    border-top: 4px solid {color};'>
            <div style='font-size: 1.5rem; margin-bottom: 0.25rem;'>{icon}</div>
            <div style='font-weight: 600; color: #333; font-size: 0.9rem;'>{name}</div>
            <div style='font-size: 1.25rem; font-weight: 700; color: #333; margin: 0.25rem 0;'>
                {price:,.2f}
            </div>
            <div style='color: {color}; font-size: 0.85rem; font-weight: 600;'>
                {arrow} {sign}{change:,.2f} ({sign}{change_rate:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
                    border-top: 4px solid #ccc;'>
            <div style='font-size: 1.5rem; margin-bottom: 0.25rem;'>{icon}</div>
            <div style='font-weight: 600; color: #333; font-size: 0.9rem;'>{name}</div>
            <div style='font-size: 1.1rem; color: #888; margin: 0.5rem 0;'>
                데이터 로딩 중...
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_exchange_card(name: str, data: dict, icon: str):
    """환율 카드 렌더링"""
    if data:
        rate = data.get('rate', 0)
        change = data.get('change', 0)
        change_rate = data.get('change_rate', 0)

        # 환율은 상승이 원화 약세 (빨강), 하락이 원화 강세 (파랑)
        if change > 0:
            color = "#FF3B30"
            arrow = "▲"
            sign = "+"
        elif change < 0:
            color = "#007AFF"
            arrow = "▼"
            sign = ""
        else:
            color = "#888"
            arrow = "-"
            sign = ""

        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
                    border-top: 4px solid {color};'>
            <div style='font-size: 1.5rem; margin-bottom: 0.25rem;'>{icon}</div>
            <div style='font-weight: 600; color: #333; font-size: 0.9rem;'>{name}</div>
            <div style='font-size: 1.25rem; font-weight: 700; color: #333; margin: 0.25rem 0;'>
                {rate:,.2f}원
            </div>
            <div style='color: {color}; font-size: 0.85rem; font-weight: 600;'>
                {arrow} {sign}{change:,.2f} ({sign}{change_rate:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
                    border-top: 4px solid #ccc;'>
            <div style='font-size: 1.5rem; margin-bottom: 0.25rem;'>{icon}</div>
            <div style='font-weight: 600; color: #333; font-size: 0.9rem;'>{name}</div>
            <div style='font-size: 1.1rem; color: #888; margin: 0.5rem 0;'>
                데이터 로딩 중...
            </div>
        </div>
        """, unsafe_allow_html=True)


# ===== 관심종목 실시간 모니터링 =====

def _render_watchlist_section(api):
    """관심종목 실시간 모니터링 섹션"""
    import html

    st.markdown("### 📌 관심종목 실시간 모니터링")

    # 관심종목 세션 초기화
    if 'watchlist' not in st.session_state:
        st.session_state['watchlist'] = ['005930', '000660', '035720']  # 기본값: 삼성전자, SK하이닉스, 카카오

    # 관심종목 관리 UI
    col1, col2 = st.columns([3, 1])

    with col1:
        # 종목 추가
        all_stocks = [(c, n, 'KOSPI') for c, n in get_kospi_stocks()] + [(c, n, 'KOSDAQ') for c, n in get_kosdaq_stocks()]
        options = [f"{n} ({c})" for c, n, m in all_stocks]
        new_stock = st.selectbox("종목 추가", ["선택하세요..."] + options, key="watchlist_add")

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ 추가", key="add_watchlist"):
            if new_stock != "선택하세요...":
                code = new_stock.split("(")[1].split(")")[0]
                if code not in st.session_state['watchlist']:
                    if len(st.session_state['watchlist']) < 20:
                        st.session_state['watchlist'].append(code)
                        st.rerun()
                    else:
                        st.warning("최대 20개까지 추가 가능합니다.")
                else:
                    st.info("이미 추가된 종목입니다.")

    # 현재 관심종목 수 표시
    watchlist = st.session_state['watchlist']
    st.caption(f"📊 관심종목 {len(watchlist)}/20개 | WebSocket 실시간 시세 (최대 20개)")

    # WebSocket 연결 확인
    ws = _get_websocket_connection()
    is_realtime = ws is not None and ws.is_connected

    # 디버깅: HTS_ID 확인
    hts_id = os.getenv("KIS_HTS_ID")

    if is_realtime:
        # WebSocket으로 모든 관심종목 구독
        codes_to_subscribe = [c for c in watchlist if c not in ws.get_subscribed_codes()]
        if codes_to_subscribe:
            ws.subscribe(codes_to_subscribe)
            time.sleep(0.5)  # 데이터 수신 대기

        st.markdown("""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    padding: 0.4rem 0.8rem; border-radius: 20px; display: inline-block; margin-bottom: 0.75rem;'>
            <span style='color: white; font-weight: 600; font-size: 0.8rem;'>
                🟢 실시간 시세 연결됨
            </span>
        </div>
        """, unsafe_allow_html=True)
    elif hts_id:
        # HTS_ID는 있지만 연결 실패
        st.warning(f"⚠️ WebSocket 연결 실패 (HTS_ID: {hts_id[:3]}***). 장 운영시간(09:00~15:30)에 다시 시도해주세요.")
        if st.button("🔄 WebSocket 재연결 시도", key="ws_reconnect"):
            if 'kis_websocket' in st.session_state:
                del st.session_state['kis_websocket']
            st.rerun()
    else:
        st.info("💡 실시간 시세를 사용하려면 .env에 KIS_HTS_ID를 설정하세요.")

    # 관심종목 테이블 렌더링
    if not watchlist:
        st.info("관심종목을 추가해주세요.")
        return

    # 종목 정보 수집
    stock_data = []
    for code in watchlist:
        stock_name = get_stock_name(code)

        if is_realtime:
            # WebSocket 실시간 데이터
            realtime = ws.get_realtime_price(code)
            if realtime:
                stock_data.append({
                    'code': code,
                    'name': stock_name,
                    'price': realtime.get('price', 0),
                    'change': realtime.get('change', 0),
                    'change_rate': realtime.get('change_rate', 0),
                    'volume': realtime.get('volume', 0),
                    'time': realtime.get('time', ''),
                    'is_realtime': True
                })
            else:
                # 실시간 데이터 없으면 REST API 사용
                info = _get_stock_info_cached(api, code) if api else None
                if info:
                    stock_data.append({
                        'code': code,
                        'name': stock_name,
                        'price': info.get('price', 0),
                        'change': 0,
                        'change_rate': info.get('change_rate', 0),
                        'volume': info.get('volume', 0),
                        'time': '',
                        'is_realtime': False
                    })
        else:
            # REST API 사용
            info = _get_stock_info_cached(api, code) if api else None
            if info:
                stock_data.append({
                    'code': code,
                    'name': stock_name,
                    'price': info.get('price', 0),
                    'change': 0,
                    'change_rate': info.get('change_rate', 0),
                    'volume': info.get('volume', 0),
                    'time': '',
                    'is_realtime': False
                })

    # 종목 행 렌더링 - Streamlit 기본 컴포넌트 사용
    for i, stock in enumerate(stock_data):
        code = stock['code']
        name = stock['name']
        price = stock['price']
        change_rate = stock['change_rate']
        volume = stock['volume']
        trade_time = stock['time']
        is_rt = stock['is_realtime']

        # 색상 결정
        if change_rate > 0:
            arrow = "▲"
            sign = "+"
            delta_color = "normal"
        elif change_rate < 0:
            arrow = "▼"
            sign = ""
            delta_color = "inverse"
        else:
            arrow = "-"
            sign = ""
            delta_color = "off"

        # 실시간 배지
        rt_badge = "🔴 " if is_rt else ""

        # 시간 표시
        time_str = ""
        if trade_time and len(trade_time) >= 6:
            time_str = f" ({trade_time[:2]}:{trade_time[2:4]})"

        col1, col2, col3, col4, col5 = st.columns([2.5, 1.5, 1.2, 0.5, 0.5])

        with col1:
            st.write(f"**{rt_badge}{name}** ({code}){time_str}")

        with col2:
            # 상승/하락 색상 (더 선명하게)
            if change_rate > 0:
                rate_color = "#FF3B30"  # 빨간색 (상승)
                rate_text = f"▲ +{change_rate:.2f}%"
            elif change_rate < 0:
                rate_color = "#007AFF"  # 파란색 (하락)
                rate_text = f"▼ {change_rate:.2f}%"
            else:
                rate_color = "#888888"
                rate_text = f"- 0.00%"

            st.markdown(f"""
            <div style='text-align: right;'>
                <span style='font-size: 1.2rem; font-weight: 700;'>{price:,}원</span><br>
                <span style='color: {rate_color}; font-weight: 700; font-size: 0.95rem;'>{rate_text}</span>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.write(f"거래량: {volume:,}")

        with col4:
            if st.button("📈", key=f"chart_{code}", help="차트 보기"):
                st.session_state['watchlist_chart_code'] = code
                st.session_state['watchlist_chart_name'] = name

        with col5:
            if st.button("🗑️", key=f"del_{code}", help="삭제"):
                st.session_state['watchlist'].remove(code)
                if is_realtime:
                    ws.unsubscribe([code])
                st.rerun()

        st.divider()

    # 업데이트 시간
    st.caption(f"🕐 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

    # 선택된 종목 차트 표시
    if 'watchlist_chart_code' in st.session_state and st.session_state.get('watchlist_chart_code'):
        _render_watchlist_chart(api, st.session_state['watchlist_chart_code'],
                                st.session_state.get('watchlist_chart_name', ''))

    # 자동 새로고침 (장중에만)
    from datetime import time as dt_time
    now = datetime.now()
    is_market_open = (
        now.weekday() < 5 and
        dt_time(9, 0) <= now.time() <= dt_time(15, 30)
    )

    if is_market_open and is_realtime:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=3000, limit=None, key="watchlist_autorefresh")
            st.caption("⏱️ 장중 3초마다 자동 갱신")
        except ImportError:
            if st.button("🔄 새로고침", key="refresh_watchlist"):
                st.rerun()


def _render_watchlist_chart(api, code: str, name: str):
    """관심종목 차트 렌더링"""
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
        try:
            chart_data = api.get_daily_price(code, start_date, end_date)
        except Exception as e:
            st.error(f"차트 데이터 로딩 실패: {e}")
            chart_data = None

    if chart_data is not None and len(chart_data) > 0:
        # 캔들스틱 차트 생성
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

        st.plotly_chart(fig, use_container_width=True, key=f"watchlist_chart_{code}")
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")

    # 차트 닫기 버튼
    if st.button("❌ 차트 닫기", key="close_watchlist_chart"):
        st.session_state['watchlist_chart_code'] = None
        st.session_state['watchlist_chart_name'] = None
        st.rerun()
