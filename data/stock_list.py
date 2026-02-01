"""
KOSPI/KOSDAQ 전체 종목 리스트
KRX(한국거래소)에서 실시간으로 전체 종목 가져오기
"""
import pandas as pd
from functools import lru_cache
import time

# ============================================================
# 기본 종목 리스트 (KRX 연결 실패시 사용) - 시가총액 상위
# 반드시 함수 정의보다 먼저 선언해야 함!
# ============================================================
KOSPI_STOCKS_DEFAULT = [
    # 시가총액 TOP 50
    ('005930', '삼성전자'), ('000660', 'SK하이닉스'), ('373220', 'LG에너지솔루션'),
    ('207940', '삼성바이오로직스'), ('005380', '현대차'), ('000270', '기아'),
    ('068270', '셀트리온'), ('035420', 'NAVER'), ('006400', '삼성SDI'),
    ('051910', 'LG화학'), ('003670', '포스코홀딩스'), ('105560', 'KB금융'),
    ('055550', '신한지주'), ('012330', '현대모비스'), ('066570', 'LG전자'),
    ('028260', '삼성물산'), ('096770', 'SK이노베이션'), ('034730', 'SK'),
    ('003550', 'LG'), ('032830', '삼성생명'), ('035720', '카카오'),
    ('086790', '하나금융지주'), ('316140', '우리금융지주'), ('010130', '고려아연'),
    ('009150', '삼성전기'), ('033780', 'KT&G'), ('011200', 'HMM'),
    ('024110', '기업은행'), ('009540', '한국조선해양'), ('017670', 'SK텔레콤'),
    ('030200', 'KT'), ('034020', '두산에너빌리티'), ('004020', '현대제철'),
    ('011070', 'LG이노텍'), ('036570', 'NCsoft'), ('047810', '한국항공우주'),
    ('000810', '삼성화재'), ('097950', 'CJ제일제당'), ('010950', 'S-Oil'),
    ('078930', 'GS'), ('090430', '아모레퍼시픽'), ('004990', '롯데지주'),
    ('015760', '한국전력'), ('000100', '유한양행'), ('323410', '카카오뱅크'),
    ('012450', '한화에어로스페이스'), ('011170', '롯데케미칼'), ('009830', '한화솔루션'),
    ('180640', '한진칼'), ('267260', '현대일렉트릭'),
    # 추가 종목 (시가총액 51-100위)
    ('042670', '두산밥캣'), ('010140', '삼성중공업'), ('139480', '이마트'),
    ('377300', '카카오페이'), ('005490', 'POSCO'), ('004370', '농심'),
    ('036460', '한국가스공사'), ('011780', '금호석유'), ('018260', '삼성에스디에스'),
    ('088980', '맥쿼리인프라'), ('009240', '한샘'), ('000720', '현대건설'),
    ('006360', 'GS건설'), ('003490', '대한항공'), ('020150', '일진머티리얼즈'),
    ('161390', '한국타이어앤테크놀로지'), ('032640', 'LG유플러스'), ('047050', '포스코인터내셔널'),
    ('052690', '한전기술'), ('028050', '삼성엔지니어링'), ('008770', '호텔신라'),
    ('014680', '한솔케미칼'), ('000880', '한화'), ('251270', '넷마블'),
    ('361610', 'SK아이이테크놀로지'), ('006280', '녹십자'), ('138040', '메리츠금융지주'),
    ('272210', '한화시스템'), ('002790', '아모레G'), ('003230', '삼양식품'),
]

