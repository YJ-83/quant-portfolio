"""
차트 매매 전략 모듈
- 골든크로스/데드크로스 전략
- 거래량 급증 전략
- 매집봉 탐지 전략
- 이평선 지지 전략
- 박스권 돌파 전략
"""
from abc import abstractmethod
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@dataclass
class ChartSignal:
    """차트 시그널 결과"""
    code: str
    name: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    signal_strength: float  # 0~100
    signal_date: str
    price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    description: str = ""
    indicators: Dict = None


class ChartIndicators:
    """기술적 지표 계산 유틸리티"""

    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """단순 이동평균선"""
        return prices.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """지수 이동평균선"""
        return prices.ewm(span=period, adjust=False).mean()

    @staticmethod
    def volume_ma(volumes: pd.Series, period: int) -> pd.Series:
        """거래량 이동평균"""
        return volumes.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, std_mult: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 (상단, 중단, 하단)"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_mult)
        lower = middle - (std * std_mult)
        return upper, middle, lower

    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI (상대강도지수)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD (macd선, 시그널선, 히스토그램)"""
        fast_ema = prices.ewm(span=fast, adjust=False).mean()
        slow_ema = prices.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """ATR (평균 진폭)"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()


class BaseChartStrategy:
    """차트 전략 베이스 클래스"""

    def __init__(self):
        self.indicators = ChartIndicators()

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        """
        OHLCV 데이터 분석

        Args:
            ohlcv: DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume']
            code: 종목코드
            name: 종목명

        Returns:
            ChartSignal or None
        """
        pass


class GoldenCrossStrategy(BaseChartStrategy):
    """골든크로스/데드크로스 전략"""

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period

    @property
    def name(self) -> str:
        return f"골든크로스 ({self.short_period}/{self.long_period})"

    @property
    def description(self) -> str:
        return f"{self.short_period}일선이 {self.long_period}일선을 상향 돌파하면 매수, 하향 돌파하면 매도"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        if len(ohlcv) < self.long_period + 2:
            return None

        df = ohlcv.copy()
        df['ma_short'] = self.indicators.sma(df['close'], self.short_period)
        df['ma_long'] = self.indicators.sma(df['close'], self.long_period)

        # 크로스 감지 (오늘 vs 어제)
        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        cross_up = (yesterday['ma_short'] <= yesterday['ma_long']) and (today['ma_short'] > today['ma_long'])
        cross_down = (yesterday['ma_short'] >= yesterday['ma_long']) and (today['ma_short'] < today['ma_long'])

        if cross_up:
            # 골든크로스 - 매수 시그널
            strength = min(100, ((today['ma_short'] / today['ma_long'] - 1) * 1000))
            return ChartSignal(
                code=code,
                name=name,
                signal_type='BUY',
                signal_strength=max(50, strength),
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                target_price=today['close'] * 1.10,  # 10% 목표
                stop_loss=today['close'] * 0.95,     # 5% 손절
                description=f"골든크로스 발생: {self.short_period}일선({today['ma_short']:.0f}) > {self.long_period}일선({today['ma_long']:.0f})",
                indicators={
                    'ma_short': today['ma_short'],
                    'ma_long': today['ma_long'],
                    'cross_type': 'golden'
                }
            )
        elif cross_down:
            # 데드크로스 - 매도 시그널
            strength = min(100, ((1 - today['ma_short'] / today['ma_long']) * 1000))
            return ChartSignal(
                code=code,
                name=name,
                signal_type='SELL',
                signal_strength=max(50, strength),
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                description=f"데드크로스 발생: {self.short_period}일선({today['ma_short']:.0f}) < {self.long_period}일선({today['ma_long']:.0f})",
                indicators={
                    'ma_short': today['ma_short'],
                    'ma_long': today['ma_long'],
                    'cross_type': 'dead'
                }
            )

        return None


