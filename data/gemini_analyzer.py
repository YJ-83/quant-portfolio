"""
Google Gemini API 기반 주식 분석 모듈
토큰 효율화를 위해 배치 처리 및 캐싱 적용
"""
import os
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import lru_cache

# Gemini API 라이브러리
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-generativeai 패키지가 설치되지 않았습니다. pip install google-generativeai")


# ============================================================
# 캐시 설정
# ============================================================
_ANALYSIS_CACHE: Dict[str, Dict] = {}
_CACHE_DURATION = 3600  # 1시간 캐시


class GeminiAnalyzer:
    """Gemini API 기반 주식 분석기"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Gemini API 키. None이면 환경변수에서 로드
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model = None
        self.initialized = False

        if self.api_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                # gemini-1.5-flash: 빠르고 저렴 (토큰 효율적)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.initialized = True
            except Exception as e:
                print(f"Gemini 초기화 실패: {e}")

    def is_available(self) -> bool:
        """Gemini API 사용 가능 여부"""
        return self.initialized and self.model is not None

    def analyze_news_sentiment(self, news_titles: List[str], stock_name: str = "") -> Dict:
        """
        뉴스 제목들의 감성 분석 (배치 처리로 토큰 절약)

        Args:
            news_titles: 뉴스 제목 리스트
            stock_name: 종목명

        Returns:
            감성 분석 결과
        """
        if not self.is_available():
            return {'error': 'Gemini API 사용 불가', 'sentiment': 'unknown'}

        if not news_titles:
            return {'sentiment': 'neutral', 'score': 0, 'analysis': '분석할 뉴스가 없습니다'}

        # 캐시 키 생성 (제목들의 해시)
        cache_key = f"sentiment_{hash(tuple(news_titles[:10]))}"
        if cache_key in _ANALYSIS_CACHE:
            cached = _ANALYSIS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data']

        # 토큰 절약: 최대 10개 제목만, 각 제목 최대 50자
        titles_text = "\n".join([
            f"- {title[:50]}" for title in news_titles[:10]
        ])

        prompt = f"""다음은 {stock_name or '주식'} 관련 뉴스 제목들입니다.
전체적인 감성을 분석해주세요.

뉴스 제목:
{titles_text}

