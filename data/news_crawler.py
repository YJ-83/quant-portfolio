"""
네이버 증권 뉴스 크롤링 모듈
토큰 절약을 위해 제목만 수집하고 캐싱 적용
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from functools import lru_cache
import json
import os
from pathlib import Path

# 캐시 설정
_NEWS_CACHE: Dict[str, Dict] = {}
_CACHE_DURATION = 1800  # 30분 캐시


class NewsCrawler:
    """네이버 증권 뉴스 크롤러"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.base_url = "https://finance.naver.com"

    def get_stock_news(self, stock_code: str, count: int = 10) -> List[Dict]:
        """
        종목별 뉴스 가져오기 (제목만 - 토큰 절약)

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
            # 네이버 증권 종목 뉴스 페이지
            url = f"{self.base_url}/item/news_news.naver?code={stock_code}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'euc-kr'

            soup = BeautifulSoup(response.text, 'html.parser')

            # 뉴스 테이블 파싱
            news_table = soup.select_one('table.type5')
            if news_table:
                rows = news_table.select('tr')

                for row in rows:
                    title_cell = row.select_one('td.title a')
                    date_cell = row.select_one('td.date')
                    source_cell = row.select_one('td.info')

                    if title_cell and date_cell:
                        title = title_cell.get_text(strip=True)
                        date = date_cell.get_text(strip=True)
                        source = source_cell.get_text(strip=True) if source_cell else "네이버뉴스"
                        news_url = self.base_url + title_cell.get('href', '')

                        # 제목이 너무 짧으면 스킵
                        if len(title) < 5:
                            continue

                        news_list.append({
                            'title': title,
                            'date': date,
                            'url': news_url,
                            'source': source
                        })

                        if len(news_list) >= count * 2:  # 여유있게 수집
                            break

            # 캐시 저장
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
            # 네이버 증권 시장 뉴스
            url = f"{self.base_url}/news/mainnews.naver"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'euc-kr'

            soup = BeautifulSoup(response.text, 'html.parser')

            # 메인 뉴스 영역
            news_items = soup.select('div.mainNewsList dd a')

            for item in news_items:
                title = item.get_text(strip=True)
                if len(title) >= 10:
                    news_list.append({
                        'title': title,
                        'date': datetime.now().strftime('%Y.%m.%d'),
                        'url': self.base_url + item.get('href', ''),
                        'source': '네이버뉴스'
                    })

                if len(news_list) >= count * 2:
                    break

            # 추가로 시장 이슈 뉴스도 수집
            issue_items = soup.select('div.section_strategy dd a')
            for item in issue_items:
                title = item.get_text(strip=True)
                if len(title) >= 10:
                    news_list.append({
                        'title': title,
                        'date': datetime.now().strftime('%Y.%m.%d'),
                        'url': self.base_url + item.get('href', ''),
                        'source': '네이버뉴스'
                    })

                if len(news_list) >= count * 2:
                    break

            # 캐시 저장
            _NEWS_CACHE[cache_key] = {
                'data': news_list,
                'time': time.time()
            }

        except Exception as e:
            print(f"시장 뉴스 크롤링 실패: {e}")

        return news_list[:count]

    def get_sector_news(self, sector_name: str, count: int = 10) -> List[Dict]:
        """
        섹터별 관련 뉴스 검색

        Args:
            sector_name: 섹터명 (예: "반도체", "자동차")
            count: 가져올 뉴스 개수
        """
        cache_key = f"sector_{sector_name}"

        # 캐시 확인
        if cache_key in _NEWS_CACHE:
            cached = _NEWS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data'][:count]

        news_list = []

        try:
            # 네이버 뉴스 검색
            search_url = f"https://search.naver.com/search.naver?where=news&query={sector_name}+주식"
            response = requests.get(search_url, headers=self.headers, timeout=10)

            soup = BeautifulSoup(response.text, 'html.parser')

            # 뉴스 검색 결과
            news_items = soup.select('div.news_area a.news_tit')

            for item in news_items:
                title = item.get_text(strip=True)
                if len(title) >= 10:
                    news_list.append({
                        'title': title,
                        'date': datetime.now().strftime('%Y.%m.%d'),
                        'url': item.get('href', ''),
                        'source': '네이버검색'
                    })

                if len(news_list) >= count:
                    break

            # 캐시 저장
            _NEWS_CACHE[cache_key] = {
                'data': news_list,
                'time': time.time()
            }

        except Exception as e:
            print(f"섹터 뉴스 크롤링 실패 ({sector_name}): {e}")

        return news_list[:count]


# ============================================================
# 키워드 기반 간단 감성 분석 (API 호출 없이)
# ============================================================
POSITIVE_KEYWORDS = [
    '상승', '급등', '신고가', '돌파', '호재', '수혜', '강세', '급상승',
    '매수', '추천', '목표가 상향', '실적 호조', '흑자', '전환', '성장',
    '수주', '계약', '투자', '확대', '증가', '개선', '기대', '긍정',
    '상한가', '랠리', '반등', '회복', '호실적', '어닝서프라이즈'
]

NEGATIVE_KEYWORDS = [
    '하락', '급락', '신저가', '추락', '악재', '리스크', '약세', '급하락',
    '매도', '경고', '목표가 하향', '실적 부진', '적자', '손실', '감소',
    '취소', '해지', '축소', '감소', '악화', '우려', '부정', '하한가',
    '폭락', '조정', '하회', '부진', '어닝쇼크', '실망'
]


def simple_sentiment_analysis(title: str) -> Dict:
    """
    키워드 기반 간단 감성 분석 (토큰 절약)

    Args:
        title: 뉴스 제목

    Returns:
        {'sentiment': 'positive'|'negative'|'neutral', 'score': float, 'keywords': []}
    """
    title_lower = title.lower()

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

    if score > 0.3:
        sentiment = 'positive'
    elif score < -0.3:
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
