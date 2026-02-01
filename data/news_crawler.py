"""
네이버 증권 뉴스 크롤링 모듈
모바일 API 사용으로 안정적인 뉴스 수집
토큰 절약을 위해 제목만 수집하고 캐싱 적용
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import json

# 캐시 설정
_NEWS_CACHE: Dict[str, Dict] = {}
_CACHE_DURATION = 1800  # 30분 캐시


class NewsCrawler:
    """네이버 증권 뉴스 크롤러 (모바일 API 사용)"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json',
            'Referer': 'https://m.stock.naver.com'
        }
        self.api_base = "https://m.stock.naver.com/api"

    def get_stock_news(self, stock_code: str, count: int = 10) -> List[Dict]:
        """
        종목별 뉴스 가져오기 (네이버 모바일 API 사용)

        Args:
            stock_code: 종목코드 (6자리)
            count: 가져올 뉴스 개수

        Returns:
            뉴스 리스트 [{title, date, url, source}, ...]
        """
        cache_key = f"stock_{stock_code}"

        # 캐시 확인
        if cache_key in _NEWS_CACHE:
            cached = _NEWS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data'][:count]

        news_list = []

        try:
            # 네이버 모바일 주식 뉴스 API
            url = f"{self.api_base}/news/stock/{stock_code}?page=1&pageSize={count}"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                for cluster in data:
                    items = cluster.get('items', [])
                    for item in items:
                        title = item.get('title', '').replace('&amp;', '&').replace('&quot;', '"')
                        if len(title) < 5:
                            continue

                        # 날짜 파싱 (202602011601 형식)
                        date_str = item.get('datetime', '')
                        if len(date_str) >= 8:
                            formatted_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}"
                        else:
                            formatted_date = datetime.now().strftime('%Y.%m.%d')

                        news_list.append({
                            'title': title,
                            'date': formatted_date,
                            'source': item.get('officeName', '네이버뉴스'),
                            'url': f"https://m.stock.naver.com/news/article/{item.get('id', '')}"
                        })

                        if len(news_list) >= count:
                            break
                    if len(news_list) >= count:
                        break

            # 캐시 저장
            if news_list:
                _NEWS_CACHE[cache_key] = {
                    'data': news_list,
                    'time': time.time()
                }

        except Exception as e:
            print(f"종목 뉴스 크롤링 실패 ({stock_code}): {e}")

        return news_list[:count]

    def get_market_news(self, count: int = 15) -> List[Dict]:
        """
        시장 전체 뉴스 가져오기

        Args:
            count: 가져올 뉴스 개수

        Returns:
            뉴스 리스트
        """
        cache_key = "market_news"

        # 캐시 확인
        if cache_key in _NEWS_CACHE:
            cached = _NEWS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data'][:count]

        news_list = []

        try:
            # 시장 뉴스 API
            url = f"{self.api_base}/news/latest?page=1&pageSize={count}"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                items = data if isinstance(data, list) else data.get('items', [])
                for item in items:
                    if isinstance(item, dict):
                        # 클러스터 형태인 경우
                        if 'items' in item:
                            for sub_item in item['items']:
                                title = sub_item.get('title', '').replace('&amp;', '&').replace('&quot;', '"')
                                if len(title) >= 10:
                                    date_str = sub_item.get('datetime', '')
                                    formatted_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}" if len(date_str) >= 8 else datetime.now().strftime('%Y.%m.%d')
                                    news_list.append({
                                        'title': title,
                                        'date': formatted_date,
                                        'source': sub_item.get('officeName', '네이버뉴스'),
                                        'url': ''
                                    })
                        else:
                            title = item.get('title', '').replace('&amp;', '&').replace('&quot;', '"')
                            if len(title) >= 10:
                                date_str = item.get('datetime', '')
                                formatted_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}" if len(date_str) >= 8 else datetime.now().strftime('%Y.%m.%d')
                                news_list.append({
                                    'title': title,
                                    'date': formatted_date,
                                    'source': item.get('officeName', '네이버뉴스'),
                                    'url': ''
                                })

                    if len(news_list) >= count:
                        break

            # 시장 뉴스가 없으면 대표 종목 뉴스로 대체
            if not news_list:
                major_stocks = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, NAVER
                for code in major_stocks:
                    stock_news = self.get_stock_news(code, 5)
                    news_list.extend(stock_news)
                    if len(news_list) >= count:
                        break

            # 캐시 저장
            if news_list:
                _NEWS_CACHE[cache_key] = {
                    'data': news_list,
                    'time': time.time()
                }

        except Exception as e:
            print(f"시장 뉴스 크롤링 실패: {e}")

        return news_list[:count]

    def get_sector_news(self, sector_name: str, count: int = 10) -> List[Dict]:
        """
        섹터별 관련 뉴스 검색 (섹터 대표 종목 뉴스)

        Args:
            sector_name: 섹터명 (예: "반도체", "자동차")
            count: 가져올 뉴스 개수
        """
        # 섹터별 대표 종목
        sector_stocks = {
            '반도체': ['005930', '000660'],  # 삼성전자, SK하이닉스
            '자동차': ['005380', '000270'],  # 현대차, 기아
            '바이오': ['207940', '068270'],  # 삼성바이오, 셀트리온
            '2차전지': ['373220', '006400'],  # LG에너지솔루션, 삼성SDI
            'AI': ['035420', '035720'],  # NAVER, 카카오
            'IT': ['035420', '035720', '005930'],
            '금융': ['105560', '055550'],  # KB금융, 신한지주
            '화학': ['051910', '011170'],  # LG화학, 롯데케미칼
        }

        codes = sector_stocks.get(sector_name, ['005930'])
        news_list = []

        for code in codes:
            stock_news = self.get_stock_news(code, count // len(codes) + 1)
            news_list.extend(stock_news)

        return news_list[:count]


# ============================================================
# 키워드 기반 간단 감성 분석 (API 호출 없이)
# ============================================================
POSITIVE_KEYWORDS = [
    '상승', '급등', '신고가', '돌파', '호재', '수혜', '강세', '급상승',
    '매수', '추천', '목표가 상향', '실적 호조', '흑자', '전환', '성장',
    '수주', '계약', '투자', '확대', '증가', '개선', '기대', '긍정',
    '상한가', '랠리', '반등', '회복', '호실적', '어닝서프라이즈',
    '최고', '대박', '폭등', '급증', '사상최대', '신기록'
]

NEGATIVE_KEYWORDS = [
    '하락', '급락', '신저가', '추락', '악재', '리스크', '약세', '급하락',
    '매도', '경고', '목표가 하향', '실적 부진', '적자', '손실', '감소',
    '취소', '해지', '축소', '감소', '악화', '우려', '부정', '하한가',
    '폭락', '조정', '하회', '부진', '어닝쇼크', '실망',
    '최악', '위기', '급감', '파산', '퇴출'
]


def simple_sentiment_analysis(title: str) -> Dict:
    """
    키워드 기반 간단 감성 분석 (토큰 절약)

    Args:
        title: 뉴스 제목

    Returns:
        {'sentiment': 'positive'|'negative'|'neutral', 'score': float, 'keywords': []}
    """
    pos_count = 0
    neg_count = 0
    found_keywords = []

    for kw in POSITIVE_KEYWORDS:
        if kw in title:
            pos_count += 1
            found_keywords.append((kw, 'positive'))

    for kw in NEGATIVE_KEYWORDS:
        if kw in title:
            neg_count += 1
            found_keywords.append((kw, 'negative'))

    total = pos_count + neg_count
    if total == 0:
        return {'sentiment': 'neutral', 'score': 0.0, 'keywords': []}

    score = (pos_count - neg_count) / total

    if score > 0.2:
        sentiment = 'positive'
    elif score < -0.2:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'

    return {
        'sentiment': sentiment,
        'score': score,
        'keywords': found_keywords
    }


def analyze_news_batch(news_list: List[Dict]) -> Dict:
    """
    뉴스 배치 감성 분석 (키워드 기반)

    Args:
        news_list: 뉴스 리스트

    Returns:
        종합 감성 분석 결과
    """
    if not news_list:
        return {
            'overall_sentiment': 'neutral',
            'positive_ratio': 0,
            'negative_ratio': 0,
            'neutral_ratio': 0,
            'details': []
        }

    positive = 0
    negative = 0
    neutral = 0
    details = []

    for news in news_list:
        result = simple_sentiment_analysis(news['title'])
        details.append({
            'title': news['title'],
            'date': news.get('date', ''),
            'source': news.get('source', ''),
            **result
        })

        if result['sentiment'] == 'positive':
            positive += 1
        elif result['sentiment'] == 'negative':
            negative += 1
        else:
            neutral += 1

    total = len(news_list)

    # 전체 감성 결정
    if positive > negative and positive > neutral:
        overall = 'positive'
    elif negative > positive and negative > neutral:
        overall = 'negative'
    else:
        overall = 'neutral'

    return {
        'overall_sentiment': overall,
        'positive_ratio': positive / total * 100,
        'negative_ratio': negative / total * 100,
        'neutral_ratio': neutral / total * 100,
        'positive_count': positive,
        'negative_count': negative,
        'neutral_count': neutral,
        'total_count': total,
        'details': details
    }


def clear_news_cache():
    """뉴스 캐시 초기화"""
    global _NEWS_CACHE
    _NEWS_CACHE = {}


# 싱글톤 인스턴스
_crawler_instance: Optional[NewsCrawler] = None


def get_crawler() -> NewsCrawler:
    """크롤러 싱글톤 인스턴스"""
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = NewsCrawler()
    return _crawler_instance
