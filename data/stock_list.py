"""
KOSPI/KOSDAQ 전체 종목 리스트
KRX(한국거래소)에서 실시간으로 전체 종목 가져오기
+ 네이버 금융에서 섹터/업종 정보 크롤링
"""
import pandas as pd
from functools import lru_cache
import time
import requests
from typing import Optional

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
# 네이버 금융 섹터 크롤링 캐시
# ============================================================
_NAVER_SECTOR_CACHE = {}
_NAVER_CACHE_DURATION = 86400  # 24시간 캐시


def get_sector_from_naver(code: str) -> Optional[str]:
    """
    네이버 금융에서 종목의 업종/섹터 정보 크롤링

    Args:
        code: 6자리 종목코드

    Returns:
        업종명 (없으면 None)
    """
    global _NAVER_SECTOR_CACHE

    # 캐시 확인
    if code in _NAVER_SECTOR_CACHE:
        cached = _NAVER_SECTOR_CACHE[code]
        if time.time() - cached['time'] < _NAVER_CACHE_DURATION:
            return cached['sector']

    try:
        # 네이버 금융 종목 페이지
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'euc-kr'

        if response.status_code != 200:
            return None

        html = response.text

        # 업종 정보 추출 (여러 패턴 시도)
        sector = None

        # 패턴 1: <em class="t_nm">업종명</em> (기업개요 섹션)
        import re

        # 업종 링크에서 추출 (예: /item/coinfo.naver?code=005930&amp;target=sector)
        pattern1 = r'href="/sise/sise_group_detail\.naver\?type=upjong&amp;no=\d+">([^<]+)</a>'
        match1 = re.search(pattern1, html)
        if match1:
            sector = match1.group(1).strip()

        # 패턴 2: 기업개요에서 업종 정보 (tab_con1 내)
        if not sector:
            pattern2 = r'업종</em>\s*<dd>([^<]+)</dd>'
            match2 = re.search(pattern2, html)
            if match2:
                sector = match2.group(1).strip()

        # 패턴 3: 상단 업종 배지
        if not sector:
            pattern3 = r'class="t_nm">([^<]+)</em>\s*</td>'
            match3 = re.search(pattern3, html)
            if match3:
                sector = match3.group(1).strip()

        # 패턴 4: 더 일반적인 업종 패턴
        if not sector:
            pattern4 = r'업종[:\s]*</th>\s*<td[^>]*>([^<]+)</td>'
            match4 = re.search(pattern4, html, re.IGNORECASE)
            if match4:
                sector = match4.group(1).strip()

        # 캐시 저장
        if sector:
            _NAVER_SECTOR_CACHE[code] = {'sector': sector, 'time': time.time()}
            return sector

        # 못 찾으면 None 캐시 (반복 요청 방지)
        _NAVER_SECTOR_CACHE[code] = {'sector': None, 'time': time.time()}
        return None

    except Exception as e:
        print(f"[NaverSector] {code} 조회 실패: {e}")
        return None