class VolumeBreakoutStrategy(BaseChartStrategy):
    """거래량 급증 전략 - 실시간 모드 지원"""

    def __init__(self, volume_mult: float = 2.0, volume_period: int = 20, min_change: float = 0.02):
        super().__init__()
        self.volume_mult = volume_mult  # 평균 대비 배수
        self.volume_period = volume_period  # 거래량 평균 기간
        self.min_change = min_change  # 최소 가격 변동률 (2%)

    @property
    def name(self) -> str:
        return f"거래량 급증 ({self.volume_mult}배)"

    @property
    def description(self) -> str:
        return f"거래량이 {self.volume_period}일 평균의 {self.volume_mult}배 이상이고 가격 상승시 매수"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        """일봉 기반 분석 (기존 방식)"""
        if len(ohlcv) < self.volume_period + 1:
            return None

        df = ohlcv.copy()
        df['vol_ma'] = self.indicators.volume_ma(df['volume'], self.volume_period)
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        df['change'] = df['close'].pct_change()

        today = df.iloc[-1]

        # 거래량 급증 + 가격 상승
        if today['vol_ratio'] >= self.volume_mult and today['change'] >= self.min_change:
            strength = min(100, today['vol_ratio'] * 20 + today['change'] * 200)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='BUY',
                signal_strength=strength,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                target_price=today['close'] * 1.08,
                stop_loss=today['close'] * 0.97,
                description=f"거래량 {today['vol_ratio']:.1f}배 급증, 가격 {today['change']*100:.1f}% 상승",
                indicators={
                    'volume': today['volume'],
                    'vol_ma': today['vol_ma'],
                    'vol_ratio': today['vol_ratio'],
                    'price_change': today['change']
                }
            )

        # 거래량 급증 + 가격 하락 (매도 시그널)
        elif today['vol_ratio'] >= self.volume_mult and today['change'] <= -self.min_change:
            strength = min(100, today['vol_ratio'] * 20 + abs(today['change']) * 200)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='SELL',
                signal_strength=strength,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                description=f"거래량 {today['vol_ratio']:.1f}배 급증, 가격 {today['change']*100:.1f}% 하락 (매도 경고)",
                indicators={
                    'volume': today['volume'],
                    'vol_ma': today['vol_ma'],
                    'vol_ratio': today['vol_ratio'],
                    'price_change': today['change']
                }
            )

        return None

    def analyze_realtime(self, ohlcv: pd.DataFrame, realtime_info: dict, code: str, name: str) -> Optional[ChartSignal]:
        """
        실시간 데이터 기반 분석

        Args:
            ohlcv: 과거 일봉 데이터 (평균 거래량 계산용)
            realtime_info: 실시간 현재가 정보 {'price': 현재가, 'volume': 오늘 누적거래량,
                          'change_rate': 등락률, 'prev_close': 전일종가}
            code: 종목코드
            name: 종목명
        """
        if len(ohlcv) < self.volume_period:
            return None

        # 과거 데이터에서 평균 거래량 계산 (오늘 제외)
        df = ohlcv.copy()
        vol_ma = df['volume'].tail(self.volume_period).mean()

        # 실시간 데이터
        current_price = realtime_info.get('price', 0)
        current_volume = realtime_info.get('volume', 0)
        change_rate = realtime_info.get('change_rate', 0) / 100  # % -> 소수
        prev_close = realtime_info.get('prev_close', 0)

        if vol_ma == 0 or current_price == 0:
            return None

        # 거래량 비율 계산
        vol_ratio = current_volume / vol_ma

        # 거래량 급증 + 가격 상승
        if vol_ratio >= self.volume_mult and change_rate >= self.min_change:
            strength = min(100, vol_ratio * 20 + change_rate * 200)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='BUY',
                signal_strength=strength,
                signal_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                price=current_price,
                target_price=current_price * 1.08,
                stop_loss=current_price * 0.97,
                description=f"[실시간] 거래량 {vol_ratio:.1f}배 급증, 가격 {change_rate*100:.1f}% 상승",
                indicators={
                    'volume': current_volume,
                    'vol_ma': vol_ma,
                    'vol_ratio': vol_ratio,
                    'price_change': change_rate,
                    'realtime': True
                }
            )

        # 거래량 급증 + 가격 하락
        elif vol_ratio >= self.volume_mult and change_rate <= -self.min_change:
            strength = min(100, vol_ratio * 20 + abs(change_rate) * 200)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='SELL',
                signal_strength=strength,
                signal_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                price=current_price,
                description=f"[실시간] 거래량 {vol_ratio:.1f}배 급증, 가격 {change_rate*100:.1f}% 하락",
                indicators={
                    'volume': current_volume,
                    'vol_ma': vol_ma,
                    'vol_ratio': vol_ratio,
                    'price_change': change_rate,
                    'realtime': True
                }
            )

        return None


