"""
KOSPI/KOSDAQ 전체 종목 리스트
KRX(한국거래소)에서 실시간으로 전체 종목 가져오기
"""
import pandas as pd
from functools import lru_cache
import time

# 캐시된 종목 리스트 (전역 변수)
_KOSPI_CACHE = None
_KOSDAQ_CACHE = None
_CACHE_TIME = 0
_CACHE_DURATION = 3600  # 1시간 캐시


def _fetch_krx_stocks(market: str) -> list:
    """KRX에서 종목 리스트 가져오기 (시가총액 순 정렬)"""
    try:
        if market == "KOSPI":
            url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt"
        else:  # KOSDAQ
            url = "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt"

        df = pd.read_html(url, encoding='euc-kr')[0]

        # 종목코드를 6자리 문자열로 변환
        stocks = []
        for _, row in df.iterrows():
            code = str(row['종목코드']).zfill(6)
            name = row['회사명']
            # 스팩, ETF 등 제외, 종목코드가 숫자로만 구성된 것만 (우선주 등 제외)
            if not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']) and code.isdigit():
                stocks.append((code, name))

        # 시가총액 대표 종목을 앞으로 정렬
        priority_kospi = ['005930', '000660', '373220', '207940', '005380', '000270',
                         '068270', '035420', '006400', '051910', '003670', '105560']
        priority_kosdaq = ['247540', '086520', '091990', '263750', '293490', '035900',
                          '352820', '041510', '112040', '196170', '066970', '028300']

        priority = priority_kospi if market == "KOSPI" else priority_kosdaq

        # 우선순위 종목을 앞에, 나머지는 이름순 정렬
        priority_stocks = []
        other_stocks = []

        for code, name in stocks:
            if code in priority:
                priority_stocks.append((code, name, priority.index(code)))
            else:
                other_stocks.append((code, name))

        # 우선순위 종목 정렬
        priority_stocks.sort(key=lambda x: x[2])
        priority_stocks = [(code, name) for code, name, _ in priority_stocks]

        # 나머지 이름순 정렬
        other_stocks.sort(key=lambda x: x[1])

        return priority_stocks + other_stocks
    except Exception as e:
        print(f"KRX 종목 조회 실패 ({market}): {e}")
        return []


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
        _KOSPI_CACHE = stocks
        _CACHE_TIME = current_time
        return stocks

    # 실패시 기존 캐시 또는 기본값 반환
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
        _KOSDAQ_CACHE = stocks
        _CACHE_TIME = current_time
        return stocks

    # 실패시 기존 캐시 또는 기본값 반환
    return _KOSDAQ_CACHE or KOSDAQ_STOCKS_DEFAULT


# 기본 종목 리스트 (KRX 연결 실패시 사용)
KOSPI_STOCKS_DEFAULT = [
    ('005930', '삼성전자'), ('000660', 'SK하이닉스'), ('373220', 'LG에너지솔루션'),
    ('207940', '삼성바이오로직스'), ('005380', '현대차'), ('000270', '기아'),
    ('068270', '셀트리온'), ('035420', 'NAVER'), ('006400', '삼성SDI'),
    ('051910', 'LG화학'), ('003670', '포스코홀딩스'), ('105560', 'KB금융'),
    ('055550', '신한지주'), ('012330', '현대모비스'), ('066570', 'LG전자'),
    ('028260', '삼성물산'), ('096770', 'SK이노베이션'), ('034730', 'SK'),
    ('003550', 'LG'), ('032830', '삼성생명'),
]

KOSDAQ_STOCKS_DEFAULT = [
    ('247540', '에코프로비엠'), ('086520', '에코프로'), ('091990', '셀트리온헬스케어'),
    ('263750', '펄어비스'), ('293490', '카카오게임즈'), ('035900', 'JYP Ent.'),
    ('352820', '하이브'), ('041510', '에스엠'), ('112040', '위메이드'),
    ('196170', '알테오젠'), ('066970', '엘앤에프'), ('028300', 'HLB'),
    ('257720', '실리콘투'), ('000250', '삼천당제약'), ('145020', '휴젤'),
    ('095340', 'ISC'), ('122870', '와이지엔터테인먼트'), ('039030', '이오테크닉스'),
    ('068760', '셀트리온제약'), ('240810', '원익IPS'),
]

# 호환성을 위한 변수 (동적으로 로드)
KOSPI_STOCKS = get_kospi_stocks()
KOSDAQ_STOCKS = get_kosdaq_stocks()


# 섹터 정보 (대표 종목 기준)
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
