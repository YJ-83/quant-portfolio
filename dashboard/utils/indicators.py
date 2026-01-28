"""
기술적 지표 계산 공통 모듈
- RSI, MACD, 볼린저밴드, 거래량 분석 등
- screener.py, chart_strategy.py 등에서 공유
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any


# ========== RSI (Relative Strength Index) ==========

def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    RSI 계산

    Args:
        prices: 종가 시리즈
        period: 기간 (기본 14일)

    Returns:
        RSI 값 (0-100)
    """
    if len(prices) < period + 1:
        return 50.0

    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # ZeroDivisionError 방지: avg_loss가 0이면 RS를 매우 큰 값으로 설정
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rs = rs.fillna(100)  # loss가 0이면 RSI는 100에 가까움
    rsi = 100 - (100 / (1 + rs))

    result = rsi.iloc[-1]
    return float(result) if not pd.isna(result) else 50.0


def get_rsi_signal(rsi: float) -> Dict[str, Any]:
    """
    RSI 기반 매매 시그널

    Args:
        rsi: RSI 값

    Returns:
        시그널 정보 dict
    """
    if rsi <= 25:
        return {'signal': 'strong_buy', 'strength': '강함', 'message': 'RSI 극심한 과매도'}
    elif rsi <= 30:
        return {'signal': 'buy', 'strength': '보통', 'message': 'RSI 과매도 구간'}
    elif rsi >= 75:
        return {'signal': 'strong_sell', 'strength': '강함', 'message': 'RSI 극심한 과매수'}
    elif rsi >= 70:
        return {'signal': 'sell', 'strength': '보통', 'message': 'RSI 과매수 구간'}
    else:
        return {'signal': 'neutral', 'strength': '없음', 'message': '중립'}


# ========== MACD (Moving Average Convergence Divergence) ==========

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Any]:
    """
    MACD 계산

    Args:
        prices: 종가 시리즈
        fast: 단기 EMA 기간 (기본 12)
        slow: 장기 EMA 기간 (기본 26)
        signal: 시그널 EMA 기간 (기본 9)

    Returns:
        MACD 정보 dict (macd, signal, histogram, golden_cross, dead_cross)
    """
    if len(prices) < slow + signal:
        return {
            'macd': 0,
            'signal': 0,
            'histogram': 0,
            'golden_cross': False,
            'dead_cross': False,
            'cross': None  # 호환성 유지
        }

    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    # 골든크로스/데드크로스 감지
    golden_cross = False
    dead_cross = False
    cross = None

    if len(histogram) >= 2:
        prev_hist = histogram.iloc[-2]
        curr_hist = histogram.iloc[-1]
        if prev_hist < 0 and curr_hist > 0:
            golden_cross = True
            cross = 'golden'
        elif prev_hist > 0 and curr_hist < 0:
            dead_cross = True
            cross = 'dead'

    return {
        'macd': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0,
        'signal': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0,
        'histogram': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0,
        'golden_cross': golden_cross,
        'dead_cross': dead_cross,
        'cross': cross  # 호환성 유지 ('golden', 'dead', None)
    }