class AccumulationStrategy(BaseChartStrategy):
    """매집봉 탐지 전략"""

    def __init__(self, min_vol_ratio: float = 1.5, max_body_ratio: float = 0.3):
        super().__init__()
        self.min_vol_ratio = min_vol_ratio  # 평균 대비 최소 거래량 배수
        self.max_body_ratio = max_body_ratio  # 봉대비 몸통 최대 비율 (짧은 몸통)

    @property
    def name(self) -> str:
        return "매집봉 탐지"

    @property
    def description(self) -> str:
        return "거래량 증가 + 짧은 양봉 = 세력 매집 신호"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        if len(ohlcv) < 21:
            return None

        df = ohlcv.copy()
        df['vol_ma'] = self.indicators.volume_ma(df['volume'], 20)
        df['vol_ratio'] = df['volume'] / df['vol_ma']

        # 봉 분석
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_ratio'] = df['body'] / df['range'].replace(0, np.nan)
        df['is_bullish'] = df['close'] > df['open']

        today = df.iloc[-1]

        # 매집봉 조건: 거래량 증가 + 짧은 몸통 + 양봉
        if (today['vol_ratio'] >= self.min_vol_ratio and
            today['body_ratio'] <= self.max_body_ratio and
            today['is_bullish'] and
            today['range'] > 0):

            # 연속 매집 여부 확인
            accumulation_days = 0
            for i in range(-5, 0):
                row = df.iloc[i]
                if (row['vol_ratio'] >= 1.0 and
                    row['body_ratio'] <= 0.5 and
                    row['is_bullish']):
                    accumulation_days += 1

            strength = min(100, 50 + today['vol_ratio'] * 10 + accumulation_days * 10)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='BUY',
                signal_strength=strength,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                target_price=today['close'] * 1.15,
                stop_loss=today['low'] * 0.98,
                description=f"매집봉 감지: 거래량 {today['vol_ratio']:.1f}배, 몸통비율 {today['body_ratio']*100:.1f}% (연속 {accumulation_days}일)",
                indicators={
                    'vol_ratio': today['vol_ratio'],
                    'body_ratio': today['body_ratio'],
                    'accumulation_days': accumulation_days,
                    'upper_shadow': today['high'] - max(today['open'], today['close']),
                    'lower_shadow': min(today['open'], today['close']) - today['low']
                }
            )

        return None


