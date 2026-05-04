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


# ──────────────────────────────────────────────────────────────
# 매매 판단 (interpretation) — 화면에 "사라/말라"가 명확히 보이게
# ──────────────────────────────────────────────────────────────
def interpret_fib_ma200(close, lookback: int = 120) -> Optional[Dict]:
    """
    피보나치 + 200MA 종합 해석. 매매 스타일별 명확한 판단을 dict로 반환.

    Returns:
        {
          'current_price': float,
          'ma200': float | None,
          'ma200_diff_pct': float | None,   # 현재가가 200MA 대비 몇 % 위/아래
          'trend_label': str,               # '강한 상승' / '상승' / '갈림' / '하락'
          'fib': fibonacci_retracement_levels() 결과,
          'position_label': str,            # '23.6%↓~38.2%↑ 사이' / '23.6% 위' / ...
          'next_support': dict | None,      # 가장 가까운 아래 피보 레벨
          'next_resistance': dict | None,   # 가장 가까운 위 피보 레벨
          'verdicts': [
              {'style': '풀매수 (현재가)', 'badge': '🔴 비추', 'reason': '...'},
              {'style': '분할매수 (중장기)', 'badge': '🟡 관망', 'plan': [...], 'reason': '...'},
              {'style': '보유중', 'badge': '🟢 HOLD', 'stop': price, 'reason': '...'},
              {'style': '단기 트레이딩', 'badge': '🟡 관망', 'reason': '...'},
          ],
          'short_stop': float | None,       # 단기 손절선
          'mid_stop': float | None,         # 중기 손절선 (보통 200MA)
        }
    """
    import pandas as pd

    if close is None or len(close) < 60:
        return None

    fib = fibonacci_retracement_levels(close, lookback)
    if not fib:
        return None

    current_price = float(close.iloc[-1])

    ma200 = None
    ma200_diff_pct = None
    if len(close) >= 200:
        ma200 = float(close.rolling(200).mean().iloc[-1])
        if ma200 > 0:
            ma200_diff_pct = (current_price - ma200) / ma200 * 100

    # ── 추세 라벨
    if ma200_diff_pct is None:
        trend_label = "데이터 부족 (200일 미만)"
    elif ma200_diff_pct >= 20:
        trend_label = "강한 상승추세 (200MA +20%↑)"
    elif ma200_diff_pct >= 5:
        trend_label = "상승추세"
    elif ma200_diff_pct >= -5:
        trend_label = "추세 갈림 (200MA 근접)"
    elif ma200_diff_pct >= -20:
        trend_label = "하락 진입"
    else:
        trend_label = "강한 하락추세"

    # ── 위치 라벨 + next support/resistance
    # 피보 레벨 가격 정렬 (높은 가격 → 낮은 가격)
    sorted_levels = sorted(
        [(k, v) for k, v in fib['levels'].items() if k not in ('0.000', '1.000')],
        key=lambda x: x[1],
        reverse=True,
    )
    next_resistance = None
    next_support = None
    above_levels = [(k, v) for k, v in sorted_levels if v >= current_price]
    below_levels = [(k, v) for k, v in sorted_levels if v < current_price]
    if above_levels:
        k, v = above_levels[-1]  # 위쪽 중 가장 가까운
        next_resistance = {'level': k, 'price': v, 'gap_pct': (v - current_price) / current_price * 100}
    if below_levels:
        k, v = below_levels[0]   # 아래쪽 중 가장 가까운
        next_support = {'level': k, 'price': v, 'gap_pct': (current_price - v) / current_price * 100}

    if next_resistance and next_support:
        position_label = f"{next_support['level']} ↑ ~ {next_resistance['level']} ↓ 사이"
    elif next_support:
        position_label = f"{next_support['level']} 위 (모든 되돌림 위)"
    elif next_resistance:
        position_label = f"{next_resistance['level']} 아래 (이탈)"
    else:
        position_label = "위치 판정 불가"

    # ── 손절선
    short_stop = next_support['price'] if next_support else None
    mid_stop = ma200

    # ── 스타일별 매매 판단
    verdicts = []

    # (1) 풀매수 (지금 즉시 풀매수)
    if ma200_diff_pct is None or ma200_diff_pct < -5:
        verdicts.append({
            'style': '🔥 풀매수 (현재가)',
            'badge': '🔴 비추',
            'reason': '추세가 약하거나 200MA 아래 → 현재가 풀매수 위험',
        })
    elif ma200_diff_pct >= 20 and next_support and next_support['gap_pct'] < 3:
        verdicts.append({
            'style': '🔥 풀매수 (현재가)',
            'badge': '🟡 보수적',
            'reason': f"강한 추세이나 이미 +{ma200_diff_pct:.0f}% 상승 + 직전 지지({next_support['level']}) 근접 → 분할이 유리",
        })
    elif ma200_diff_pct >= 5:
        verdicts.append({
            'style': '🔥 풀매수 (현재가)',
            'badge': '🟡 관망',
            'reason': f"상승추세이나 단일 진입은 R:R 나쁨. 다음 지지({next_support['level'] if next_support else '?'})에서 분할 권장",
        })
    else:
        verdicts.append({
            'style': '🔥 풀매수 (현재가)',
            'badge': '🔴 비추',
            'reason': '추세 모호 → 풀매수 위험',
        })

    # (2) 분할매수 (중장기)
    plan_levels = []
    for key in ('0.382', '0.500', '0.618'):
        price = fib['levels'].get(key)
        if price and price < current_price:
            plan_levels.append({'level': f"{float(key)*100:.1f}%", 'price': price})
    if plan_levels and (ma200_diff_pct is None or ma200_diff_pct >= -10):
        verdicts.append({
            'style': '📦 분할매수 (중장기)',
            'badge': '🟢 권장',
            'plan': plan_levels[:3],
            'reason': f"피보 38.2/50/61.8% 분할 진입. 핵심 손절: 200MA {f'{ma200:,.0f}원' if ma200 else '미산정'}",
        })
    else:
        verdicts.append({
            'style': '📦 분할매수 (중장기)',
            'badge': '🔴 비추',
            'reason': '추세 약화 — 분할 진입 의미 없음',
        })

    # (3) 보유중
    if ma200 is None:
        verdicts.append({
            'style': '🤝 보유중',
            'badge': '⚪ 데이터 부족',
            'reason': '200MA 산출 불가 (데이터 부족)',
        })
    elif current_price >= ma200:
        verdicts.append({
            'style': '🤝 보유중',
            'badge': '🟢 HOLD',
            'stop': ma200,
            'reason': f"200MA({ma200:,.0f}원) 위 → 추세 유효. 200MA 이탈 시 매도",
        })
    else:
        verdicts.append({
            'style': '🤝 보유중',
            'badge': '🔴 매도 검토',
            'stop': ma200,
            'reason': f"200MA({ma200:,.0f}원) 이탈 → 추세 종료 신호",
        })

    # (4) 단기 트레이딩
    if next_support and next_support['gap_pct'] < 1:
        verdicts.append({
            'style': '⚡ 단기 트레이딩',
            'badge': '🟢 진입 시도',
            'reason': f"가장 가까운 지지({next_support['level']}) 근접 — 반등 노림. 손절: 해당 레벨 하단",
        })
    elif next_resistance and next_resistance['gap_pct'] < 1 and ma200_diff_pct is not None and ma200_diff_pct > 5:
        verdicts.append({
            'style': '⚡ 단기 트레이딩',
            'badge': '🟡 단기 매도/숏',
            'reason': f"가장 가까운 저항({next_resistance['level']}) 근접 — 단기 조정 가능",
        })
    else:
        verdicts.append({
            'style': '⚡ 단기 트레이딩',
            'badge': '⚪ 관망',
            'reason': '주요 레벨에서 중간 지점 — 명확한 신호 없음',
        })

    return {
        'current_price': current_price,
        'ma200': ma200,
        'ma200_diff_pct': ma200_diff_pct,
        'trend_label': trend_label,
        'fib': fib,
        'position_label': position_label,
        'next_support': next_support,
        'next_resistance': next_resistance,
        'verdicts': verdicts,
        'short_stop': short_stop,
        'mid_stop': mid_stop,
    }
