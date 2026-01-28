"""
캐싱 정책 설정 모듈
- 전체 프로젝트의 캐싱 TTL(Time To Live) 통합 관리
- 일관된 캐싱 전략 적용
"""
import streamlit as st
from functools import wraps
from typing import Callable, Any


# ========== 캐싱 TTL 설정 (초 단위) ==========
CACHE_TTL = {
    # 실시간 데이터 (30초)
    'realtime': 30,

    # 일중 데이터 (5분)
    'intraday': 300,

    # 일별 데이터 (1시간)
    'daily': 3600,

    # 주간 데이터 (6시간)
    'weekly': 21600,

    # 정적 데이터 (24시간)
    'static': 86400,

    # 종목 리스트 (12시간)
    'stock_list': 43200,

    # 설정 데이터 (영구 - 세션 기간)
    'config': None,  # None = 영구 캐싱
}


# ========== 데이터 유형별 권장 TTL ==========
DATA_TYPE_TTL = {
    # 시세 관련
    'current_price': CACHE_TTL['realtime'],       # 현재가
    'orderbook': CACHE_TTL['realtime'],           # 호가
    'minute_chart': CACHE_TTL['intraday'],        # 분봉

    # 차트 관련
    'daily_chart': CACHE_TTL['daily'],            # 일봉
    'weekly_chart': CACHE_TTL['weekly'],          # 주봉
    'monthly_chart': CACHE_TTL['weekly'],         # 월봉

    # 종목 정보
    'stock_info': CACHE_TTL['daily'],             # 종목 기본 정보
    'stock_list': CACHE_TTL['stock_list'],        # 종목 리스트
    'financial_data': CACHE_TTL['weekly'],        # 재무 데이터

    # 분석 결과
    'technical_analysis': CACHE_TTL['intraday'],  # 기술적 분석
    'backtest_result': CACHE_TTL['static'],       # 백테스트 결과
    'screening_result': CACHE_TTL['realtime'],    # 스크리닝 결과
}


def get_ttl(data_type: str) -> int:
    """데이터 유형에 따른 TTL 반환

    Args:
        data_type: 데이터 유형 문자열

    Returns:
        TTL 값 (초)
    """
    return DATA_TYPE_TTL.get(data_type, CACHE_TTL['daily'])


def cached_data(ttl_type: str = 'daily'):
    """
    Streamlit 캐시 데코레이터 래퍼

    사용 예:
        @cached_data('realtime')
        def get_current_price(code):
            ...

    Args:
        ttl_type: 캐시 유형 ('realtime', 'intraday', 'daily', 'static' 등)
    """
    ttl = CACHE_TTL.get(ttl_type, CACHE_TTL['daily'])

    def decorator(func: Callable) -> Callable:
        if ttl is None:
            # 영구 캐싱
            cached_func = st.cache_data(func)
        else:
            cached_func = st.cache_data(ttl=ttl)(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return cached_func(*args, **kwargs)

        return wrapper

    return decorator


def clear_cache(cache_type: str = 'all'):
    """캐시 클리어

    Args:
        cache_type: 클리어할 캐시 유형 ('all', 'data', 'resource')
    """
    if cache_type in ('all', 'data'):
        st.cache_data.clear()
    if cache_type in ('all', 'resource'):
        st.cache_resource.clear()


# ========== 캐시 키 생성 헬퍼 ==========

def make_cache_key(*args, **kwargs) -> str:
    """캐시 키 생성

    Args:
        *args: 위치 인자들
        **kwargs: 키워드 인자들

    Returns:
        캐시 키 문자열
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    return "_".join(key_parts)
