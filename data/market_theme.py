"""
실시간 주도 테마/섹터 분석 서비스
네이버 증권 크롤링 기반
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time
from typing import List, Dict, Optional
from dataclasses import dataclass
import time as time_module


@dataclass
class ThemeInfo:
    """테마 정보"""
    rank: int
    name: str
    change_rate: float  # 등락률
    leader_stock: str   # 대장주
    leader_code: str    # 대장주 코드
    stock_count: int    # 종목수
    theme_code: str     # 테마 코드


@dataclass
class SectorInfo:
    """섹터(업종) 정보"""
    rank: int
    name: str
    change_rate: float
    volume: int  # 거래량
    sector_code: str


@dataclass
class TopMoverStock:
    """급등/급락 종목"""
    rank: int
    code: str
    name: str
    price: int
    change_rate: float
    volume: int
    market: str  # KOSPI/KOSDAQ


class MarketThemeService:
    """실시간 주도 테마/섹터 분석 서비스"""

    # 네이버 증권 URL
    THEME_URL = "https://finance.naver.com/sise/theme.naver"
    SECTOR_URL = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    TOP_GAINERS_URL = "https://finance.naver.com/sise/lastsise2.naver"
    TOP_LOSERS_URL = "https://finance.naver.com/sise/lastsise2.naver?sosession=down"
    NEWS_URL = "https://finance.naver.com/news/mainnews.naver"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    def __init__(self):
        self._theme_cache = None
        self._theme_cache_time = 0
        self._sector_cache = None
        self._sector_cache_time = 0
        self._gainers_cache = None
        self._gainers_cache_time = 0
        self._losers_cache = None
        self._losers_cache_time = 0
        self._news_cache = None
        self._news_cache_time = 0
        self.cache_duration = 60  # 1분 캐시

    def _is_cache_valid(self, cache_time: float) -> bool:
        """캐시 유효성 확인"""
        return (time_module.time() - cache_time) < self.cache_duration

    def _fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """HTML 가져오기"""
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.encoding = 'euc-kr'
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"크롤링 오류: {e}")
            return None

    def get_hot_themes(self, top_n: int = 10, sort_by: str = 'change') -> List[ThemeInfo]:
        """
        상승률 TOP 테마 가져오기

        Args:
            top_n: 상위 N개
            sort_by: 정렬 기준 ('change': 등락률, 'volume': 거래량)
        """
        # 캐시 확인
        if self._theme_cache and self._is_cache_valid(self._theme_cache_time):
            themes = self._theme_cache
        else:
            themes = self._crawl_themes()
            self._theme_cache = themes
            self._theme_cache_time = time_module.time()

        if not themes:
            return []

        # 상승 테마만 필터링 후 정렬
        rising_themes = [t for t in themes if t.change_rate > 0]
        rising_themes.sort(key=lambda x: x.change_rate, reverse=True)

        return rising_themes[:top_n]

    def get_falling_themes(self, top_n: int = 10) -> List[ThemeInfo]:
        """하락률 TOP 테마"""
        if self._theme_cache and self._is_cache_valid(self._theme_cache_time):
            themes = self._theme_cache
        else:
            themes = self._crawl_themes()
            self._theme_cache = themes
            self._theme_cache_time = time_module.time()

        if not themes:
            return []

        falling_themes = [t for t in themes if t.change_rate < 0]
        falling_themes.sort(key=lambda x: x.change_rate)

        return falling_themes[:top_n]

    def _crawl_themes(self) -> List[ThemeInfo]:
        """네이버 테마 크롤링"""
        themes = []

        try:
            soup = self._fetch_html(self.THEME_URL)
            if not soup:
                return themes

            # 테마 테이블 찾기 - 여러 클래스 시도
            table = soup.find('table', {'class': 'type_1'})
            if not table:
                table = soup.find('table', {'class': 'theme'})
            if not table:
                # 모든 테이블에서 찾기
                tables = soup.find_all('table')
                for t in tables:
                    if t.find('a', href=lambda x: x and 'theme' in x.lower() if x else False):
                        table = t
                        break
            if not table:
                return themes

            rows = table.find_all('tr')

            rank = 0
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                try:
                    # 테마명 - 첫번째 컬럼에서 링크 찾기
                    theme_link = cols[0].find('a')
                    if not theme_link:
                        continue

                    theme_name = theme_link.text.strip()
                    if not theme_name:
                        continue

                    theme_href = theme_link.get('href', '')
                    theme_code = ''
                    if 'no=' in theme_href:
                        theme_code = theme_href.split('no=')[-1].split('&')[0]

                    # 등락률 찾기 - % 포함된 텍스트 찾기
                    change_rate = 0
                    for col in cols:
                        col_text = col.text.strip()
                        if '%' in col_text:
                            change_text = col_text.replace('%', '').replace('+', '').replace(',', '').strip()
                            try:
                                change_rate = float(change_text)
                                break
                            except:
                                continue

                    if change_rate == 0:
                        # 두번째 또는 세번째 컬럼에서 시도
                        for idx in [1, 2]:
                            if idx < len(cols):
                                try:
                                    change_text = cols[idx].text.strip().replace('%', '').replace('+', '').replace(',', '')
                                    if change_text and change_text != '-':
                                        change_rate = float(change_text)
                                        break
                                except:
                                    continue

                    # 대장주 찾기 - 종목 링크 찾기 (main/item 또는 code= 포함)
                    leader_stock = ''
                    leader_code = ''
                    for col in cols[1:]:  # 첫번째 컬럼은 테마명이므로 제외
                        links = col.find_all('a')
                        for link in links:
                            href = link.get('href', '')
                            if 'code=' in href or '/item/' in href:
                                leader_stock = link.text.strip()
                                if 'code=' in href:
                                    leader_code = href.split('code=')[-1].split('&')[0]
                                break
                        if leader_stock:
                            break

                    # 종목수 (추정)
                    stock_count = 0

                    rank += 1
                    themes.append(ThemeInfo(
                        rank=rank,
                        name=theme_name,
                        change_rate=change_rate,
                        leader_stock=leader_stock,
                        leader_code=leader_code,
                        stock_count=stock_count,
                        theme_code=theme_code
                    ))

                except (ValueError, AttributeError, IndexError) as e:
                    continue

        except Exception as e:
            print(f"테마 크롤링 오류: {e}")

        return themes

    def get_sector_ranking(self, top_n: int = 10, rising: bool = True) -> List[SectorInfo]:
        """
        업종별 등락률 순위

        Args:
            top_n: 상위 N개
            rising: True면 상승 업종, False면 하락 업종
        """
        if self._sector_cache and self._is_cache_valid(self._sector_cache_time):
            sectors = self._sector_cache
        else:
            sectors = self._crawl_sectors()
            self._sector_cache = sectors
            self._sector_cache_time = time_module.time()

        if not sectors:
            return []

        if rising:
            filtered = [s for s in sectors if s.change_rate > 0]
            filtered.sort(key=lambda x: x.change_rate, reverse=True)
        else:
            filtered = [s for s in sectors if s.change_rate < 0]
            filtered.sort(key=lambda x: x.change_rate)

        return filtered[:top_n]

    def _crawl_sectors(self) -> List[SectorInfo]:
        """네이버 업종별 시세 크롤링"""
        sectors = []

        try:
            soup = self._fetch_html(self.SECTOR_URL)
            if not soup:
                return sectors

            table = soup.find('table', {'class': 'type_1'})
            if not table:
                return sectors

            rows = table.find_all('tr')
            rank = 0

            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                try:
                    # 업종명
                    sector_link = cols[0].find('a')
                    if not sector_link:
                        continue

                    sector_name = sector_link.text.strip()
                    sector_href = sector_link.get('href', '')
                    sector_code = ''
                    if 'no=' in sector_href:
                        sector_code = sector_href.split('no=')[-1].split('&')[0]

                    # 등락률
                    change_text = cols[1].text.strip().replace('%', '').replace('+', '').replace(',', '')
                    if not change_text or change_text == '-':
                        continue
                    change_rate = float(change_text)

                    rank += 1
                    sectors.append(SectorInfo(
                        rank=rank,
                        name=sector_name,
                        change_rate=change_rate,
                        volume=0,
                        sector_code=sector_code
                    ))

                except (ValueError, AttributeError, IndexError):
                    continue

        except Exception as e:
            print(f"업종 크롤링 오류: {e}")

        return sectors

    def get_top_gainers(self, top_n: int = 10) -> List[TopMoverStock]:
        """급등 종목"""
        if self._gainers_cache and self._is_cache_valid(self._gainers_cache_time):
            return self._gainers_cache[:top_n]

        gainers = self._crawl_top_movers(rising=True)
        self._gainers_cache = gainers
        self._gainers_cache_time = time_module.time()

        return gainers[:top_n]

    def get_top_losers(self, top_n: int = 10) -> List[TopMoverStock]:
        """급락 종목"""
        if self._losers_cache and self._is_cache_valid(self._losers_cache_time):
            return self._losers_cache[:top_n]

        losers = self._crawl_top_movers(rising=False)
        self._losers_cache = losers
        self._losers_cache_time = time_module.time()

        return losers[:top_n]

    def _crawl_top_movers(self, rising: bool = True) -> List[TopMoverStock]:
        """급등/급락 종목 크롤링"""
        stocks = []
        url = "https://finance.naver.com/sise/lastsise2.naver" if rising else "https://finance.naver.com/sise/lastsise2.naver?sosok=down"

        try:
            soup = self._fetch_html(url)
            if not soup:
                return stocks

            table = soup.find('table', {'class': 'type_2'})
            if not table:
                return stocks

            rows = table.find_all('tr')
            rank = 0

            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 6:
                    continue

                try:
                    # 종목명
                    stock_link = cols[1].find('a')
                    if not stock_link:
                        continue

                    stock_name = stock_link.text.strip()
                    stock_href = stock_link.get('href', '')
                    stock_code = ''
                    if 'code=' in stock_href:
                        stock_code = stock_href.split('code=')[-1].split('&')[0]

                    # 현재가
                    price_text = cols[2].text.strip().replace(',', '')
                    price = int(price_text) if price_text.isdigit() else 0

                    # 등락률
                    change_text = cols[4].text.strip().replace('%', '').replace('+', '').replace(',', '')
                    try:
                        change_rate = float(change_text)
                    except:
                        continue

                    # 거래량
                    volume_text = cols[5].text.strip().replace(',', '')
                    volume = int(volume_text) if volume_text.isdigit() else 0

                    rank += 1
                    stocks.append(TopMoverStock(
                        rank=rank,
                        code=stock_code,
                        name=stock_name,
                        price=price,
                        change_rate=change_rate,
                        volume=volume,
                        market='KOSPI'  # 기본값
                    ))

                except (ValueError, AttributeError, IndexError):
                    continue

        except Exception as e:
            print(f"급등/급락 크롤링 오류: {e}")

        return stocks

    def get_market_news(self, top_n: int = 5) -> List[Dict]:
        """주요 경제 뉴스 헤드라인"""
        if self._news_cache and self._is_cache_valid(self._news_cache_time):
            return self._news_cache[:top_n]

        news = self._crawl_news()
        self._news_cache = news
        self._news_cache_time = time_module.time()

        return news[:top_n]

    def _crawl_news(self) -> List[Dict]:
        """네이버 금융 뉴스 크롤링"""
        news_list = []

        try:
            soup = self._fetch_html(self.NEWS_URL)
            if not soup:
                return news_list

            # 뉴스 리스트 찾기
            news_items = soup.find_all('li', {'class': 'block1'})

            for item in news_items[:10]:
                try:
                    # 제목은 articleSubject 내의 a 태그에서 추출
                    subject = item.find('dd', {'class': 'articleSubject'})
                    if not subject:
                        continue

                    link = subject.find('a')
                    if not link:
                        continue

                    title = link.text.strip()
                    url = link.get('href', '')

                    # 시간은 wdate 클래스에서 추출
                    time_span = item.find('span', {'class': 'wdate'})
                    news_time = time_span.text.strip() if time_span else ''

                    if title:  # 제목이 있는 경우만 추가
                        news_list.append({
                            'title': title,
                            'url': url,
                            'time': news_time
                        })

                except (AttributeError, IndexError):
                    continue

        except Exception as e:
            print(f"뉴스 크롤링 오류: {e}")

        return news_list

    def is_market_open(self) -> bool:
        """장 운영 시간 확인 (09:00 ~ 15:30)"""
        now = datetime.now()
        # 주말 체크
        if now.weekday() >= 5:
            return False
        # 시간 체크
        market_open = time(9, 0)
        market_close = time(15, 30)
        current_time = now.time()
        return market_open <= current_time <= market_close

    def get_market_status(self) -> str:
        """현재 시장 상태"""
        now = datetime.now()
        current_time = now.time()

        if now.weekday() >= 5:
            return "휴장 (주말)"

        if current_time < time(9, 0):
            return "장 시작 전"
        elif current_time > time(15, 30):
            return "장 마감"
        else:
            return "장중"

    def get_all_market_data(self) -> Dict:
        """전체 시장 데이터 한번에 가져오기"""
        return {
            'status': self.get_market_status(),
            'is_open': self.is_market_open(),
            'hot_themes': self.get_hot_themes(5),
            'falling_themes': self.get_falling_themes(5),
            'rising_sectors': self.get_sector_ranking(5, rising=True),
            'falling_sectors': self.get_sector_ranking(5, rising=False),
            'top_gainers': self.get_top_gainers(5),
            'top_losers': self.get_top_losers(5),
            'news': self.get_market_news(5),
            'update_time': datetime.now().strftime('%H:%M:%S')
        }

    def refresh_cache(self):
        """캐시 강제 갱신"""
        self._theme_cache = None
        self._sector_cache = None
        self._gainers_cache = None
        self._losers_cache = None
        self._news_cache = None
