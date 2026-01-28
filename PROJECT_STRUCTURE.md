# 퀀트 포트폴리오 시스템 설계서

## 1. 프로젝트 개요

키움 API를 활용한 한국 주식 퀀트 전략 시스템
- 마법공식, 멀티팩터, 섹터중립 전략 구현
- 백테스트 엔진 포함
- 웹 대시보드 UI

## 2. 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.10+, FastAPI |
| Data | 키움 API (pykiwoom), pandas, numpy |
| Database | SQLite (개발), PostgreSQL (운영) |
| Backtest | 자체 구현 엔진 |
| Frontend | Streamlit 또는 Dash |
| 시각화 | Plotly, matplotlib |

## 3. 디렉토리 구조

```
quant-portfolio/
├── config/
│   ├── __init__.py
│   └── settings.py              # 설정 관리
│
├── data/
│   ├── __init__.py
│   ├── kiwoom_api.py            # 키움 API 연동
│   ├── data_collector.py        # 데이터 수집기
│   └── database.py              # DB 관리
│
├── factors/
│   ├── __init__.py
│   ├── base.py                  # 팩터 베이스 클래스
│   ├── quality.py               # 퀄리티 팩터 (ROE, GPA, CFO)
│   ├── value.py                 # 밸류 팩터 (PER, PBR, PSR, PCR, EY)
│   └── momentum.py              # 모멘텀 팩터 (3M, 6M, 12M)
│
├── strategies/
│   ├── __init__.py
│   ├── base.py                  # 전략 베이스 클래스
│   ├── magic_formula.py         # 마법공식 전략
│   ├── multifactor.py           # 멀티팩터 전략
│   └── sector_neutral.py        # 섹터중립 전략
│
├── backtest/
│   ├── __init__.py
│   ├── engine.py                # 백테스트 엔진
│   ├── metrics.py               # 성과 지표 계산
│   └── report.py                # 리포트 생성
│
├── utils/
│   ├── __init__.py
│   ├── ranking.py               # 랭킹 및 Z-score
│   ├── outlier.py               # 이상치 처리
│   └── helpers.py               # 유틸리티 함수
│
├── dashboard/
│   ├── __init__.py
│   ├── app.py                   # Streamlit 메인 앱
│   ├── pages/
│   │   ├── home.py              # 홈 대시보드
│   │   ├── strategy.py          # 전략 선택/실행
│   │   ├── backtest.py          # 백테스트 결과
│   │   └── portfolio.py         # 포트폴리오 현황
│   └── components/
│       ├── charts.py            # 차트 컴포넌트
│       └── tables.py            # 테이블 컴포넌트
│
├── tests/
│   ├── __init__.py
│   ├── test_factors.py
│   ├── test_strategies.py
│   └── test_backtest.py
│
├── data_store/                  # 데이터 저장소
│   ├── stocks.db                # SQLite DB
│   └── cache/                   # 캐시 데이터
│
├── main.py                      # CLI 실행
├── requirements.txt
└── README.md
```

## 4. 핵심 모듈 설계

### 4.1 키움 API 연동 (data/kiwoom_api.py)

```python
class KiwoomAPI:
    """키움 API 래퍼 클래스"""

    def __init__(self):
        self.api = None
        self.connected = False

    def connect(self) -> bool:
        """API 연결"""
        pass

    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """전체 종목 리스트 조회
        - 코스피, 코스닥, 전체
        """
        pass

    def get_financial_data(self, code: str) -> pd.DataFrame:
        """재무제표 데이터 조회
        - ROE, 매출총이익, 영업현금흐름
        - 자산, 부채, 자본
        """
        pass

    def get_price_data(self, code: str, period: int = 365) -> pd.DataFrame:
        """주가 데이터 조회
        - OHLCV 데이터
        - 지정 기간
        """
        pass

    def get_sector_info(self, code: str) -> str:
        """섹터/업종 정보 조회"""
        pass
```

### 4.2 팩터 계산 (factors/)