class MABounceStrategy(BaseChartStrategy):
    """이동평균선 지지 전략"""

    def __init__(self, ma_periods: List[int] = None, tolerance: float = 0.02):
        super().__init__()
        self.ma_periods = ma_periods or [20, 60, 120]  # 20일, 60일, 120일선
        self.tolerance = tolerance  # 지지선 근접 허용 범위 (2%)

    @property
    def name(self) -> str:
        return f"이평선 지지 ({'/'.join(map(str, self.ma_periods))})"

    @property
    def description(self) -> str:
        return f"{'/'.join(map(str, self.ma_periods))}일선에서 지지받고 반등시 매수"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        max_period = max(self.ma_periods)
        if len(ohlcv) < max_period + 3:
            return None

        df = ohlcv.copy()

        # 각 이평선 계산
        for period in self.ma_periods:
            df[f'ma_{period}'] = self.indicators.sma(df['close'], period)

        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        day_before = df.iloc[-3]

        # 각 이평선에서 지지 여부 확인
        for period in self.ma_periods:
            ma_col = f'ma_{period}'
            ma_today = today[ma_col]

            # 조건: 어제 저가가 이평선 근처까지 하락 + 오늘 반등
            low_near_ma = abs(yesterday['low'] - yesterday[ma_col]) / yesterday[ma_col] <= self.tolerance
            bounced_up = today['close'] > yesterday['close'] and today['close'] > today['open']
            above_ma = today['close'] > ma_today

            if low_near_ma and bounced_up and above_ma:
                strength = 60 + (period / max(self.ma_periods)) * 30  # 장기선일수록 강한 신호

                return ChartSignal(
                    code=code,
                    name=name,
                    signal_type='BUY',
                    signal_strength=strength,
                    signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                    price=today['close'],
                    target_price=today['close'] * 1.08,
                    stop_loss=ma_today * 0.98,  # 이평선 이탈시 손절
                    description=f"{period}일선({ma_today:.0f}) 지지 후 반등",
                    indicators={
                        'support_ma': period,
                        'ma_value': ma_today,
                        'bounce_percent': (today['close'] / yesterday['low'] - 1) * 100
                    }
                )

        return None


class BoxBreakoutStrategy(BaseChartStrategy):
    """박스권 돌파 전략"""

    def __init__(self, lookback_days: int = 20, breakout_threshold: float = 0.02, min_vol_ratio: float = 1.5):
        super().__init__()
        self.lookback_days = lookback_days  # 박스권 확인 기간
        self.breakout_threshold = breakout_threshold  # 돌파 기준 (2%)
        self.min_vol_ratio = min_vol_ratio  # 최소 거래량 배수

    @property
    def name(self) -> str:
        return f"박스권 돌파 ({self.lookback_days}일)"

    @property
    def description(self) -> str:
        return f"{self.lookback_days}일간 고점을 거래량 동반 돌파시 매수"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        if len(ohlcv) < self.lookback_days + 1:
            return None

        df = ohlcv.copy()
        df['vol_ma'] = self.indicators.volume_ma(df['volume'], 20)
        df['vol_ratio'] = df['volume'] / df['vol_ma']

        today = df.iloc[-1]
        box_data = df.iloc[-(self.lookback_days + 1):-1]  # 오늘 제외한 과거 N일

        # 박스권 상단/하단
        box_high = box_data['high'].max()
        box_low = box_data['low'].min()
        box_range = (box_high - box_low) / box_low

        # 상단 돌파 조건
        breakout_up = today['close'] > box_high * (1 + self.breakout_threshold)
        volume_confirm = today['vol_ratio'] >= self.min_vol_ratio

        # 하단 이탈 조건 (매도)
        breakout_down = today['close'] < box_low * (1 - self.breakout_threshold)

        if breakout_up and volume_confirm:
            strength = min(100, 60 + today['vol_ratio'] * 10 + box_range * 100)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='BUY',
                signal_strength=strength,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                target_price=today['close'] + (box_high - box_low),  # 박스 높이만큼 목표
                stop_loss=box_high * 0.98,  # 박스 상단 근처 손절
                description=f"{self.lookback_days}일 박스권 상단({box_high:.0f}) 돌파, 거래량 {today['vol_ratio']:.1f}배",
                indicators={
                    'box_high': box_high,
                    'box_low': box_low,
                    'box_range_pct': box_range * 100,
                    'vol_ratio': today['vol_ratio'],
                    'breakout_pct': (today['close'] / box_high - 1) * 100
                }
            )
        elif breakout_down:
            strength = min(100, 60 + abs(today['close'] / box_low - 1) * 200)

            return ChartSignal(
                code=code,
                name=name,
                signal_type='SELL',
                signal_strength=strength,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                description=f"{self.lookback_days}일 박스권 하단({box_low:.0f}) 이탈 경고",
                indicators={
                    'box_high': box_high,
                    'box_low': box_low,
                    'breakdown_pct': (today['close'] / box_low - 1) * 100
                }
            )

        return None