def get_detailed_sector_from_naver(code: str) -> dict:
    """
    네이버 금융에서 상세 섹터 정보 조회

    Returns:
        {
            'sector': 업종명,
            'sub_sector': 세부업종 (있으면),
            'industry': 산업군,
            'source': 'naver'
        }
    """
    global _NAVER_SECTOR_CACHE

    cache_key = f"{code}_detailed"
    if cache_key in _NAVER_SECTOR_CACHE:
        cached = _NAVER_SECTOR_CACHE[cache_key]
        if time.time() - cached['time'] < _NAVER_CACHE_DURATION:
            return cached['data']

    result = {
        'sector': None,
        'sub_sector': None,
        'industry': None,
        'source': 'naver'
    }

    try:
        # BeautifulSoup 사용하여 더 안정적으로 파싱
        from bs4 import BeautifulSoup

        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        response = requests.get(url, headers=headers, timeout=10)

        # 인코딩 자동 감지 시도
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = 'euc-kr'

        if response.status_code != 200:
            return result

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 업종 링크에서 추출 (가장 정확)
        # <a href="/sise/sise_group_detail.naver?type=upjong&no=267">반도체와반도체장비</a>
        sector_link = soup.find('a', href=lambda x: x and 'sise_group_detail' in x and 'upjong' in x)
        if sector_link:
            result['sector'] = sector_link.get_text(strip=True)

        # 2. 상단 시장구분 (코스피/코스닥)
        market_em = soup.find('em', class_='t_nm')
        if market_em:
            result['industry'] = market_em.get_text(strip=True)
            if not result['sector']:
                result['sector'] = market_em.get_text(strip=True)

        # 섹터명 정제
        if result['sector']:
            result['sub_sector'] = _refine_sector_name(result['sector'])

        # 캐시 저장
        _NAVER_SECTOR_CACHE[cache_key] = {'data': result, 'time': time.time()}
        return result

    except ImportError:
        # BeautifulSoup 없으면 정규식 fallback
        pass
    except Exception as e:
        print(f"[NaverSector] {code} 상세 조회 실패: {e}")

    # BeautifulSoup 없을 때 정규식 fallback
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'euc-kr'

        if response.status_code != 200:
            return result

        html = response.text
        import re

        # 업종 링크에서 추출
        pattern = r'href="[^"]*sise_group_detail[^"]*upjong[^"]*">([^<]+)</a>'
        match = re.search(pattern, html)
        if match:
            result['sector'] = match.group(1).strip()
            result['sub_sector'] = _refine_sector_name(result['sector'])

        _NAVER_SECTOR_CACHE[cache_key] = {'data': result, 'time': time.time()}
        return result

    except Exception as e:
        print(f"[NaverSector] {code} regex fallback 실패: {e}")
        return result


def _refine_sector_name(raw_sector: str) -> str:
    """네이버 업종명을 세부 분류로 정제"""
    # 업종명 매핑 (네이버 -> 세부 섹터)
    sector_mapping = {
        # 반도체
        '반도체와반도체장비': '반도체',
        '반도체': '반도체',
        '전자장비와기기': '반도체장비',
        '전자부품': '전자부품',

        # IT/소프트웨어
        '소프트웨어': 'AI/소프트웨어',
        'IT서비스': 'AI/IT서비스',
        '인터넷': 'AI/플랫폼',
        '게임엔터테인먼트': '게임',
        '미디어': '미디어',

        # 2차전지
        '전기장비': '2차전지',
        '에너지장비': '2차전지장비',
        '전기제품': '2차전지',

        # 자동차
        '자동차': '자동차',
        '자동차부품': '자동차부품',
        '운송장비': '자동차부품',
        '타이어': '타이어',

        # 바이오/제약
        '제약': '제약',
        '바이오': '바이오',
        '생물공학': '바이오',
        '건강관리장비와용품': '헬스케어',
        '건강관리업체및서비스': '헬스케어',

        # 화학
        '화학': '화학',
        '석유와가스': '석유화학',
        '가스유틸리티': '가스',

        # 금융
        '은행': '은행',
        '보험': '보험',
        '증권': '증권',
        '다각화된금융': '금융지주',
        '캐피탈': '카드/캐피탈',

        # 건설/부동산
        '건설': '건설',
        '부동산': '부동산',
        '건축자재': '건자재',

        # 유통/소비재
        '백화점과일반상점': '유통',
        '소매(유통)': '유통',
        '식품': '식품',
        '음식료품': '식품',
        '음료': '음료',
        '의류': '의류',
        '화장품': '화장품',
        '가정용품': '생활용품',

        # 조선/해운
        '조선': '조선',
        '해운': '해운',
        '항공': '항공',
        '항공사': '항공',

        # 방산/우주항공
        '항공우주와국방': '우주항공',
        '국방': '방산',

        # 철강/소재
        '철강': '철강',
        '비철금속': '비철금속',
        '종이와목재': '종이/목재',

        # 통신
        '무선통신서비스': '통신/5G',
        '다각화된통신서비스': '통신/5G',
        '통신장비': '통신장비',

        # 엔터테인먼트
        '엔터테인먼트': '엔터',
        '방송과엔터테인먼트': '엔터',

        # 전력/유틸리티
        '전기유틸리티': '전력',
        '전력': '전력',
        '유틸리티': '유틸리티',

        # 기계/산업재
        '기계': '기계',
        '산업재': '산업재',
        '운송인프라': '인프라',
    }

    # 정확히 매칭
    if raw_sector in sector_mapping:
        return sector_mapping[raw_sector]

    # 부분 매칭
    for key, value in sector_mapping.items():
        if key in raw_sector or raw_sector in key:
            return value

    # 매핑 없으면 원본 반환
    return raw_sector