```python
# factors/base.py
class BaseFactor(ABC):
    """팩터 베이스 클래스"""

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """팩터 값 계산"""
        pass

    def rank(self, values: pd.Series, ascending: bool = True) -> pd.Series:
        """랭킹 계산"""
        return values.rank(ascending=ascending, method='min')

    def zscore(self, values: pd.Series) -> pd.Series:
        """Z-score 정규화"""
        return (values - values.mean()) / values.std()

# factors/quality.py
class QualityFactor(BaseFactor):
    """퀄리티 팩터"""

    def calculate_roe(self, data: pd.DataFrame) -> pd.Series:
        """ROE = 순이익 / 자기자본"""
        return data['net_income'] / data['equity']

    def calculate_gpa(self, data: pd.DataFrame) -> pd.Series:
        """GPA = 매출총이익 / 총자산"""
        return data['gross_profit'] / data['total_assets']

    def calculate_cfo(self, data: pd.DataFrame) -> pd.Series:
        """영업현금흐름율 = 영업현금흐름 / 총자산"""
        return data['operating_cf'] / data['total_assets']

# factors/value.py
class ValueFactor(BaseFactor):
    """밸류 팩터"""

    def calculate_per(self, data: pd.DataFrame) -> pd.Series:
        """PER = 주가 / EPS"""
        pass

    def calculate_pbr(self, data: pd.DataFrame) -> pd.Series:
        """PBR = 주가 / BPS"""
        pass

    def calculate_ey(self, data: pd.DataFrame) -> pd.Series:
        """이익수익률 = EBIT / (시가총액 + 순차입금)"""
        pass

    def calculate_roc(self, data: pd.DataFrame) -> pd.Series:
        """투하자본수익률 = EBIT / 투하자본"""
        pass

# factors/momentum.py
class MomentumFactor(BaseFactor):
    """모멘텀 팩터"""

    def calculate_momentum(self, prices: pd.DataFrame, months: int) -> pd.Series:
        """N개월 수익률 계산"""
        pass
```

### 4.3 전략 (strategies/)

```python
# strategies/base.py
class BaseStrategy(ABC):
    """전략 베이스 클래스"""

    def __init__(self, top_n: int = 30):
        self.top_n = top_n
        self.selected_stocks = []

    @abstractmethod
    def select_stocks(self, data: pd.DataFrame) -> pd.DataFrame:
        """종목 선정"""
        pass

    def apply_winsorize(self, data: pd.Series, lower: float = 0.01, upper: float = 0.99):
        """윈저라이징 적용"""
        pass

# strategies/magic_formula.py
class MagicFormulaStrategy(BaseStrategy):
    """마법공식 전략
    - 이익수익률(EY) + 투하자본수익률(ROC)
    """

    def select_stocks(self, data: pd.DataFrame) -> pd.DataFrame:
        # 1. EY 랭킹 계산
        # 2. ROC 랭킹 계산
        # 3. 합산 랭킹으로 상위 N개 선정
        pass

# strategies/multifactor.py
class MultifactorStrategy(BaseStrategy):
    """멀티팩터 전략
    - 퀄리티(33%) + 밸류(33%) + 모멘텀(33%)
    """

    def __init__(self, weights: dict = None):
        super().__init__()
        self.weights = weights or {
            'quality': 0.333,
            'value': 0.333,
            'momentum': 0.334
        }

    def select_stocks(self, data: pd.DataFrame) -> pd.DataFrame:
        # 1. 각 팩터별 Z-score(Rank) 계산
        # 2. 가중치 적용하여 합산
        # 3. 상위 N개 선정
        pass

# strategies/sector_neutral.py
class SectorNeutralStrategy(BaseStrategy):
    """섹터중립 전략
    - 섹터 내 Z-score 정규화
    """

    def select_stocks(self, data: pd.DataFrame) -> pd.DataFrame:
        # 1. 섹터별 그룹화
        # 2. 섹터 내 Z-score 계산
        # 3. 각 섹터에서 상위 종목 선정
        pass
```

### 4.4 백테스트 엔진 (backtest/)

```python
# backtest/engine.py
class BacktestEngine:
    """백테스트 엔진"""

    def __init__(self,
                 strategy: BaseStrategy,
                 start_date: str,
                 end_date: str,
                 initial_capital: float = 100_000_000,
                 rebalance_period: str = 'quarterly'):
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.rebalance_period = rebalance_period
        self.portfolio_history = []

    def run(self) -> BacktestResult:
        """백테스트 실행"""
        # 1. 리밸런싱 날짜 생성
        # 2. 각 리밸런싱 시점에서 종목 선정
        # 3. 포트폴리오 가치 계산
        # 4. 결과 반환
        pass

    def _calculate_portfolio_value(self, holdings: dict, prices: pd.DataFrame) -> float:
        """포트폴리오 가치 계산"""
        pass

# backtest/metrics.py
class PerformanceMetrics:
    """성과 지표 계산"""

    @staticmethod
    def calculate_cagr(returns: pd.Series) -> float:
        """연평균 복합 성장률"""
        pass

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """샤프 비율"""
        pass

    @staticmethod
    def calculate_mdd(values: pd.Series) -> float:
        """최대 낙폭 (Maximum Drawdown)"""
        pass

    @staticmethod
    def calculate_volatility(returns: pd.Series) -> float:
        """변동성"""
        pass

    @staticmethod
    def calculate_win_rate(returns: pd.Series) -> float:
        """승률"""
        pass

# backtest/report.py
@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    cagr: float
    sharpe_ratio: float
    mdd: float
    volatility: float
    win_rate: float
    portfolio_history: pd.DataFrame
    trade_history: pd.DataFrame
```

