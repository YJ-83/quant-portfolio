# 퀀트 포트폴리오 시스템

한국투자증권 Open API를 활용한 한국 주식 퀀트 전략 시스템

## 주요 기능

- **마법공식 전략**: Joel Greenblatt의 "좋은 기업을 싸게 사라" 전략
- **멀티팩터 전략**: 퀄리티 + 밸류 + 모멘텀 팩터 결합
- **섹터 중립 전략**: 섹터 편중 방지를 위한 상대 강도 전략
- **백테스트 엔진**: 과거 성과 시뮬레이션 및 성과 지표 계산
- **웹 대시보드**: Streamlit 기반 실시간 대시보드

## 설치

```bash
# 저장소 클론
git clone https://github.com/yourusername/quant-portfolio.git
cd quant-portfolio

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 한국투자증권 API 설정

### 1. API 신청

[KIS Developers](https://apiportal.koreainvestment.com/intro)에서 API 서비스를 신청합니다.

### 2. 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=your_account_number_here  # 선택사항
```

또는 직접 환경변수 설정:

```bash
export KIS_APP_KEY="your_app_key"
export KIS_APP_SECRET="your_app_secret"
```

## 사용법

### 데이터 수집

```bash
# 한국투자증권 API로 전체 데이터 수집
python main.py collect --all

# 대안 데이터 소스 사용 (FinanceDataReader)
python main.py collect --all --use-alternative

# 일일 업데이트
python main.py collect --daily
```

### 전략 실행

```bash
# 마법공식 전략
python main.py run --strategy magic_formula --top-n 30

# 멀티팩터 전략
python main.py run --strategy multifactor --top-n 30

# 섹터 중립 전략
python main.py run --strategy sector_neutral --top-n 30

# 결과를 CSV로 저장
python main.py run --strategy magic_formula --output result.csv
```

### 백테스트

```bash
# 마법공식 백테스트
python main.py backtest --strategy magic_formula \
    --start 2021-01-01 --end 2023-12-31

# 초기 자본금 및 리밸런싱 주기 설정
python main.py backtest --strategy multifactor \
    --start 2020-01-01 \
    --initial-capital 50000000 \
    --rebalance monthly
```

### 웹 대시보드

```bash
# 대시보드 실행 (기본 포트: 8501)
python main.py dashboard

# 포트 지정
python main.py dashboard --port 8080
```

브라우저에서 접속:
- **로컬**: http://localhost:8501

## 프로젝트 구조

```
quant-portfolio/
├── config/              # 설정 관리
├── data/                # 데이터 수집 (한국투자증권 API)
│   ├── kis_api.py       # 한국투자증권 API 연동
│   ├── data_collector.py
│   └── database.py
├── factors/             # 팩터 계산
│   ├── quality.py       # ROE, GPA, CFO
│   ├── value.py         # PER, PBR, PSR, PCR, EY
│   └── momentum.py      # 3M, 6M, 12M 모멘텀
├── strategies/          # 전략
│   ├── magic_formula.py # 마법공식
│   ├── multifactor.py   # 멀티팩터
│   └── sector_neutral.py
├── backtest/            # 백테스트 엔진
├── dashboard/           # Streamlit 웹 대시보드
├── utils/               # 유틸리티
└── tests/               # 테스트
```

## 전략 설명

### 마법공식 (Magic Formula)

Joel Greenblatt의 "주식시장을 이기는 작은 책"에서 소개된 전략

- **이익수익률(EY)** = EBIT / (시가총액 + 순차입금)
- **투하자본수익률(ROC)** = EBIT / 투하자본
- 두 지표의 랭킹 합산으로 상위 종목 선정

### 멀티팩터

3가지 팩터를 결합한 전략:

| 팩터 | 비중 | 지표 |
|------|------|------|
| 퀄리티 | 33% | ROE, GPA, 영업현금흐름율 |
| 밸류 | 33% | PER, PBR, PSR, PCR |
| 모멘텀 | 34% | 3M, 6M, 12M 수익률 |

### 섹터 중립

- 섹터 내 상대 강도로 종목 선정
- 특정 섹터 편중 방지
- 모멘텀 전략의 섹터 쏠림 해결

## 성과 지표

- **CAGR**: 연평균 복합 성장률
- **샤프 비율**: 위험 조정 수익률
- **소르티노 비율**: 하방 위험 조정 수익률
- **MDD**: 최대 낙폭
- **칼마 비율**: CAGR / MDD
- **승률**: 양수 수익률 비중

## 참고 자료

- [퀀트 전략을 이용한 종목선정 (심화)](https://hyunyulhenry.github.io/quant_cookbook/)
- [KIS Developers 공식 포털](https://apiportal.koreainvestment.com/intro)
- [python-kis GitHub](https://github.com/Soju06/python-kis)
- Joel Greenblatt, "The Little Book That Beats the Market"

## 라이선스

MIT License