# ============================================================
# 섹터 정보 (세부 분류) - 정적 매핑 (Fallback)
# ============================================================
SECTOR_MAP = {
    # ===== 반도체 =====
    '005930': '반도체', '000660': '반도체',  # 삼성전자, SK하이닉스
    '009150': '반도체장비', '034220': '반도체',  # 삼성전기, LG디스플레이
    '042700': '반도체장비', '403870': '반도체장비',  # 한미반도체, HPSP
    '005290': '반도체', '000990': '반도체',  # 동진쎄미켐, DB하이텍
    '357780': '반도체', '036930': '반도체소재',  # 솔브레인, 주성엔지니어링
    '058470': '반도체', '166090': '반도체',  # 리노공업, 하나마이크론

    # ===== 2차전지/배터리 =====
    '373220': '2차전지', '006400': '2차전지',  # LG에너지솔루션, 삼성SDI
    '051910': '2차전지소재', '003670': '2차전지소재',  # LG화학, 포스코퓨처엠
    '247540': '2차전지소재', '012450': '2차전지',  # 에코프로비엠, 한화에어로스페이스(배터리)
    '086520': '2차전지소재', '298040': '2차전지',  # 에코프로, 효성중공업
    '011790': '2차전지소재', '006260': '2차전지',  # SKC, LS
    '298050': '2차전지장비', '064350': '2차전지장비',  # 효성화학, 현대로템

    # ===== 우주항공/방산 =====
    '012450': '우주항공', '047810': '방산',  # 한화에어로스페이스, 한국항공우주
    '079550': '방산', '012750': '방산',  # LIG넥스원, 에스원
    '003570': '조선방산', '010620': '방산',  # SNT다이내믹스, 현대미포조선
    '042660': '방산', '067310': '방산전자',  # 한화오션, 세방리튬배터리(우주)
    '138930': '우주항공', '042670': '방산',  # BNK금융지주(우주펀드), 두산에너빌리티
    '298690': '우주항공',  # AP위성

    # ===== 자동차/전기차 =====
    '005380': '자동차', '000270': '자동차',  # 현대차, 기아
    '012330': '자동차부품', '011210': '타이어',  # 현대모비스, 현대위아
    '161390': '전기차부품', '018880': '자동차부품',  # 한국타이어앤테크놀로지, 한온시스템
    '004020': '자동차', '009540': '자동차부품',  # 현대제철, 한국조선해양

    # ===== 바이오/제약/헬스케어 =====
    '207940': '바이오', '068270': '바이오',  # 삼성바이오로직스, 셀트리온
    '326030': '바이오', '091990': '헬스케어',  # SK바이오팜, 셀트리온헬스케어
    '141080': '바이오CMO', '145020': '바이오',  # 레고켐바이오, 휴젤
    '196170': '제약', '185750': '진단키트',  # 알테오젠, 종근당
    '086900': '바이오', '000120': '제약',  # 메디톡스, CJ제일제당
    '128940': '바이오', '006280': '제약',  # 한미약품, 녹십자
    '002630': '화장품', '090430': '화장품',  # 코스맥스, 아모레퍼시픽

    # ===== AI/소프트웨어/IT =====
    '035420': 'AI/플랫폼', '035720': 'AI/플랫폼',  # 네이버, 카카오
    '036570': 'AI/게임', '263750': 'AI/게임',  # 엔씨소프트, 펄어비스
    '259960': 'AI반도체', '293490': 'AI/SaaS',  # 크래프톤, 카카오게임즈
    '000100': 'AI인프라', '017670': '통신/5G',  # 유한양행, SK텔레콤
    '030200': '통신/5G', '032640': '통신/5G',  # KT, LG유플러스

    # ===== 로봇/자동화 =====
    '138580': '로봇', '090460': '로봇',  # 니드텍, 레인보우로보틱스
    '272290': '로봇', '317330': '로봇',  # 알루코, 덕산테코피아
    '298000': '자동화장비', '056190': '로봇부품',  # 효성티앤씨, 에스에프에이

    # ===== 금융 =====
    '105560': '은행', '055550': '은행',  # KB금융, 신한지주
    '086790': '보험', '000810': '보험',  # 하나금융지주, 삼성화재
    '316140': '카드/캐피탈', '024110': '증권',  # 우리금융지주, 기업은행
    '138930': '금융지주', '003540': '증권',  # BNK금융지주, 대신증권

    # ===== 화학/소재 =====
    '011170': '화학', '011780': '화학',  # 롯데케미칼, 금호석유화학
    '096770': '석유화학', '010950': '석유화학',  # SK이노베이션, S-Oil
    '015760': '정유', '006120': 'SK그룹',  # 한국전력, SK디스커버리
    '004370': '가스', '034730': 'SK그룹',  # 농심, SK

    # ===== 조선/해운 =====
    '009540': '조선', '010620': '조선',  # 한국조선해양, 현대미포조선
    '042660': '조선', '003620': '조선',  # 한화오션, 쌍용C&E
    '028670': '해운', '011200': '해운',  # 팬오션, HMM

    # ===== 건설/부동산 =====
    '000720': '건설', '006360': '건설',  # 현대건설, GS건설
    '034730': '건설', '000210': '건설',  # SK, 대림산업
    '004020': '철강/건자재', '005490': '철강',  # 현대제철, POSCO홀딩스

    # ===== 엔터테인먼트/미디어 =====
    '035900': '엔터', '352820': '엔터',  # JYP엔터테인먼트, 하이브
    '041510': '엔터', '122870': '미디어',  # SM, YG플러스
    '079160': '미디어', '067160': '미디어',  # CJ CGV, 아프리카TV

    # ===== 식품/유통 =====
    '097950': '유통', '004170': '유통',  # CJ제일제당, 신세계
    '069960': '유통', '139480': '유통',  # 현대백화점, 이마트
    '004020': '유통', '051600': '식품',  # BGF리테일, 한국첨단소재

    # ===== 기타 산업재 =====
    '010140': '산업재', '042670': '에너지장비',  # 삼성중공업, 두산에너빌리티
    '298050': '화학/섬유', '298040': '전력설비',  # 효성화학, 효성중공업

    # ===== 코스닥 주요 종목 =====
    '119830': '에너지솔루션',  # 아이텍
    '028300': '반도체장비',  # HLB
    '112040': 'AI반도체',  # 위메이드
    '095340': 'AI',  # ISC
    '039030': 'IoT',  # 이오테크닉스
    '293490': '게임',  # 카카오게임즈
    '058970': 'AI소프트웨어',  # 엠로
    '086960': 'AI로봇',  # MDS테크
    '214150': 'AI클라우드',  # 클래시스
    '352820': 'K-POP',  # 하이브
}