### 4.5 웹 대시보드 (dashboard/)

```python
# dashboard/app.py (Streamlit)
import streamlit as st

def main():
    st.set_page_config(
        page_title="퀀트 포트폴리오 시스템",
        page_icon="📈",
        layout="wide"
    )

    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴",
        ["홈", "전략 실행", "백테스트", "포트폴리오"]
    )

    if menu == "홈":
        show_home()
    elif menu == "전략 실행":
        show_strategy()
    elif menu == "백테스트":
        show_backtest()
    elif menu == "포트폴리오":
        show_portfolio()
```

## 5. 데이터 플로우

```
┌─────────────────┐
│   키움 API      │
│  (실시간 데이터) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Collector │
│  (수집 및 정제)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │
│  (SQLite/PG)    │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────────┐
│Factors│ │ Backtest  │
│ 계산  │ │   Engine  │
└───┬───┘ └─────┬─────┘
    │           │
    ▼           ▼
┌─────────────────┐
│   Strategies    │
│   (종목 선정)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Dashboard     │
│   (시각화)       │
└─────────────────┘
```

## 6. 주요 계산 공식

### 6.1 팩터 계산

| 팩터 | 공식 |
|------|------|
| ROE | 순이익 / 자기자본 |
| GPA | 매출총이익 / 총자산 |
| 영업현금흐름율 | 영업현금흐름 / 총자산 |
| PER | 주가 / EPS |
| PBR | 주가 / BPS |
| PSR | 시가총액 / 매출액 |
| PCR | 주가 / 주당현금흐름 |
| EY (이익수익률) | EBIT / (시가총액 + 순차입금) |
| ROC (투하자본수익률) | EBIT / 투하자본 |
| 모멘텀 | (현재가 - N개월전 가격) / N개월전 가격 |

### 6.2 팩터 결합

```
최종점수 = Σ Z-Score(Rank(팩터_i)) × 가중치_i
```

### 6.3 성과 지표

| 지표 | 공식 |
|------|------|
| CAGR | (최종가치/초기자본)^(1/년수) - 1 |
| 샤프비율 | (평균수익률 - 무위험수익률) / 변동성 |
| MDD | max((고점 - 저점) / 고점) |
| 변동성 | 일간수익률의 표준편차 × √252 |

## 7. 구현 순서

### Phase 1: 기반 구축
1. 프로젝트 구조 생성
2. 키움 API 연동 모듈
3. 데이터베이스 설계 및 구현
4. 데이터 수집기 구현

### Phase 2: 핵심 로직
5. 팩터 계산 모듈 구현
6. 이상치 처리 유틸리티
7. 랭킹/정규화 유틸리티

### Phase 3: 전략 구현
8. 마법공식 전략
9. 멀티팩터 전략
10. 섹터중립 전략

### Phase 4: 백테스트
11. 백테스트 엔진
12. 성과 지표 계산
13. 리포트 생성

### Phase 5: 대시보드
14. Streamlit 앱 구조
15. 홈 대시보드
16. 전략 실행 페이지
17. 백테스트 결과 페이지
18. 포트폴리오 현황 페이지

## 8. 키움 API 주요 함수

| 기능 | TR 코드 | 설명 |
|------|---------|------|
| 종목리스트 | - | GetCodeListByMarket |
| 주가조회 | opt10081 | 일봉 데이터 |
| 재무정보 | opt10001 | 주식기본정보 |
| 재무제표 | opt10014 | 재무정보요청 |
| 업종정보 | - | GetMasterCodeName |

## 9. 참고사항

### 키움 API 제약
- 1초당 5회 조회 제한
- 연속조회 시 0.2초 대기 필요
- Windows 환경에서만 동작
- 32bit Python 필요

### 대안 데이터 소스
키움 API 외에도 백업용으로:
- FinanceDataReader: 무료, 주가/재무
- pykrx: KRX 데이터
- OpenDartReader: DART 공시 데이터