class TripleMAStrategy(BaseChartStrategy):
    """3중 이동평균선 정배열 전략 (5, 20, 60일선)"""

    def __init__(self):
        super().__init__()
        self.periods = [5, 20, 60]

    @property
    def name(self) -> str:
        return "3중 이평선 정배열"

    @property
    def description(self) -> str:
        return "5일선 > 20일선 > 60일선 정배열 시작시 매수"

    def analyze(self, ohlcv: pd.DataFrame, code: str, name: str) -> Optional[ChartSignal]:
        if len(ohlcv) < 62:
            return None

        df = ohlcv.copy()
        for p in self.periods:
            df[f'ma_{p}'] = self.indicators.sma(df['close'], p)

        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        # 오늘 정배열
        aligned_today = (today['ma_5'] > today['ma_20'] > today['ma_60'])
        # 어제는 정배열 아님 (전환점)
        not_aligned_yesterday = not (yesterday['ma_5'] > yesterday['ma_20'] > yesterday['ma_60'])

        if aligned_today and not_aligned_yesterday:
            # 가격이 모든 이평선 위에 있어야 함
            if today['close'] > today['ma_5']:
                strength = 75

                return ChartSignal(
                    code=code,
                    name=name,
                    signal_type='BUY',
                    signal_strength=strength,
                    signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                    price=today['close'],
                    target_price=today['close'] * 1.12,
                    stop_loss=today['ma_20'] * 0.98,
                    description=f"3중 정배열 시작: 5일({today['ma_5']:.0f}) > 20일({today['ma_20']:.0f}) > 60일({today['ma_60']:.0f})",
                    indicators={
                        'ma_5': today['ma_5'],
                        'ma_20': today['ma_20'],
                        'ma_60': today['ma_60']
                    }
                )

        # 역배열 전환 (매도)
        reverse_today = (today['ma_5'] < today['ma_20'] < today['ma_60'])
        not_reverse_yesterday = not (yesterday['ma_5'] < yesterday['ma_20'] < yesterday['ma_60'])

        if reverse_today and not_reverse_yesterday:
            return ChartSignal(
                code=code,
                name=name,
                signal_type='SELL',
                signal_strength=70,
                signal_date=str(today.get('date', datetime.now().strftime('%Y-%m-%d'))),
                price=today['close'],
                description=f"3중 역배열 시작: 5일({today['ma_5']:.0f}) < 20일({today['ma_20']:.0f}) < 60일({today['ma_60']:.0f})",
                indicators={
                    'ma_5': today['ma_5'],
                    'ma_20': today['ma_20'],
                    'ma_60': today['ma_60']
                }
            )

        return None


# 전략 레지스트리
CHART_STRATEGIES = {
    'golden_cross': GoldenCrossStrategy,
    'volume_breakout': VolumeBreakoutStrategy,
    'accumulation': AccumulationStrategy,
    'ma_bounce': MABounceStrategy,
    'box_breakout': BoxBreakoutStrategy,
    'triple_ma': TripleMAStrategy,
}


def get_chart_strategy(strategy_name: str, **kwargs) -> BaseChartStrategy:
    """전략 인스턴스 생성"""
    if strategy_name not in CHART_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    return CHART_STRATEGIES[strategy_name](**kwargs)


def scan_all_strategies(ohlcv: pd.DataFrame, code: str, name: str) -> List[ChartSignal]:
    """모든 전략으로 스캔하여 시그널 반환"""
    signals = []
    for strategy_name, strategy_cls in CHART_STRATEGIES.items():
        try:
            strategy = strategy_cls()
            signal = strategy.analyze(ohlcv, code, name)
            if signal:
                signals.append(signal)
        except Exception as e:
            continue
    return signals