# ============================================================
# 유틸리티 함수
# ============================================================
def get_sector(code: str, use_naver: bool = True) -> str:
    """
    종목의 섹터 반환

    Args:
        code: 6자리 종목코드
        use_naver: True면 네이버 금융에서 실시간 조회 (기본값)

    Returns:
        섹터/업종명
    """
    # 1. 정적 매핑 먼저 확인 (빠름)
    if code in SECTOR_MAP:
        return SECTOR_MAP[code]

    # 2. 네이버 금융에서 조회 (use_naver=True일 때)
    if use_naver:
        try:
            naver_result = get_detailed_sector_from_naver(code)
            if naver_result and naver_result.get('sub_sector'):
                return naver_result['sub_sector']
            elif naver_result and naver_result.get('sector'):
                return naver_result['sector']
        except Exception as e:
            print(f"[get_sector] 네이버 조회 실패 {code}: {e}")

    # 3. Fallback
    return '기타'


def get_sector_with_source(code: str) -> dict:
    """
    섹터 정보와 출처를 함께 반환

    Returns:
        {
            'sector': 섹터명,
            'source': 'static' | 'naver' | 'fallback'
        }
    """
    # 1. 정적 매핑 확인
    if code in SECTOR_MAP:
        return {'sector': SECTOR_MAP[code], 'source': 'static'}

    # 2. 네이버 조회
    try:
        naver_result = get_detailed_sector_from_naver(code)
        if naver_result and naver_result.get('sub_sector'):
            return {'sector': naver_result['sub_sector'], 'source': 'naver'}
        elif naver_result and naver_result.get('sector'):
            return {'sector': naver_result['sector'], 'source': 'naver'}
    except Exception:
        pass

    return {'sector': '기타', 'source': 'fallback'}


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
