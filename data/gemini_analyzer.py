"""
Google Gemini API 기반 주식 분석 모듈
새로운 google-genai 패키지 사용
토큰 효율화를 위해 배치 처리 및 캐싱 적용
"""
import os
import time
import re
from typing import Dict, List, Optional
from datetime import datetime

# Gemini API 라이브러리 (새 버전)
GEMINI_AVAILABLE = False
GEMINI_NEW_API = False
genai_client = None

try:
    from google import genai
    GEMINI_AVAILABLE = True
    GEMINI_NEW_API = True
    print("[Gemini] google-genai 패키지 로드 성공 (새 API)")
except ImportError:
    try:
        # 구버전 fallback
        import google.generativeai as genai_old
        GEMINI_AVAILABLE = True
        GEMINI_NEW_API = False
        print("[Gemini] google.generativeai 패키지 로드 성공 (구 API)")
    except ImportError:
        print("[Gemini] Warning: Gemini 패키지가 설치되지 않았습니다.")


# ============================================================
# 캐시 설정
# ============================================================
_ANALYSIS_CACHE: Dict[str, Dict] = {}
_CACHE_DURATION = 3600  # 1시간 캐시


def _get_api_key_from_secrets() -> Optional[str]:
    """Streamlit Secrets 또는 환경변수에서 API 키 로드"""
    # 1. Streamlit Secrets 시도 (Streamlit Cloud)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GEMINI_API_KEY' in st.secrets:
            print("[Gemini] Streamlit Secrets에서 API 키 로드")
            return st.secrets['GEMINI_API_KEY']
    except Exception:
        pass

    # 2. 환경변수 시도
    key = os.getenv('GEMINI_API_KEY')
    if key:
        print("[Gemini] 환경변수에서 API 키 로드")
        return key

    print("[Gemini] API 키를 찾을 수 없음")
    return None


