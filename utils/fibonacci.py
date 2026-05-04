"""
피보나치 되돌림 + 200MA Confluence 분석 유틸

- 최근 N일 구간의 저점→고점(또는 고점→저점)을 자동 인식해 되돌림 레벨 계산
- 200일 이동평균과 피보나치 레벨이 겹치는 구간(confluence)을 감지
- 핵심 인사이트(웹 리서치 기반): 0.618 또는 0.382 되돌림 레벨이 200MA와 ±2% 이내로
  겹치면 "강한 지지/저항" 신호로 해석. 단일 지표보다 신뢰도가 높음.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

import pandas as pd

# 표준 피보나치 비율 (0.0 / 1.0 = 시작·끝점, 나머지는 되돌림 레벨)
FIB_LEVELS: Tuple[float, ...] = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)


def find_swing_low_high(
    close: pd.Series, lookback: int = 120
) -> Optional[Dict[str, float]]:
    """
    최근 `lookback`일 안에서 가장 낮은 종가와 가장 높은 종가, 그리고 둘의 시간 순서를 식별.

    Returns:
        {
            'low': float, 'low_idx': int (음수 인덱스, -1이 최신),
            'high': float, 'high_idx': int,
            'direction': 'up' | 'down'  (저점이 먼저면 'up', 고점이 먼저면 'down')
        }
        데이터 부족 시 None.
    """
    if close is None or len(close) < 2:
        return None
    window = close.iloc[-lookback:] if len(close) > lookback else close
    if window.empty:
        return None

    low_pos = int(window.values.argmin())
    high_pos = int(window.values.argmax())
    if low_pos == high_pos:
        return None

    n = len(window)
    return {
        "low": float(window.iloc[low_pos]),
        "low_idx": low_pos - n,  # -1 = 가장 최신
        "high": float(window.iloc[high_pos]),
        "high_idx": high_pos - n,
        "direction": "up" if low_pos < high_pos else "down",
    }


def fibonacci_retracement_levels(
    close: pd.Series, lookback: int = 120
) -> Optional[Dict]:
    """
    되돌림 레벨 dict 반환. 상승 추세(저점→고점)에서는 고점에서 하락한 가격이
    어느 비율에서 지지받는지를 보여주고, 반대 방향이면 그 반대.

    Returns:
        {
            'direction': 'up' | 'down',
            'low': float, 'high': float, 'range': float,
            'levels': {'0.0': float, '0.236': float, ..., '1.0': float}
        }
    """
    swing = find_swing_low_high(close, lookback)
    if swing is None:
        return None

    low = swing["low"]
    high = swing["high"]
    rng = high - low
    if rng <= 0:
        return None

    # direction='up' (상승추세): 고점에서 되돌림 → 가격 = high - rng * level
    # direction='down' (하락추세): 저점에서 반등 → 가격 = low + rng * level
    if swing["direction"] == "up":
        levels = {f"{lv:.3f}": high - rng * lv for lv in FIB_LEVELS}
    else:
        levels = {f"{lv:.3f}": low + rng * lv for lv in FIB_LEVELS}

    return {
        "direction": swing["direction"],
        "low": low,
        "high": high,
        "range": rng,
        "low_idx": swing["low_idx"],
        "high_idx": swing["high_idx"],
        "levels": levels,
    }


def detect_ma200_fibonacci_confluence(
    close: pd.Series,
    lookback: int = 120,
    tolerance_pct: float = 2.0,
) -> Optional[Dict]:
    """
    200일선과 피보나치 되돌림 레벨이 ±tolerance_pct% 이내에서 겹치는지 검사.

    Returns:
        confluence가 있으면 {
            'ma200': float,
            'matched': [{'level': '0.618', 'price': float, 'gap_pct': float}, ...],
            'fib': fibonacci_retracement_levels() 결과,
            'price': float (현재가),
            'price_zone': '지지권' | '저항권' | '중립'  (현재가가 매칭 레벨 근처면 의미있는 zone)
        }
        없으면 None.

    웹 리서치 인사이트: 0.382 / 0.5 / 0.618 레벨에서의 confluence가 가장 의미있음.
    이 함수는 모든 레벨을 검사하되, 0.0/1.0(시작·끝점)은 제외.
    """
    if close is None or len(close) < 200:
        return None

    ma200 = float(close.rolling(200).mean().iloc[-1])
    if ma200 <= 0:
        return None

    fib = fibonacci_retracement_levels(close, lookback)
    if not fib:
        return None

    matched = []
    for level_key, level_price in fib["levels"].items():
        # 시작·끝점은 의미없음
        if level_key in ("0.000", "1.000"):
            continue
        if level_price <= 0:
            continue
        gap_pct = abs(level_price - ma200) / ma200 * 100
        if gap_pct <= tolerance_pct:
            matched.append({
                "level": level_key,
                "price": level_price,
                "gap_pct": round(gap_pct, 3),
            })

    if not matched:
        return None

    current_price = float(close.iloc[-1])

    # 현재가가 confluence 가격과 가까우면 (±2%) 매수/저항 후보 zone
    closest = min(matched, key=lambda m: abs(m["price"] - current_price))
    closest_gap_pct = abs(closest["price"] - current_price) / current_price * 100
    if closest_gap_pct <= 2.0:
        # 상승추세 + 현재가가 confluence 위 = 지지권
        # 하락추세 + 현재가가 confluence 아래 = 저항권
        if fib["direction"] == "up" and current_price >= closest["price"] * 0.99:
            zone = "지지권"
        elif fib["direction"] == "down" and current_price <= closest["price"] * 1.01:
            zone = "저항권"
        else:
            zone = "근접"
    else:
        zone = "중립"

    return {
        "ma200": ma200,
        "matched": matched,
        "fib": fib,
        "price": current_price,
        "price_zone": zone,
    }


def fibonacci_summary_text(fib: Dict) -> str:
    """간결한 요약 텍스트 (UI 표시용)."""
    if not fib:
        return "되돌림 데이터 없음"
    direction = "상승추세 되돌림" if fib["direction"] == "up" else "하락추세 반등"
    levels = fib["levels"]
    return (
        f"{direction}: 저점 {fib['low']:,.0f} → 고점 {fib['high']:,.0f}, "
        f"38.2% {levels['0.382']:,.0f} / "
        f"50% {levels['0.500']:,.0f} / "
        f"61.8% {levels['0.618']:,.0f}"
    )
