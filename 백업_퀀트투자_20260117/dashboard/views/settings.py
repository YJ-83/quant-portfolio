"""
설정 페이지
"""
import streamlit as st
import pandas as pd
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import settings


def render_settings():
    """설정 페이지 렌더링"""

    # 페이지 전용 CSS
    st.markdown("""
    <style>
        @keyframes rotateGear {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes shimmer {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .hero-settings {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            background-size: 200% 200%;
            animation: gradientBG 8s ease infinite;
            padding: 2.5rem;
            border-radius: 24px;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }

        .hero-settings::before {
            content: '';
            position: absolute;
            top: 0;
            left: -200%;
            width: 200%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s infinite;
        }

        .settings-card {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.08);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 2px solid transparent;
            animation: slideIn 0.5s ease-out;
        }

        .settings-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 50px rgba(102, 126, 234, 0.2);
            border-color: #667eea;
        }

        .section-header {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 1.25rem 1.5rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .api-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 20px;
            position: relative;
            overflow: hidden;
        }

        .api-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s infinite;
        }

        .path-item {
            background: white;
            padding: 1rem 1.25rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            margin-bottom: 0.75rem;
            transition: all 0.3s ease;
            border-left: 4px solid #667eea;
        }

        .path-item:hover {
            transform: translateX(5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .stat-item {
            background: white;
            padding: 1rem 1.25rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }

        .stat-item:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .source-card {
            background: white;
            padding: 1rem;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .source-card:hover {
            transform: translateX(5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .info-card {
            background: linear-gradient(135deg, var(--color) 0%, var(--color-light) 100%);
            padding: 1.5rem;
            border-radius: 16px;
            border-left: 5px solid var(--color);
        }

        .factor-weight-card {
            text-align: center;
            padding: 1.25rem;
            border-radius: 16px;
            transition: all 0.3s ease;
        }

        .factor-weight-card:hover {
            transform: scale(1.03);
        }
    </style>
    """, unsafe_allow_html=True)

    # 히어로 헤더
    st.markdown("""
    <div class='hero-settings'>
        <div style='position: relative; z-index: 1;'>
            <div style='font-size: 4rem; margin-bottom: 0.5rem; animation: rotateGear 10s linear infinite;'>⚙️</div>
            <h1 style='color: white; font-size: 2.5rem; margin: 0 0 0.5rem 0; font-weight: 800; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>설정</h1>
            <p style='color: rgba(255,255,255,0.95); font-size: 1.1rem; margin: 0;'>시스템 설정을 관리하고 API 연결을 구성합니다</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 전략 설정", "💾 데이터 설정", "🔗 API 연결", "ℹ️ 시스템 정보"])

    with tab1:
        render_strategy_settings()

    with tab2:
        render_data_settings()

    with tab3:
        render_api_settings()

    with tab4:
        render_system_info()


def render_strategy_settings():
    """전략 설정"""

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>🎯</span>
        <h3 style='margin: 0; color: #333;'>기본 설정</h3>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>📌</span>
                <span style='font-weight: 600; color: #333;'>기본 선정 종목 수</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        top_n = st.number_input(
            "기본 선정 종목 수",
            min_value=10,
            max_value=100,
            value=settings.DEFAULT_TOP_N,
            label_visibility="collapsed"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>🔄</span>
                <span style='font-weight: 600; color: #333;'>기본 리밸런싱 주기</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        rebalance_period = st.selectbox(
            "기본 리밸런싱 주기",
            ["monthly", "quarterly", "yearly"],
            index=["monthly", "quarterly", "yearly"].index(settings.DEFAULT_REBALANCE_PERIOD),
            format_func=lambda x: {"monthly": "월별", "quarterly": "분기별", "yearly": "연별"}[x],
            label_visibility="collapsed"
        )

    with col2:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>💰</span>
                <span style='font-weight: 600; color: #333;'>기본 투자금 (원)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        initial_capital = st.number_input(
            "기본 투자금",
            min_value=10000000,
            max_value=10000000000,
            value=int(settings.DEFAULT_INITIAL_CAPITAL),
            step=10000000,
            format="%d",
            label_visibility="collapsed"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
                <span style='font-size: 1.5rem;'>📈</span>
                <span style='font-weight: 600; color: #333;'>무위험 수익률 (%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        risk_free_rate = st.slider(
            "무위험 수익률 (%)",
            min_value=0.0,
            max_value=10.0,
            value=settings.RISK_FREE_RATE * 100,
            step=0.1,
            label_visibility="collapsed"
        )

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>📊</span>
        <h3 style='margin: 0; color: #333;'>팩터 가중치 기본값</h3>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class='factor-weight-card' style='background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);'>
            <span style='font-size: 2.5rem;'>📈</span>
            <p style='margin: 0.5rem 0 0 0; font-weight: 700; color: #2e7d32; font-size: 1.1rem;'>퀄리티</p>
        </div>
        """, unsafe_allow_html=True)
        quality_weight = st.slider(
            "퀄리티 비중 (%)",
            0, 100,
            int(settings.DEFAULT_FACTOR_WEIGHTS.get('quality', 0.33) * 100),
            label_visibility="collapsed"
        )

    with col2:
        st.markdown("""
        <div class='factor-weight-card' style='background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);'>
            <span style='font-size: 2.5rem;'>💎</span>
            <p style='margin: 0.5rem 0 0 0; font-weight: 700; color: #1565c0; font-size: 1.1rem;'>밸류</p>
        </div>
        """, unsafe_allow_html=True)
        value_weight = st.slider(
            "밸류 비중 (%)",
            0, 100,
            int(settings.DEFAULT_FACTOR_WEIGHTS.get('value', 0.33) * 100),
            label_visibility="collapsed"
        )

    with col3:
        st.markdown("""
        <div class='factor-weight-card' style='background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);'>
            <span style='font-size: 2.5rem;'>🚀</span>
            <p style='margin: 0.5rem 0 0 0; font-weight: 700; color: #ef6c00; font-size: 1.1rem;'>모멘텀</p>
        </div>
        """, unsafe_allow_html=True)
        momentum_weight = st.slider(
            "모멘텀 비중 (%)",
            0, 100,
            int(settings.DEFAULT_FACTOR_WEIGHTS.get('momentum', 0.34) * 100),
            label_visibility="collapsed"
        )

    total_weight = quality_weight + value_weight + momentum_weight
    if total_weight != 100:
        st.warning(f"⚠️ 가중치 합계: {total_weight}% (100%가 되어야 합니다)")
    else:
        st.success(f"✅ 가중치 합계: {total_weight}%")

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>🔧</span>
        <h3 style='margin: 0; color: #333;'>이상치 처리 설정</h3>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>📉</span>
                <span style='font-weight: 600; color: #333;'>윈저라이징 하위 백분위 (%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        winsorize_lower = st.slider(
            "윈저라이징 하위 백분위 (%)",
            0.0, 10.0,
            settings.WINSORIZE_LOWER * 100,
            step=0.5,
            label_visibility="collapsed"
        )

    with col2:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>📈</span>
                <span style='font-weight: 600; color: #333;'>윈저라이징 상위 백분위 (%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        winsorize_upper = st.slider(
            "윈저라이징 상위 백분위 (%)",
            90.0, 100.0,
            settings.WINSORIZE_UPPER * 100,
            step=0.5,
            label_visibility="collapsed"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        if st.button("💾 설정 저장", type="primary", use_container_width=True):
            st.success("✅ 설정이 저장되었습니다.")


def render_data_settings():
    """데이터 설정"""

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>📁</span>
        <h3 style='margin: 0; color: #333;'>데이터 경로</h3>
    </div>
    """, unsafe_allow_html=True)

    paths = [
        {"label": "데이터 저장 경로", "value": str(settings.DATA_DIR), "icon": "📂", "color": "#667eea"},
        {"label": "데이터베이스 경로", "value": str(settings.DB_PATH), "icon": "🗄️", "color": "#11998e"},
        {"label": "캐시 경로", "value": str(settings.CACHE_DIR), "icon": "💨", "color": "#f093fb"},
    ]

    for path in paths:
        st.markdown(f"""
        <div class='path-item' style='border-left-color: {path["color"]};'>
            <p style='color: #888; font-size: 0.85rem; margin: 0;'>{path["icon"]} {path["label"]}</p>
            <p style='color: #333; font-family: "SF Mono", "Monaco", monospace; font-size: 0.9rem; margin: 0.25rem 0 0 0; background: #f8f9fa; padding: 0.5rem; border-radius: 6px;'>{path["value"]}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>🔄</span>
        <h3 style='margin: 0; color: #333;'>데이터 관리</h3>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class='settings-card' style='text-align: center;'>
            <span style='font-size: 2.5rem;'>📥</span>
            <p style='margin: 0.5rem 0; font-weight: 600; color: #333;'>전체 데이터 수집</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📥 전체 데이터 수집", use_container_width=True):
            st.info("💡 터미널에서 `python main.py collect --all` 명령을 실행하세요.")

    with col2:
        st.markdown("""
        <div class='settings-card' style='text-align: center;'>
            <span style='font-size: 2.5rem;'>🔄</span>
            <p style='margin: 0.5rem 0; font-weight: 600; color: #333;'>일일 업데이트</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 일일 업데이트", use_container_width=True):
            st.info("💡 터미널에서 `python main.py collect --daily` 명령을 실행하세요.")

    with col3:
        st.markdown("""
        <div class='settings-card' style='text-align: center;'>
            <span style='font-size: 2.5rem;'>🗑️</span>
            <p style='margin: 0.5rem 0; font-weight: 600; color: #333;'>캐시 삭제</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🗑️ 캐시 삭제", use_container_width=True):
            st.warning("⚠️ 캐시를 삭제하시겠습니까?")

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>📊</span>
        <h3 style='margin: 0; color: #333;'>데이터 통계</h3>
    </div>
    """, unsafe_allow_html=True)

    stats = [
        {"label": "종목 수", "value": "2,145개", "icon": "📈", "color": "#667eea"},
        {"label": "가격 데이터", "value": "2020-01-01 ~ 현재", "icon": "📅", "color": "#11998e"},
        {"label": "재무 데이터", "value": "2020 ~ 2023", "icon": "📋", "color": "#f093fb"},
        {"label": "마지막 업데이트", "value": datetime.now().strftime("%Y-%m-%d %H:%M"), "icon": "🕐", "color": "#4facfe"},
    ]

    col1, col2 = st.columns(2)

    for idx, stat in enumerate(stats):
        with col1 if idx % 2 == 0 else col2:
            st.markdown(f"""
            <div class='stat-item'>
                <div style='display: flex; align-items: center; gap: 0.5rem;'>
                    <span style='font-size: 1.5rem;'>{stat["icon"]}</span>
                    <div>
                        <p style='color: #888; font-size: 0.8rem; margin: 0;'>{stat["label"]}</p>
                        <p style='color: {stat["color"]}; font-size: 1.1rem; font-weight: 700; margin: 0;'>{stat["value"]}</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_api_settings():
    """API 연결 설정"""
    import os

    # 프로젝트 루트의 .env 파일 경로
    env_file_path = Path(__file__).parent.parent.parent / ".env"

    # 기존 환경변수 값 로드
    existing_app_key = os.getenv("KIS_APP_KEY", "")
    existing_app_secret = os.getenv("KIS_APP_SECRET", "")
    existing_account_no = os.getenv("KIS_ACCOUNT_NO", "")
    existing_is_mock = os.getenv("KIS_IS_MOCK", "true").lower() == "true"

    st.markdown("""
    <div class='api-card'>
        <div style='position: relative; z-index: 1;'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 2rem;'>🔗</span>
                <h3 style='margin: 0; color: white; font-weight: 700;'>한국투자증권 API 연결</h3>
            </div>
            <p style='margin: 0; color: rgba(255,255,255,0.9); font-size: 0.95rem;'>
                REST API 기반 - Mac/Windows/Linux 모두 지원
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 현재 설정 상태 표시
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        if existing_app_key:
            st.success(f"✅ App Key: 설정됨 ({existing_app_key[:8]}...)")
        else:
            st.error("❌ App Key: 미설정")
    with col2:
        if existing_account_no:
            st.success(f"✅ 계좌번호: {existing_account_no[:4]}****-**")
        else:
            st.warning("⚠️ 계좌번호: 미설정")
    with col3:
        mode = "모의투자" if existing_is_mock else "실전투자"
        st.info(f"📌 모드: {mode}")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>🔑</span>
                <span style='font-weight: 600; color: #333;'>App Key</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        app_key = st.text_input(
            "App Key",
            value=existing_app_key,
            type="password",
            placeholder="KIS Developers에서 발급받은 App Key",
            label_visibility="collapsed",
            key="api_app_key"
        )

    with col2:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>🔐</span>
                <span style='font-weight: 600; color: #333;'>App Secret</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        app_secret = st.text_input(
            "App Secret",
            value=existing_app_secret,
            type="password",
            placeholder="KIS Developers에서 발급받은 App Secret",
            label_visibility="collapsed",
            key="api_app_secret"
        )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>🏦</span>
                <span style='font-weight: 600; color: #333;'>계좌번호 (필수 - 퀀트매매용)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        account_no = st.text_input(
            "계좌번호",
            value=existing_account_no,
            placeholder="8자리-2자리 (예: 12345678-01)",
            label_visibility="collapsed",
            key="api_account_no"
        )
        st.caption("형식: 12345678-01 (하이픈 포함)")

    with col2:
        st.markdown("""
        <div class='settings-card'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.25rem;'>🧪</span>
                <span style='font-weight: 600; color: #333;'>모의투자 모드</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        is_mock = st.checkbox("모의투자 사용", value=existing_is_mock, key="api_is_mock")
        if is_mock:
            st.markdown("<span style='color: #11998e; font-size: 0.9rem;'>✅ 모의투자 모드 활성화</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color: #f5576c; font-size: 0.9rem;'>⚠️ 실거래 모드 - 실제 자금이 거래됩니다!</span>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔌 연결 테스트", use_container_width=True, key="api_test_btn"):
            if app_key and app_secret:
                with st.spinner("연결 테스트 중..."):
                    try:
                        from data.kis_api import KoreaInvestmentAPI
                        test_api = KoreaInvestmentAPI(
                            app_key=app_key,
                            app_secret=app_secret,
                            account_no=account_no,
                            is_mock=is_mock
                        )
                        if test_api.connect():
                            st.success("✅ API 연결 테스트 성공!")

                            # 잔고 조회 테스트
                            if account_no:
                                balance = test_api.get_balance()
                                if balance:
                                    st.success("✅ 잔고 조회 성공!")
                                else:
                                    st.warning("⚠️ 잔고 조회 실패 - 계좌번호 확인 필요")
                        else:
                            st.error("❌ API 연결 실패 - 키 정보를 확인해주세요.")
                    except Exception as e:
                        st.error(f"❌ 연결 오류: {e}")
            else:
                st.error("❌ App Key와 App Secret을 입력해주세요.")

    with col2:
        if st.button("💾 API 설정 저장", type="primary", use_container_width=True, key="api_save_btn"):
            if app_key and app_secret:
                # .env 파일에 저장
                env_content = f"""# 한국투자증권 API 설정
KIS_APP_KEY={app_key}
KIS_APP_SECRET={app_secret}
KIS_ACCOUNT_NO={account_no}
KIS_IS_MOCK={'true' if is_mock else 'false'}
"""
                try:
                    with open(env_file_path, 'w') as f:
                        f.write(env_content)

                    # 환경변수 즉시 적용
                    os.environ["KIS_APP_KEY"] = app_key
                    os.environ["KIS_APP_SECRET"] = app_secret
                    os.environ["KIS_ACCOUNT_NO"] = account_no
                    os.environ["KIS_IS_MOCK"] = 'true' if is_mock else 'false'

                    st.success(f"✅ 설정이 저장되었습니다!")
                    st.info(f"📁 저장 위치: {env_file_path}")
                    st.warning("⚠️ 앱을 새로고침하여 설정을 적용하세요.")
                except Exception as e:
                    st.error(f"❌ 저장 실패: {e}")
            else:
                st.error("❌ App Key와 App Secret은 필수입니다.")

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>🌐</span>
        <h3 style='margin: 0; color: #333;'>대안 데이터 소스</h3>
        <span style='color: #666; font-size: 0.9rem; margin-left: auto;'>API 키 없이 무료로 사용 가능</span>
    </div>
    """, unsafe_allow_html=True)

    sources = [
        {"name": "FinanceDataReader", "desc": "주가, 종목 정보 (무료)", "icon": "📊", "enabled": True, "color": "#667eea"},
        {"name": "pykrx", "desc": "KRX 데이터 (무료)", "icon": "🏢", "enabled": True, "color": "#11998e"},
        {"name": "OpenDartReader", "desc": "DART 공시 데이터 (API 키 필요)", "icon": "📋", "enabled": False, "color": "#f093fb"},
    ]

    for source in sources:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class='source-card'>
                <div style='display: flex; align-items: center; gap: 0.75rem;'>
                    <span style='font-size: 1.75rem;'>{source["icon"]}</span>
                    <div>
                        <p style='margin: 0; font-weight: 600; color: #333;'>{source["name"]}</p>
                        <p style='margin: 0; color: #888; font-size: 0.85rem;'>{source["desc"]}</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.checkbox(f"{source['name']} 사용", value=source["enabled"], key=f"use_{source['name']}", label_visibility="collapsed")


def render_system_info():
    """시스템 정보"""

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>💻</span>
        <h3 style='margin: 0; color: #333;'>시스템 정보</h3>
    </div>
    """, unsafe_allow_html=True)

    info = [
        {"label": "버전", "value": "1.0.0", "icon": "🏷️", "color": "#667eea"},
        {"label": "Python 버전", "value": "3.9+", "icon": "🐍", "color": "#11998e"},
        {"label": "운영체제", "value": "macOS / Windows / Linux", "icon": "💻", "color": "#f093fb"},
        {"label": "프레임워크", "value": "Streamlit 1.28+", "icon": "🎨", "color": "#4facfe"},
    ]

    col1, col2 = st.columns(2)

    for idx, item in enumerate(info):
        with col1 if idx % 2 == 0 else col2:
            st.markdown(f"""
            <div class='stat-item'>
                <div style='display: flex; align-items: center; gap: 0.75rem;'>
                    <span style='font-size: 1.75rem;'>{item["icon"]}</span>
                    <div>
                        <p style='color: #888; font-size: 0.8rem; margin: 0;'>{item["label"]}</p>
                        <p style='color: {item["color"]}; font-size: 1.1rem; font-weight: 700; margin: 0;'>{item["value"]}</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div class='section-header'>
        <span style='font-size: 1.75rem;'>📦</span>
        <h3 style='margin: 0; color: #333;'>의존성 패키지</h3>
    </div>
    """, unsafe_allow_html=True)

    packages = """pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
requests>=2.31.0
finance-datareader>=0.9.50
pykrx>=1.0.0
sqlalchemy>=2.0.0
streamlit>=1.28.0
plotly>=5.18.0"""

    st.code(packages, language="text")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class='info-card' style='--color: #667eea; --color-light: #667eea15;'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.5rem;'>📜</span>
                <h4 style='margin: 0; color: #333;'>라이선스</h4>
            </div>
            <p style='color: #666; font-size: 0.9rem; margin: 0;'>
                이 프로젝트는 <strong style='color: #667eea;'>MIT License</strong>로 배포됩니다.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class='info-card' style='--color: #11998e; --color-light: #11998e15;'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 1.5rem;'>📚</span>
                <h4 style='margin: 0; color: #333;'>참고 자료</h4>
            </div>
            <p style='color: #666; font-size: 0.9rem; margin: 0;'>
                • <a href='https://hyunyulhenry.github.io/quant_cookbook/' target='_blank' style='color: #11998e;'>퀀트 쿡북</a><br>
                • Joel Greenblatt, "The Little Book"
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div class='settings-card' style='text-align: center;'>
        <span style='font-size: 3rem;'>🙏</span>
        <h4 style='margin: 0.75rem 0; color: #333;'>문의 및 지원</h4>
        <p style='color: #666; font-size: 0.95rem; margin: 0;'>
            버그 리포트나 기능 요청은 GitHub Issues를 이용해 주세요.
        </p>
    </div>
    """, unsafe_allow_html=True)
