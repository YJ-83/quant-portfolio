"""
로그인 페이지 - 개별 사용자 API 키 입력 및 인증
"""
import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data.kis_api import KoreaInvestmentAPI


def render_login_page():
    """로그인 페이지 렌더링 (set_page_config는 app.py에서 이미 호출됨)"""

    st.title("🔐 퀀트 포트폴리오 로그인")
    st.markdown("---")

    st.info("""
    **한국투자증권 API 키가 필요합니다**

    1. [한국투자증권 OpenAPI](https://apiportal.koreainvestment.com/) 접속
    2. 회원가입 후 API 키 발급
    3. 아래에 API 정보 입력
    """)

    with st.form("login_form"):
        st.subheader("API 설정")

        app_key = st.text_input(
            "App Key",
            type="password",
            placeholder="발급받은 App Key 입력",
            help="한국투자증권에서 발급받은 App Key"
        )

        app_secret = st.text_input(
            "App Secret",
            type="password",
            placeholder="발급받은 App Secret 입력",
            help="한국투자증권에서 발급받은 App Secret"
        )

        account_no = st.text_input(
            "계좌번호",
            placeholder="예: 12345678901",
            help="10자리 계좌번호 (- 없이 입력)"
        )

        is_mock = st.checkbox(
            "모의투자 모드",
            value=True,
            help="체크하면 모의투자 서버 사용 (권장)"
        )

        submitted = st.form_submit_button("🔑 로그인", use_container_width=True)

        if submitted:
            if not app_key or not app_secret:
                st.error("App Key와 App Secret은 필수입니다.")
                return False

            # API 연결 테스트
            with st.spinner("API 연결 테스트 중..."):
                try:
                    api = KoreaInvestmentAPI(
                        app_key=app_key,
                        app_secret=app_secret,
                        account_no=account_no,
                        is_mock=is_mock
                    )

                    # 토큰 발급 테스트
                    api._ensure_token()

                    if api.access_token:
                        # 세션에 저장
                        st.session_state['logged_in'] = True
                        st.session_state['api_key'] = app_key
                        st.session_state['api_secret'] = app_secret
                        st.session_state['account_no'] = account_no
                        st.session_state['is_mock'] = is_mock
                        st.session_state['access_token'] = api.access_token
                        st.session_state['token_expires_at'] = api.token_expires_at

                        st.success("✅ 로그인 성공!")
                        st.balloons()
                        st.rerun()
                        return True
                    else:
                        st.error("토큰 발급 실패. API 키를 확인해주세요.")
                        return False

                except Exception as e:
                    st.error(f"❌ 연결 실패: {str(e)}")
                    return False

    # 하단 안내
    st.markdown("---")
    with st.expander("💡 API 키 발급 방법"):
        st.markdown("""
        1. **한국투자증권 계좌 개설** (없는 경우)
        2. **[OpenAPI 포털](https://apiportal.koreainvestment.com/) 접속**
        3. **회원가입 및 로그인**
        4. **API 신청** → App Key, App Secret 발급
        5. **모의투자 신청** (선택, 권장)

        > ⚠️ API 키는 타인에게 절대 공유하지 마세요!
        """)

    return False


def check_login():
    """로그인 상태 확인"""
    return st.session_state.get('logged_in', False)


def get_session_api():
    """세션에서 API 인스턴스 생성"""
    if not check_login():
        return None

    try:
        api = KoreaInvestmentAPI(
            app_key=st.session_state.get('api_key'),
            app_secret=st.session_state.get('api_secret'),
            account_no=st.session_state.get('account_no'),
            is_mock=st.session_state.get('is_mock', True)
        )

        # 캐시된 토큰 사용
        if st.session_state.get('access_token'):
            api.access_token = st.session_state['access_token']
            api.token_expires_at = st.session_state.get('token_expires_at')

        return api
    except Exception as e:
        st.error(f"API 초기화 실패: {e}")
        return None


def logout():
    """로그아웃 처리"""
    keys_to_remove = [
        'logged_in', 'api_key', 'api_secret', 'account_no',
        'is_mock', 'access_token', 'token_expires_at'
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]


def render_logout_button():
    """로그아웃 버튼 렌더링 (사이드바용)"""
    with st.sidebar:
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1:
            mode = "모의투자" if st.session_state.get('is_mock', True) else "실전투자"
            st.caption(f"🔐 {mode} 모드")
        with col2:
            if st.button("로그아웃", key="logout_btn"):
                logout()
                st.rerun()
