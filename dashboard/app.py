"""
Streamlit 대시보드 메인 앱
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

# 페이지 설정 - 반드시 가장 먼저 실행
st.set_page_config(
    page_title="YJ 놀이터",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# PWA (Progressive Web App) 메타태그 - 모바일 설치 지원
st.markdown("""
<head>
    <!-- PWA 메타태그 -->
    <link rel="manifest" href="app/static/manifest.json">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="YJ 놀이터">
    <meta name="theme-color" content="#667eea">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <!-- 아이콘 -->
    <link rel="apple-touch-icon" href="app/static/icon-192.png">
    <link rel="icon" type="image/png" sizes="192x192" href="app/static/icon-192.png">
    <link rel="icon" type="image/png" sizes="512x512" href="app/static/icon-512.png">
</head>
""", unsafe_allow_html=True)

# 로그인 모듈 import
from views.login import render_login_page, check_login, render_logout_button, get_session_api

# .env 파일 로드 (로컬 개발용 - 로그인 안 했을 때 fallback)
def load_env_file():
    """프로젝트 루트의 .env 파일 로드 (로컬 개발용)"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 로그인 체크 - 로그인 안 되어 있으면 로그인 페이지 표시
if not check_login():
    # 로컬 .env 파일이 있으면 자동 로그인 시도 (개발 편의)
    load_env_file()
    if os.getenv("KIS_APP_KEY") and os.getenv("KIS_APP_SECRET"):
        # .env 파일의 키로 자동 세션 설정
        st.session_state['logged_in'] = True
        st.session_state['api_key'] = os.getenv("KIS_APP_KEY")
        st.session_state['api_secret'] = os.getenv("KIS_APP_SECRET")
        st.session_state['account_no'] = os.getenv("KIS_ACCOUNT_NO", "")
        st.session_state['is_mock'] = os.getenv("KIS_IS_MOCK", "true").lower() == "true"
    else:
        # 로그인 페이지 표시
        render_login_page()
        st.stop()

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

    /* ========== 모바일 반응형 스타일 ========== */
    @media (max-width: 768px) {
        /* 메인 컨테이너 패딩 축소 */
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            padding-top: 0.5rem;
        }

        /* 사이드바 모바일 최적화 (숨기지 않고 축소) */
        [data-testid="stSidebar"] {
            width: 200px !important;
            min-width: 200px !important;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 0.5rem !important;
        }

        /* 사이드바 내 텍스트 크기 축소 */
        [data-testid="stSidebar"] .stRadio label {
            font-size: 0.85rem !important;
            padding: 0.5rem 0.75rem !important;
        }

        /* 메트릭 카드 크기 조정 */
        [data-testid="stMetric"] {
            padding: 0.75rem;
            border-radius: 10px;
        }

        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
        }

        /* 버튼 크기 조정 */
        .stButton > button {
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
            width: 100%;
        }

        /* 차트 컨테이너 */
        .js-plotly-plot {
            border-radius: 8px;
        }

        /* 플롯리 차트 높이 강제 조정 */
        .js-plotly-plot .main-svg {
            max-height: 350px !important;
        }

        /* 헤더 크기 조정 */
        h1 {
            font-size: 1.5rem !important;
        }

        h2 {
            font-size: 1.2rem !important;
        }

        h3 {
            font-size: 1rem !important;
        }

        /* 테이블 스크롤 */
        .stDataFrame {
            overflow-x: auto;
        }

        /* 컬럼 간격 축소 */
        [data-testid="column"] {
            padding: 0 0.25rem !important;
        }

        /* 카드 컨테이너 (border=True) */
        [data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
            padding: 0.5rem !important;
        }

        /* 종목 정보 텍스트 크기 */
        .stMarkdown p {
            font-size: 0.9rem;
        }

        /* 확장기(Expander) 모바일 최적화 */
        .streamlit-expanderHeader {
            font-size: 0.9rem;
            padding: 0.5rem;
        }

        /* 범례 숨김 (차트에서) */
        .legend {
            display: none !important;
        }

        /* 탭 모바일 최적화 */
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 0.85rem;
        }
    }

    /* 태블릿 (768px ~ 1024px) */
    @media (min-width: 769px) and (max-width: 1024px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }
    }

    /* 터치 디바이스 최적화 */
    @media (hover: none) and (pointer: coarse) {
        /* 터치 타겟 크기 확대 */
        .stButton > button {
            min-height: 44px;
            min-width: 44px;
        }

        /* 체크박스/라디오 버튼 크기 */
        .stCheckbox, .stRadio {
            padding: 0.5rem 0;
        }

        /* 슬라이더 터치 영역 확대 */
        .stSlider [data-baseweb="slider"] {
            padding: 1.5rem 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# 사이드바 헤더
st.sidebar.markdown("""
<div style='text-align: center; padding: 1.5rem 0;'>
    <div style='font-size: 4rem; margin-bottom: 0.5rem; animation: float 3s ease-in-out infinite;'>🎮</div>
    <h1 style='font-size: 1.5rem; margin: 0; background: linear-gradient(135deg, #667eea, #f093fb); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>YJ 놀이터</h1>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# 메뉴 선택
menu_options = {
    "🏠 홈": "home",
    "🎯 전략 실행": "strategy",
    "📂 섹터 분류": "sector",
    "📊 차트 전략": "chart_strategy",
    "📈 백테스트": "backtest",
    "💹 퀀트 매매": "quant_trading",
    "💼 포트폴리오": "portfolio",
    "⚙️ 설정": "settings"
}

# 메뉴 선택 상태 관리
if 'menu_selection' not in st.session_state:
    st.session_state['menu_selection'] = "🏠 홈"

menu = st.sidebar.radio(
    "메뉴",
    list(menu_options.keys()),
    index=list(menu_options.keys()).index(st.session_state.get('menu_selection', "🏠 홈")),
    key="sidebar_menu",
    label_visibility="collapsed"
)

# 사이드바 메뉴 변경 시 session_state 업데이트
if menu != st.session_state.get('menu_selection'):
    st.session_state['menu_selection'] = menu

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

# 모바일 모드 토글
st.sidebar.markdown("---")
mobile_mode = st.sidebar.toggle(
    "📱 모바일 모드",
    value=st.session_state.get('mobile_mode', False),
    key='mobile_toggle',
    help="차트 크기 축소, 간소화된 UI"
)
if mobile_mode != st.session_state.get('mobile_mode', False):
    st.session_state['mobile_mode'] = mobile_mode
    st.rerun()

# 로그아웃 버튼
render_logout_button()

# 푸터
st.sidebar.markdown("---")

# PWA 설치 안내 (모바일에서만 표시)
st.sidebar.markdown("""
<div id="pwa-install-guide" style='background: linear-gradient(135deg, rgba(56,239,125,0.2), rgba(102,126,234,0.2));
     padding: 0.75rem; border-radius: 12px; margin-bottom: 0.5rem; border: 1px solid rgba(56,239,125,0.3);'>
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
        <span style='font-size: 1.2rem;'>📲</span>
        <span style='font-size: 0.85rem; color: white; font-weight: 600;'>앱 설치하기</span>
    </div>
    <p style='color: rgba(255,255,255,0.8); font-size: 0.75rem; margin: 0; line-height: 1.4;'>
        <strong>iOS:</strong> Safari 공유 → 홈 화면에 추가<br>
        <strong>Android:</strong> 메뉴 → 앱 설치 or 홈 화면에 추가
    </p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style='text-align: center; padding: 1rem 0;'>
    <p style='color: rgba(255,255,255,0.5); font-size: 0.75rem; margin: 0;'>
        YJ 놀이터 v1.0<br>
        <span style='color: rgba(255,255,255,0.3);'>Powered by Streamlit</span>
    </p>
</div>
""", unsafe_allow_html=True)

# 모바일 모드일 때 상단 퀵 메뉴 표시
if st.session_state.get('mobile_mode', False):
    st.markdown("#### 📱 퀵 메뉴")
    mobile_menu_cols = st.columns(3)
    mobile_menus = [
        ("🏠", "home", "홈"),
        ("📊", "chart_strategy", "차트"),
        ("💹", "quant_trading", "매매"),
    ]
    for i, (icon, key, label) in enumerate(mobile_menus):
        with mobile_menu_cols[i]:
            if st.button(f"{icon}", key=f"mobile_menu_{key}", help=label, use_container_width=True):
                # 해당 메뉴로 이동
                menu_keys = list(menu_options.keys())
                menu_values = list(menu_options.values())
                if key in menu_values:
                    idx = menu_values.index(key)
                    st.session_state['menu_selection'] = menu_keys[idx]
                    st.rerun()
    st.markdown("---")

# 페이지 라우팅
if menu == "🏠 홈":
    from views.home import render_home
    render_home()
elif menu == "🎯 전략 실행":
    from views.strategy import render_strategy
    render_strategy()
elif menu == "📂 섹터 분류":
    from views.sector import render_sector
    render_sector()
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
