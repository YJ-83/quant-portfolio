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
import html

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# .env 파일 로드 (override=True로 기존 환경변수 덮어쓰기)
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

# 종목 리스트 import (KRX에서 동적으로 가져옴)
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name
from data.market_theme import MarketThemeService

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection

# 공통 지표 함수 import
from dashboard.utils.indicators import calculate_volume_profile

# 태쏘 전략 함수 import
from dashboard.utils.indicators import (
    detect_box_range,
    detect_box_breakout,
    detect_new_high_trend,
    analyze_swing_patterns
)

# 스윙 포인트 감지 함수 import
from dashboard.utils.chart_utils import detect_swing_points, render_investor_trend

# 이동평균선 옵션
MA_OPTIONS = {
    'MA5': (5, '#FF6B6B', '5일선'),
    'MA10': (10, '#4ECDC4', '10일선'),
    'MA20': (20, '#FFE66D', '20일선'),
    'MA60': (60, '#95E1D3', '60일선'),
    'MA120': (120, '#8B00FF', '120일선'),  # 보라색
    'MA200': (200, '#DC143C', '200일선'),  # 진홍 (장기추세 — 다크 배경에서도 선명)
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

# calculate_volume_profile 함수는 dashboard.utils.indicators에서 import


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

    # 모바일 모드 토글 (화면 상단에 표시 - 사이드바가 숨겨질 경우 대비)
    mobile_mode = st.session_state.get('mobile_mode', False)

    # 모바일 모드 상태에 따른 헤더 축소
    if mobile_mode:
        col_title, col_toggle = st.columns([4, 1])
        with col_title:
            st.markdown(f"### 📊 시장 현황")
            st.caption(f"{datetime.now().strftime('%m/%d %H:%M')}")
        with col_toggle:
            if st.button("🖥️", help="데스크탑 모드로 전환"):
                st.session_state['mobile_mode'] = False
                st.rerun()
    else:
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
    api = get_api_connection()
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

    # 뉴스 기반 주도 섹터 분석
    _render_news_sector_analysis()

    st.markdown("---")

    # 스윙매매 시그널 요약 카드 (태쏘 전략)
    _render_swing_signal_summary(api)

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


# _get_api_connection 함수는 dashboard/utils/api_helper.py로 통합됨
# 아래 호출부에서 get_api_connection() 사용


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

        # 5. MACD 분석 (12, 26, 9 설정)
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line

        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_hist = macd_hist.iloc[-1]
        prev_hist = macd_hist.iloc[-2] if len(macd_hist) > 1 else 0

        result['macd'] = current_macd
        result['macd_signal'] = current_signal
        result['macd_hist'] = current_hist

        # MACD 상태 판단
        if current_macd > current_signal and current_hist > prev_hist:
            result['macd_status'] = '강세 상승'
            result['macd_color'] = '#38ef7d'
            macd_score = 80
        elif current_macd > current_signal:
            result['macd_status'] = '골든크로스'
            result['macd_color'] = '#FFD700'
            macd_score = 65
        elif current_macd < current_signal and current_hist < prev_hist:
            result['macd_status'] = '약세 하락'
            result['macd_color'] = '#FF6B6B'
            macd_score = 20
        elif current_macd < current_signal:
            result['macd_status'] = '데드크로스'
            result['macd_color'] = '#FFA500'
            macd_score = 35
        else:
            result['macd_status'] = '중립'
            result['macd_color'] = '#888'
            macd_score = 50

        # 6. Williams %R 분석 (14일) - 81% 승률의 고효율 지표
        highest_high = df['high'].rolling(window=14).max()
        lowest_low = df['low'].rolling(window=14).min()
        williams_r = ((highest_high - df['close']) / (highest_high - lowest_low)) * -100
        current_williams_r = williams_r.iloc[-1]
        result['williams_r'] = current_williams_r

        if current_williams_r >= -20:
            result['williams_r_status'] = '과매수'
            result['williams_r_color'] = '#FF6B6B'
            williams_r_score = 30
        elif current_williams_r >= -50:
            result['williams_r_status'] = '강세'
            result['williams_r_color'] = '#38ef7d'
            williams_r_score = 70
        elif current_williams_r >= -80:
            result['williams_r_status'] = '약세'
            result['williams_r_color'] = '#FFA500'
            williams_r_score = 40
        else:
            result['williams_r_status'] = '과매도'
            result['williams_r_color'] = '#007AFF'
            williams_r_score = 65  # 반등 기대

        # 종합 차트 점수 (가중치 적용: 이평선 20%, 거래량 20%, RSI 15%, MACD 15%, BB 10%, Williams %R 20%)
        # Williams %R 추가 (81% 승률 지표)
        result['chart_score'] = (ma_score * 0.20 + vol_score * 0.20 + rsi_score * 0.15 + macd_score * 0.15 + bb_score * 0.10 + williams_r_score * 0.20)

        return result

    except Exception as e:
        return None


def _render_fib_ma200_section(api, code: str, stock_name: str):
    """200일선 + 피보나치 되돌림 confluence 분석 섹션.

    웹 리서치 인사이트:
    - 0.382 / 0.5 / 0.618 되돌림 레벨이 200MA와 ±2% 이내로 겹치면 강한 지지/저항.
    - 정배열 + confluence = 추세 매수 지점 후보, 역배열 + confluence = 매도 후보.
    """
    if api is None:
        return
    try:
        from utils.fibonacci import (
            fibonacci_retracement_levels,
            detect_ma200_fibonacci_confluence,
            fibonacci_summary_text,
            interpret_fib_ma200,
        )
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty or len(df) < 60:
            return
        close = df['close']

        st.markdown("---")
        st.markdown("#### 📐 200MA + 피보나치 되돌림 분석")

        fib = fibonacci_retracement_levels(close, lookback=120)
        conf = detect_ma200_fibonacci_confluence(close, lookback=120, tolerance_pct=2.0) \
            if len(close) >= 200 else None
        interp = interpret_fib_ma200(close, lookback=120)

        # ─── 1) 핵심 결론 배너 (가장 위) ───────────────
        if interp:
            cur = interp['current_price']
            ma200_val = interp.get('ma200')
            ma200_pct = interp.get('ma200_diff_pct')
            trend = interp['trend_label']
            pos = interp['position_label']
            ns = interp.get('next_support')
            nr = interp.get('next_resistance')

            # 추세 색
            if ma200_pct is None:
                trend_color = '#888'
            elif ma200_pct >= 20:
                trend_color = '#22c55e'
            elif ma200_pct >= 5:
                trend_color = '#86efac'
            elif ma200_pct >= -5:
                trend_color = '#f59e0b'
            else:
                trend_color = '#ef4444'

            ma200_html = (
                f"200MA <b style='color:#fff;'>{ma200_val:,.0f}원</b> · "
                f"<span style='color:{trend_color};'>{ma200_pct:+.1f}%</span>"
                if ma200_val else "200MA: 데이터 부족"
            )
            ns_html = (f"⬇ 다음 지지 <b>{ns['level']}</b> {ns['price']:,.0f}원 (-{ns['gap_pct']:.1f}%)"
                       if ns else "⬇ 아래 지지 없음")
            nr_html = (f"⬆ 다음 저항 <b>{nr['level']}</b> {nr['price']:,.0f}원 (+{nr['gap_pct']:.1f}%)"
                       if nr else "⬆ 위 저항 없음")

            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 1rem 1.2rem; border-radius: 14px; border-left: 5px solid {trend_color}; margin-bottom: 1rem;'>
              <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem;'>
                <div>
                  <span style='color:#888; font-size:0.85rem;'>현재가</span>
                  <span style='color:#fff; font-size:1.3rem; font-weight:700; margin-left:0.4rem;'>{cur:,.0f}원</span>
                </div>
                <div style='color:{trend_color}; font-weight:700;'>📊 {trend}</div>
                <div style='color:#ddd; font-size:0.9rem;'>{ma200_html}</div>
              </div>
              <div style='margin-top:0.6rem; color:#bbb; font-size:0.9rem;'>
                위치: <b style='color:#fff;'>{pos}</b> · {ns_html} · {nr_html}
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ─── 2) 매매 판단 카드 (스타일별 결론) ───────────────
        if interp and interp.get('verdicts'):
            st.markdown("##### 🎯 매매 판단 (스타일별)")
            badge_color_map = {
                '🔴': '#ef4444', '🟡': '#f59e0b', '🟢': '#22c55e', '⚪': '#888',
            }
            cols = st.columns(len(interp['verdicts']))
            for col, v in zip(cols, interp['verdicts']):
                badge = v['badge']
                badge_emoji = badge[0] if badge else '⚪'
                bcolor = badge_color_map.get(badge_emoji, '#888')
                # plan(분할) 정보
                plan_html = ""
                if v.get('plan'):
                    plan_html = "<div style='margin-top:0.5rem; font-size:0.82rem; color:#aaa;'>" + \
                        " · ".join([f"{p['level']}@{p['price']:,.0f}원" for p in v['plan']]) + "</div>"
                stop_html = ""
                if v.get('stop'):
                    stop_html = f"<div style='margin-top:0.4rem; font-size:0.8rem; color:#fbbf24;'>🛑 손절: {v['stop']:,.0f}원</div>"
                with col:
                    st.markdown(f"""
                    <div style='background:#1a1a2e; padding:0.9rem 1rem; border-radius:12px; border-top:4px solid {bcolor}; min-height:140px;'>
                      <div style='color:#888; font-size:0.85rem;'>{v['style']}</div>
                      <div style='color:{bcolor}; font-size:1.15rem; font-weight:700; margin:0.4rem 0;'>{v['badge']}</div>
                      <div style='color:#ddd; font-size:0.82rem; line-height:1.4;'>{v['reason']}</div>
                      {plan_html}
                      {stop_html}
                    </div>
                    """, unsafe_allow_html=True)

            # 핵심 손절선 요약
            if interp.get('short_stop') or interp.get('mid_stop'):
                short_s = interp.get('short_stop')
                mid_s = interp.get('mid_stop')
                stops = []
                if short_s:
                    stops.append(f"단기 <b style='color:#fbbf24;'>{short_s:,.0f}원</b>")
                if mid_s:
                    stops.append(f"중기(200MA) <b style='color:#ef4444;'>{mid_s:,.0f}원</b>")
                if stops:
                    st.markdown(
                        f"<div style='margin-top:0.5rem; padding:0.6rem 1rem; background:#1a0f0f; border-radius:8px; border-left:4px solid #ef4444;'>"
                        f"<span style='color:#fbbf24; font-weight:700;'>🛑 핵심 손절선:</span> "
                        f"<span style='color:#ddd;'>{' · '.join(stops)}</span></div>",
                        unsafe_allow_html=True
                    )

        # ─── 3) 상세: 피보 레벨 표 + Confluence 박스 ───────────────
        col1, col2 = st.columns([2, 1])
        with col1:
            if not fib:
                st.info("최근 120일 구간에서 의미있는 저점/고점을 찾지 못했습니다.")
            else:
                direction_label = "📈 상승추세 (저점→고점)" if fib['direction'] == 'up' else "📉 하락추세 (고점→저점)"
                st.markdown(f"**{direction_label}**")
                st.caption(fibonacci_summary_text(fib))
                # 레벨별 표시
                rows = []
                for lv in ('0.236', '0.382', '0.500', '0.618', '0.786'):
                    price = fib['levels'].get(lv)
                    if price is None:
                        continue
                    diff_pct = (close.iloc[-1] - price) / price * 100 if price else 0
                    rows.append({
                        '레벨': f"{float(lv)*100:.1f}%",
                        '가격': f"{price:,.0f}원",
                        '현재가 대비': f"{diff_pct:+.2f}%",
                    })
                if rows:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with col2:
            if conf and conf.get('matched'):
                ma200 = conf['ma200']
                zone = conf['price_zone']
                zone_color = {
                    '지지권': '#22c55e',
                    '저항권': '#ef4444',
                    '근접': '#f59e0b',
                    '중립': '#888',
                }.get(zone, '#888')
                matched_lines = "<br>".join([
                    f"• <b>{m['level']}</b> @ {m['price']:,.0f}원 (200MA와 {m['gap_pct']:.2f}% 차)"
                    for m in conf['matched']
                ])
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 12px; border: 2px solid {zone_color};'>
                    <p style='color: {zone_color}; margin: 0; font-weight: 700; font-size: 1.05rem;'>⚡ Confluence 감지: {zone}</p>
                    <p style='color: #ddd; margin: 0.5rem 0 0; font-size: 0.85rem;'>200MA: <b>{ma200:,.0f}원</b></p>
                    <p style='color: #ddd; margin: 0.5rem 0 0; font-size: 0.85rem;'>{matched_lines}</p>
                </div>
                """, unsafe_allow_html=True)
            elif len(close) >= 200:
                ma200 = float(close.rolling(200).mean().iloc[-1])
                st.markdown(f"""
                <div style='background: #1a1a2e; padding: 1rem; border-radius: 12px; border: 1px solid #333;'>
                    <p style='color: #888; margin: 0;'>200MA: {ma200:,.0f}원</p>
                    <p style='color: #888; margin: 0.5rem 0 0; font-size: 0.85rem;'>강한 confluence 없음 (일반 추세 종목)</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("200일 데이터 부족 (200일선 계산 불가)")

        # 면책 캡션
        st.caption("⚠️ 이 분석은 기술적 지표 기반 참고 자료입니다. 투자 추천이 아닙니다.")
    except Exception as e:
        # 분석 실패해도 페이지 전체는 영향 없게
        st.caption(f"피보나치 분석 일시 실패: {str(e)[:80]}")


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

        # 적자 여부 확인
        is_deficit = (per < 0) or (eps < 0)

        # 이익수익률 (Earnings Yield) = EPS / Price = 1/PER
        if per > 0:
            earnings_yield = (1 / per) * 100
        elif eps > 0 and price > 0:
            earnings_yield = (eps / price) * 100
        elif per < 0:
            # 적자: 음수 PER의 역수를 표시 (참고용)
            earnings_yield = (1 / per) * 100  # 음수값 유지
        else:
            earnings_yield = 0

        # ROE 추정 (= EPS / BPS)
        if bps > 0 and eps != 0:
            roe = (eps / bps) * 100  # 음수 EPS면 음수 ROE
        else:
            roe = 0

        # 점수 계산 (간소화 버전) - 적자면 0점
        # 이익수익률: 높을수록 좋음 (5% 이상이면 양호, 15%이면 만점)
        # 기존 10% 기준에서 15% 기준으로 완화 (더 현실적인 평가)
        ey_score = min(earnings_yield / 15 * 100, 100) if earnings_yield > 0 else 0
        # ROE: 버핏 기준 15% 이상이면 우수 (15%=100점, 기존 20%에서 완화)
        roe_score = min(roe / 15 * 100, 100) if roe > 0 else 0

        # 마법공식 종합 점수
        magic_score = (ey_score + roe_score) / 2 if (ey_score > 0 or roe_score > 0) else 0

        # 등급 결정
        if is_deficit:
            grade = "적자"
            grade_color = "#DC143C"
            grade_desc = "적자 기업"
        elif magic_score >= 70:
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

        # EY/ROE 표시 문자열
        ey_display = f"<span style='color: #DC143C;'>{earnings_yield:.2f}% (적자)</span>" if earnings_yield < 0 else f"{earnings_yield:.2f}%"
        roe_display = f"<span style='color: #DC143C;'>{roe:.2f}% (적자)</span>" if roe < 0 else f"{roe:.2f}%"

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
                    <span style='font-weight: 600;'>{ey_display}</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: {"#DC143C" if earnings_yield < 0 else "#667eea"}; height: 100%; width: {max(ey_score, 5) if earnings_yield != 0 else 0:.0f}%;'></div>
                </div>
            </div>
            <div>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>자본수익률 (ROE)</span>
                    <span style='font-weight: 600;'>{roe_display}</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: {"#DC143C" if roe < 0 else "#764ba2"}; height: 100%; width: {max(roe_score, 5) if roe != 0 else 0:.0f}%;'></div>
                </div>
            </div>
            <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                <span style='color: #888; font-size: 0.8rem;'>{"⚠️ 적자 기업 - 투자 주의 필요" if is_deficit else "💡 마법공식: 저평가 우량주 (EY↑, ROE↑)"}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # 멀티팩터 분석
        st.markdown("""<div style='background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'><span style='color: white; font-weight: 700;'>📈 멀티팩터 분석</span></div>""", unsafe_allow_html=True)

        # 밸류 점수 (PER, PBR 기반)
        # PER: 낮을수록 좋음 (10 이하면 만점, 30 이상이면 0점) - 적자(음수PER)는 별도 처리
        if per > 0:
            value_per_score = max(0, min(100, (30 - per) / 20 * 100))
        elif per < 0:
            # 적자 기업: PER 음수 - 밸류 점수 계산 불가, PBR만으로 판단
            value_per_score = 0
        else:
            value_per_score = 0

        # PBR: 낮을수록 좋음 (1 이하면 만점, 5 이상이면 0점)
        # 기존 3 기준에서 5로 확장 (성장주/IT주 등 고PBR 업종 반영)
        if pbr > 0:
            value_pbr_score = max(0, min(100, (5 - pbr) / 4 * 100))
        else:
            value_pbr_score = 0

        # 적자 기업은 PBR만으로 밸류 점수 계산
        if is_deficit and value_pbr_score > 0:
            value_score = value_pbr_score  # PBR만 사용
        else:
            value_score = (value_per_score + value_pbr_score) / 2 if (value_per_score > 0 or value_pbr_score > 0) else 0

        # 퀄리티 점수 (ROE 기반) - 적자면 0점
        quality_score = roe_score  # 마법공식에서 계산한 ROE 점수 재사용

        # 전체 멀티팩터 점수 (밸류 50% + 퀄리티 50%)
        multi_score = (value_score * 0.5 + quality_score * 0.5) if (value_score > 0 or quality_score > 0) else 0

        # 등급 결정
        if is_deficit:
            m_grade = "적자"
            m_grade_color = "#DC143C"
            m_grade_desc = "적자 기업"
        elif multi_score >= 70:
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

        # PER 표시 문자열
        per_display = f"<span style='color: #DC143C;'>PER {per:.1f} (적자)</span>" if per < 0 else f"PER {per:.1f}"
        roe_display_multi = f"<span style='color: #DC143C;'>ROE {roe:.1f}% (적자)</span>" if roe < 0 else f"ROE {roe:.1f}%"

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
                <div style='color: #888; font-size: 0.75rem; margin-top: 0.2rem;'>{per_display} | PBR {pbr:.2f}</div>
            </div>
            <div>
                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                    <span style='color: #666;'>퀄리티 팩터</span>
                    <span style='font-weight: 600;'>{quality_score:.0f}점</span>
                </div>
                <div style='background: #e9ecef; border-radius: 4px; height: 6px; overflow: hidden;'>
                    <div style='background: {"#DC143C" if roe < 0 else "#f093fb"}; height: 100%; width: {max(quality_score, 5) if roe != 0 else 0:.0f}%;'></div>
                </div>
                <div style='color: #888; font-size: 0.75rem; margin-top: 0.2rem;'>{roe_display_multi}</div>
            </div>
            <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                <span style='color: #888; font-size: 0.8rem;'>{"⚠️ 적자 기업 - PBR 기준 밸류만 유효" if is_deficit else "💡 멀티팩터: 밸류(저PER,저PBR) + 퀄리티(고ROE)"}</span>
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
            macd_status = chart_analysis.get('macd_status', '-')
            macd_color = chart_analysis.get('macd_color', '#888')
            williams_r = chart_analysis.get('williams_r', -50)
            williams_r_status = chart_analysis.get('williams_r_status', '-')
            williams_r_color = chart_analysis.get('williams_r_color', '#888')
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
                        <span style='color: #666; font-size: 0.85rem;'>MACD</span>
                        <span style='font-weight: 600; color: {macd_color}; font-size: 0.85rem;'>{macd_status}</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>볼린저밴드</span>
                        <span style='font-weight: 600; color: {bb_color}; font-size: 0.85rem;'>{bb_status}</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <span style='color: #666; font-size: 0.85rem;'>Williams %R</span>
                        <span style='font-weight: 600; color: {williams_r_color}; font-size: 0.85rem;'>{williams_r:.1f} ({williams_r_status})</span>
                    </div>
                </div>
                <div style='margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed #e0e0e0;'>
                    <span style='color: #888; font-size: 0.8rem;'>💡 기술분석: 이평선, 거래량, RSI, MACD, BB, Williams %R</span>
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

    # ========== 추가 퀀트 지표 (F-Score, GP/A, 시가총액 필터) ==========
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    with st.expander("📊 추가 퀀트 지표 (F-Score, GP/A, 소형주 필터)", expanded=False):
        add_col1, add_col2, add_col3 = st.columns(3)

        # === F-Score 간소화 버전 (4점 만점) ===
        with add_col1:
            st.markdown("**🏆 F-Score (간소화)**")

            f_score = 0
            f_details = []

            # F1: ROA > 0 (순이익 양수)
            if eps > 0:
                f_score += 1
                f_details.append(("ROA 양수", True))
            else:
                f_details.append(("ROA 양수", False))

            # F2: 영업현금흐름 양수 추정 (EPS > 0이고 PER < 30이면 양호로 추정)
            if eps > 0 and per > 0 and per < 30:
                f_score += 1
                f_details.append(("현금흐름 양호", True))
            else:
                f_details.append(("현금흐름 양호", False))

            # F3: ROE 개선 (ROE > 10%면 양호로 추정)
            if roe > 10:
                f_score += 1
                f_details.append(("ROE 양호(>10%)", True))
            else:
                f_details.append(("ROE 양호(>10%)", False))

            # F4: 저부채 (PBR < 3이면 자본효율 양호로 추정)
            if pbr > 0 and pbr < 3:
                f_score += 1
                f_details.append(("자본효율 양호", True))
            else:
                f_details.append(("자본효율 양호", False))

            # F-Score 등급 (4점 만점)
            if f_score >= 4:
                f_grade = "A"
                f_color = "#38ef7d"
                f_desc = "우수"
            elif f_score >= 3:
                f_grade = "B"
                f_color = "#FFD700"
                f_desc = "양호"
            elif f_score >= 2:
                f_grade = "C"
                f_color = "#FFA500"
                f_desc = "보통"
            else:
                f_grade = "D"
                f_color = "#FF6B6B"
                f_desc = "미흡"

            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 0.8rem; border-radius: 8px; border: 1px solid #e0e0e0;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;'>
                    <span style='font-weight: 600;'>F-Score</span>
                    <span style='background: {f_color}; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 700;'>{f_score}/4 ({f_grade})</span>
                </div>
            """, unsafe_allow_html=True)

            for item, passed in f_details:
                icon = "✅" if passed else "❌"
                st.markdown(f"<span style='font-size: 0.85rem;'>{icon} {item}</span>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("💡 Piotroski F-Score 간소화 버전 (원본 9점→4점)")

        # === GP/A 퀄리티 팩터 ===
        with add_col2:
            st.markdown("**📈 GP/A (퀄리티)**")

            # GP/A 추정: 매출총이익/자산 ≈ (EPS * 발행주식수) / 시가총액 * PBR
            # 간소화: ROE * (1 - 세율) ≈ 수익성 지표로 대체
            # 실제로는 매출총이익 데이터가 필요하지만, EPS/BPS 비율로 근사
            market_cap = info.get('market_cap', 0)

            if bps > 0 and eps != 0:
                # 추정 GP/A = (순이익률 추정) * 회전율 근사
                gpa_estimate = abs(eps / bps) * 100  # ROE를 GP/A 근사치로 사용
            else:
                gpa_estimate = 0

            # GP/A 등급 (높을수록 좋음)
            if gpa_estimate >= 20:
                gpa_grade = "A"
                gpa_color = "#38ef7d"
                gpa_desc = "고품질"
            elif gpa_estimate >= 10:
                gpa_grade = "B"
                gpa_color = "#FFD700"
                gpa_desc = "양호"
            elif gpa_estimate >= 5:
                gpa_grade = "C"
                gpa_color = "#FFA500"
                gpa_desc = "보통"
            else:
                gpa_grade = "D"
                gpa_color = "#FF6B6B"
                gpa_desc = "저품질"

            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 0.8rem; border-radius: 8px; border: 1px solid #e0e0e0;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;'>
                    <span style='font-weight: 600;'>GP/A 추정</span>
                    <span style='background: {gpa_color}; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 700;'>{gpa_estimate:.1f}% ({gpa_grade})</span>
                </div>
                <div style='font-size: 0.85rem; color: #666;'>
                    <div>• 등급: {gpa_desc}</div>
                    <div>• ROE 기반 추정치</div>
                    <div>• 높을수록 수익성 우수</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption("💡 GP/A: 매출총이익/자산 (ROE 기반 추정)")

        # === 소형주 필터 + 업종 PER ===
        with add_col3:
            st.markdown("**🎯 투자 필터**")

            # 시가총액 분류
            if market_cap > 0:
                if market_cap >= 10e12:  # 10조 이상
                    cap_category = "대형주"
                    cap_color = "#667eea"
                    cap_bonus = 0
                elif market_cap >= 1e12:  # 1조 이상
                    cap_category = "중형주"
                    cap_color = "#11998e"
                    cap_bonus = 5
                elif market_cap >= 3000e8:  # 3000억 이상
                    cap_category = "중소형주"
                    cap_color = "#FFD700"
                    cap_bonus = 10
                else:
                    cap_category = "소형주"
                    cap_color = "#f5576c"
                    cap_bonus = 15  # 마법공식 소형주 프리미엄
                cap_str = f"{market_cap/1e8:,.0f}억"
            else:
                cap_category = "N/A"
                cap_color = "#888"
                cap_bonus = 0
                cap_str = "N/A"

            # 업종 평균 PER 대비 (간소화: 시장 평균 15 기준)
            market_avg_per = 15  # KOSPI 평균 PER 근사
            if per > 0:
                per_vs_market = ((per - market_avg_per) / market_avg_per) * 100
                if per_vs_market < -30:
                    per_status = "크게 저평가"
                    per_color = "#38ef7d"
                elif per_vs_market < 0:
                    per_status = "저평가"
                    per_color = "#FFD700"
                elif per_vs_market < 30:
                    per_status = "적정"
                    per_color = "#FFA500"
                else:
                    per_status = "고평가"
                    per_color = "#FF6B6B"
            elif per < 0:
                per_vs_market = 0
                per_status = "적자 (N/A)"
                per_color = "#DC143C"
            else:
                per_vs_market = 0
                per_status = "N/A"
                per_color = "#888"

            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 0.8rem; border-radius: 8px; border: 1px solid #e0e0e0;'>
                <div style='margin-bottom: 0.5rem;'>
                    <span style='color: #666; font-size: 0.85rem;'>시가총액 분류</span>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <span style='font-weight: 600;'>{cap_str}</span>
                        <span style='background: {cap_color}; color: white; padding: 0.15rem 0.5rem; border-radius: 8px; font-size: 0.8rem;'>{cap_category}</span>
                    </div>
                </div>
                <div style='margin-bottom: 0.5rem;'>
                    <span style='color: #666; font-size: 0.85rem;'>PER vs 시장평균(15)</span>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <span style='font-weight: 600;'>{per_vs_market:+.1f}%</span>
                        <span style='color: {per_color}; font-weight: 600;'>{per_status}</span>
                    </div>
                </div>
                <div style='font-size: 0.8rem; color: #888; border-top: 1px dashed #ddd; padding-top: 0.4rem; margin-top: 0.3rem;'>
                    💡 소형주 마법공식 보너스: +{cap_bonus}점
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption("💡 소형주에서 마법공식 효과 극대화")

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

        # 등락 배지 색상
        badge_bg = "#FF4444" if change_rate >= 0 else "#4444FF"

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>현재가</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{info['price']:,}원</p>
                <span style='background: {badge_bg}; color: white; padding: 0.25rem 0.6rem; border-radius: 4px; font-weight: 700; font-size: 0.95rem;'>{rate_text}</span>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            cap = info['market_cap']
            cap_str = f"{cap/1e12:.1f}조" if cap >= 1e12 else f"{cap/1e8:.0f}억"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>시가총액</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{cap_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            # PER: 적자 기업(음수 PER)도 표시
            per_val = info['per']
            if per_val > 0:
                per_color = "white"
                per_str = f"{per_val:.2f}"
            elif per_val < 0:
                per_color = "#DC143C"
                per_str = f"{per_val:.2f}"
            else:
                per_color = "white"
                per_str = "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>PER</p>
                <p style='color: {per_color}; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{per_str}</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            # EPS: 적자 기업도 음수로 표시 (0이면 N/A)
            eps_val = info['eps']
            if eps_val != 0:
                eps_color = "#DC143C" if eps_val < 0 else "white"
                eps_str = f"{eps_val:,.0f}원"
            else:
                eps_color = "white"
                eps_str = "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>EPS</p>
                <p style='color: {eps_color}; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{eps_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            bps_str = f"{info['bps']:,.0f}원" if info['bps'] > 0 else "-"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>BPS</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{bps_str}</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            vol = info['volume']
            vol_str = f"{vol/10000:,.0f}만" if vol >= 10000 else f"{vol:,}"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                <p style='color: #888; margin: 0; font-size: 0.85rem;'>거래량</p>
                <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{vol_str}</p>
            </div>
            """, unsafe_allow_html=True)

        # 상장주식수 + 섹터 행 추가
        try:
            from data.market_data_cache import (
                get_market_cap_for, format_shares, format_market_cap,
                get_detailed_sector_cached, get_sector_cached,
            )
            _cap = get_market_cap_for(code) or {}
            shares_val = int(_cap.get('shares', 0))
            cap_val = int(_cap.get('market_cap', 0))
            _sec_info = get_detailed_sector_cached(code) or {}
            sector_text = _sec_info.get('sub_sector') or _sec_info.get('sector') or get_sector_cached(code)
            industry_text = _sec_info.get('industry') or ''
        except Exception:
            shares_val = 0
            cap_val = 0
            sector_text = '기타'
            industry_text = ''
        if shares_val or cap_val:
            st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                    <p style='color: #888; margin: 0; font-size: 0.85rem;'>상장주식수</p>
                    <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.3rem 0;'>{format_shares(shares_val)}</p>
                </div>
                """, unsafe_allow_html=True)
            with sc2:
                # 정확한 시총 (pykrx 기반, 원 단위)
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                    <p style='color: #888; margin: 0; font-size: 0.85rem;'>시가총액 (정확)</p>
                    <p style='color: white; font-size: 1.5rem; font-weight: 700; margin: 0.3rem 0;'>{format_market_cap(cap_val)}</p>
                </div>
                """, unsafe_allow_html=True)
            with sc3:
                # 1주당 시총 비율 = 현재가 검증용 (참고)
                price_val = info.get('price', 0)
                ratio_str = "-"
                if shares_val > 0 and cap_val > 0:
                    implied_price = cap_val / shares_val
                    diff_pct = ((price_val - implied_price) / implied_price * 100) if implied_price else 0
                    ratio_str = f"{implied_price:,.0f}원 ({diff_pct:+.1f}%)"
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.2rem; border-radius: 16px; border: 1px solid #333;'>
                    <p style='color: #888; margin: 0; font-size: 0.85rem;'>시총÷주식수</p>
                    <p style='color: white; font-size: 1.1rem; font-weight: 700; margin: 0.3rem 0;'>{ratio_str}</p>
                </div>
                """, unsafe_allow_html=True)

            # 섹터 / 주요 분야 한 줄 카드 (네이버 금융 출처)
            if sector_text and sector_text != '기타':
                detail_line = f" <span style='color: #888; font-size: 0.9rem;'>· {industry_text}</span>" if industry_text and industry_text != sector_text else ""
                st.markdown(f"""
                <div style='margin-top: 0.8rem; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 0.9rem 1.2rem; border-radius: 12px; border-left: 4px solid #5856D6;'>
                    <span style='color: #888; font-size: 0.8rem;'>🏷️ 섹터 / 주요 분야</span>
                    <span style='color: white; font-size: 1.05rem; font-weight: 600; margin-left: 0.6rem;'>{sector_text}</span>
                    {detail_line}
                </div>
                """, unsafe_allow_html=True)
    elif not realtime_displayed:
        # REST API도 실패하고 WebSocket도 없는 경우
        st.warning("종목 정보를 불러올 수 없습니다.")
        return

    # info가 없어도 realtime이 있으면 계속 진행
    if not info:
        info = {}

    # 투자자별 매매동향 표시 (개인/기관/외국인)
    st.markdown("---")
    st.markdown("#### 📊 투자자별 매매동향")
    render_investor_trend(api, code, stock_name, days=5, key_prefix=f"home_inv_{code}")

    # 마법공식 & 멀티팩터 분석 섹션
    _render_quant_analysis_section(api, info, code, stock_name)

    # 200MA + 피보나치 confluence 분석
    _render_fib_ma200_section(api, code, stock_name)

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
                # 5일, 20일, 60일, 120일선 기본 선택
                # 기본 선택: 5/20/60/120/200 (200일선은 장기추세 기준 — 항상 기본 표시)
                if st.checkbox(label, value=(ma_key in ['MA5', 'MA20', 'MA60', 'MA120', 'MA200']), key=f"{ma_key}_{code}"):
                    selected_mas.append(ma_key)

    with col2:
        st.markdown("**📊 보조지표**")
        indicator_cols = st.columns(5)
        selected_indicators = []
        for i, (ind_key, ind_name) in enumerate(INDICATOR_OPTIONS.items()):
            with indicator_cols[i]:
                if st.checkbox(ind_name, value=(ind_key == 'bollinger'), key=f"{ind_key}_{code}"):
                    selected_indicators.append(ind_key)
        # 매물대 옵션
        with indicator_cols[4]:
            show_volume_profile = st.checkbox("매물대", value=True, key=f"vp_{code}")

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

        # 매물대 표시 여부에 따라 레이아웃 결정
        if show_volume_profile:
            # 2열 레이아웃: 왼쪽 차트(85%), 오른쪽 매물대(15%)
            fig = make_subplots(
                rows=total_rows, cols=2,
                shared_xaxes=True,
                shared_yaxes=True,  # 가격 축 공유
                vertical_spacing=0.02,
                horizontal_spacing=0.01,
                row_heights=row_heights,
                column_widths=[0.85, 0.15],
                specs=[[{"secondary_y": False}, {"secondary_y": False}] for _ in range(total_rows)]
            )
        else:
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
                line=dict(width=1),
                whiskerwidth=0.8
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

        # 이동평균선 (200일선은 두껍게 — 장기추세 기준)
        for ma_key in selected_mas:
            period_val, color, label = MA_OPTIONS[ma_key]
            if len(chart_data) >= period_val:
                ma_values = chart_data['close'].rolling(window=period_val).mean()
                line_w = 2.5 if period_val == 200 else 1.5
                fig.add_trace(go.Scatter(
                    x=chart_data[time_col], y=ma_values,
                    mode='lines', name=label,
                    line=dict(color=color, width=line_w)
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

        # 스윙 포인트 (저점/고점 마커) - 캔들차트에만 표시
        if chart_style == '캔들차트' and len(chart_data) >= 10:
            swing_order = 3 if len(chart_data) < 100 else 5
            swing_high_idx, swing_low_idx = detect_swing_points(chart_data, order=swing_order)

            price_range = chart_data['high'].max() - chart_data['low'].min()
            marker_offset = price_range * 0.02

            # 저점 마커
            if len(swing_low_idx) > 0:
                recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                low_dates = chart_data[time_col].iloc[recent_low_idx]
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
                high_dates = chart_data[time_col].iloc[recent_high_idx]
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

            # 상승 추세선 (저점 연결) - 최근 저점이 2개 이상이고 상승 추세일 때
            if len(swing_low_idx) >= 2:
                try:
                    recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                    low_x = list(recent_lows)
                    low_y = [chart_data['low'].iloc[i] for i in recent_lows]

                    slope, intercept, _, _, _ = stats.linregress(low_x, low_y)

                    # 상승 추세선만 표시 (기울기 > 0)
                    if slope > 0:
                        # 추세선을 차트 전체에 걸쳐 그리기
                        x_start = swing_low_idx[0] if len(swing_low_idx) > 0 else 0
                        x_end = len(chart_data) - 1
                        y_start = slope * x_start + intercept
                        y_end = slope * x_end + intercept

                        # Y값 클리핑 (차트 범위 내로 제한)
                        y_start = max(price_low - price_margin, min(price_high + price_margin, y_start))
                        y_end = max(price_low - price_margin, min(price_high + price_margin, y_end))

                        fig.add_trace(go.Scatter(
                            x=[chart_data[time_col].iloc[x_start], chart_data[time_col].iloc[x_end]],
                            y=[y_start, y_end],
                            mode='lines',
                            name='상승 추세선',
                            line=dict(color='#00C853', width=2, dash='solid'),
                            hovertemplate='상승 추세선<extra></extra>',
                            showlegend=True
                        ), row=1, col=1)
                except:
                    pass

            # 하락 추세선 (고점 연결) - 최근 고점이 2개 이상이고 하락 추세일 때
            if len(swing_high_idx) >= 2:
                try:
                    recent_highs = swing_high_idx[-5:] if len(swing_high_idx) >= 5 else swing_high_idx
                    high_x = list(recent_highs)
                    high_y = [chart_data['high'].iloc[i] for i in recent_highs]

                    slope, intercept, _, _, _ = stats.linregress(high_x, high_y)

                    # 하락 추세선만 표시 (기울기 < 0)
                    if slope < 0:
                        x_start = swing_high_idx[0] if len(swing_high_idx) > 0 else 0
                        x_end = len(chart_data) - 1
                        y_start = slope * x_start + intercept
                        y_end = slope * x_end + intercept

                        # Y값 클리핑 (차트 범위 내로 제한)
                        y_start = max(price_low - price_margin, min(price_high + price_margin, y_start))
                        y_end = max(price_low - price_margin, min(price_high + price_margin, y_end))

                        fig.add_trace(go.Scatter(
                            x=[chart_data[time_col].iloc[x_start], chart_data[time_col].iloc[x_end]],
                            y=[y_start, y_end],
                            mode='lines',
                            name='하락 추세선',
                            line=dict(color='#FF3B30', width=2, dash='solid'),
                            hovertemplate='하락 추세선<extra></extra>',
                            showlegend=True
                        ), row=1, col=1)
                except:
                    pass

        # 매물대 (Volume Profile) - 우측에 가로 막대 차트
        if show_volume_profile:
            price_levels, volumes, poc_price = calculate_volume_profile(chart_data, num_bins=30)
            if price_levels and volumes:
                # 거래량 정규화 (최대값 기준 %)
                max_vol = max(volumes) if max(volumes) > 0 else 1
                norm_volumes = [v / max_vol * 100 for v in volumes]

                # 매물대 색상 (POC는 강조)
                vp_colors = []
                for i, pl in enumerate(price_levels):
                    if poc_price and abs(pl - poc_price) < (price_levels[1] - price_levels[0]):
                        vp_colors.append('rgba(255, 193, 7, 0.9)')  # POC - 노란색
                    else:
                        vp_colors.append('rgba(102, 126, 234, 0.6)')  # 일반 - 보라색

                fig.add_trace(go.Bar(
                    y=price_levels,
                    x=norm_volumes,
                    orientation='h',
                    name='매물대',
                    marker_color=vp_colors,
                    showlegend=True,
                    hovertemplate='가격: %{y:,.0f}원<br>거래량: %{customdata:,.0f}<extra></extra>',
                    customdata=volumes
                ), row=1, col=2)

                # POC 라인 (가격 차트에 표시)
                if poc_price:
                    fig.add_hline(
                        y=poc_price, line_dash="dash",
                        line_color="rgba(255, 193, 7, 0.8)", line_width=1.5,
                        annotation_text=f"POC {poc_price:,.0f}",
                        annotation_position="left",
                        row=1, col=1
                    )

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

        # 매물대 축 설정 (우측 패널)
        if show_volume_profile:
            fig.update_xaxes(showticklabels=False, showgrid=False, row=1, col=2)
            fig.update_yaxes(showticklabels=False, showgrid=False, row=1, col=2)
            # 다른 행의 2열 숨기기
            for row in range(2, total_rows + 1):
                fig.update_xaxes(visible=False, row=row, col=2)
                fig.update_yaxes(visible=False, row=row, col=2)

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

        # ========== 매매 신호 세분화 표시 (새로 추가) ==========
        st.markdown("---")
        st.markdown("#### 💡 상세 매매 신호 (AI 기술적 분석)")

        # 보유 평균가 입력 UI
        col_hold1, col_hold2 = st.columns([3, 1])
        with col_hold1:
            holding_price_input = st.number_input(
                "📊 보유 평균가 입력 (선택사항)",
                min_value=0,
                value=0,
                step=100,
                help="보유 중인 종목이라면 평균 매수가를 입력하세요. 익절/손절 가이드가 제공됩니다.",
                key=f"holding_price_{code}"
            )
        with col_hold2:
            st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
            if holding_price_input > 0:
                st.success(f"✅ {holding_price_input:,.0f}원")

        # 보유가 입력 여부에 따라 분석
        holding_price = holding_price_input if holding_price_input > 0 else None

        try:
            from dashboard.utils.indicators import get_enhanced_trading_signal

            signal_result = get_enhanced_trading_signal(chart_data, holding_price=holding_price)
        except Exception as e:
            st.error(f"매매 신호 분석 오류: {str(e)}")
            signal_result = None

        if signal_result:
            # 신호 타입별 색상 및 이모지
            signal_colors = {
                'strong_buy': ('#00C853', '🟢', 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'),
                'buy': ('#4CAF50', '🟢', 'linear-gradient(135deg, #56ab2f 0%, #a8e063 100%)'),
                'stable_buy': ('#8BC34A', '🟡', 'linear-gradient(135deg, #7f7fd5 0%, #86a8e7 100%)'),
                'hold': ('#FFC107', '⚪', 'linear-gradient(135deg, #FFB75E 0%, #ED8F03 100%)'),
                'sell': ('#FF5722', '🔴', 'linear-gradient(135deg, #f12711 0%, #f5af19 100%)'),
                'strong_sell': ('#F44336', '🔴', 'linear-gradient(135deg, #c31432 0%, #240b36 100%)')
            }

            signal_type = signal_result['signal_type']
            signal_name = signal_result['signal_name']
            confidence = signal_result['confidence']
            strategy = signal_result['strategy']
            indicators = signal_result['indicators']

            color, emoji, gradient = signal_colors.get(signal_type, ('#888', '⚪', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'))

            # 신호 카드
            col1, col2, col3 = st.columns([2, 2, 3])

            with col1:
                st.markdown(f"""
                <div style='background: {gradient}; padding: 1.5rem; border-radius: 16px; text-align: center; border: 2px solid {color};'>
                    <p style='color: white; margin: 0; font-size: 1rem; opacity: 0.9;'>매매 신호</p>
                    <p style='color: white; font-size: 2.5rem; font-weight: 700; margin: 0.5rem 0;'>{emoji} {signal_name}</p>
                    <p style='color: white; margin: 0; font-size: 0.9rem; opacity: 0.8;'>신뢰도: {confidence:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                # 가격 정보 (분할 매수)
                entry_price = signal_result.get('entry_price')
                entry_price_2 = signal_result.get('entry_price_2')
                entry_price_3 = signal_result.get('entry_price_3')
                stop_loss = signal_result.get('stop_loss')
                target_price = signal_result.get('target_price')

                price_html = "<div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.5rem; border-radius: 16px; border: 1px solid #333;'>"
                if entry_price:
                    # 신호 타입에 따라 제목 변경
                    if signal_type in ['sell', 'strong_sell']:
                        price_html += f"<p style='color: #f5576c; margin: 0 0 0.5rem 0; font-size: 0.85rem;'>📉 매도 권장 - 반등 조건</p>"
                    elif signal_type == 'hold':
                        price_html += f"<p style='color: #FFC107; margin: 0 0 0.5rem 0; font-size: 0.85rem;'>⏳ 조건부 진입 전략</p>"
                    else:
                        price_html += f"<p style='color: #888; margin: 0 0 0.5rem 0; font-size: 0.85rem;'>📊 분할 매수 전략</p>"

                    price_html += f"<p style='color: #11998e; font-size: 1.2rem; font-weight: 700; margin: 0.2rem 0;'>1차: {entry_price:,.0f}원</p>"
                    if entry_price_2:
                        price_html += f"<p style='color: #38ef7d; font-size: 1.1rem; font-weight: 600; margin: 0.2rem 0;'>2차: {entry_price_2:,.0f}원</p>"
                    if entry_price_3:
                        price_html += f"<p style='color: #56ab2f; font-size: 1.0rem; font-weight: 500; margin: 0.2rem 0;'>3차: {entry_price_3:,.0f}원</p>"
                    price_html += "<hr style='border: none; border-top: 1px solid #333; margin: 0.5rem 0;'>"
                if stop_loss:
                    price_html += f"<p style='color: #f5576c; font-size: 0.9rem; margin: 0.2rem 0;'>🛑 손절가: {stop_loss:,.0f}원</p>"
                if target_price:
                    price_html += f"<p style='color: #667eea; font-size: 0.9rem; margin: 0.2rem 0;'>🎯 목표가: {target_price:,.0f}원</p>"
                price_html += "</div>"
                st.markdown(price_html, unsafe_allow_html=True)

            with col3:
                # 전략 설명 및 지표
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.5rem; border-radius: 16px; border: 1px solid #333;'>
                    <p style='color: white; font-weight: 600; margin: 0 0 0.5rem 0; font-size: 0.95rem;'>{strategy}</p>
                    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.85rem;'>
                        <div><span style='color: #888;'>RSI:</span> <span style='color: white;'>{indicators['rsi']:.1f}</span></div>
                        <div><span style='color: #888;'>MACD:</span> <span style='color: white;'>{indicators['macd']:.2f}</span></div>
                        <div><span style='color: #888;'>BB위치:</span> <span style='color: white;'>{indicators['bb_position']:.1f}%</span></div>
                        <div><span style='color: #888;'>거래량:</span> <span style='color: white;'>{indicators['volume_ratio']:.1f}배</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # === 추가 정보: 시장 환경 & 거래량 추세 ===
            st.markdown("---")
            col_m1, col_m2, col_m3 = st.columns(3)

            with col_m1:
                # 시장 리스크
                market_risk_kr = signal_result.get('market_risk_kr', '➖ 중립')
                market_comment = signal_result.get('market_comment', '시장 방향성 확인')
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                    <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>시장 환경</p>
                    <p style='color: white; font-size: 1.1rem; font-weight: 600; margin: 0.3rem 0;'>{market_risk_kr}</p>
                    <p style='color: #95a5a6; margin: 0; font-size: 0.75rem;'>{market_comment}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_m2:
                # 거래량 추세
                volume_trend_kr = signal_result.get('volume_trend_kr', '거래량 안정')
                volume_change_3d = signal_result.get('volume_change_3d', 0)
                volume_trend = signal_result.get('volume_trend', 'stable')

                trend_color = '#11998e' if volume_trend in ['surge', 'increasing'] else '#f5576c' if volume_trend == 'decreasing' else '#888'

                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                    <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>거래량 추세</p>
                    <p style='color: {trend_color}; font-size: 1.1rem; font-weight: 600; margin: 0.3rem 0;'>{volume_trend_kr}</p>
                    <p style='color: #95a5a6; margin: 0; font-size: 0.75rem;'>3일 평균 변화</p>
                </div>
                """, unsafe_allow_html=True)

            with col_m3:
                # 매도 가이드 (보유 중인 경우만)
                sell_guide_kr = signal_result.get('sell_guide_kr')

                if sell_guide_kr:
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                        <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>보유 가이드</p>
                        <p style='color: white; font-size: 1.0rem; font-weight: 600; margin: 0.3rem 0;'>{sell_guide_kr}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                        <p style='color: #95a5a6; margin: 0; font-size: 0.85rem;'>보유 가이드</p>
                        <p style='color: #7f8c8d; font-size: 0.9rem; font-weight: 500; margin: 0.3rem 0;'>신규 매매 분석</p>
                    </div>
                    """, unsafe_allow_html=True)

            # 출처 표시
            st.caption("📚 **신호 출처:** [볼린저밴드 가이드](https://www.xs.com/ko/blog/볼린저밴드/), [RSI/MACD 분석](https://moneyrecipe.blog/rsi-macd-bollingerband-limitations/), [기술적 분석 지표](https://jackerlab.com/futures-trading-technical-indicators-timeframe-guide/) | 💡 **개선:** ChatGPT 전문가 인사이트 반영")

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
    """일봉/주봉/월봉 데이터 조회 (재시도 로직 포함)

    Args:
        _api: API 인스턴스
        code: 종목코드
        days: 조회 일수
        period: D(일봉), W(주봉), M(월봉)
    """
    import sys
    import time

    max_retries = 3
    retry_delay = 1.0

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    period_name = {'D': '일봉', 'W': '주봉', 'M': '월봉'}.get(period, '일봉')

    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] {period_name} 요청: {code}, {start}~{end} (시도 {attempt+1}/{max_retries})", file=sys.stderr)

            # 토큰 갱신 시도
            if hasattr(_api, '_ensure_token'):
                _api._ensure_token()

            df = _api.get_daily_price(code, start, end, period=period)
            if df is None or df.empty:
                print(f"[DEBUG] {period_name} 데이터 없음: {code}", file=sys.stderr)
                return pd.DataFrame()
            print(f"[DEBUG] {period_name} 데이터 {len(df)}개 로드: {code}", file=sys.stderr)
            return df

        except (BrokenPipeError, ConnectionError, ConnectionResetError) as e:
            print(f"[DEBUG] {period_name} 연결 오류 (시도 {attempt+1}): {code}, {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                if hasattr(_api, 'access_token'):
                    _api.access_token = None  # 토큰 강제 갱신
                continue
            return pd.DataFrame()

        except Exception as e:
            print(f"[DEBUG] {period_name} 데이터 로드 오류: {code}, {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return pd.DataFrame()

    return pd.DataFrame()


def _get_minute_chart_data(_api, code: str, minute: int) -> pd.DataFrame:
    """분봉 데이터 조회 (재시도 로직 포함)"""
    import sys
    import time

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] 분봉 요청: {code}, {minute}분 (시도 {attempt+1}/{max_retries})", file=sys.stderr)

            if hasattr(_api, '_ensure_token'):
                _api._ensure_token()

            df = _api.get_minute_price(code, minute)
            if df is None or df.empty:
                print(f"[DEBUG] 분봉 데이터 없음: {code}, {minute}분", file=sys.stderr)
                return pd.DataFrame()
            print(f"[DEBUG] 분봉 데이터 {len(df)}개 로드: {code}", file=sys.stderr)
            return df

        except (BrokenPipeError, ConnectionError, ConnectionResetError) as e:
            print(f"[DEBUG] 분봉 연결 오류 (시도 {attempt+1}): {code}, {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                if hasattr(_api, 'access_token'):
                    _api.access_token = None
                continue
            return pd.DataFrame()

        except Exception as e:
            print(f"[DEBUG] 분봉 데이터 로드 오류: {code}, {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return pd.DataFrame()

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


# (관심종목 실시간 모니터링 섹션 제거됨)

# ========== 스윙매매 시그널 요약 카드 ==========

def _render_swing_signal_summary(api):
    """스윙매매 시그널 요약 카드 (태쏘 전략 포함)"""

    st.markdown("### 🎯 스윙매매 시그널 요약")
    st.caption("태쏘 스윙투자 전략 기반 - 박스권 돌파, 신고가 추세, 스윙 패턴 요약")

    # 세션 캐시 키
    cache_key = 'swing_signal_summary'
    cache_time_key = 'swing_signal_summary_time'

    # 캐시 유효시간 (10분)
    cache_valid = False
    if cache_key in st.session_state and cache_time_key in st.session_state:
        elapsed = (datetime.now() - st.session_state[cache_time_key]).total_seconds()
        if elapsed < 600:  # 10분
            cache_valid = True

    # 분석 모드 선택 및 버튼
    col_mode, col_refresh, col_info = st.columns([2, 1, 2])

    with col_mode:
        scan_mode = st.radio(
            "분석 범위",
            ["시총 상위 50개", "전종목 (KOSPI+KOSDAQ)"],
            horizontal=True,
            key="swing_scan_mode",
            help="전종목 분석은 시간이 오래 걸릴 수 있습니다 (약 2,500개 종목)"
        )
        full_scan = scan_mode == "전종목 (KOSPI+KOSDAQ)"

    # 분석 시작 플래그
    start_analysis_key = 'swing_start_analysis'
    start_analysis = False

    with col_refresh:
        if st.button("🔄 분석 시작", key="refresh_swing_summary"):
            start_analysis = True
            # 분석 모드가 바뀌었거나 새로 시작하면 캐시 무효화
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            cache_valid = False

    # 분석 모드가 바뀌면 캐시 무효화 (단, 자동 분석은 시작하지 않음)
    mode_key = 'swing_last_scan_mode'
    if mode_key in st.session_state and st.session_state[mode_key] != full_scan:
        cache_valid = False
        if cache_key in st.session_state:
            del st.session_state[cache_key]
    st.session_state[mode_key] = full_scan

    with col_info:
        if cache_valid and cache_time_key in st.session_state:
            summary_cached = st.session_state.get(cache_key, {})
            scanned = summary_cached.get('total_scanned', 0)
            mode_text = "전종목" if summary_cached.get('scan_mode') == 'full' else "상위 50"
            st.caption(f"마지막 업데이트: {st.session_state[cache_time_key].strftime('%H:%M:%S')} ({mode_text}, {scanned:,}개 분석)")

    if not api:
        st.warning("API 연결이 필요합니다.")
        return

    # 캐시 데이터 사용 또는 새로 분석 (버튼 클릭 시에만 분석 시작)
    if cache_valid and cache_key in st.session_state:
        summary = st.session_state[cache_key]
    elif start_analysis:
        # "분석 시작" 버튼을 클릭했을 때만 분석 실행
        if full_scan:
            # 전종목 분석: 진행률 표시
            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            status_placeholder.info("🔍 전종목 스윙 시그널 분석 중... (병렬 처리)")
            progress_bar = progress_placeholder.progress(0, text="분석 준비 중...")

            def update_progress(completed, total):
                pct = int(completed / total * 100)
                progress_bar.progress(pct / 100, text=f"분석 중... {completed:,}/{total:,} ({pct}%)")

            summary = _analyze_swing_signals_quick(api, full_scan=True, progress_callback=update_progress)

            progress_placeholder.empty()
            status_placeholder.empty()
        else:
            # 빠른 분석: 스피너만 표시
            with st.spinner("주요 종목 스윙 시그널 분석 중..."):
                summary = _analyze_swing_signals_quick(api, full_scan=False)

        st.session_state[cache_key] = summary
        st.session_state[cache_time_key] = datetime.now()
    else:
        # 캐시도 없고 버튼도 안 눌렀으면 안내 메시지만 표시
        st.info("👆 '분석 시작' 버튼을 클릭하여 스윙 시그널 분석을 시작하세요.")
        return

    if not summary:
        st.info("분석 결과가 없습니다.")
        return

    # 요약 카드 4개 표시
    col1, col2, col3, col4 = st.columns(4)

    signal_types = [
        ("box_breakout", "📦 박스 돌파", summary.get('box_breakout_count', 0), summary.get('box_breakout_stocks', []), "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"),
        ("new_high", "🚀 신고가", summary.get('new_high_count', 0), summary.get('new_high_stocks', []), "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"),
        ("double_bottom", "📐 쌍바닥", summary.get('double_bottom_count', 0), summary.get('double_bottom_stocks', []), "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"),
        ("pullback", "📈 눌림목", summary.get('pullback_count', 0), summary.get('pullback_stocks', []), "linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%)")
    ]

    for col, (signal_key, title, count, stocks, gradient) in zip([col1, col2, col3, col4], signal_types):
        with col:
            _render_signal_card_with_button(signal_key, title, count, stocks, gradient)

    # 선택된 시그널 상세 표시
    _render_signal_detail(api, summary)


def _render_signal_card_with_button(signal_key: str, title: str, count: int, stocks: list, gradient: str):
    """시그널 카드 렌더링 (클릭 가능)"""
    # 상위 3개 종목만 표시
    top_stocks = stocks[:3] if stocks else []
    stocks_html = ""
    for s in top_stocks:
        change = s.get('change', 0)
        change_color = "#FF3B30" if change > 0 else "#007AFF" if change < 0 else "#888"
        stocks_html += f"<div style='font-size: 0.75rem; margin: 2px 0;'>{s.get('name', '')} <span style='color:{change_color};'>{change:+.1f}%</span></div>"

    if not stocks_html:
        stocks_html = "<div style='font-size: 0.75rem; color: #888;'>-</div>"

    # 카드 렌더링
    st.markdown(f"""
    <div style='background: {gradient}; padding: 1rem; border-radius: 12px; color: white; min-height: 140px;'>
        <div style='font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem;'>{title}</div>
        <div style='font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem;'>{count}개</div>
        <div style='background: rgba(255,255,255,0.2); padding: 0.5rem; border-radius: 8px;'>
            {stocks_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 클릭 버튼 (카드 아래)
    if count > 0:
        is_selected = st.session_state.get('selected_signal_type') == signal_key
        btn_label = "▼ 접기" if is_selected else "▶ 상세보기"
        if st.button(btn_label, key=f"btn_signal_{signal_key}", use_container_width=True):
            if is_selected:
                st.session_state['selected_signal_type'] = None
            else:
                st.session_state['selected_signal_type'] = signal_key
            st.rerun()


def _render_signal_detail(api, summary: dict):
    """선택된 시그널 상세 정보 표시"""
    selected = st.session_state.get('selected_signal_type')
    if not selected:
        return

    # 시그널 타입별 데이터 매핑
    signal_map = {
        'box_breakout': ('📦 박스 돌파 종목', summary.get('box_breakout_stocks', [])),
        'new_high': ('🚀 신고가 종목', summary.get('new_high_stocks', [])),
        'double_bottom': ('📐 쌍바닥 종목', summary.get('double_bottom_stocks', [])),
        'pullback': ('📈 눌림목 종목', summary.get('pullback_stocks', []))
    }

    title, stocks = signal_map.get(selected, ('', []))
    if not stocks:
        return

    st.markdown(f"### {title} ({len(stocks)}개)")

    # 현재 열린 차트 종목 코드
    open_chart_code = st.session_state.get('signal_detail_chart_code')

    # 종목 목록을 테이블로 표시 (각 종목 아래에 차트 표시)
    for idx, stock in enumerate(stocks):
        code = stock.get('code', '')
        name = stock.get('name', '')
        price = stock.get('price', 0)
        change = stock.get('change', 0)

        with st.container(border=True):
            col_info, col_chart_btn = st.columns([3, 1])

            with col_info:
                change_color = "red" if change > 0 else "blue" if change < 0 else "gray"
                change_sign = "+" if change > 0 else ""
                st.markdown(f"**{name}** ({code})")
                st.markdown(f"현재가: {price:,.0f}원 | <span style='color:{change_color};'>{change_sign}{change:.2f}%</span>", unsafe_allow_html=True)

            with col_chart_btn:
                # 현재 종목 차트가 열려있으면 닫기 버튼, 아니면 차트 버튼
                if open_chart_code == code:
                    if st.button("❌ 닫기", key=f"close_chart_{selected}_{code}"):
                        st.session_state['signal_detail_chart_code'] = None
                        st.session_state['signal_detail_chart_name'] = None
                        st.rerun()
                else:
                    if st.button("📈 차트", key=f"chart_signal_{selected}_{code}"):
                        st.session_state['signal_detail_chart_code'] = code
                        st.session_state['signal_detail_chart_name'] = name
                        st.rerun()

            # 해당 종목의 차트가 선택된 경우 바로 아래에 차트 표시
            if open_chart_code == code and api:
                st.markdown(f"#### 📊 {name} ({code}) 차트")

                try:
                    df = api.get_daily_price(code, period="D")
                    if df is not None and not df.empty:
                        df = df.tail(120).copy()

                        from dashboard.utils.chart_utils import render_candlestick_chart, is_mobile, get_chart_config

                        # 모바일 대응 설정
                        mobile_mode = is_mobile()
                        config = get_chart_config(mobile_mode)

                        render_candlestick_chart(
                            data=df,
                            code=code,
                            name=name,
                            key_prefix=f"signal_detail_{code}",
                            height=config['height'],
                            show_ma=True,
                            show_volume=True,
                            show_volume_profile=config['show_volume_profile'],
                            show_swing_points=config['show_swing_points'],
                            show_box_range=True,
                            ma_periods=config['ma_periods']
                        )

                        # 시그널별 추가 정보 표시 (데스크탑에서만)
                        if not mobile_mode:
                            _render_signal_specific_info(df, selected, code, name)

                except Exception as e:
                    st.error(f"차트 로드 오류: {e}")


def _render_signal_specific_info(df, signal_type: str, code: str, name: str):
    """시그널 타입별 상세 정보 표시"""
    st.markdown("##### 📋 시그널 상세 분석")

    if signal_type == 'box_breakout':
        result = detect_box_breakout(df, period=20, volume_confirm=True)
        if result and result.get('detected'):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("돌파 방향", "상단 돌파 ↑" if result.get('direction') == 'up' else "하단 이탈 ↓")
            with col2:
                st.metric("돌파 가격", f"{result.get('breakout_price', 0):,.0f}원")
            with col3:
                st.metric("거래량 배수", f"{result.get('volume_ratio', 1):.1f}배")
            if result.get('volume_confirmed'):
                st.success("✅ 거래량 확인됨 (신뢰도 높음)")

    elif signal_type == 'new_high':
        result = detect_new_high_trend(df, lookback=60, breakout_days=3)
        if result and result.get('detected'):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("60일 신고가", f"{result.get('historical_high', 0):,.0f}원")
            with col2:
                st.metric("52주 신고가", "근접" if result.get('is_52w_high') else "미달")
            with col3:
                st.metric("거래량 급증", "예" if result.get('volume_surge') else "아니오")
            if result.get('is_bullish'):
                st.success("✅ 이평선 정배열 (상승 추세)")

    elif signal_type == 'double_bottom':
        from dashboard.utils.indicators import detect_double_bottom
        result = detect_double_bottom(df, lookback=60, tolerance=0.03)
        if result and result.get('detected'):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("첫번째 저점", f"{result.get('first_low', 0):,.0f}원")
            with col2:
                st.metric("두번째 저점", f"{result.get('second_low', 0):,.0f}원")
            with col3:
                st.metric("넥라인", f"{result.get('neckline', 0):,.0f}원")
            if result.get('neckline_broken'):
                st.success("✅ 넥라인 돌파! (매수 신호)")
            else:
                st.info("⏳ 넥라인 돌파 대기 중")

    elif signal_type == 'pullback':
        from dashboard.utils.indicators import detect_pullback_buy
        result = detect_pullback_buy(df, ma_periods=[5, 20, 60])
        if result and result.get('detected'):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("지지선", f"{result.get('support_ma', 0)}일선")
            with col2:
                st.metric("지지가격", f"{result.get('ma_value', 0):,.0f}원")
            with col3:
                st.metric("정배열", "예" if result.get('is_bullish_aligned') else "아니오")
            if result.get('volume_decreased'):
                st.success("✅ 거래량 감소 (조정 구간)")


def _render_signal_card(title: str, count: int, stocks: list, gradient: str):
    """시그널 카드 렌더링 (하위 호환성)"""
    _render_signal_card_with_button("legacy", title, count, stocks, gradient)


def _analyze_single_stock(args) -> dict:
    """단일 종목 분석 (병렬 처리용)"""
    code, name, api = args
    result = {
        'code': code,
        'name': name,
        'box_breakout': None,
        'new_high': None,
        'double_bottom': None,
        'pullback': None
    }

    try:
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty or len(df) < 30:
            return result

        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2] if len(df) >= 2 else current_price
        change = (current_price - prev_price) / prev_price * 100 if prev_price > 0 else 0

        stock_info = {'code': code, 'name': name, 'price': current_price, 'change': change}

        # 박스권 돌파 분석
        try:
            breakout = detect_box_breakout(df, period=20, volume_confirm=True)
            if breakout and breakout.get('direction') == 'up':
                strength = breakout.get('strength', '')
                is_strong = strength == 'strong' or (isinstance(strength, (int, float)) and strength >= 0.7)
                if breakout.get('volume_confirmed') or is_strong:
                    result['box_breakout'] = stock_info
        except Exception:
            pass

        # 신고가 분석
        try:
            new_high = detect_new_high_trend(df, lookback=60, breakout_days=3)
            if new_high and new_high.get('detected'):
                new_high_strength = new_high.get('strength', '')
                is_new_high_strong = new_high_strength == 'strong' or (isinstance(new_high_strength, (int, float)) and new_high_strength >= 0.7)
                if new_high.get('is_52w_high') and is_new_high_strong:
                    result['new_high'] = stock_info
        except Exception:
            pass

        # 스윙 패턴 분석
        try:
            swing = analyze_swing_patterns(df)
            if swing:
                for pattern in swing.get('patterns', []):
                    if pattern.get('detected'):
                        if pattern.get('pattern') == 'double_bottom':
                            result['double_bottom'] = stock_info
                        elif pattern.get('pattern') == 'pullback':
                            result['pullback'] = stock_info
        except Exception:
            pass

    except Exception:
        pass

    return result


def _analyze_swing_signals_quick(api, full_scan: bool = False, progress_callback=None) -> dict:
    """
    스윙 시그널 분석 (병렬 처리 버전)

    Args:
        api: KIS API 인스턴스
        full_scan: True면 전종목 분석, False면 시총 상위 50개만 분석
        progress_callback: 진행률 콜백 함수

    Returns:
        분석 결과 딕셔너리
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    summary = {
        'box_breakout_count': 0,
        'box_breakout_stocks': [],
        'new_high_count': 0,
        'new_high_stocks': [],
        'double_bottom_count': 0,
        'double_bottom_stocks': [],
        'pullback_count': 0,
        'pullback_stocks': [],
        'scan_mode': 'full' if full_scan else 'quick',
        'total_scanned': 0
    }

    # 분석 대상 종목 선택
    if full_scan:
        target_stocks = get_kospi_stocks() + get_kosdaq_stocks()
    else:
        target_stocks = get_kospi_stocks()[:30] + get_kosdaq_stocks()[:20]

    summary['total_scanned'] = len(target_stocks)
    total = len(target_stocks)

    # 병렬 처리를 위한 워커 수 설정 (API 제한 고려)
    max_workers = 10 if full_scan else 5

    # 결과 수집용 리스트 (thread-safe)
    results_lock = threading.Lock()
    completed = [0]

    def process_stock(stock_tuple):
        code, name = stock_tuple
        result = _analyze_single_stock((code, name, api))

        # 진행률 업데이트
        with results_lock:
            completed[0] += 1
            if progress_callback and completed[0] % 50 == 0:
                progress_callback(completed[0], total)

        return result

    # 병렬 처리 실행
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_stock, stock): stock for stock in target_stocks}

        for future in as_completed(futures):
            try:
                result = future.result(timeout=10)

                if result.get('box_breakout'):
                    summary['box_breakout_count'] += 1
                    summary['box_breakout_stocks'].append(result['box_breakout'])

                if result.get('new_high'):
                    summary['new_high_count'] += 1
                    summary['new_high_stocks'].append(result['new_high'])

                if result.get('double_bottom'):
                    summary['double_bottom_count'] += 1
                    summary['double_bottom_stocks'].append(result['double_bottom'])

                if result.get('pullback'):
                    summary['pullback_count'] += 1
                    summary['pullback_stocks'].append(result['pullback'])

            except Exception:
                continue

    # 등락률 순 정렬
    for key in ['box_breakout_stocks', 'new_high_stocks', 'double_bottom_stocks', 'pullback_stocks']:
        summary[key] = sorted(summary[key], key=lambda x: x.get('change', 0), reverse=True)

    return summary


# ===== 뉴스 기반 주도 섹터 분석 =====

@st.cache_data(ttl=3600, show_spinner=False)  # 1시간 캐시
def _fetch_weekly_news_summary() -> dict:
    """
    최근 일주일 뉴스를 크롤링하여 주도 섹터 분석
    네이버 금융 뉴스 기반
    """
    import requests
    from bs4 import BeautifulSoup
    from collections import Counter
    import re

    # 섹터/테마 키워드 매핑
    SECTOR_KEYWORDS = {
        '반도체': ['반도체', 'HBM', 'AI반도체', '메모리', 'DRAM', 'NAND', '삼성전자', 'SK하이닉스', '파운드리', 'GPU', 'NPU'],
        '2차전지': ['2차전지', '배터리', 'LFP', 'NCM', '전고체', '리튬', '양극재', '음극재', 'LG에너지', '삼성SDI', 'CATL', '테슬라'],
        'AI/소프트웨어': ['AI', '인공지능', 'ChatGPT', 'LLM', '클라우드', 'SaaS', '네이버', '카카오', '생성AI', 'AI에이전트'],
        '바이오/제약': ['바이오', '제약', '신약', '임상', 'FDA', 'GLP-1', '비만치료제', '삼성바이오', '셀트리온', 'ADC', '항암제'],
        '자동차/모빌리티': ['자동차', '전기차', 'EV', '자율주행', '현대차', '기아', '테슬라', '로보택시', 'SDV', '전장'],
        '조선/해운': ['조선', '해운', 'LNG선', '컨테이너', 'HD한국조선', '삼성중공업', 'HMM', 'VLCC'],
        '원자력/에너지': ['원전', '원자력', 'SMR', '우라늄', '두산에너빌리티', '한수원', '에너지전환'],
        '방산/항공우주': ['방산', '항공우주', '한화에어로', '위성', 'K-방산', '수출', 'UAE', '폴란드'],
        '엔터/미디어': ['엔터', '한류', 'K팝', 'BTS', '하이브', 'JYP', 'SM', '넷플릭스', 'OTT'],
        '금융/증권': ['금융', '증권', '은행', '보험', '배당', 'PBR', '금리', '기준금리'],
        '건설/부동산': ['건설', '부동산', '아파트', 'PF', '인프라', '재건축', '재개발'],
        '철강/화학': ['철강', '화학', '포스코', 'LG화학', '석유화학', '정유'],
        '유통/소비재': ['유통', '소비재', '이커머스', '쿠팡', '네이버쇼핑', '명품', '화장품'],
        '게임': ['게임', '넥슨', '엔씨소프트', '크래프톤', '넷마블', 'PC게임', '모바일게임'],
        '로봇/자동화': ['로봇', '자동화', '휴머노이드', '두산로보틱스', '레인보우로보틱스', '산업용로봇'],
    }

    result = {
        'sector_mentions': Counter(),
        'top_keywords': Counter(),
        'news_items': [],
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'period': '실시간 뉴스'  # 네이버 금융 메인/증권 뉴스 기반
    }

    try:
        # 네이버 증권 뉴스 (최근 7일치)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        news_urls = [
            'https://finance.naver.com/news/mainnews.naver',  # 메인뉴스
            'https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258',  # 증권
        ]

        all_titles = []

        for url in news_urls:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.encoding = 'euc-kr'
                soup = BeautifulSoup(resp.text, 'html.parser')

                # 뉴스 제목 추출
                news_items = soup.select('dd.articleSubject a, li.newsList a, a.articleSubject')
                for item in news_items[:30]:
                    title = item.get_text(strip=True)
                    if len(title) > 10:
                        all_titles.append(title)
                        result['news_items'].append({
                            'title': title[:80] + '...' if len(title) > 80 else title,
                            'url': 'https://finance.naver.com' + item.get('href', '')
                        })
            except Exception:
                continue

        # 섹터별 언급 횟수 카운트
        for title in all_titles:
            for sector, keywords in SECTOR_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in title:
                        result['sector_mentions'][sector] += 1
                        result['top_keywords'][keyword] += 1
                        break  # 한 섹터당 하나만 카운트

        # 중복 제거 및 정렬
        result['news_items'] = result['news_items'][:20]  # 최대 20개

    except Exception as e:
        result['error'] = str(e)

    return result


def _render_news_sector_analysis():
    """뉴스 기반 주도 섹터 분석 카드 렌더링"""
    import html

    st.markdown("### 📰 뉴스 기반 주도 섹터 분석")

    with st.spinner("최근 뉴스 분석 중..."):
        news_data = _fetch_weekly_news_summary()

    if news_data.get('error'):
        st.warning(f"뉴스 데이터 로드 오류: {news_data['error']}")
        return

    sector_mentions = news_data.get('sector_mentions', {})
    top_keywords = news_data.get('top_keywords', {})

    if not sector_mentions:
        st.info("분석할 뉴스 데이터가 없습니다.")
        return

    # 상위 섹터 추출
    top_sectors = sector_mentions.most_common(8)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'>
            <span style='color: white; font-weight: 700;'>🎯 주도 섹터 (뉴스 언급 빈도)</span>
        </div>
        """, unsafe_allow_html=True)

        if top_sectors:
            max_count = top_sectors[0][1] if top_sectors else 1

            for i, (sector, count) in enumerate(top_sectors):
                sector_name = html.escape(sector)
                # 비율에 따른 막대 너비
                bar_width = int((count / max_count) * 100)
                # 순위에 따른 색상
                colors = ['#FF6B6B', '#FF8E53', '#FFB347', '#4ECDC4', '#45B7D1', '#96CEB4', '#88D8B0', '#FFEAA7']
                color = colors[i] if i < len(colors) else '#667eea'

                rank_emoji = ['🥇', '🥈', '🥉'][i] if i < 3 else f'{i+1}.'

                st.markdown(f"""
                <div style='background: white; padding: 0.5rem 0.8rem; border-radius: 8px; margin-bottom: 0.4rem;'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;'>
                        <span style='font-weight: 600;'>{rank_emoji} {sector_name}</span>
                        <span style='color: {color}; font-weight: 700;'>{count}회</span>
                    </div>
                    <div style='background: #f0f0f0; border-radius: 4px; height: 8px; overflow: hidden;'>
                        <div style='background: {color}; width: {bar_width}%; height: 100%;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("섹터 데이터 없음")

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 0.6rem 1rem; border-radius: 10px; margin-bottom: 0.75rem;'>
            <span style='color: white; font-weight: 700;'>🔑 핵심 키워드 TOP 10</span>
        </div>
        """, unsafe_allow_html=True)

        top_kw = top_keywords.most_common(10)
        if top_kw:
            # 키워드 태그 클라우드 스타일
            kw_html = "<div style='display: flex; flex-wrap: wrap; gap: 0.4rem;'>"
            for keyword, count in top_kw:
                kw_escaped = html.escape(keyword)
                # 빈도에 따른 크기 조정
                font_size = min(1.2, 0.75 + (count / top_kw[0][1]) * 0.5)
                kw_html += (
                    f"<span style='background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%); "
                    f"padding: 0.3rem 0.6rem; border-radius: 15px; font-size: {font_size:.2f}rem; "
                    f"border: 1px solid #667eea40; white-space: nowrap;'>"
                    f"{kw_escaped} <span style='color: #667eea; font-weight: 600;'>({count})</span>"
                    f"</span>"
                )
            kw_html += "</div>"
            st.markdown(kw_html, unsafe_allow_html=True)
        else:
            st.info("키워드 데이터 없음")

        # 분석 인사이트
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background: #f8f9fa; padding: 0.8rem; border-radius: 8px; border-left: 4px solid #667eea;'>
            <span style='font-weight: 600; color: #333;'>📊 분석 인사이트</span>
        </div>
        """, unsafe_allow_html=True)

        if top_sectors:
            leader = top_sectors[0][0]
            second = top_sectors[1][0] if len(top_sectors) > 1 else None

            insight = f"현재 시장은 **{leader}** 섹터가 가장 주목받고 있습니다."
            if second:
                insight += f" **{second}** 섹터도 관심도가 높습니다."

            st.markdown(f"""
            <div style='background: white; padding: 0.6rem 0.8rem; border-radius: 8px; margin-top: 0.4rem;'>
                <span style='font-size: 0.9rem;'>{insight}</span>
            </div>
            """, unsafe_allow_html=True)

    # 관련 뉴스 헤드라인 (접는 형태)
    with st.expander("📰 최근 주요 뉴스 헤드라인", expanded=False):
        news_items = news_data.get('news_items', [])[:10]
        if news_items:
            for item in news_items:
                title = html.escape(item['title'])
                st.markdown(f"• {title}")
        else:
            st.info("뉴스 헤드라인 없음")

    st.caption(f"🕐 분석 기준: {news_data.get('analysis_date', '-')} | {news_data.get('period', '-')}")