def get_macd_signal(macd_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MACD 기반 매매 시그널
    """
    if macd_data.get('golden_cross'):
        return {'signal': 'buy', 'strength': '강함', 'message': 'MACD 골든크로스'}
    elif macd_data.get('dead_cross'):
        return {'signal': 'sell', 'strength': '강함', 'message': 'MACD 데드크로스'}
    elif macd_data.get('histogram', 0) > 0:
        return {'signal': 'bullish', 'strength': '약함', 'message': 'MACD 양수 (상승세)'}
    elif macd_data.get('histogram', 0) < 0:
        return {'signal': 'bearish', 'strength': '약함', 'message': 'MACD 음수 (하락세)'}
    else:
        return {'signal': 'neutral', 'strength': '없음', 'message': '중립'}


# ========== 볼린저밴드 (Bollinger Bands) ==========

def calculate_bollinger(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, Any]:
    """
    볼린저밴드 계산

    Args:
        prices: 종가 시리즈
        period: 이동평균 기간 (기본 20)
        std_dev: 표준편차 배수 (기본 2)

    Returns:
        볼린저밴드 정보 dict
    """
    if len(prices) < period:
        return {
            'upper': 0,
            'middle': 0,
            'lower': 0,
            'position': 0.5,
            'bandwidth': 0,
            'touch_upper': False,
            'touch_lower': False
        }

    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    current_price = prices.iloc[-1]
    upper_val = upper.iloc[-1]
    middle_val = middle.iloc[-1]
    lower_val = lower.iloc[-1]

    # 밴드 내 위치 (0 = 하단, 1 = 상단)
    band_width = upper_val - lower_val
    position = (current_price - lower_val) / band_width if band_width > 0 else 0.5

    # 밴드폭 (백분율)
    bandwidth_pct = (band_width / middle_val * 100) if middle_val > 0 else 0

    return {
        'upper': float(upper_val) if not pd.isna(upper_val) else 0,
        'middle': float(middle_val) if not pd.isna(middle_val) else 0,
        'lower': float(lower_val) if not pd.isna(lower_val) else 0,
        'position': float(position),  # 0~1 정규화
        'bandwidth': float(bandwidth_pct),  # 백분율
        'touch_upper': current_price >= upper_val,
        'touch_lower': current_price <= lower_val
    }


def get_bollinger_signal(bb_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    볼린저밴드 기반 매매 시그널
    """
    position = bb_data.get('position', 0.5)

    if bb_data.get('touch_lower') or position <= 0.05:
        return {'signal': 'strong_buy', 'strength': '강함', 'message': '볼린저 하단 돌파'}
    elif position <= 0.1:
        return {'signal': 'buy', 'strength': '보통', 'message': '볼린저 하단 근접'}
    elif bb_data.get('touch_upper') or position >= 0.95:
        return {'signal': 'strong_sell', 'strength': '강함', 'message': '볼린저 상단 돌파'}
    elif position >= 0.9:
        return {'signal': 'sell', 'strength': '보통', 'message': '볼린저 상단 근접'}
    else:
        return {'signal': 'neutral', 'strength': '없음', 'message': '중립'}


# ========== 거래량 분석 ==========

def calculate_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
    """
    거래량 비율 계산 (현재 거래량 / 평균 거래량)

    Args:
        volumes: 거래량 시리즈
        period: 평균 계산 기간 (기본 20)

    Returns:
        거래량 비율 (1.0 = 평균)
    """
    if len(volumes) < period + 1:
        return 1.0

    avg_volume = volumes.iloc[-period-1:-1].mean()
    current_volume = volumes.iloc[-1]

    if avg_volume == 0:
        return 1.0

    return float(current_volume / avg_volume)


def get_volume_signal(volume_ratio: float, price_change: float = 0) -> Dict[str, Any]:
    """
    거래량 기반 매매 시그널

    Args:
        volume_ratio: 거래량 비율
        price_change: 가격 변동률 (양수=상승, 음수=하락)
    """
    if volume_ratio >= 5:
        strength = '매우강함'
        if price_change > 0:
            return {'signal': 'strong_buy', 'strength': strength, 'message': f'거래량 폭발 ({volume_ratio:.1f}배)'}
        else:
            return {'signal': 'strong_sell', 'strength': strength, 'message': f'거래량 폭발 하락 ({volume_ratio:.1f}배)'}
    elif volume_ratio >= 3:
        strength = '강함'
        if price_change > 0:
            return {'signal': 'buy', 'strength': strength, 'message': f'거래량 급증 ({volume_ratio:.1f}배)'}
        else:
            return {'signal': 'sell', 'strength': strength, 'message': f'거래량 급증 하락 ({volume_ratio:.1f}배)'}
    elif volume_ratio >= 2:
        strength = '보통'
        if price_change > 0:
            return {'signal': 'weak_buy', 'strength': strength, 'message': f'거래량 증가 ({volume_ratio:.1f}배)'}
        else:
            return {'signal': 'weak_sell', 'strength': strength, 'message': f'거래량 증가 하락 ({volume_ratio:.1f}배)'}
    elif volume_ratio <= 0.5:
        return {'signal': 'low_volume', 'strength': '약함', 'message': f'거래량 급감 ({volume_ratio:.1f}배)'}
    else:
        return {'signal': 'neutral', 'strength': '없음', 'message': '거래량 정상'}


# ========== 이동평균선 ==========

def calculate_moving_averages(prices: pd.Series, periods: list = [5, 20, 60, 120]) -> Dict[int, float]:
    """
    여러 기간의 이동평균선 계산

    Args:
        prices: 종가 시리즈
        periods: 계산할 기간 리스트

    Returns:
        {기간: 이동평균값} dict
    """
    result = {}
    for period in periods:
        if len(prices) >= period:
            ma = prices.rolling(window=period).mean().iloc[-1]
            result[period] = float(ma) if not pd.isna(ma) else None
        else:
            result[period] = None
    return result


def check_ma_alignment(ma_dict: Dict[int, float]) -> Dict[str, Any]:
    """
    이동평균선 정배열/역배열 확인

    Args:
        ma_dict: 이동평균 dict (예: {5: 100, 20: 95, 60: 90})

    Returns:
        배열 상태 정보
    """
    # 유효한 값만 필터링
    valid_mas = {k: v for k, v in sorted(ma_dict.items()) if v is not None}

    if len(valid_mas) < 2:
        return {'alignment': 'unknown', 'message': '데이터 부족'}

    periods = list(valid_mas.keys())
    values = list(valid_mas.values())

    # 정배열: 단기 > 장기 (모든 쌍에서)
    is_bullish = all(values[i] > values[i+1] for i in range(len(values)-1))

    # 역배열: 단기 < 장기
    is_bearish = all(values[i] < values[i+1] for i in range(len(values)-1))

    if is_bullish:
        return {'alignment': 'bullish', 'signal': 'buy', 'message': f'정배열 ({">".join(map(str, periods))}일선)'}
    elif is_bearish:
        return {'alignment': 'bearish', 'signal': 'sell', 'message': f'역배열 ({">".join(map(str, periods))}일선)'}
    else:
        return {'alignment': 'mixed', 'signal': 'neutral', 'message': '혼조세'}


def check_ma_cross(prices: pd.Series, fast_period: int = 5, slow_period: int = 20) -> Dict[str, Any]:
    """
    이동평균선 골든크로스/데드크로스 확인
    """
    if len(prices) < slow_period + 1:
        return {'cross': None, 'message': '데이터 부족'}

    fast_ma = prices.rolling(window=fast_period).mean()
    slow_ma = prices.rolling(window=slow_period).mean()

    # 현재와 전일 비교
    curr_fast = fast_ma.iloc[-1]
    curr_slow = slow_ma.iloc[-1]
    prev_fast = fast_ma.iloc[-2]
    prev_slow = slow_ma.iloc[-2]

    if prev_fast < prev_slow and curr_fast > curr_slow:
        return {'cross': 'golden', 'signal': 'buy', 'message': f'골든크로스 ({fast_period}/{slow_period}일선)'}
    elif prev_fast > prev_slow and curr_fast < curr_slow:
        return {'cross': 'dead', 'signal': 'sell', 'message': f'데드크로스 ({fast_period}/{slow_period}일선)'}
    else:
        return {'cross': None, 'signal': 'neutral', 'message': '크로스 없음'}


# ========== 52주 고저점 분석 ==========

def calculate_52week_range(df: pd.DataFrame, days: int = 250) -> Dict[str, Any]:
    """
    52주 고저점 분석

    Args:
        df: OHLCV 데이터프레임
        days: 분석 기간 (기본 250 거래일 ≈ 52주)

    Returns:
        52주 고저점 정보
    """
    if df is None or df.empty:
        return None

    period = min(days, len(df))
    recent_data = df.tail(period)

    low_52w = recent_data['low'].min()
    high_52w = recent_data['high'].max()
    current_price = df['close'].iloc[-1]

    # 상승/하락률 계산
    rise_from_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 0
    drop_from_high = ((high_52w - current_price) / high_52w * 100) if high_52w > 0 else 0

    return {
        'low_52w': float(low_52w),
        'high_52w': float(high_52w),
        'current_price': float(current_price),
        'rise_from_low': round(rise_from_low, 2),
        'drop_from_high': round(drop_from_high, 2),
        'is_near_low': rise_from_low < 20,  # 저점 대비 20% 이내
        'is_near_high': drop_from_high < 10  # 고점 대비 10% 이내
    }


# ========== 종합 분석 ==========

def analyze_stock_technical(df: pd.DataFrame) -> Dict[str, Any]:
    """
    종목 종합 기술적 분석

    Args:
        df: OHLCV 데이터프레임

    Returns:
        종합 분석 결과
    """
    if df is None or df.empty or len(df) < 30:
        return None

    close = df['close']
    volume = df['volume']

    # 가격 변화
    current_price = close.iloc[-1]
    prev_price = close.iloc[-2] if len(close) >= 2 else current_price
    change_rate = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

    # 기술적 지표 계산
    rsi = calculate_rsi(close)
    macd = calculate_macd(close)
    bollinger = calculate_bollinger(close)
    volume_ratio = calculate_volume_ratio(volume)
    ma_dict = calculate_moving_averages(close, [5, 20, 60, 120])

    # 시그널 수집
    signals = []

    # RSI 시그널
    rsi_signal = get_rsi_signal(rsi)
    if rsi_signal['signal'] not in ['neutral']:
        signals.append(rsi_signal)

    # MACD 시그널
    macd_signal = get_macd_signal(macd)
    if macd_signal['signal'] in ['buy', 'sell']:
        signals.append(macd_signal)

    # 볼린저밴드 시그널
    bb_signal = get_bollinger_signal(bollinger)
    if bb_signal['signal'] not in ['neutral']:
        signals.append(bb_signal)

    # 거래량 시그널
    vol_signal = get_volume_signal(volume_ratio, change_rate)
    if vol_signal['signal'] not in ['neutral']:
        signals.append(vol_signal)

    return {
        'price': float(current_price),
        'change_rate': round(change_rate, 2),
        'rsi': round(rsi, 2),
        'macd': macd,
        'bollinger': bollinger,
        'volume_ratio': round(volume_ratio, 2),
        'moving_averages': ma_dict,
        'signals': signals
    }


# ========== 쌍바닥(W패턴) / 역헤드앤숄더 패턴 감지 ==========

def detect_double_bottom(df: pd.DataFrame, lookback: int = 60, tolerance: float = 0.03) -> Dict[str, Any]:
    """
    쌍바닥(W패턴) 감지

    Args:
        df: OHLCV 데이터프레임
        lookback: 분석 기간 (기본 60일)
        tolerance: 두 저점 간 허용 오차 (기본 3%)

    Returns:
        패턴 감지 결과
    """
    if df is None or len(df) < lookback:
        return {'detected': False, 'message': '데이터 부족'}

    recent = df.tail(lookback).copy()
    lows = recent['low'].values
    closes = recent['close'].values
    highs = recent['high'].values

    # 저점 찾기 (로컬 미니멈)
    local_mins = []
    for i in range(2, len(lows) - 2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            local_mins.append((i, lows[i]))

    if len(local_mins) < 2:
        return {'detected': False, 'message': '저점 부족'}

    # 최근 두 저점 분석
    for i in range(len(local_mins) - 1, 0, -1):
        second_idx, second_low = local_mins[i]
        first_idx, first_low = local_mins[i - 1]

        # 두 저점 사이 간격 확인 (최소 10일)
        if second_idx - first_idx < 10:
            continue

        # 두 저점이 비슷한 수준인지 확인 (tolerance 내)
        low_diff = abs(second_low - first_low) / min(first_low, second_low)
        if low_diff > tolerance:
            continue

        # 두 저점 사이 고점(넥라인) 찾기
        between_highs = highs[first_idx:second_idx]
        neckline = max(between_highs)
        neckline_idx = first_idx + np.argmax(between_highs)

        # 현재 가격이 넥라인을 돌파했는지
        current_price = closes[-1]
        neckline_broken = current_price > neckline

        # 두 번째 저점 이후 상승 여부
        price_after_second = closes[second_idx:]
        rising_after_second = len(price_after_second) > 0 and price_after_second[-1] > second_low * 1.02

        if rising_after_second:
            pattern_strength = 'strong' if neckline_broken else 'forming'
            message = f'쌍바닥 패턴 감지 (넥라인: {neckline:,.0f}원)'
            if neckline_broken:
                message += ' - 넥라인 돌파!'

            return {
                'detected': True,
                'pattern': 'double_bottom',
                'strength': pattern_strength,
                'first_low': float(first_low),
                'second_low': float(second_low),
                'neckline': float(neckline),
                'neckline_broken': neckline_broken,
                'current_price': float(current_price),
                'signal': 'buy' if neckline_broken else 'watch',
                'message': message
            }

    return {'detected': False, 'message': '쌍바닥 패턴 미감지'}


def detect_inverse_head_shoulders(df: pd.DataFrame, lookback: int = 80, tolerance: float = 0.05) -> Dict[str, Any]:
    """
    역헤드앤숄더 패턴 감지

    Args:
        df: OHLCV 데이터프레임
        lookback: 분석 기간 (기본 80일)
        tolerance: 어깨 높이 허용 오차 (기본 5%)

    Returns:
        패턴 감지 결과
    """
    if df is None or len(df) < lookback:
        return {'detected': False, 'message': '데이터 부족'}

    recent = df.tail(lookback).copy()
    lows = recent['low'].values
    closes = recent['close'].values
    highs = recent['high'].values

    # 저점 찾기
    local_mins = []
    for i in range(3, len(lows) - 3):
        if lows[i] == min(lows[i-3:i+4]):
            local_mins.append((i, lows[i]))

    if len(local_mins) < 3:
        return {'detected': False, 'message': '저점 부족'}

    # 최근 3개 저점으로 패턴 분석
    for i in range(len(local_mins) - 1, 1, -1):
        right_shoulder_idx, right_shoulder = local_mins[i]
        head_idx, head = local_mins[i - 1]
        left_shoulder_idx, left_shoulder = local_mins[i - 2]

        # 헤드가 양 어깨보다 낮은지 확인
        if head >= left_shoulder or head >= right_shoulder:
            continue

        # 두 어깨가 비슷한 높이인지 확인
        shoulder_diff = abs(left_shoulder - right_shoulder) / min(left_shoulder, right_shoulder)
        if shoulder_diff > tolerance:
            continue

        # 간격 확인
        if head_idx - left_shoulder_idx < 5 or right_shoulder_idx - head_idx < 5:
            continue

        # 넥라인 계산 (두 어깨 사이 고점들의 평균)
        left_neckline = max(highs[left_shoulder_idx:head_idx])
        right_neckline = max(highs[head_idx:right_shoulder_idx])
        neckline = (left_neckline + right_neckline) / 2

        # 현재 가격이 넥라인을 돌파했는지
        current_price = closes[-1]
        neckline_broken = current_price > neckline

        pattern_strength = 'strong' if neckline_broken else 'forming'
        message = f'역헤드앤숄더 패턴 감지 (넥라인: {neckline:,.0f}원)'
        if neckline_broken:
            message += ' - 넥라인 돌파!'

        return {
            'detected': True,
            'pattern': 'inverse_head_shoulders',
            'strength': pattern_strength,
            'left_shoulder': float(left_shoulder),
            'head': float(head),
            'right_shoulder': float(right_shoulder),
            'neckline': float(neckline),
            'neckline_broken': neckline_broken,
            'current_price': float(current_price),
            'signal': 'buy' if neckline_broken else 'watch',
            'message': message
        }

    return {'detected': False, 'message': '역헤드앤숄더 패턴 미감지'}


# ========== 눌림목 매수 타이밍 감지 ==========

def detect_pullback_buy(df: pd.DataFrame, ma_periods: list = [5, 20, 60]) -> Dict[str, Any]:
    """
    눌림목 매수 타이밍 감지
    상승 추세 중 이동평균선 지지 확인

    Args:
        df: OHLCV 데이터프레임
        ma_periods: 확인할 이동평균 기간 리스트

    Returns:
        눌림목 분석 결과
    """
    if df is None or len(df) < max(ma_periods) + 20:
        return {'detected': False, 'message': '데이터 부족'}

    close = df['close']
    low = df['low']
    volume = df['volume']

    # 이동평균선 계산
    mas = {}
    for period in ma_periods:
        mas[period] = close.rolling(window=period).mean()

    current_price = close.iloc[-1]
    current_low = low.iloc[-1]

    # 정배열 확인 (5일 > 20일 > 60일)
    is_bullish_aligned = True
    for i in range(len(ma_periods) - 1):
        shorter = mas[ma_periods[i]].iloc[-1]
        longer = mas[ma_periods[i + 1]].iloc[-1]
        if shorter < longer:
            is_bullish_aligned = False
            break

    # 눌림목 조건: 가격이 단기 MA 아래로 내려왔다가 지지받는 경우
    pullback_detected = False
    support_ma = None

    for period in ma_periods:
        ma_value = mas[period].iloc[-1]
        ma_prev = mas[period].iloc[-5:-1].mean()  # 최근 4일 평균

        # 저가가 이동평균선 근처까지 내려왔는지 (3% 이내)
        if current_low <= ma_value * 1.03 and current_price > ma_value:
            pullback_detected = True
            support_ma = period
            break

    # 거래량 감소 확인 (조정 구간 특성)
    recent_volume = volume.iloc[-5:].mean()
    prev_volume = volume.iloc[-20:-5].mean()
    volume_decreased = recent_volume < prev_volume * 0.8

    if pullback_detected and is_bullish_aligned:
        strength = 'strong' if volume_decreased else 'moderate'
        message = f'눌림목 매수 타이밍 ({support_ma}일선 지지)'
        if volume_decreased:
            message += ' + 거래량 감소'

        return {
            'detected': True,
            'pattern': 'pullback',
            'strength': strength,
            'support_ma': support_ma,
            'ma_value': float(mas[support_ma].iloc[-1]),
            'current_price': float(current_price),
            'is_bullish_aligned': is_bullish_aligned,
            'volume_decreased': volume_decreased,
            'signal': 'buy',
            'message': message
        }

    return {'detected': False, 'message': '눌림목 패턴 미감지'}


# ========== 세력 매집 패턴 분석 ==========

def detect_accumulation(df: pd.DataFrame, lookback: int = 30) -> Dict[str, Any]:
    """
    세력 매집 패턴 감지
    거래량 급증 + 가격 횡보 = 매집 구간

    Args:
        df: OHLCV 데이터프레임
        lookback: 분석 기간 (기본 30일)

    Returns:
        매집 패턴 분석 결과
    """
    if df is None or len(df) < lookback + 20:
        return {'detected': False, 'message': '데이터 부족'}

    recent = df.tail(lookback).copy()
    close = recent['close']
    volume = recent['volume']

    # 이전 기간 데이터
    prev = df.iloc[-(lookback + 20):-(lookback)]
    prev_avg_volume = prev['volume'].mean()
    prev_close = prev['close'].mean()

    # 가격 변동성 계산 (횡보 확인)
    close_mean = close.mean()
    if close_mean > 0:
        price_volatility = (close.max() - close.min()) / close_mean * 100
    else:
        price_volatility = 0  # 모든 값이 0인 경우 (매우 드문 케이스)
    is_sideways = price_volatility < 15  # 15% 이내 변동

    # 거래량 분석
    avg_volume = volume.mean()
    volume_ratio = avg_volume / prev_avg_volume if prev_avg_volume > 0 else 1

    # OBV (On Balance Volume) 분석
    obv = []
    obv_val = 0
    for i in range(len(close)):
        if i > 0:
            if close.iloc[i] > close.iloc[i-1]:
                obv_val += volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv_val -= volume.iloc[i]
        obv.append(obv_val)

    obv_series = pd.Series(obv)
    # OBV 추세 계산 (빈 시리즈 및 0으로 나누기 보호)
    if len(obv_series) > 0 and obv_series.iloc[0] != 0:
        obv_trend = (obv_series.iloc[-1] - obv_series.iloc[0]) / abs(obv_series.iloc[0]) * 100
    else:
        obv_trend = 0

    # 거래량 급증일 수 계산
    high_volume_days = sum(1 for v in volume if v > prev_avg_volume * 2)

    # 매집 패턴 판정
    accumulation_detected = False
    accumulation_score = 0

    if is_sideways:
        accumulation_score += 1
    if volume_ratio >= 1.5:
        accumulation_score += 1
    if obv_trend > 20:  # OBV 상승 추세
        accumulation_score += 1
    if high_volume_days >= 3:
        accumulation_score += 1

    if accumulation_score >= 3:
        accumulation_detected = True

    if accumulation_detected:
        strength = 'strong' if accumulation_score >= 4 else 'moderate'
        message = f'매집 패턴 감지 (거래량 {volume_ratio:.1f}배, OBV +{obv_trend:.1f}%)'

        return {
            'detected': True,
            'pattern': 'accumulation',
            'strength': strength,
            'is_sideways': is_sideways,
            'volume_ratio': round(volume_ratio, 2),
            'obv_trend': round(obv_trend, 2),
            'high_volume_days': high_volume_days,
            'accumulation_score': accumulation_score,
            'signal': 'watch',  # 매집 중이므로 관망
            'message': message
        }

    return {'detected': False, 'message': '매집 패턴 미감지'}


# ========== 매물대 분석 ==========

def analyze_volume_profile(df: pd.DataFrame, num_bins: int = 20) -> Dict[str, Any]:
    """
    가격대별 거래량 분포(Volume Profile) 분석

    Args:
        df: OHLCV 데이터프레임
        num_bins: 가격대 구간 수 (기본 20)

    Returns:
        매물대 분석 결과
    """
    if df is None or len(df) < 60:
        return {'detected': False, 'message': '데이터 부족'}

    # 최근 120일 데이터
    recent = df.tail(120)

    # 가격 범위
    price_min = recent['low'].min()
    price_max = recent['high'].max()
    price_range = price_max - price_min
    bin_size = price_range / num_bins

    # 가격대별 거래량 집계
    volume_by_price = {}
    for i in range(num_bins):
        price_low = price_min + i * bin_size
        price_high = price_min + (i + 1) * bin_size
        mid_price = (price_low + price_high) / 2

        # 해당 가격대를 지나간 거래량 합산
        mask = (recent['low'] <= price_high) & (recent['high'] >= price_low)
        total_volume = recent.loc[mask, 'volume'].sum()
        volume_by_price[mid_price] = total_volume

    # 주요 매물대 찾기 (상위 3개)
    sorted_zones = sorted(volume_by_price.items(), key=lambda x: x[1], reverse=True)
    major_zones = sorted_zones[:3]

    current_price = df['close'].iloc[-1]

    # 가장 가까운 지지/저항 매물대 찾기
    support_zone = None
    resistance_zone = None

    for price, volume in sorted_zones:
        if price < current_price and (support_zone is None or price > support_zone[0]):
            support_zone = (price, volume)
        elif price > current_price and (resistance_zone is None or price < resistance_zone[0]):
            resistance_zone = (price, volume)

    # 현재 가격이 매물대 근처인지
    near_support = support_zone and abs(current_price - support_zone[0]) / current_price < 0.03
    near_resistance = resistance_zone and abs(resistance_zone[0] - current_price) / current_price < 0.03

    return {
        'detected': True,
        'major_zones': [(round(p, 0), int(v)) for p, v in major_zones],
        'support_zone': (round(support_zone[0], 0), int(support_zone[1])) if support_zone else None,
        'resistance_zone': (round(resistance_zone[0], 0), int(resistance_zone[1])) if resistance_zone else None,
        'current_price': float(current_price),
        'near_support': near_support,
        'near_resistance': near_resistance,
        'signal': 'buy' if near_support else ('sell' if near_resistance else 'neutral'),
        'message': f'매물대 분석: 지지 {support_zone[0]:,.0f}원 / 저항 {resistance_zone[0]:,.0f}원' if support_zone and resistance_zone else '매물대 분석 완료'
    }


# ========== 이격도 분석 ==========

def calculate_disparity(df: pd.DataFrame, periods: list = [5, 20, 60]) -> Dict[str, Any]:
    """
    이격도 분석 (현재가격 / 이동평균 * 100)

    Args:
        df: OHLCV 데이터프레임
        periods: 분석할 이동평균 기간

    Returns:
        이격도 분석 결과
    """
    if df is None or len(df) < max(periods) + 1:
        return {'detected': False, 'message': '데이터 부족'}

    close = df['close']
    current_price = close.iloc[-1]

    disparities = {}
    signals = []

    for period in periods:
        ma = close.rolling(window=period).mean().iloc[-1]
        if ma > 0:
            disparity = (current_price / ma) * 100
            disparities[period] = round(disparity, 2)

            # 과매수/과매도 판단
            if disparity < 95:  # 5% 이상 하락 이격
                signals.append(f'{period}일 이격도 과매도 ({disparity:.1f}%)')
            elif disparity > 110:  # 10% 이상 상승 이격
                signals.append(f'{period}일 이격도 과매수 ({disparity:.1f}%)')

    # 종합 판단
    avg_disparity = sum(disparities.values()) / len(disparities) if disparities else 100

    if avg_disparity < 95:
        overall_signal = 'oversold'
        message = '이격도 과매도 구간 (매수 기회)'
    elif avg_disparity > 108:
        overall_signal = 'overbought'
        message = '이격도 과매수 구간 (조정 주의)'
    else:
        overall_signal = 'neutral'
        message = '이격도 정상 범위'

    return {
        'detected': True,
        'disparities': disparities,
        'avg_disparity': round(avg_disparity, 2),
        'signals': signals,
        'overall_signal': overall_signal,
        'signal': 'buy' if overall_signal == 'oversold' else ('sell' if overall_signal == 'overbought' else 'neutral'),
        'message': message
    }


# ========== 종합 스윙매매 분석 ==========

def analyze_swing_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """
    스윙매매를 위한 종합 패턴 분석

    Args:
        df: OHLCV 데이터프레임

    Returns:
        종합 스윙매매 분석 결과
    """
    if df is None or df.empty:
        return None

    results = {
        'patterns': [],
        'signals': [],
        'buy_signals': 0,
        'sell_signals': 0,
        'watch_signals': 0
    }

    # 1. 쌍바닥 패턴
    double_bottom = detect_double_bottom(df)
    if double_bottom.get('detected'):
        results['patterns'].append(double_bottom)
        if double_bottom.get('signal') == 'buy':
            results['buy_signals'] += 1
            results['signals'].append({'type': '쌍바닥', 'signal': 'buy', 'message': double_bottom['message']})
        elif double_bottom.get('signal') == 'watch':
            results['watch_signals'] += 1
            results['signals'].append({'type': '쌍바닥', 'signal': 'watch', 'message': double_bottom['message']})

    # 2. 역헤드앤숄더
    ihs = detect_inverse_head_shoulders(df)
    if ihs.get('detected'):
        results['patterns'].append(ihs)
        if ihs.get('signal') == 'buy':
            results['buy_signals'] += 1
            results['signals'].append({'type': '역헤드앤숄더', 'signal': 'buy', 'message': ihs['message']})
        elif ihs.get('signal') == 'watch':
            results['watch_signals'] += 1
            results['signals'].append({'type': '역헤드앤숄더', 'signal': 'watch', 'message': ihs['message']})

    # 3. 눌림목 매수
    pullback = detect_pullback_buy(df)
    if pullback.get('detected'):
        results['patterns'].append(pullback)
        results['buy_signals'] += 1
        results['signals'].append({'type': '눌림목', 'signal': 'buy', 'message': pullback['message']})

    # 4. 매집 패턴
    accumulation = detect_accumulation(df)
    if accumulation.get('detected'):
        results['patterns'].append(accumulation)
        results['watch_signals'] += 1
        results['signals'].append({'type': '매집', 'signal': 'watch', 'message': accumulation['message']})

    # 5. 매물대 분석
    volume_profile = analyze_volume_profile(df)
    if volume_profile.get('detected'):
        results['volume_profile'] = volume_profile
        if volume_profile.get('near_support'):
            results['buy_signals'] += 1
            results['signals'].append({'type': '매물대', 'signal': 'buy', 'message': '지지 매물대 근접'})
        elif volume_profile.get('near_resistance'):
            results['sell_signals'] += 1
            results['signals'].append({'type': '매물대', 'signal': 'sell', 'message': '저항 매물대 근접'})

    # 6. 이격도 분석
    disparity = calculate_disparity(df)
    if disparity.get('detected'):
        results['disparity'] = disparity
        if disparity.get('overall_signal') == 'oversold':
            results['buy_signals'] += 1
            results['signals'].append({'type': '이격도', 'signal': 'buy', 'message': disparity['message']})
        elif disparity.get('overall_signal') == 'overbought':
            results['sell_signals'] += 1
            results['signals'].append({'type': '이격도', 'signal': 'sell', 'message': disparity['message']})

    # 종합 판단
    if results['buy_signals'] >= 2:
        results['overall'] = 'strong_buy'
        results['overall_message'] = f"매수 신호 {results['buy_signals']}개 감지"
    elif results['buy_signals'] == 1:
        results['overall'] = 'buy'
        results['overall_message'] = '매수 관심'
    elif results['sell_signals'] >= 2:
        results['overall'] = 'sell'
        results['overall_message'] = f"매도/관망 신호 {results['sell_signals']}개 감지"
    elif results['watch_signals'] >= 1:
        results['overall'] = 'watch'
        results['overall_message'] = '관망 (패턴 형성 중)'
    else:
        results['overall'] = 'neutral'
        results['overall_message'] = '특별한 신호 없음'

    return results


# ========== 태쏘 전략: 박스권 분석 ==========

def detect_box_range(df: pd.DataFrame, period: int = 20, tolerance: float = 0.05) -> Dict[str, Any]:
    """
    박스권 자동 감지 (태쏘 스윙투자 전략)

    Args:
        df: OHLCV 데이터프레임
        period: 박스권 계산 기간 (기본 20일)
        tolerance: 박스권 판정 허용 오차 (기본 5%)

    Returns:
        박스권 분석 결과
    """
    if df is None or len(df) < period:
        return {'detected': False, 'message': '데이터 부족'}

    recent = df.tail(period).copy()

    # 박스권 상단/하단 계산
    upper = recent['high'].max()
    lower = recent['low'].min()
    mid = (upper + lower) / 2
    range_pct = ((upper - lower) / lower) * 100

    current_price = df['close'].iloc[-1]

    # 박스권 내 위치 (0: 하단, 100: 상단)
    if upper != lower:
        position_pct = ((current_price - lower) / (upper - lower)) * 100
    else:
        position_pct = 50

    # 박스권 판정 (변동폭 15% 이내를 박스권으로 간주)
    is_box_range = range_pct <= 15

    # 돌파/이탈 감지
    prev_close = df['close'].iloc[-2] if len(df) >= 2 else current_price
    breakout_up = current_price > upper and prev_close <= upper
    breakdown = current_price < lower and prev_close >= lower

    # 박스권 상단/하단 근접 여부 (3% 이내)
    near_upper = abs(current_price - upper) / upper < 0.03
    near_lower = abs(current_price - lower) / lower < 0.03

    # 시그널 판정
    if breakout_up:
        signal = 'breakout_buy'
        message = f'박스권 상단 돌파! ({upper:,.0f}원 → {current_price:,.0f}원)'
    elif breakdown:
        signal = 'breakdown_sell'
        message = f'박스권 하단 이탈! ({lower:,.0f}원 → {current_price:,.0f}원)'
    elif near_lower and is_box_range:
        signal = 'box_buy'
        message = f'박스권 하단 지지 매수 구간 (하단: {lower:,.0f}원)'
    elif near_upper and is_box_range:
        signal = 'box_sell'
        message = f'박스권 상단 저항 매도 구간 (상단: {upper:,.0f}원)'
    else:
        signal = 'neutral'
        message = f'박스권 중간 ({range_pct:.1f}% 범위)'

    return {
        'detected': True,
        'is_box_range': is_box_range,
        'upper': float(upper),
        'lower': float(lower),
        'mid': float(mid),
        'range_pct': round(range_pct, 2),
        'current_price': float(current_price),
        'position_pct': round(position_pct, 2),
        'near_upper': near_upper,
        'near_lower': near_lower,
        'breakout_up': breakout_up,
        'breakdown': breakdown,
        'signal': signal,
        'message': message
    }


def detect_box_breakout(df: pd.DataFrame, period: int = 20, volume_confirm: bool = True) -> Dict[str, Any]:
    """
    박스권 돌파 시그널 감지 (거래량 확인 포함)

    Args:
        df: OHLCV 데이터프레임
        period: 박스권 계산 기간
        volume_confirm: 거래량 확인 여부

    Returns:
        돌파 시그널 분석 결과
    """
    if df is None or len(df) < period + 5:
        return {'detected': False, 'message': '데이터 부족'}

    # 이전 박스권 (오늘 제외)
    box_data = df.iloc[-(period+1):-1]
    upper = box_data['high'].max()
    lower = box_data['low'].min()

    current = df.iloc[-1]
    current_price = current['close']
    current_volume = current['volume']

    # 평균 거래량 대비 비율
    avg_volume = box_data['volume'].mean()
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

    # 돌파 확인
    breakout_up = current_price > upper
    breakdown = current_price < lower

    # 거래량 확인 (1.5배 이상이면 신뢰도 높음)
    volume_confirmed = volume_ratio >= 1.5

    if breakout_up:
        strength = 'strong' if volume_confirmed else 'weak'
        confidence = min(100, int(volume_ratio * 50)) if volume_confirm else 70
        message = f'상단 돌파 ({upper:,.0f}원)'
        if volume_confirmed:
            message += f' + 거래량 {volume_ratio:.1f}배'

        return {
            'detected': True,
            'direction': 'up',
            'breakout_price': float(upper),
            'current_price': float(current_price),
            'volume_ratio': round(volume_ratio, 2),
            'volume_confirmed': volume_confirmed,
            'strength': strength,
            'confidence': confidence,
            'signal': 'buy',
            'message': message
        }

    elif breakdown:
        strength = 'strong' if volume_confirmed else 'weak'
        message = f'하단 이탈 ({lower:,.0f}원)'
        if volume_confirmed:
            message += f' + 거래량 {volume_ratio:.1f}배'

        return {
            'detected': True,
            'direction': 'down',
            'breakout_price': float(lower),
            'current_price': float(current_price),
            'volume_ratio': round(volume_ratio, 2),
            'volume_confirmed': volume_confirmed,
            'strength': strength,
            'signal': 'sell',
            'message': message
        }

    return {'detected': False, 'message': '돌파 신호 없음'}


# ========== 태쏘 전략: 분할 매수/매도 계산기 ==========

def calculate_triangle_division(
    total_amount: float,
    base_price: float,
    division_pct: list = [3, 5, 7],
    direction: str = 'buy'
) -> Dict[str, Any]:
    """
    삼각분할 비중 조절법 (태쏘 스윙투자 전략)
    - 하락 시 비중을 늘려가며 분할 매수
    - 상승 시 비중을 줄여가며 분할 매도

    Args:
        total_amount: 총 투자금액
        base_price: 기준 가격 (현재가)
        division_pct: 분할 간격 (%) [1차, 2차, 3차]
        direction: 'buy' (하락 시 매수) or 'sell' (상승 시 매도)

    Returns:
        분할 매수/매도 계획
    """
    # 삼각분할 비율: 1:2:3 (합계 6)
    ratios = [1/6, 2/6, 3/6]  # 약 16.7%, 33.3%, 50%

    result = {
        'type': 'triangle',
        'direction': direction,
        'total_amount': total_amount,
        'base_price': base_price,
        'divisions': []
    }

    cumulative_qty = 0
    cumulative_amount = 0

    for i, (ratio, pct) in enumerate(zip(ratios, division_pct)):
        if direction == 'buy':
            # 하락 시 매수: 가격이 낮아질수록 비중 증가
            target_price = base_price * (1 - pct / 100)
        else:
            # 상승 시 매도: 가격이 높아질수록 비중 감소 (역순)
            target_price = base_price * (1 + pct / 100)

        amount = total_amount * ratio
        qty = int(amount / target_price)
        actual_amount = qty * target_price

        cumulative_qty += qty
        cumulative_amount += actual_amount

        # 평균 단가 계산
        avg_price = cumulative_amount / cumulative_qty if cumulative_qty > 0 else target_price

        result['divisions'].append({
            'step': i + 1,
            'target_price': round(target_price, 0),
            'change_pct': -pct if direction == 'buy' else pct,
            'ratio': round(ratio * 100, 1),
            'amount': round(amount, 0),
            'quantity': qty,
            'actual_amount': round(actual_amount, 0),
            'cumulative_qty': cumulative_qty,
            'cumulative_amount': round(cumulative_amount, 0),
            'avg_price': round(avg_price, 0)
        })

    # 전체 요약
    result['summary'] = {
        'total_quantity': cumulative_qty,
        'total_invested': round(cumulative_amount, 0),
        'avg_price': round(cumulative_amount / cumulative_qty, 0) if cumulative_qty > 0 else 0,
        'vs_base_price': round((cumulative_amount / cumulative_qty / base_price - 1) * 100, 2) if cumulative_qty > 0 else 0
    }

    return result


def calculate_diamond_division(
    total_amount: float,
    base_price: float,
    division_pct: list = [3, 5, 7, 10],
    direction: str = 'buy'
) -> Dict[str, Any]:
    """
    다이아몬드 분할 비중 조절법 (태쏘 신고가 추세매매)
    - 중간에 비중을 가장 크게 (다이아몬드 형태)
    - 신고가 돌파 후 추세 추종 매매에 적합

    Args:
        total_amount: 총 투자금액
        base_price: 기준 가격 (현재가)
        division_pct: 분할 간격 (%) [1차, 2차, 3차, 4차]
        direction: 'buy' or 'sell'

    Returns:
        분할 매수/매도 계획
    """
    # 다이아몬드 분할 비율: 1:2:2:1 (합계 6)
    ratios = [1/6, 2/6, 2/6, 1/6]  # 약 16.7%, 33.3%, 33.3%, 16.7%

    result = {
        'type': 'diamond',
        'direction': direction,
        'total_amount': total_amount,
        'base_price': base_price,
        'divisions': []
    }

    cumulative_qty = 0
    cumulative_amount = 0

    for i, (ratio, pct) in enumerate(zip(ratios, division_pct)):
        if direction == 'buy':
            target_price = base_price * (1 - pct / 100)
        else:
            target_price = base_price * (1 + pct / 100)

        amount = total_amount * ratio
        qty = int(amount / target_price)
        actual_amount = qty * target_price

        cumulative_qty += qty
        cumulative_amount += actual_amount
        avg_price = cumulative_amount / cumulative_qty if cumulative_qty > 0 else target_price

        result['divisions'].append({
            'step': i + 1,
            'target_price': round(target_price, 0),
            'change_pct': -pct if direction == 'buy' else pct,
            'ratio': round(ratio * 100, 1),
            'amount': round(amount, 0),
            'quantity': qty,
            'actual_amount': round(actual_amount, 0),
            'cumulative_qty': cumulative_qty,
            'cumulative_amount': round(cumulative_amount, 0),
            'avg_price': round(avg_price, 0)
        })

    result['summary'] = {
        'total_quantity': cumulative_qty,
        'total_invested': round(cumulative_amount, 0),
        'avg_price': round(cumulative_amount / cumulative_qty, 0) if cumulative_qty > 0 else 0,
        'vs_base_price': round((cumulative_amount / cumulative_qty / base_price - 1) * 100, 2) if cumulative_qty > 0 else 0
    }

    return result


def calculate_equal_division(
    total_amount: float,
    base_price: float,
    num_divisions: int = 3,
    division_pct: float = 5,
    direction: str = 'buy'
) -> Dict[str, Any]:
    """
    균등 분할 매수/매도 계산기

    Args:
        total_amount: 총 투자금액
        base_price: 기준 가격
        num_divisions: 분할 횟수 (기본 3회)
        division_pct: 각 분할 간격 (%)
        direction: 'buy' or 'sell'

    Returns:
        균등 분할 계획
    """
    ratio = 1 / num_divisions

    result = {
        'type': 'equal',
        'direction': direction,
        'total_amount': total_amount,
        'base_price': base_price,
        'divisions': []
    }

    cumulative_qty = 0
    cumulative_amount = 0

    for i in range(num_divisions):
        pct = division_pct * i
        if direction == 'buy':
            target_price = base_price * (1 - pct / 100)
        else:
            target_price = base_price * (1 + pct / 100)

        amount = total_amount * ratio
        qty = int(amount / target_price)
        actual_amount = qty * target_price

        cumulative_qty += qty
        cumulative_amount += actual_amount
        avg_price = cumulative_amount / cumulative_qty if cumulative_qty > 0 else target_price

        result['divisions'].append({
            'step': i + 1,
            'target_price': round(target_price, 0),
            'change_pct': -pct if direction == 'buy' else pct,
            'ratio': round(ratio * 100, 1),
            'amount': round(amount, 0),
            'quantity': qty,
            'actual_amount': round(actual_amount, 0),
            'cumulative_qty': cumulative_qty,
            'cumulative_amount': round(cumulative_amount, 0),
            'avg_price': round(avg_price, 0)
        })

    result['summary'] = {
        'total_quantity': cumulative_qty,
        'total_invested': round(cumulative_amount, 0),
        'avg_price': round(cumulative_amount / cumulative_qty, 0) if cumulative_qty > 0 else 0,
        'vs_base_price': round((cumulative_amount / cumulative_qty / base_price - 1) * 100, 2) if cumulative_qty > 0 else 0
    }

    return result


# ========== 태쏘 전략: 신고가 추세매매 ==========

def detect_new_high_trend(df: pd.DataFrame, lookback: int = 60, breakout_days: int = 3) -> Dict[str, Any]:
    """
    신고가 추세매매 시그널 감지 (태쏘 전략)

    Args:
        df: OHLCV 데이터프레임
        lookback: 신고가 확인 기간 (기본 60일)
        breakout_days: 돌파 확인 일수 (기본 3일)

    Returns:
        신고가 추세 분석 결과
    """
    if df is None or len(df) < lookback + breakout_days:
        return {'detected': False, 'message': '데이터 부족'}

    # 과거 데이터 (최근 breakout_days 제외)
    historical = df.iloc[-(lookback + breakout_days):-breakout_days]
    historical_high = historical['high'].max()

    # 최근 데이터
    recent = df.tail(breakout_days)
    current_price = df['close'].iloc[-1]
    recent_high = recent['high'].max()

    # 52주 신고가 확인
    if len(df) >= 252:
        high_52w = df.tail(252)['high'].max()
        is_52w_high = current_price >= high_52w * 0.98
    else:
        high_52w = df['high'].max()
        is_52w_high = current_price >= high_52w * 0.98

    # 신고가 돌파 여부
    new_high_breakout = recent_high > historical_high

    # 거래량 확인
    recent_volume = recent['volume'].mean()
    prev_volume = historical['volume'].mean()
    volume_ratio = recent_volume / prev_volume if prev_volume > 0 else 1
    volume_surge = volume_ratio >= 1.5

    # 추세 강도 계산
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    ma20 = df['close'].rolling(20).mean().iloc[-1]
    ma60 = df['close'].rolling(60).mean().iloc[-1] if len(df) >= 60 else ma20

    # 정배열 확인
    is_bullish = ma5 > ma20 > ma60

    if new_high_breakout:
        if is_52w_high and volume_surge and is_bullish:
            signal = 'strong_buy'
            strength = 'strong'
            message = f'52주 신고가 돌파! (거래량 {volume_ratio:.1f}배, 정배열)'
        elif new_high_breakout and (volume_surge or is_bullish):
            signal = 'buy'
            strength = 'moderate'
            message = f'{lookback}일 신고가 돌파 ({historical_high:,.0f}원 → {recent_high:,.0f}원)'
        else:
            signal = 'watch'
            strength = 'weak'
            message = '신고가 돌파 (거래량 미확인)'

        return {
            'detected': True,
            'pattern': 'new_high_trend',
            'historical_high': float(historical_high),
            'recent_high': float(recent_high),
            'current_price': float(current_price),
            'is_52w_high': is_52w_high,
            'high_52w': float(high_52w),
            'volume_ratio': round(volume_ratio, 2),
            'volume_surge': volume_surge,
            'is_bullish': is_bullish,
            'strength': strength,
            'signal': signal,
            'message': message
        }

    return {'detected': False, 'message': '신고가 돌파 미감지'}


# ========== 태쏘 전략: 종합 분석 ==========

def analyze_tasso_strategy(df: pd.DataFrame, total_amount: float = 10000000) -> Dict[str, Any]:
    """
    태쏘 스윙투자 전략 종합 분석

    Args:
        df: OHLCV 데이터프레임
        total_amount: 투자 예정 금액 (기본 1000만원)

    Returns:
        종합 분석 결과
    """
    if df is None or df.empty:
        return None

    current_price = df['close'].iloc[-1]

    result = {
        'current_price': float(current_price),
        'analysis_date': df.index[-1].strftime('%Y-%m-%d') if hasattr(df.index[-1], 'strftime') else str(df.index[-1]),
        'strategies': [],
        'recommended_action': None,
        'division_plan': None
    }

    # 1. 박스권 분석
    box = detect_box_range(df)
    if box.get('detected'):
        result['box_range'] = box
        if box.get('signal') in ['box_buy', 'breakout_buy']:
            result['strategies'].append({
                'name': '박스권 매매',
                'signal': box['signal'],
                'message': box['message']
            })

    # 2. 박스권 돌파 분석
    breakout = detect_box_breakout(df)
    if breakout.get('detected'):
        result['breakout'] = breakout
        result['strategies'].append({
            'name': '박스권 돌파',
            'signal': breakout['signal'],
            'message': breakout['message']
        })

    # 3. 신고가 추세 분석
    new_high = detect_new_high_trend(df)
    if new_high.get('detected'):
        result['new_high'] = new_high
        result['strategies'].append({
            'name': '신고가 추세',
            'signal': new_high['signal'],
            'message': new_high['message']
        })

    # 추천 행동 결정
    buy_signals = sum(1 for s in result['strategies'] if 'buy' in s['signal'])
    sell_signals = sum(1 for s in result['strategies'] if 'sell' in s['signal'])

    if buy_signals >= 2:
        result['recommended_action'] = 'strong_buy'
        result['action_message'] = f'강력 매수 ({buy_signals}개 신호)'
        # 다이아몬드 분할 추천 (신고가 추세)
        result['division_plan'] = calculate_diamond_division(total_amount, current_price)
    elif buy_signals == 1:
        result['recommended_action'] = 'buy'
        result['action_message'] = '매수 고려'
        # 삼각분할 추천 (박스권 하단)
        result['division_plan'] = calculate_triangle_division(total_amount, current_price)
    elif sell_signals >= 1:
        result['recommended_action'] = 'sell'
        result['action_message'] = '매도/관망 권장'
        result['division_plan'] = calculate_triangle_division(total_amount, current_price, direction='sell')
    else:
        result['recommended_action'] = 'watch'
        result['action_message'] = '관망'
        result['division_plan'] = calculate_equal_division(total_amount, current_price)

    return result


# ========== 다이버전스 분석 (RSI/MACD) ==========

def detect_rsi_divergence(df: pd.DataFrame, lookback: int = 30, rsi_period: int = 14) -> Dict[str, Any]:
    """
    RSI 다이버전스 감지
    - 상승 다이버전스: 가격은 저점 갱신, RSI는 저점 상승 (매수 신호)
    - 하락 다이버전스: 가격은 고점 갱신, RSI는 고점 하락 (매도 신호)

    Args:
        df: OHLCV 데이터프레임
        lookback: 분석 기간 (기본 30일)
        rsi_period: RSI 계산 기간 (기본 14일)

    Returns:
        다이버전스 분석 결과
    """
    if df is None or len(df) < lookback + rsi_period:
        return {'detected': False, 'message': '데이터 부족'}

    close = df['close']
    low = df['low']
    high = df['high']

    # RSI 계산
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=rsi_period).mean()
    avg_loss = loss.rolling(window=rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rs = rs.fillna(100)
    rsi = 100 - (100 / (1 + rs))

    # 최근 데이터
    recent_low = low.tail(lookback).values
    recent_high = high.tail(lookback).values
    recent_rsi = rsi.tail(lookback).values

    # 저점 찾기 (상승 다이버전스용)
    price_lows = []
    for i in range(2, len(recent_low) - 2):
        if recent_low[i] < recent_low[i-1] and recent_low[i] < recent_low[i-2] and \
           recent_low[i] < recent_low[i+1] and recent_low[i] < recent_low[i+2]:
            price_lows.append((i, recent_low[i], recent_rsi[i]))

    # 고점 찾기 (하락 다이버전스용)
    price_highs = []
    for i in range(2, len(recent_high) - 2):
        if recent_high[i] > recent_high[i-1] and recent_high[i] > recent_high[i-2] and \
           recent_high[i] > recent_high[i+1] and recent_high[i] > recent_high[i+2]:
            price_highs.append((i, recent_high[i], recent_rsi[i]))

    current_price = close.iloc[-1]
    current_rsi = rsi.iloc[-1]

    # 상승 다이버전스 확인 (가격 저점 하락 + RSI 저점 상승)
    if len(price_lows) >= 2:
        for i in range(len(price_lows) - 1, 0, -1):
            idx2, price2, rsi2 = price_lows[i]
            idx1, price1, rsi1 = price_lows[i - 1]

            if idx2 - idx1 >= 5:  # 최소 5일 간격
                # 가격은 하락, RSI는 상승
                if price2 < price1 and rsi2 > rsi1:
                    strength = 'strong' if (rsi1 < 30 or rsi2 < 35) else 'moderate'
                    return {
                        'detected': True,
                        'type': 'bullish',
                        'pattern': 'rsi_divergence',
                        'strength': strength,
                        'price_low1': float(price1),
                        'price_low2': float(price2),
                        'rsi_low1': round(rsi1, 2),
                        'rsi_low2': round(rsi2, 2),
                        'current_price': float(current_price),
                        'current_rsi': round(current_rsi, 2),
                        'signal': 'buy',
                        'message': f'RSI 상승 다이버전스 (가격↓ RSI↑) - 반등 가능성'
                    }

    # 하락 다이버전스 확인 (가격 고점 상승 + RSI 고점 하락)
    if len(price_highs) >= 2:
        for i in range(len(price_highs) - 1, 0, -1):
            idx2, price2, rsi2 = price_highs[i]
            idx1, price1, rsi1 = price_highs[i - 1]

            if idx2 - idx1 >= 5:
                # 가격은 상승, RSI는 하락
                if price2 > price1 and rsi2 < rsi1:
                    strength = 'strong' if (rsi1 > 70 or rsi2 > 65) else 'moderate'
                    return {
                        'detected': True,
                        'type': 'bearish',
                        'pattern': 'rsi_divergence',
                        'strength': strength,
                        'price_high1': float(price1),
                        'price_high2': float(price2),
                        'rsi_high1': round(rsi1, 2),
                        'rsi_high2': round(rsi2, 2),
                        'current_price': float(current_price),
                        'current_rsi': round(current_rsi, 2),
                        'signal': 'sell',
                        'message': f'RSI 하락 다이버전스 (가격↑ RSI↓) - 조정 가능성'
                    }

    return {'detected': False, 'message': 'RSI 다이버전스 미감지'}


def detect_macd_divergence(df: pd.DataFrame, lookback: int = 40,
                           fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Any]:
    """
    MACD 다이버전스 감지
    - 상승 다이버전스: 가격은 저점 갱신, MACD는 저점 상승 (매수 신호)
    - 하락 다이버전스: 가격은 고점 갱신, MACD는 고점 하락 (매도 신호)

    Args:
        df: OHLCV 데이터프레임
        lookback: 분석 기간 (기본 40일)
        fast: MACD 단기 EMA (기본 12)
        slow: MACD 장기 EMA (기본 26)
        signal: MACD 시그널 EMA (기본 9)

    Returns:
        다이버전스 분석 결과
    """
    if df is None or len(df) < lookback + slow + signal:
        return {'detected': False, 'message': '데이터 부족'}

    close = df['close']
    low = df['low']
    high = df['high']

    # MACD 계산
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line  # MACD 히스토그램 = MACD - Signal

    # 최근 데이터
    recent_low = low.tail(lookback).values
    recent_high = high.tail(lookback).values
    recent_macd = macd_line.tail(lookback).values

    # 저점 찾기 (상승 다이버전스용)
    price_lows = []
    for i in range(2, len(recent_low) - 2):
        if recent_low[i] < recent_low[i-1] and recent_low[i] < recent_low[i-2] and \
           recent_low[i] < recent_low[i+1] and recent_low[i] < recent_low[i+2]:
            price_lows.append((i, recent_low[i], recent_macd[i]))

    # 고점 찾기 (하락 다이버전스용)
    price_highs = []
    for i in range(2, len(recent_high) - 2):
        if recent_high[i] > recent_high[i-1] and recent_high[i] > recent_high[i-2] and \
           recent_high[i] > recent_high[i+1] and recent_high[i] > recent_high[i+2]:
            price_highs.append((i, recent_high[i], recent_macd[i]))

    current_price = close.iloc[-1]
    current_macd = macd_line.iloc[-1]

    # 상승 다이버전스 확인
    if len(price_lows) >= 2:
        for i in range(len(price_lows) - 1, 0, -1):
            idx2, price2, macd2 = price_lows[i]
            idx1, price1, macd1 = price_lows[i - 1]

            if idx2 - idx1 >= 5:
                # 가격은 하락, MACD는 상승
                if price2 < price1 and macd2 > macd1:
                    strength = 'strong' if (macd1 < 0 and macd2 < 0) else 'moderate'
                    return {
                        'detected': True,
                        'type': 'bullish',
                        'pattern': 'macd_divergence',
                        'strength': strength,
                        'price_low1': float(price1),
                        'price_low2': float(price2),
                        'macd_low1': round(macd1, 4),
                        'macd_low2': round(macd2, 4),
                        'current_price': float(current_price),
                        'current_macd': round(current_macd, 4),
                        'signal': 'buy',
                        'message': f'MACD 상승 다이버전스 (가격↓ MACD↑) - 반등 가능성'
                    }

    # 하락 다이버전스 확인
    if len(price_highs) >= 2:
        for i in range(len(price_highs) - 1, 0, -1):
            idx2, price2, macd2 = price_highs[i]
            idx1, price1, macd1 = price_highs[i - 1]

            if idx2 - idx1 >= 5:
                # 가격은 상승, MACD는 하락
                if price2 > price1 and macd2 < macd1:
                    strength = 'strong' if (macd1 > 0 and macd2 > 0) else 'moderate'
                    return {
                        'detected': True,
                        'type': 'bearish',
                        'pattern': 'macd_divergence',
                        'strength': strength,
                        'price_high1': float(price1),
                        'price_high2': float(price2),
                        'macd_high1': round(macd1, 4),
                        'macd_high2': round(macd2, 4),
                        'current_price': float(current_price),
                        'current_macd': round(current_macd, 4),
                        'signal': 'sell',
                        'message': f'MACD 하락 다이버전스 (가격↑ MACD↓) - 조정 가능성'
                    }

    return {'detected': False, 'message': 'MACD 다이버전스 미감지'}


def analyze_divergence(df: pd.DataFrame) -> Dict[str, Any]:
    """
    종합 다이버전스 분석 (RSI + MACD)

    Args:
        df: OHLCV 데이터프레임

    Returns:
        종합 다이버전스 분석 결과
    """
    if df is None or df.empty:
        return {'detected': False, 'message': '데이터 없음'}

    result = {
        'rsi_divergence': None,
        'macd_divergence': None,
        'signals': [],
        'overall': 'neutral',
        'overall_message': '다이버전스 미감지'
    }

    # RSI 다이버전스
    rsi_div = detect_rsi_divergence(df)
    if rsi_div.get('detected'):
        result['rsi_divergence'] = rsi_div
        result['signals'].append({
            'type': 'RSI',
            'direction': rsi_div['type'],
            'signal': rsi_div['signal'],
            'message': rsi_div['message']
        })

    # MACD 다이버전스
    macd_div = detect_macd_divergence(df)
    if macd_div.get('detected'):
        result['macd_divergence'] = macd_div
        result['signals'].append({
            'type': 'MACD',
            'direction': macd_div['type'],
            'signal': macd_div['signal'],
            'message': macd_div['message']
        })

    # 종합 판단
    bullish_count = sum(1 for s in result['signals'] if s['direction'] == 'bullish')
    bearish_count = sum(1 for s in result['signals'] if s['direction'] == 'bearish')

    if bullish_count >= 2:
        result['overall'] = 'strong_buy'
        result['overall_message'] = 'RSI + MACD 상승 다이버전스 동시 발생! (강력 매수 신호)'
        result['detected'] = True
    elif bearish_count >= 2:
        result['overall'] = 'strong_sell'
        result['overall_message'] = 'RSI + MACD 하락 다이버전스 동시 발생! (강력 매도 신호)'
        result['detected'] = True
    elif bullish_count == 1:
        result['overall'] = 'buy'
        result['overall_message'] = '상승 다이버전스 감지 (매수 관심)'
        result['detected'] = True
    elif bearish_count == 1:
        result['overall'] = 'sell'
        result['overall_message'] = '하락 다이버전스 감지 (매도 관심)'
        result['detected'] = True
    else:
        result['detected'] = False

    return result


# ========== 차트용 Volume Profile 계산 ==========

def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 30) -> tuple:
    """
    매물대(Volume Profile) 계산 - OHLC 범위 분산 방식
    차트 표시용으로 튜플 형태 반환

    Args:
        df: OHLCV DataFrame
        num_bins: 가격대 구간 수 (기본 30)

    Returns:
        (price_levels, volumes, poc_price): 가격대 리스트, 거래량 리스트, POC(최대거래량 가격)
    """
    if df is None or df.empty or len(df) < 5:
        return [], [], None

    # 전체 가격 범위
    price_min = df['low'].min()
    price_max = df['high'].max()

    if price_min >= price_max:
        return [], [], None

    # 가격대 구간 생성
    bin_size = (price_max - price_min) / num_bins
    price_levels = [price_min + (i + 0.5) * bin_size for i in range(num_bins)]
    volumes = [0.0] * num_bins

    # 각 캔들의 거래량을 가격대에 분배
    for idx in range(len(df)):
        row = df.iloc[idx]
        high = row['high']
        low = row['low']
        vol = row['volume']

        if high <= low or vol <= 0:
            continue

        # 해당 캔들이 걸치는 구간들에 거래량 분배
        for i in range(num_bins):
            bin_low = price_min + i * bin_size
            bin_high = bin_low + bin_size

            # 구간과 캔들 범위의 교집합
            overlap_low = max(low, bin_low)
            overlap_high = min(high, bin_high)

            if overlap_high > overlap_low:
                overlap_ratio = (overlap_high - overlap_low) / (high - low)
                volumes[i] += vol * overlap_ratio

    # POC (Point of Control) - 최대 거래량 가격대
    if max(volumes) > 0:
        poc_idx = volumes.index(max(volumes))
        poc_price = price_levels[poc_idx]
    else:
        poc_price = None

    return price_levels, volumes, poc_price