KOSDAQ_STOCKS_DEFAULT = [
    # 시가총액 TOP 50
    ('247540', '에코프로비엠'), ('086520', '에코프로'), ('091990', '셀트리온헬스케어'),
    ('263750', '펄어비스'), ('293490', '카카오게임즈'), ('035900', 'JYP Ent.'),
    ('352820', '하이브'), ('041510', '에스엠'), ('112040', '위메이드'),
    ('196170', '알테오젠'), ('066970', '엘앤에프'), ('028300', 'HLB'),
    ('257720', '실리콘투'), ('000250', '삼천당제약'), ('145020', '휴젤'),
    ('095340', 'ISC'), ('122870', '와이지엔터테인먼트'), ('039030', '이오테크닉스'),
    ('068760', '셀트리온제약'), ('240810', '원익IPS'), ('005290', '동진쎄미켐'),
    ('357780', '솔브레인'), ('137310', '에스디바이오센서'), ('328130', '루닛'),
    ('053800', '안랩'), ('403870', 'HPSP'), ('140410', '메지온'),
    ('058470', '리노공업'), ('214150', '클래시스'), ('041920', '메디아나'),
    ('078600', '대주전자재료'), ('226330', '신테카바이오'), ('067310', '하나마이크론'),
    ('215600', '신라젠'), ('348210', '넥틴'), ('036930', '주성엔지니어링'),
    ('141080', '레고켐바이오'), ('131970', '테스나'), ('083310', '엘오티베큠'),
    ('222080', '씨아이에스'), ('060280', '큐렉소'), ('357550', '석경에이티'),
    ('950140', '잉글우드랩'), ('314930', '바이오다인'), ('039200', '오스코텍'),
    ('090460', '비에이치'), ('043150', '바텍'), ('045970', '코아시아'),
    ('222800', '심텍'), ('038540', '상상인'),
]

# ============================================================
# 캐시 변수
# ============================================================
_KOSPI_CACHE = None
_KOSDAQ_CACHE = None
_CACHE_TIME = 0
_CACHE_DURATION = 3600  # 1시간 캐시


# ============================================================
# 종목 로드 함수
# ============================================================
def _fetch_krx_stocks(market: str) -> list:
    """KRX에서 종목 리스트 가져오기 (시가총액 순 정렬)"""
    stocks = []

    # 방법 1: FinanceDataReader 사용 (가장 안정적, Streamlit Cloud 호환)
    try:
        import FinanceDataReader as fdr
        if market == "KOSPI":
            df = fdr.StockListing('KOSPI')
        else:
            df = fdr.StockListing('KOSDAQ')

        for _, row in df.iterrows():
            code = str(row.get('Code', row.get('Symbol', ''))).zfill(6)
            name = row.get('Name', '')
            # 스팩, ETF 등 제외
            if name and not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']):
                # 우선주 제외 (코드가 숫자로만 구성)
                if code.isdigit():
                    stocks.append((code, name))
        if stocks:
            print(f"FinanceDataReader로 {market} {len(stocks)}개 종목 로드 성공")
            return stocks
    except Exception as e1:
        print(f"FinanceDataReader 종목 조회 실패 ({market}): {e1}")

    # 방법 2: pykrx 사용 (fallback)
    try:
        from pykrx import stock
        if market == "KOSPI":
            tickers = stock.get_market_ticker_list(market="KOSPI")
        else:
            tickers = stock.get_market_ticker_list(market="KOSDAQ")

        for ticker in tickers:
            name = stock.get_market_ticker_name(ticker)
            if not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']):
                stocks.append((ticker, name))
        if stocks:
            print(f"pykrx로 {market} {len(stocks)}개 종목 로드 성공")
            return stocks
    except Exception as e2:
        print(f"pykrx 종목 조회도 실패 ({market}): {e2}")

    # 방법 3: KRX 직접 조회 (최후의 fallback)
    try:
        if market == "KOSPI":
            url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt"
        else:
            url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt"

        df = pd.read_html(url, encoding='euc-kr')[0]

        for _, row in df.iterrows():
            code = str(row['종목코드']).zfill(6)
            name = row['회사명']
            if not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']) and code.isdigit():
                stocks.append((code, name))
        if stocks:
            print(f"KRX 직접 조회로 {market} {len(stocks)}개 종목 로드 성공")
            return stocks
    except Exception as e3:
        print(f"KRX 직접 조회도 실패 ({market}): {e3}")

    # 모든 방법 실패 시 빈 리스트 반환 (caller에서 기본값 사용)
    return []


def _sort_stocks_by_priority(stocks: list, market: str) -> list:
    """시가총액 대표 종목을 앞으로 정렬"""
    if not stocks:
        return stocks

    priority_kospi = ['005930', '000660', '373220', '207940', '005380', '000270',
                     '068270', '035420', '006400', '051910', '003670', '105560']
    priority_kosdaq = ['247540', '086520', '091990', '263750', '293490', '035900',
                      '352820', '041510', '112040', '196170', '066970', '028300']

    priority = priority_kospi if market == "KOSPI" else priority_kosdaq

    priority_stocks = []
    other_stocks = []

    for code, name in stocks:
        if code in priority:
            priority_stocks.append((code, name, priority.index(code)))
        else:
            other_stocks.append((code, name))

    priority_stocks.sort(key=lambda x: x[2])
    priority_stocks = [(code, name) for code, name, _ in priority_stocks]
    other_stocks.sort(key=lambda x: x[1])

    return priority_stocks + other_stocks


