"""
에러 핸들링 표준화 모듈
- 전체 프로젝트의 에러 처리 통합
- 일관된 에러 메시지 표시
"""
import streamlit as st
import traceback
import logging
from functools import wraps
from typing import Callable, Any, Optional, TypeVar, Union

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('quant_portfolio')

T = TypeVar('T')


# ========== 에러 메시지 템플릿 ==========
ERROR_MESSAGES = {
    'api_connection': "API 연결에 실패했습니다. 네트워크 연결을 확인해주세요.",
    'api_auth': "API 인증에 실패했습니다. 인증 정보를 확인해주세요.",
    'data_load': "데이터를 불러오는 중 오류가 발생했습니다.",
    'data_empty': "데이터가 없습니다.",
    'invalid_input': "잘못된 입력입니다.",
    'calculation': "계산 중 오류가 발생했습니다.",
    'file_not_found': "파일을 찾을 수 없습니다.",
    'permission_denied': "접근 권한이 없습니다.",
    'timeout': "요청 시간이 초과되었습니다.",
    'unknown': "알 수 없는 오류가 발생했습니다.",
}


def get_error_message(error_type: str, detail: str = "") -> str:
    """에러 메시지 생성

    Args:
        error_type: 에러 유형
        detail: 추가 상세 정보

    Returns:
        포맷팅된 에러 메시지
    """
    base_message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES['unknown'])
    if detail:
        return f"{base_message}\n상세: {detail}"
    return base_message


# ========== 안전한 실행 래퍼 ==========

def safe_execute(
    func: Callable[[], T],
    default: Optional[T] = None,
    show_error: bool = True,
    error_type: str = 'unknown',
    error_detail: str = ""
) -> Optional[T]:
    """
    안전한 함수 실행 래퍼

    Args:
        func: 실행할 함수 (인자 없는 람다 또는 함수)
        default: 에러 시 반환할 기본값
        show_error: Streamlit에 에러 표시 여부
        error_type: 에러 메시지 유형
        error_detail: 추가 에러 상세 정보

    Returns:
        함수 실행 결과 또는 기본값

    사용 예:
        result = safe_execute(
            lambda: risky_function(arg1, arg2),
            default=[],
            error_type='data_load'
        )
    """
    try:
        return func()
    except Exception as e:
        logger.error(f"Error in safe_execute: {e}")
        logger.debug(traceback.format_exc())

        if show_error:
            message = get_error_message(error_type, error_detail or str(e))
            st.error(f"❌ {message}")

        return default


def safe_execute_with_spinner(
    func: Callable[[], T],
    spinner_text: str = "처리 중...",
    default: Optional[T] = None,
    show_error: bool = True,
    error_type: str = 'unknown'
) -> Optional[T]:
    """
    스피너와 함께 안전한 함수 실행

    Args:
        func: 실행할 함수
        spinner_text: 스피너에 표시할 텍스트
        default: 에러 시 반환할 기본값
        show_error: 에러 표시 여부
        error_type: 에러 메시지 유형

    Returns:
        함수 실행 결과 또는 기본값
    """
    with st.spinner(spinner_text):
        return safe_execute(func, default, show_error, error_type)


# ========== 데코레이터 ==========

def handle_errors(
    default: Any = None,
    show_error: bool = True,
    error_type: str = 'unknown',
    log_error: bool = True
):
    """
    에러 핸들링 데코레이터

    Args:
        default: 에러 시 반환할 기본값
        show_error: Streamlit에 에러 표시 여부
        error_type: 에러 메시지 유형
        log_error: 에러 로깅 여부

    사용 예:
        @handle_errors(default=[], error_type='data_load')
        def load_stock_data(code):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {e}")
                    logger.debug(traceback.format_exc())

                if show_error:
                    message = get_error_message(error_type, str(e))
                    st.error(f"❌ {message}")

                return default

        return wrapper
    return decorator


def handle_api_errors(func: Callable) -> Callable:
    """
    API 에러 전용 데코레이터

    사용 예:
        @handle_api_errors
        def call_api(endpoint):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            logger.error(f"Connection error in {func.__name__}: {e}")
            st.error(f"❌ {get_error_message('api_connection')}")
            return None
        except TimeoutError as e:
            logger.error(f"Timeout in {func.__name__}: {e}")
            st.error(f"❌ {get_error_message('timeout')}")
            return None
        except PermissionError as e:
            logger.error(f"Permission error in {func.__name__}: {e}")
            st.error(f"❌ {get_error_message('api_auth')}")
            return None
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            st.error(f"❌ {get_error_message('unknown', str(e))}")
            return None

    return wrapper


# ========== 검증 헬퍼 ==========

def validate_dataframe(
    df,
    min_rows: int = 1,
    required_columns: list = None,
    error_message: str = None
) -> bool:
    """
    DataFrame 검증

    Args:
        df: 검증할 DataFrame
        min_rows: 최소 행 수
        required_columns: 필수 컬럼 리스트
        error_message: 커스텀 에러 메시지

    Returns:
        검증 통과 여부
    """
    import pandas as pd

    if df is None:
        if error_message:
            st.warning(f"⚠️ {error_message}")
        else:
            st.warning("⚠️ 데이터가 없습니다.")
        return False

    if not isinstance(df, pd.DataFrame):
        st.warning("⚠️ 올바른 데이터 형식이 아닙니다.")
        return False

    if len(df) < min_rows:
        if error_message:
            st.warning(f"⚠️ {error_message}")
        else:
            st.warning(f"⚠️ 데이터가 부족합니다. (최소 {min_rows}행 필요)")
        return False

    if required_columns:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            st.warning(f"⚠️ 필수 컬럼이 없습니다: {', '.join(missing)}")
            return False

    return True


def validate_not_empty(
    value: Any,
    field_name: str = "값"
) -> bool:
    """
    빈 값 검증

    Args:
        value: 검증할 값
        field_name: 필드명 (에러 메시지용)

    Returns:
        검증 통과 여부
    """
    if value is None or value == "" or (hasattr(value, '__len__') and len(value) == 0):
        st.warning(f"⚠️ {field_name}을(를) 입력해주세요.")
        return False
    return True


def validate_numeric_range(
    value: Union[int, float],
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
    field_name: str = "값"
) -> bool:
    """
    숫자 범위 검증

    Args:
        value: 검증할 값
        min_val: 최소값 (None이면 검사 안함)
        max_val: 최대값 (None이면 검사 안함)
        field_name: 필드명 (에러 메시지용)

    Returns:
        검증 통과 여부
    """
    if not isinstance(value, (int, float)):
        st.warning(f"⚠️ {field_name}은(는) 숫자여야 합니다.")
        return False

    if min_val is not None and value < min_val:
        st.warning(f"⚠️ {field_name}은(는) {min_val} 이상이어야 합니다.")
        return False

    if max_val is not None and value > max_val:
        st.warning(f"⚠️ {field_name}은(는) {max_val} 이하여야 합니다.")
        return False

    return True