class GeminiAnalyzer:
    """Gemini API 기반 주식 분석기"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Gemini API 키. None이면 Secrets/환경변수에서 로드
        """
        self.api_key = api_key or _get_api_key_from_secrets()
        self.client = None
        self.initialized = False
        self.use_new_api = False

        self.init_error = None
        self.last_error = None  # 마지막 API 호출 오류

        if self.api_key and GEMINI_AVAILABLE:
            if GEMINI_NEW_API:
                try:
                    # 새 API 시도
                    from google import genai
                    self.client = genai.Client(api_key=self.api_key)
                    self.use_new_api = True
                    self.initialized = True
                    print(f"[Gemini] 새 API 초기화 성공 (키: {self.api_key[:10]}...)")
                except Exception as e1:
                    self.init_error = str(e1)
                    print(f"[Gemini] 새 API 초기화 실패: {e1}")
            else:
                try:
                    # 구 API
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=self.api_key)
                    self.client = genai_old.GenerativeModel('gemini-1.5-flash')
                    self.use_new_api = False
                    self.initialized = True
                    print(f"[Gemini] 구 API 초기화 성공 (키: {self.api_key[:10]}...)")
                except Exception as e2:
                    self.init_error = str(e2)
                    print(f"[Gemini] 구 API 초기화 실패: {e2}")
        else:
            if not self.api_key:
                self.init_error = "API 키 없음"
            elif not GEMINI_AVAILABLE:
                self.init_error = "Gemini 패키지 없음"

    def is_available(self) -> bool:
        """Gemini API 사용 가능 여부"""
        return self.initialized and self.client is not None

    def _generate_content(self, prompt: str, max_tokens: int = 150) -> Optional[str]:
        """통합 컨텐츠 생성 - 여러 모델 시도"""
        # 디버깅: 함수 호출 마커 설정
        self.last_error = "API_CALL_STARTED"
        print("[Gemini] _generate_content 진입")

        if not self.is_available():
            self.last_error = "API 사용 불가"
            return None

        # 시도할 모델 목록 (새 google-genai API는 models/ 접두사 필요)
        # gemini-2.0-flash-lite: 가장 가벼운 2.0 모델
        # gemini-1.5-flash: 안정적인 flash 버전
        models_to_try = [
            'models/gemini-2.0-flash-lite',  # 가장 가벼운 2.0 모델
            'models/gemini-1.5-flash',       # 안정적인 flash
            'models/gemini-1.5-flash-8b',    # 더 가벼운 flash
            'models/gemini-2.0-flash',       # 최신 (쿼타 제한적)
        ]
        errors = []

        if self.use_new_api:
            # 새 API - 여러 모델 순차 시도
            for model_name in models_to_try:
                try:
                    print(f"[Gemini] {model_name} 시도 중...")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            'max_output_tokens': max_tokens,
                            'temperature': 0.3
                        }
                    )
                    print(f"[Gemini] {model_name} 성공!")
                    self.last_error = None
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    errors.append(f"{model_name}: {error_str[:100]}")
                    if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                        print(f"[Gemini] {model_name} 쿼타 초과, 2초 대기 후 다음 모델 시도...")
                        time.sleep(2)  # Rate limit 대기
                        continue  # 다음 모델 시도
                    elif '404' in error_str or 'NOT_FOUND' in error_str:
                        print(f"[Gemini] {model_name} 모델 없음, 다음 모델 시도...")
                        continue
                    else:
                        print(f"[Gemini] {model_name} 오류: {e}")
                        continue  # 다른 에러도 다음 모델 시도
            # 모든 모델 실패
            self.last_error = " | ".join(errors)
            print(f"[Gemini] 모든 모델 실패: {self.last_error}")
            return None
        else:
            # 구 API
            try:
                response = self.client.generate_content(
                    prompt,
                    generation_config={
                        'max_output_tokens': max_tokens,
                        'temperature': 0.3
                    }
                )
                return response.text
            except Exception as e:
                print(f"[Gemini] 구 API 오류: {e}")
                return None

    def analyze_news_sentiment(self, news_titles: List[str], stock_name: str = "") -> Dict:
        """
        뉴스 제목들의 감성 분석 (배치 처리로 토큰 절약)
        """
        if not self.is_available():
            return {'error': 'Gemini API 사용 불가', 'sentiment': 'unknown'}

        if not news_titles:
            return {'sentiment': 'neutral', 'score': 0, 'analysis': '분석할 뉴스가 없습니다'}

        # 캐시 키
        cache_key = f"sentiment_{hash(tuple(news_titles[:10]))}"
        if cache_key in _ANALYSIS_CACHE:
            cached = _ANALYSIS_CACHE[cache_key]
            if time.time() - cached['time'] < _CACHE_DURATION:
                return cached['data']

        # 프롬프트 (토큰 절약)
        titles_text = "\n".join([f"- {title[:50]}" for title in news_titles[:10]])

        prompt = f"""다음 {stock_name or '주식'} 뉴스 제목들의 감성을 분석하세요.

{titles_text}

답변 형식:
감성: [긍정/부정/중립]
점수: [-1.0~1.0]
요약: [한 줄]"""

        result_text = self._generate_content(prompt, 100)

        if not result_text:
            return self._fallback_sentiment(news_titles)

        # 파싱
        sentiment = 'neutral'
        score = 0.0
        summary = result_text

        if '긍정' in result_text:
            sentiment = 'positive'
        elif '부정' in result_text:
            sentiment = 'negative'

        score_match = re.search(r'점수[:\s]*([+-]?\d*\.?\d+)', result_text)
        if score_match:
            try:
                score = float(score_match.group(1))
                score = max(-1.0, min(1.0, score))
            except:
                pass

        summary_match = re.search(r'요약[:\s]*(.+?)(?:\n|$)', result_text)
        if summary_match:
            summary = summary_match.group(1).strip()

        result = {
            'sentiment': sentiment,
            'score': score,
            'analysis': summary,
            'news_count': len(news_titles)
        }

        _ANALYSIS_CACHE[cache_key] = {'data': result, 'time': time.time()}
        return result

    def _fallback_sentiment(self, news_titles: List[str]) -> Dict:
        """키워드 기반 fallback 감성 분석"""
        from data.news_crawler import analyze_news_batch
        news_list = [{'title': t} for t in news_titles]
        batch = analyze_news_batch(news_list)
        return {
            'sentiment': batch['overall_sentiment'],
            'score': (batch['positive_ratio'] - batch['negative_ratio']) / 100,
            'analysis': f"키워드 분석: 긍정 {batch['positive_ratio']:.0f}%, 부정 {batch['negative_ratio']:.0f}%",
            'is_fallback': True
        }

    def get_stock_recommendation(
        self,
        stock_name: str,
        current_price: float,
        price_change: float,
        technical_signals: Dict,
        news_sentiment: Dict
    ) -> Dict:
        """종합 매매 추천 생성"""
        # 디버깅: 함수 진입 마커
        self.last_error = "ENTERED_GET_RECOMMENDATION"
        print(f"[Gemini] get_stock_recommendation 진입 - is_available: {self.is_available()}")

        # 캐시 완전 비활성화 - 매번 API 호출 강제 (디버깅용)
        # 캐시 키 생성만 하고, 저장/조회는 하지 않음
        cache_key = f"rec_{stock_name}_{datetime.now().strftime('%Y%m%d%H')}"
        # 기존 캐시 삭제 (fallback 결과가 남아있을 수 있음)
        if cache_key in _ANALYSIS_CACHE:
            del _ANALYSIS_CACHE[cache_key]

        if not self.is_available():
            self.last_error = "NOT_AVAILABLE_IN_RECOMMENDATION"
            return self._fallback_recommendation(technical_signals, news_sentiment)

        # 기술적 신호 요약
        tech_summary = self._summarize_technical(technical_signals)

        prompt = f"""주식 분석:
종목: {stock_name}
현재가: {current_price:,.0f}원 ({price_change:+.2f}%)
기술분석: {tech_summary}
뉴스감성: {news_sentiment.get('sentiment', '중립')}

답변 형식:
추천: [매수/매도/관망]
신뢰도: [1-5]
근거: [한 줄]"""

        print(f"[Gemini] get_stock_recommendation 호출 - {stock_name}")

        try:
            result_text = self._generate_content(prompt, 100)
            print(f"[Gemini] _generate_content 결과: {result_text[:50] if result_text else 'None'}")
        except Exception as gen_error:
            self.last_error = f"generate_content 예외: {str(gen_error)[:200]}"
            print(f"[Gemini] _generate_content 예외 발생: {gen_error}")
            return self._fallback_recommendation(technical_signals, news_sentiment)

        if not result_text:
            print(f"[Gemini] fallback으로 전환, last_error: {self.last_error}")
            return self._fallback_recommendation(technical_signals, news_sentiment)

        # 파싱
        recommendation = '관망'
        confidence = 3

        if '매수' in result_text:
            recommendation = '매수'
        elif '매도' in result_text:
            recommendation = '매도'

        conf_match = re.search(r'신뢰도[:\s]*(\d)', result_text)
        if conf_match:
            confidence = int(conf_match.group(1))
            confidence = max(1, min(5, confidence))

        reason_match = re.search(r'근거[:\s]*(.+?)(?:\n|$)', result_text, re.DOTALL)
        reason = reason_match.group(1).strip()[:150] if reason_match else result_text[:150]

        result = {
            'recommendation': recommendation,
            'confidence': confidence,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }

        # 캐시 저장 비활성화 (디버깅용)
        # _ANALYSIS_CACHE[cache_key] = {'data': result, 'time': time.time()}
        return result

    def _summarize_technical(self, signals: Dict) -> str:
        """기술적 지표 요약"""
        parts = []
        if 'rsi' in signals:
            rsi = signals['rsi']
            status = '과매수' if rsi > 70 else ('과매도' if rsi < 30 else '중립')
            parts.append(f"RSI {rsi:.0f}({status})")
        if 'ma_trend' in signals:
            parts.append(signals['ma_trend'].replace(' 📈', '').replace(' 📉', ''))
        return ", ".join(parts) if parts else "정보없음"

    def _fallback_recommendation(self, technical_signals: Dict, news_sentiment: Dict) -> Dict:
        """규칙 기반 추천"""
        score = 0
        api_error = getattr(self, 'last_error', None)

        # RSI
        rsi = technical_signals.get('rsi', 50)
        if rsi < 30:
            score += 1
        elif rsi > 70:
            score -= 1

        # MACD
        if technical_signals.get('macd', 0) > technical_signals.get('macd_signal', 0):
            score += 0.5
        else:
            score -= 0.5

        # 뉴스
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

        reason = '기술적 지표와 뉴스 감성을 종합한 규칙 기반 분석입니다.'
        if api_error:
            reason += f' (API 오류: {api_error[:100]})'

        return {
            'recommendation': recommendation,
            'confidence': 2,
            'reason': reason,
            'is_fallback': True,
            'api_error': api_error,
            'timestamp': datetime.now().isoformat()
        }


def clear_analysis_cache():
    """분석 캐시 초기화"""
    global _ANALYSIS_CACHE
    _ANALYSIS_CACHE = {}


# 싱글톤
_analyzer_instance: Optional[GeminiAnalyzer] = None


def get_analyzer(api_key: Optional[str] = None) -> GeminiAnalyzer:
    """분석기 싱글톤"""
    global _analyzer_instance
    if _analyzer_instance is None or api_key:
        _analyzer_instance = GeminiAnalyzer(api_key)
    return _analyzer_instance