def get_kospi_stocks() -> list:
    """KOSPI 전체 종목 리스트 (캐시 사용)"""
    global _KOSPI_CACHE, _CACHE_TIME

    current_time = time.time()

    # 캐시가 유효하면 캐시 반환
    if _KOSPI_CACHE and (current_time - _CACHE_TIME) < _CACHE_DURATION:
        return _KOSPI_CACHE

    # KRX에서 가져오기
    stocks = _fetch_krx_stocks("KOSPI")

    if stocks:
        stocks = _sort_stocks_by_priority(stocks, "KOSPI")
        _KOSPI_CACHE = stocks
        _CACHE_TIME = current_time
        return stocks

    # 실패시 기존 캐시 또는 기본값 반환
    print(f"KOSPI 종목 로드 실패, 기본값({len(KOSPI_STOCKS_DEFAULT)}개) 사용")
    return _KOSPI_CACHE or KOSPI_STOCKS_DEFAULT


def get_kosdaq_stocks() -> list:
    """KOSDAQ 전체 종목 리스트 (캐시 사용)"""
    global _KOSDAQ_CACHE, _CACHE_TIME

    current_time = time.time()

    # 캐시가 유효하면 캐시 반환
    if _KOSDAQ_CACHE and (current_time - _CACHE_TIME) < _CACHE_DURATION:
        return _KOSDAQ_CACHE

    # KRX에서 가져오기
    stocks = _fetch_krx_stocks("KOSDAQ")

    if stocks:
        stocks = _sort_stocks_by_priority(stocks, "KOSDAQ")
        _KOSDAQ_CACHE = stocks
        _CACHE_TIME = current_time
        return stocks

    # 실패시 기존 캐시 또는 기본값 반환
    print(f"KOSDAQ 종목 로드 실패, 기본값({len(KOSDAQ_STOCKS_DEFAULT)}개) 사용")
    return _KOSDAQ_CACHE or KOSDAQ_STOCKS_DEFAULT


# ============================================================
# 호환성을 위한 변수 (동적으로 로드)
# ============================================================
KOSPI_STOCKS = get_kospi_stocks()
KOSDAQ_STOCKS = get_kosdaq_stocks()


# ============================================================
# 섹터 정보 (대표 종목 기준)
# ============================================================
SECTOR_MAP = {
    '005930': 'IT', '000660': 'IT', '009150': 'IT', '034220': 'IT',
    '005380': '자동차', '000270': '자동차', '012330': '자동차',
    '207940': '바이오', '068270': '바이오', '326030': '바이오',
    '105560': '금융', '055550': '금융', '086790': '금융',
    '051910': '화학', '011170': '화학', '011780': '화학',
    '096770': '에너지', '010950': '에너지', '015760': '에너지',
    '017670': '통신', '030200': '통신', '032640': '통신',
    '035420': 'IT', '004370': '소비재', '097950': '소비재',
    '000720': '건설', '006360': '건설', '010140': '산업재',
    '035900': '엔터', '352820': '엔터', '041510': '엔터',
}


# ============================================================
# 유틸리티 함수
# ============================================================
def get_sector(code: str) -> str:
    """종목의 섹터 반환"""
    return SECTOR_MAP.get(code, '기타')


def get_all_stocks():
    """전체 종목 리스트 반환"""
    return get_kospi_stocks() + get_kosdaq_stocks()


def get_stock_name(code: str) -> str:
    """종목코드로 종목명 조회"""
    for c, name in get_kospi_stocks() + get_kosdaq_stocks():
        if c == code:
            return name
    return code


def refresh_stock_list():
    """종목 리스트 강제 새로고침"""
    global _KOSPI_CACHE, _KOSDAQ_CACHE, _CACHE_TIME
    _CACHE_TIME = 0
    _KOSPI_CACHE = None
    _KOSDAQ_CACHE = None
    return get_kospi_stocks(), get_kosdaq_stocks()