다음 형식으로 간단히 답변해주세요:
감성: [긍정/부정/중립]
점수: [-1.0 ~ 1.0 사이 숫자]
요약: [한 줄 요약]"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=150,  # 토큰 제한
                    temperature=0.3  # 일관성 있는 응답
                )
            )

            result_text = response.text

            # 결과 파싱
            sentiment = 'neutral'
            score = 0.0
            summary = result_text

            if '긍정' in result_text:
                sentiment = 'positive'
            elif '부정' in result_text:
                sentiment = 'negative'

            # 점수 추출 시도
            import re
            score_match = re.search(r'점수[:\s]*([+-]?\d*\.?\d+)', result_text)
            if score_match:
                try:
                    score = float(score_match.group(1))
                    score = max(-1.0, min(1.0, score))  # 범위 제한
                except:
                    pass

            # 요약 추출 시도
            summary_match = re.search(r'요약[:\s]*(.+?)(?:\n|$)', result_text)
            if summary_match:
                summary = summary_match.group(1).strip()

            result = {
                'sentiment': sentiment,
                'score': score,
                'analysis': summary,
                'raw_response': result_text,
                'news_count': len(news_titles)
            }

            # 캐시 저장
            _ANALYSIS_CACHE[cache_key] = {
                'data': result,
                'time': time.time()
            }

            return result

        except Exception as e:
            return {
                'error': str(e),
                'sentiment': 'unknown',
                'score': 0,
                'analysis': f'분석 실패: {e}'
            }

    def get_stock_recommendation(
        self,
        stock_name: str,
        current_price: float,
        price_change: float,
        technical_signals: Dict,
        news_sentiment: Dict
    ) -> Dict:
        """
        종합 매매 추천 생성

        Args:
            stock_name: 종목명
            current_price: 현재가
            price_change: 등락률 (%)
            technical_signals: 기술적 지표 신호
            news_sentiment: 뉴스 감성 분석 결과

        Returns:
            AI 추천 결과
        """
        if not self.is_available():
            return self._fallback_recommendation(technical_signals, news_sentiment)

        # 캐시 키
        cache_key = f"rec_{stock_name}_{datetime.now().strftime('%Y%m%d%H')}"
        if cache_key in _ANALYSIS_CACHE:
            cached = _ANALYSIS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data']

        # 기술적 신호 요약
        tech_summary = self._summarize_technical(technical_signals)

        prompt = f"""주식 종목 분석 요청:

종목: {stock_name}
현재가: {current_price:,.0f}원
등락률: {price_change:+.2f}%

기술적 분석:
{tech_summary}

뉴스 감성: {news_sentiment.get('sentiment', '중립')}
뉴스 요약: {news_sentiment.get('analysis', '정보 없음')[:100]}

위 정보를 종합하여 매매 추천을 해주세요.
다음 형식으로 간단히 답변:
추천: [매수/매도/관망]
신뢰도: [1-5 사이 숫자]
근거: [2줄 이내 요약]
주의사항: [한 줄]"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=200,
                    temperature=0.4
                )
            )

            result_text = response.text

            # 결과 파싱
            recommendation = '관망'
            confidence = 3
            reason = result_text

            if '매수' in result_text:
                recommendation = '매수'
            elif '매도' in result_text:
                recommendation = '매도'

            # 신뢰도 추출
            import re
            conf_match = re.search(r'신뢰도[:\s]*(\d)', result_text)
            if conf_match:
                confidence = int(conf_match.group(1))
                confidence = max(1, min(5, confidence))

            # 근거 추출
            reason_match = re.search(r'근거[:\s]*(.+?)(?:주의|$)', result_text, re.DOTALL)
            if reason_match:
                reason = reason_match.group(1).strip()[:200]

            result = {
                'recommendation': recommendation,
                'confidence': confidence,
                'reason': reason,
                'raw_response': result_text,
                'timestamp': datetime.now().isoformat()
            }

            # 캐시 저장
            _ANALYSIS_CACHE[cache_key] = {
                'data': result,
                'time': time.time()
            }

            return result

        except Exception as e:
            return self._fallback_recommendation(technical_signals, news_sentiment)

    def _summarize_technical(self, signals: Dict) -> str:
        """기술적 지표 요약"""
        lines = []

        if 'rsi' in signals:
            rsi = signals['rsi']
            status = '과매수' if rsi > 70 else ('과매도' if rsi < 30 else '중립')
            lines.append(f"RSI: {rsi:.1f} ({status})")

        if 'macd' in signals:
            macd = signals['macd']
            signal = signals.get('macd_signal', 0)
            status = '매수신호' if macd > signal else '매도신호'
            lines.append(f"MACD: {status}")

        if 'ma_trend' in signals:
            lines.append(f"이평선: {signals['ma_trend']}")

        if 'volume_trend' in signals:
            lines.append(f"거래량: {signals['volume_trend']}")

        if 'bb_position' in signals:
            lines.append(f"볼린저밴드: {signals['bb_position']}")

        return "\n".join(lines) if lines else "기술적 분석 정보 없음"

    def _fallback_recommendation(self, technical_signals: Dict, news_sentiment: Dict) -> Dict:
        """API 실패시 규칙 기반 추천"""
        score = 0

        # 기술적 신호 점수
        if technical_signals.get('rsi', 50) < 30:
            score += 1  # 과매도 = 매수 유리
        elif technical_signals.get('rsi', 50) > 70:
            score -= 1  # 과매수 = 매도 유리

        if technical_signals.get('macd', 0) > technical_signals.get('macd_signal', 0):
            score += 1
        else:
            score -= 0.5

        # 뉴스 감성 점수
        sentiment = news_sentiment.get('sentiment', 'neutral')
        if sentiment == 'positive':
            score += 0.5
        elif sentiment == 'negative':
            score -= 0.5

        if score > 0.5:
            recommendation = '매수'
        elif score < -0.5:
            recommendation = '매도'
        else:
            recommendation = '관망'

        return {
            'recommendation': recommendation,
            'confidence': 2,  # 낮은 신뢰도 (규칙 기반)
            'reason': '기술적 지표와 뉴스 감성을 종합한 규칙 기반 분석입니다.',
            'raw_response': None,
            'is_fallback': True,
            'timestamp': datetime.now().isoformat()
        }

    def analyze_market_overview(self, market_data: Dict) -> Dict:
        """
        시장 전체 개요 분석

        Args:
            market_data: 시장 데이터 (지수, 거래량 등)

        Returns:
            시장 분석 결과
        """
        if not self.is_available():
            return {
                'outlook': 'neutral',
                'analysis': '시장 분석을 위한 AI 연결이 필요합니다.',
                'sectors': []
            }

        cache_key = f"market_{datetime.now().strftime('%Y%m%d%H')}"
        if cache_key in _ANALYSIS_CACHE:
            cached = _ANALYSIS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data']

        # 간단한 시장 데이터 요약
        market_summary = f"""
KOSPI: {market_data.get('kospi', 'N/A')} ({market_data.get('kospi_change', 'N/A')})
KOSDAQ: {market_data.get('kosdaq', 'N/A')} ({market_data.get('kosdaq_change', 'N/A')})
거래대금: {market_data.get('volume', 'N/A')}
"""

        prompt = f"""오늘 한국 주식시장 현황:
{market_summary}

시장 전망을 간단히 분석해주세요:
전망: [상승/하락/보합]
분석: [2줄 요약]
주목섹터: [1-2개 섹터]"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=150,
                    temperature=0.3
                )
            )

            result_text = response.text

            outlook = 'neutral'
            if '상승' in result_text:
                outlook = 'bullish'
            elif '하락' in result_text:
                outlook = 'bearish'

            result = {
                'outlook': outlook,
                'analysis': result_text[:300],
                'timestamp': datetime.now().isoformat()
            }

            _ANALYSIS_CACHE[cache_key] = {
                'data': result,
                'time': time.time()
            }

            return result

        except Exception as e:
            return {
                'outlook': 'unknown',
                'analysis': f'분석 실패: {e}',
                'error': str(e)
            }


def clear_analysis_cache():
    """분석 캐시 초기화"""
    global _ANALYSIS_CACHE
    _ANALYSIS_CACHE = {}


# 싱글톤 인스턴스
_analyzer_instance: Optional[GeminiAnalyzer] = None


def get_analyzer(api_key: Optional[str] = None) -> GeminiAnalyzer:
    """분석기 싱글톤 인스턴스"""
    global _analyzer_instance
    if _analyzer_instance is None or api_key:
        _analyzer_instance = GeminiAnalyzer(api_key)
    return _analyzer_instance
