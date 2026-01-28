"""
공통 API 연결 헬퍼 모듈
- 모든 뷰에서 사용하는 API 연결 로직 통합
- session_state 키 통일: 'kis_api'
"""
import streamlit as st
import os
import traceback


# 통일된 session_state 키
API_SESSION_KEY = 'kis_api'


def get_api_connection(connect: bool = True, verbose: bool = False):
    """
    API 연결 가져오기 (전체 프로젝트에서 공통 사용)

    Args:
        connect: API 연결 시도 여부 (기본 True)
        verbose: 에러 상세 출력 여부 (기본 False)

    Returns:
        KoreaInvestmentAPI 인스턴스 또는 None
    """
    if API_SESSION_KEY not in st.session_state:
        try:
            from data.kis_api import KoreaInvestmentAPI

            api = KoreaInvestmentAPI()

            if connect:
                if api.connect():
                    st.session_state[API_SESSION_KEY] = api
                else:
                    if verbose:
                        st.warning("API 연결 실패")
                    return None
            else:
                st.session_state[API_SESSION_KEY] = api

        except ImportError as e:
            if verbose:
                st.error(f"KIS API 모듈 import 실패: {e}")
            return None
        except Exception as e:
            if verbose:
                st.error(f"API 초기화 오류: {e}")
                traceback.print_exc()
            return None

    return st.session_state.get(API_SESSION_KEY)


def get_api_connection_from_env():
    """
    환경변수에서 직접 API 연결 생성 (screener 등 특수 용도)

    Returns:
        KoreaInvestmentAPI 인스턴스 또는 None
    """
    if API_SESSION_KEY in st.session_state:
        return st.session_state[API_SESSION_KEY]

    try:
        from data.kis_api import KoreaInvestmentAPI

        api_key = os.environ.get('KIS_APP_KEY')
        api_secret = os.environ.get('KIS_APP_SECRET')
        account = os.environ.get('KIS_ACCOUNT')

        if api_key and api_secret and account:
            api = KoreaInvestmentAPI()
            if api.connect():
                st.session_state[API_SESSION_KEY] = api
                return api

        # 환경변수 없으면 기본 방식 시도
        api = KoreaInvestmentAPI()
        if api.connect():
            st.session_state[API_SESSION_KEY] = api
            return api

    except Exception as e:
        return None

    return None


def clear_api_connection():
    """API 연결 세션에서 제거"""
    if API_SESSION_KEY in st.session_state:
        del st.session_state[API_SESSION_KEY]


def is_api_connected() -> bool:
    """API 연결 상태 확인"""
    return API_SESSION_KEY in st.session_state and st.session_state[API_SESSION_KEY] is not None
