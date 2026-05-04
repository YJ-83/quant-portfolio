"""
일괄 시장 데이터 캐시 (시가총액·상장주식수)

스크리너처럼 수백 종목을 처리하는 화면에서 종목당 pykrx 호출은 너무 느리므로,
하루에 한 번 전체 시장을 일괄 조회해 메모리 캐시로 들고 있다가 코드별 조회만 한다.
"""
from __future__ import annotations
import datetime
import functools
from typing import Dict, Optional


@functools.lru_cache(maxsize=4)
def _fetch_market_cap_table(date_key: str, market: str) -> Dict[str, Dict[str, int]]:
    """
    pykrx로 특정 일자의 전체 시장 시총·상장주식수를 한 번에 가져와 dict로 반환.
    date_key 단위로 캐시되므로 같은 날 안에서는 단 한 번만 네트워크 호출 발생.
    """
    try:
        from pykrx import stock
        df = stock.get_market_cap(date_key, date_key, market=market)
        if df is None or df.empty:
            return {}
        result: Dict[str, Dict[str, int]] = {}
        for ticker, row in df.iterrows():
            try:
                result[str(ticker)] = {
                    "market_cap": int(row["시가총액"]),
                    "shares": int(row["상장주식수"]),
                }
            except (KeyError, ValueError, TypeError):
                continue
        return result
    except Exception:
        return {}


def _today_key() -> str:
    """장 마감 전이면 전 영업일을 사용해도 되지만, 단순화를 위해 오늘 날짜 사용."""
    return datetime.datetime.now().strftime("%Y%m%d")


def get_market_cap_dict(market: str = "ALL") -> Dict[str, Dict[str, int]]:
    """
    {ticker: {"market_cap": int(원), "shares": int(주)}} 형태 반환.
    ALL: 코스피 + 코스닥 합본
    """
    return _fetch_market_cap_table(_today_key(), market)


def get_market_cap_for(code: str) -> Optional[Dict[str, int]]:
    """단일 종목 시총·상장주식수 lookup."""
    if not code:
        return None
    table = get_market_cap_dict("ALL")
    return table.get(str(code))


def format_market_cap(cap: int) -> str:
    """원 단위 시가총액을 사람이 읽기 좋은 형식으로."""
    if not cap or cap <= 0:
        return "-"
    if cap >= 1_000_000_000_000:
        return f"{cap / 1_000_000_000_000:.2f}조원"
    if cap >= 100_000_000:
        return f"{cap / 100_000_000:,.0f}억원"
    return f"{cap:,}원"


def format_shares(shares: int) -> str:
    """상장주식수 포맷 (만주/억주)."""
    if not shares or shares <= 0:
        return "-"
    if shares >= 100_000_000:
        return f"{shares / 100_000_000:.2f}억주"
    if shares >= 10_000:
        return f"{shares / 10_000:,.0f}만주"
    return f"{shares:,}주"


# ─────────────── 섹터 / 주요 분야 캐시 ───────────────
@functools.lru_cache(maxsize=2048)
def get_sector_cached(code: str) -> str:
    """
    네이버 + 정적 매핑 기반 섹터 조회 결과를 프로세스 단위로 캐시.
    종목당 1회만 네이버 호출, 이후 메모리 lookup.
    """
    if not code:
        return "기타"
    try:
        from data.stock_list import get_sector
        return get_sector(str(code), use_naver=True) or "기타"
    except Exception:
        return "기타"


@functools.lru_cache(maxsize=2048)
def get_detailed_sector_cached(code: str) -> Dict[str, Optional[str]]:
    """
    네이버 금융에서 상세 섹터 정보(업종/세부업종/산업군) 조회.

    Returns:
        {'sector': str|None, 'sub_sector': str|None, 'industry': str|None, 'source': str}
    """
    if not code:
        return {"sector": None, "sub_sector": None, "industry": None, "source": "fallback"}
    try:
        from data.stock_list import get_detailed_sector_from_naver
        result = get_detailed_sector_from_naver(str(code))
        if isinstance(result, dict):
            return {
                "sector": result.get("sector"),
                "sub_sector": result.get("sub_sector"),
                "industry": result.get("industry"),
                "source": result.get("source", "naver"),
            }
    except Exception:
        pass
    return {"sector": None, "sub_sector": None, "industry": None, "source": "fallback"}
