"""
Streamlit 대시보드 메인 앱
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

# .env 파일 로드
def load_env_file():
    """프로젝트 루트의 .env 파일 로드"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 앱 시작 시 .env 로드
load_env_file()

# 페이지 설정
st.set_page_config(
    page_title="퀀트 포트폴리오",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 화려한 커스텀 CSS
st.markdown("""
<style>
    /* 애니메이션 정의 */
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
    }

    @keyframes shine {
        0% { left: -100%; }
        100% { left: 100%; }
    }

    @keyframes glow {
        0%, 100% { box-shadow: 0 0 5px rgba(102, 126, 234, 0.5); }
        50% { box-shadow: 0 0 20px rgba(102, 126, 234, 0.8), 0 0 30px rgba(118, 75, 162, 0.6); }
    }

    /* 메인 컨테이너 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* 사이드바 스타일 - 더 화려하게 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        background-size: 200% 200%;
        animation: gradientBG 15s ease infinite;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] .stRadio label {
        background: rgba(255,255,255,0.1);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 0.25rem 0;
        transition: all 0.3s ease;
        border: 1px solid rgba(255,255,255,0.1);
    }

    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.2);
        transform: translateX(5px);
        border-color: rgba(255,255,255,0.3);
    }

    /* 메트릭 카드 - 더 화려하게 */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        background-size: 200% 200%;
        animation: gradientBG 5s ease infinite;
        padding: 1.25rem;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255,255,255,0.2);
        position: relative;
        overflow: hidden;
    }

    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        animation: shine 3s infinite;
    }

    [data-testid="stMetric"] label {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 500;
    }

    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 800;
        font-size: 1.5rem !important;
        text-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }

    /* 버튼 스타일 - 더 눈에 띄게 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        position: relative;
        overflow: hidden;
    }

    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        transition: left 0.5s ease;
    }

    .stButton > button:hover::before {
        left: 100%;
    }

    .stButton > button:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.6);
    }

    .stButton > button:active {
        transform: translateY(0) scale(0.98);
    }

    /* Primary 버튼 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        animation: glow 2s ease-in-out infinite;
    }

    /* 카드 스타일 */
    .glass-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.8);
        transition: all 0.3s ease;
    }

    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
    }

    .neon-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 2px solid;
        border-image: linear-gradient(135deg, #667eea, #f093fb) 1;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
    }

    /* 헤더 스타일 */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 900;
        letter-spacing: -0.5px;
    }

    h2, h3 {
        color: #1a1a2e;
        font-weight: 700;
    }

    /* 테이블 스타일 */
    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }

    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: none !important;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(102, 126, 234, 0.1);
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(102, 126, 234, 0.2);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }

    /* 구분선 */
    hr {
        border: none;
        height: 3px;
        background: linear-gradient(90deg, transparent, #667eea, #764ba2, #f093fb, transparent);
        margin: 2rem 0;
        border-radius: 2px;
    }

    /* 입력 필드 스타일 */
    .stSelectbox [data-baseweb="select"] {
        border-radius: 12px;
    }

    .stSlider [data-baseweb="slider"] {
        padding: 1rem 0;
    }

    /* 알림 스타일 */
    .stSuccess {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        border-radius: 12px;
        border: none;
        color: white;
    }

    .stWarning {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 12px;
        border: none;
    }

    .stInfo {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        border: none;
    }

    /* Expander 스타일 */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 12px;
        font-weight: 600;
    }

    /* 스크롤바 스타일 */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2, #f093fb);
    }

    /* 플롯리 차트 컨테이너 */
    .js-plotly-plot {
        border-radius: 16px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# 사이드바 헤더
st.sidebar.markdown("""
<div style='text-align: center; padding: 1.5rem 0;'>
    <div style='font-size: 4rem; margin-bottom: 0.5rem; animation: float 3s ease-in-out infinite;'>🚀</div>
    <h1 style='font-size: 1.5rem; margin: 0; background: linear-gradient(135deg, #667eea, #f093fb); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>퀀트 포트폴리오</h1>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# 메뉴 선택
menu_options = {
    "🏠 홈": "home",
    "🎯 전략 실행": "strategy",
    "📊 차트 전략": "chart_strategy",
    "📈 백테스트": "backtest",
    "💹 퀀트 매매": "quant_trading",
    "💼 포트폴리오": "portfolio",
    "⚙️ 설정": "settings"
}

menu = st.sidebar.radio(
    "메뉴",
    list(menu_options.keys()),
    index=0,
    label_visibility="collapsed"
)

# 사이드바 상태 정보
st.sidebar.markdown("---")

st.sidebar.markdown("""
<div style='background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 12px; margin: 0.5rem 0;'>
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
        <span style='font-size: 1.2rem;'>📡</span>
        <span style='font-size: 0.85rem; color: rgba(255,255,255,0.8);'>시스템 상태</span>
    </div>
    <div style='display: flex; align-items: center; gap: 0.5rem;'>
        <span style='width: 10px; height: 10px; background: #38ef7d; border-radius: 50%; animation: pulse 2s infinite;'></span>
        <span style='color: #38ef7d; font-size: 0.9rem; font-weight: 600;'>정상 작동 중</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"""
<div style='background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 12px; margin: 0.5rem 0;'>
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
        <span style='font-size: 1.2rem;'>🕐</span>
        <span style='font-size: 0.85rem; color: rgba(255,255,255,0.8);'>마지막 업데이트</span>
    </div>
    <span style='color: white; font-size: 0.95rem; font-weight: 600;'>{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='background: linear-gradient(135deg, rgba(102,126,234,0.3), rgba(240,147,251,0.3)); padding: 1rem; border-radius: 12px; margin: 0.5rem 0; border: 1px solid rgba(255,255,255,0.2);'>
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
        <span style='font-size: 1.2rem;'>📊</span>
        <span style='font-size: 0.85rem; color: rgba(255,255,255,0.8);'>분석 종목</span>
    </div>
    <span style='color: white; font-size: 1.5rem; font-weight: 800;'>2,145</span>
    <span style='color: rgba(255,255,255,0.7); font-size: 0.85rem;'> 종목</span>
</div>
""", unsafe_allow_html=True)

# 푸터
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='text-align: center; padding: 1rem 0;'>
    <p style='color: rgba(255,255,255,0.5); font-size: 0.75rem; margin: 0;'>
        퀀트 포트폴리오 v1.0<br>
        <span style='color: rgba(255,255,255,0.3);'>Powered by Streamlit</span>
    </p>
</div>
""", unsafe_allow_html=True)

# 페이지 라우팅
if menu == "🏠 홈":
    from views.home import render_home
    render_home()
elif menu == "🎯 전략 실행":
    from views.strategy import render_strategy
    render_strategy()
elif menu == "📊 차트 전략":
    from views.chart_strategy import render_chart_strategy
    render_chart_strategy()
elif menu == "📈 백테스트":
    from views.backtest import render_backtest
    render_backtest()
elif menu == "💹 퀀트 매매":
    from views.quant_trading import render_quant_trading
    render_quant_trading()
elif menu == "💼 포트폴리오":
    from views.portfolio import render_portfolio
    render_portfolio()
elif menu == "⚙️ 설정":
    from views.settings import render_settings
    render_settings()
