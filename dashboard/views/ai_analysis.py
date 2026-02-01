"""
AI 추천 및 뉴스 분석 페이지
Gemini API 기반 주식 분석 + 뉴스 감성 분석
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
import sys
import time

# 한국 시간대
KST = timezone(timedelta(hours=9))

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

# 종목 리스트
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name

# API 헬퍼
from dashboard.utils.api_helper import get_api_connection

# 뉴스 크롤러
from data.news_crawler import (
    NewsCrawler, get_crawler,
    simple_sentiment_analysis, analyze_news_batch,
    clear_news_cache
)

# Gemini 분석기
from data.gemini_analyzer import (
    GeminiAnalyzer, get_analyzer,
    clear_analysis_cache
)


def render_ai_analysis():
    """AI 추천 및 뉴스 분석 메인 렌더링"""

    # 모바일 모드 확인
    is_mobile = st.session_state.get('mobile_mode', False)

    # 헤더
    if is_mobile:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 12px; border-radius: 10px; margin-bottom: 1rem;'>
            <h3 style='color: white; margin: 0;'>🤖 AI 분석</h3>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1.5rem; border-radius: 15px; margin-bottom: 1.5rem;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);'>
            <h2 style='color: white; margin: 0; display: flex; align-items: center; gap: 0.5rem;'>
                🤖 AI 추천 및 뉴스 분석
            </h2>
            <p style='color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;'>
                Gemini AI 기반 종목 분석 · 뉴스 감성 분석 · 매매 시그널
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Gemini API 키 확인 (Streamlit Secrets 우선)
    gemini_key = None
    try:
        if 'GEMINI_API_KEY' in st.secrets:
            gemini_key = st.secrets['GEMINI_API_KEY']
    except Exception:
        pass
    if not gemini_key:
        gemini_key = os.getenv('GEMINI_API_KEY', '')

    # API 상태 표시 (키를 명시적으로 전달)
    analyzer = get_analyzer(gemini_key if gemini_key else None)
    crawler = get_crawler()

    # 디버깅: API 키 로드 상태 확인
    key_source = "없음"
    key_preview = ""
    if gemini_key:
        if 'GEMINI_API_KEY' in st.secrets if hasattr(st, 'secrets') else False:
            key_source = "Streamlit Secrets"
        else:
            key_source = "환경변수"
        key_preview = f"{gemini_key[:10]}..." if len(gemini_key) > 10 else gemini_key

    # 상태 표시 (카드 스타일)
    kst_now = datetime.now(KST)

    if is_mobile:
        cols = st.columns(3)
        with cols[0]:
            if analyzer.is_available():
                st.markdown("✅ **AI 연결**")
            else:
                st.markdown("⚠️ **API 필요**")
        with cols[1]:
            st.markdown("📰 **뉴스 준비**")
        with cols[2]:
            st.markdown(f"🕐 **{kst_now.strftime('%H:%M')}**")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            if analyzer.is_available():
                api_type = "새 API" if analyzer.use_new_api else "구 API"
                st.success(f"✅ Gemini AI 연결됨 ({api_type})")
            else:
                error_msg = getattr(analyzer, 'init_error', 'API 키 필요')
                st.warning(f"⚠️ {error_msg}")
                # 디버깅 정보 표시
                with st.expander("🔍 디버깅 정보"):
                    st.write(f"- API 키 소스: {key_source}")
                    st.write(f"- API 키 미리보기: {key_preview}")
                    st.write(f"- analyzer.initialized: {analyzer.initialized}")
                    st.write(f"- analyzer.client: {analyzer.client is not None}")
                    st.write(f"- init_error: {analyzer.init_error}")
        with col2:
            st.info("📰 뉴스 크롤링 준비됨")
        with col3:
            st.info(f"🕐 {kst_now.strftime('%H:%M')} 기준")

    # 탭 구성
    if is_mobile:
        tabs = st.tabs(["📰 뉴스", "🎯 AI추천", "📊 시장"])
    else:
        tabs = st.tabs(["📰 종목 뉴스 분석", "🎯 AI 종합 추천", "📊 시장 뉴스", "⚙️ 설정"])

    # 탭 1: 종목 뉴스 분석
    with tabs[0]:
        _render_stock_news_tab(analyzer, crawler, is_mobile)

    # 탭 2: AI 종합 추천
    with tabs[1]:
        _render_ai_recommendation_tab(analyzer, crawler, is_mobile)

    # 탭 3: 시장 뉴스
    with tabs[2]:
        _render_market_news_tab(analyzer, crawler, is_mobile)

    # 탭 4: 설정 (PC만)
    if not is_mobile and len(tabs) > 3:
        with tabs[3]:
            _render_settings_tab(analyzer)


def _render_stock_news_tab(analyzer: GeminiAnalyzer, crawler: NewsCrawler, is_mobile: bool):
    """종목별 뉴스 분석 탭"""

    # 종목 선택
    if is_mobile:
        market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="ai_news_market")
        stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
        stock_options = [f"{name} ({code})" for code, name in stocks[:100]]
        selected = st.selectbox("종목", stock_options, key="ai_news_stock")
        news_count = 10
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="ai_news_market")
        with col2:
            stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
            stock_options = [f"{name} ({code})" for code, name in stocks[:100]]
            selected = st.selectbox("종목 선택", stock_options, key="ai_news_stock")
        with col3:
            news_count = st.slider("뉴스 수", 5, 20, 10, key="ai_news_count")

    # 분석 버튼
    if st.button("🔍 뉴스 분석", key="analyze_news_btn", use_container_width=True, type="primary"):
        if selected:
            stock_code = selected.split("(")[1].replace(")", "").strip()
            stock_name = selected.split("(")[0].strip()

            with st.spinner(f"{stock_name} 뉴스 분석 중..."):
                news_list = crawler.get_stock_news(stock_code, news_count)

                if news_list:
                    batch_result = analyze_news_batch(news_list)

                    # 감성 요약 카드
                    _display_sentiment_summary(batch_result, is_mobile, stock_name)

                    # 뉴스 목록
                    st.markdown("---")

                    for i, detail in enumerate(batch_result['details'][:news_count]):
                        sentiment = detail['sentiment']
                        source = detail.get('source', '')
                        date = detail.get('date', '')
                        title = detail.get('title', '제목 없음')

                        if sentiment == 'positive':
                            color = '#00C851'
                            bg_color = '#1a3d1a'
                            emoji = '🟢'
                            badge = '긍정'
                        elif sentiment == 'negative':
                            color = '#ff4444'
                            bg_color = '#3d1a1a'
                            emoji = '🔴'
                            badge = '부정'
                        else:
                            color = '#ffbb33'
                            bg_color = '#3d3d1a'
                            emoji = '⚪'
                            badge = '중립'

                        # 검은 배경 뉴스 카드
                        st.markdown(f"""
                        <div style='background: #1a1a2e; padding: 12px 15px; border-radius: 8px;
                                    margin-bottom: 8px; border-left: 4px solid {color};
                                    display: flex; justify-content: space-between; align-items: center;'>
                            <div style='flex: 1;'>
                                <div style='color: #fff; font-size: 0.95rem; font-weight: 500;'>{emoji} {title}</div>
                                <div style='color: #888; font-size: 0.8rem; margin-top: 4px;'>📰 {source} · 📅 {date}</div>
                            </div>
                            <span style='background: {color}33; color: {color}; padding: 5px 12px;
                                         border-radius: 15px; font-size: 0.8rem; font-weight: bold;'>{badge}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    # AI 심층 분석 버튼 (항상 표시, API 없으면 메시지)
                    st.markdown("---")
                    if st.button("🤖 AI 심층 분석 요청", key="ai_deep_analysis", type="primary"):
                        if analyzer.is_available():
                            with st.spinner("Gemini AI 분석 중..."):
                                titles = [n['title'] for n in news_list]
                                ai_result = analyzer.analyze_news_sentiment(titles, stock_name)

                                if 'error' not in ai_result:
                                    st.success(f"**AI 분석 결과:** {ai_result.get('analysis', '분석 완료')}")
                                    st.info(f"감성: {ai_result.get('sentiment', 'unknown')} | 점수: {ai_result.get('score', 0):.2f}")
                                else:
                                    st.error(f"AI 분석 실패: {ai_result.get('error', '알 수 없는 오류')}")
                        else:
                            st.warning("⚠️ Gemini API 키가 설정되지 않았습니다. 설정 탭에서 API 키를 입력하세요.")
                else:
                    st.warning("해당 종목의 뉴스를 찾을 수 없습니다.")


def _render_ai_recommendation_tab(analyzer: GeminiAnalyzer, crawler: NewsCrawler, is_mobile: bool):
    """AI 종합 추천 탭"""

    if not analyzer.is_available():
        st.info("💡 Gemini API 키가 없어도 **키워드 기반 분석**은 사용 가능합니다.")

    # 종목 선택
    if is_mobile:
        market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="ai_rec_market")
        stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
        stock_options = [f"{name} ({code})" for code, name in stocks[:100]]
        selected = st.selectbox("종목", stock_options, key="ai_rec_stock")
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="ai_rec_market")
        with col2:
            stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
            stock_options = [f"{name} ({code})" for code, name in stocks[:100]]
            selected = st.selectbox("분석할 종목", stock_options, key="ai_rec_stock")

    # 분석 버튼
    if st.button("🤖 AI 분석 시작", key="start_ai_analysis", use_container_width=True, type="primary"):
        if selected:
            stock_code = selected.split("(")[1].replace(")", "").strip()
            stock_name = selected.split("(")[0].strip()

            with st.spinner(f"{stock_name} 종합 분석 중..."):
                # 1. 주가 데이터 가져오기
                current_price = 0
                price_change = 0
                technical_signals = {}

                try:
                    api = get_api_connection()
                    if api:
                        end_date = datetime.now().strftime("%Y%m%d")
                        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
                        df = api.get_daily_price(stock_code, start_date=start_date, end_date=end_date, period='D')
                        if df is not None and len(df) > 0:
                            if 'date' in df.columns:
                                df = df.sort_values('date')
                            current_price = float(df.iloc[-1]['close'])
                            prev_price = float(df.iloc[-2]['close']) if len(df) > 1 else current_price
                            price_change = ((current_price - prev_price) / prev_price) * 100
                            technical_signals = _calculate_technical_signals(df)
                except Exception as e:
                    st.caption(f"⚠️ 가격 데이터 조회 실패: {e}")

                # 2. 뉴스 감성 분석
                news_list = crawler.get_stock_news(stock_code, 10)
                if news_list:
                    news_sentiment = analyze_news_batch(news_list)
                else:
                    news_sentiment = {'overall_sentiment': 'neutral', 'positive_ratio': 0, 'negative_ratio': 0}

                # 3. AI 추천 생성
                recommendation = analyzer.get_stock_recommendation(
                    stock_name=stock_name,
                    current_price=current_price,
                    price_change=price_change,
                    technical_signals=technical_signals,
                    news_sentiment={
                        'sentiment': news_sentiment.get('overall_sentiment', 'neutral'),
                        'analysis': f"긍정 {news_sentiment.get('positive_ratio', 0):.0f}% / 부정 {news_sentiment.get('negative_ratio', 0):.0f}%"
                    }
                )

                # 결과 표시
                _display_recommendation_result(
                    stock_name, stock_code, current_price, price_change,
                    technical_signals, news_sentiment, recommendation, is_mobile
                )


def _render_market_news_tab(analyzer: GeminiAnalyzer, crawler: NewsCrawler, is_mobile: bool):
    """시장 뉴스 탭"""

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 새로고침", key="refresh_market_news"):
            clear_news_cache()
            st.rerun()

    with st.spinner("시장 뉴스 로딩..."):
        market_news = crawler.get_market_news(15)

        if market_news:
            batch_result = analyze_news_batch(market_news)
            _display_sentiment_summary(batch_result, is_mobile, "시장")

            st.markdown("---")

            for i, news in enumerate(market_news[:12]):
                sentiment_result = simple_sentiment_analysis(news['title'])
                sentiment = sentiment_result['sentiment']
                title = news.get('title', '제목 없음')
                source = news.get('source', '')
                date = news.get('date', '')

                if sentiment == 'positive':
                    color = '#00C851'
                    emoji = '🟢'
                    badge = '긍정'
                elif sentiment == 'negative':
                    color = '#ff4444'
                    emoji = '🔴'
                    badge = '부정'
                else:
                    color = '#ffbb33'
                    emoji = '⚪'
                    badge = '중립'

                # 검은 배경 뉴스 카드
                st.markdown(f"""
                <div style='background: #1a1a2e; padding: 12px 15px; border-radius: 8px;
                            margin-bottom: 8px; border-left: 4px solid {color};
                            display: flex; justify-content: space-between; align-items: center;'>
                    <div style='flex: 1;'>
                        <div style='color: #fff; font-size: 0.95rem; font-weight: 500;'>{emoji} {title}</div>
                        <div style='color: #888; font-size: 0.8rem; margin-top: 4px;'>📰 {source} · 📅 {date}</div>
                    </div>
                    <span style='background: {color}33; color: {color}; padding: 5px 12px;
                                 border-radius: 15px; font-size: 0.8rem; font-weight: bold;'>{badge}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("시장 뉴스를 불러오는 중...")


def _render_settings_tab(analyzer: GeminiAnalyzer):
    """설정 탭"""

    st.subheader("⚙️ AI 분석 설정")

    # Gemini API 키 설정
    current_key = os.getenv('GEMINI_API_KEY', '')
    masked_key = current_key[:15] + "..." if len(current_key) > 15 else "(미설정)"

    st.markdown(f"**현재 API 키:** `{masked_key}`")

    new_key = st.text_input("새 API 키 입력", type="password", placeholder="Gemini API 키", key="gemini_key_input")

    if st.button("API 키 적용", key="apply_gemini_key"):
        if new_key:
            os.environ['GEMINI_API_KEY'] = new_key
            st.session_state['gemini_api_key'] = new_key
            clear_analysis_cache()
            st.success("API 키가 적용되었습니다!")
            st.rerun()

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 뉴스 캐시 삭제"):
            clear_news_cache()
            st.success("뉴스 캐시 삭제됨")
    with col2:
        if st.button("🗑️ 분석 캐시 삭제"):
            clear_analysis_cache()
            st.success("분석 캐시 삭제됨")

    st.markdown("""
    ---
    **Gemini API 키 발급:**
    1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
    2. Google 계정 로그인
    3. "Create API Key" 클릭
    4. 발급된 키를 위 입력란에 붙여넣기
    """)


# ============================================================
# 헬퍼 함수들
# ============================================================

def _sentiment_korean(sentiment: str) -> str:
    """감성을 한글로 변환"""
    mapping = {
        'positive': '긍정',
        'negative': '부정',
        'neutral': '중립',
        'unknown': '알수없음'
    }
    return mapping.get(sentiment, sentiment)


def _display_sentiment_summary(batch_result: dict, is_mobile: bool, title: str = ""):
    """감성 분석 요약 카드 표시 - Streamlit 네이티브"""
    overall = batch_result['overall_sentiment']
    pos = batch_result.get('positive_count', 0)
    neg = batch_result.get('negative_count', 0)
    neu = batch_result.get('neutral_count', 0)
    total = batch_result.get('total_count', pos + neg + neu)

    pos_ratio = batch_result['positive_ratio']
    neg_ratio = batch_result['negative_ratio']

    if overall == 'positive':
        main_emoji = '🟢'
        main_text = '긍정적'
    elif overall == 'negative':
        main_emoji = '🔴'
        main_text = '부정적'
    else:
        main_emoji = '⚪'
        main_text = '중립적'

    # 검은 배경 카드 스타일로 가시성 개선
    st.markdown(f"""
    <div style='background: #1a1a2e; padding: 20px; border-radius: 12px; margin: 15px 0; border: 1px solid #333;'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
            <h3 style='margin: 0; color: #fff;'>{main_emoji} {title} 뉴스 감성 분석</h3>
            <span style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{main_text}</span>
        </div>
        <p style='color: #aaa; margin-bottom: 15px;'>총 {total}건 분석 완료</p>
        <div style='display: flex; gap: 15px;'>
            <div style='flex: 1; background: #0d3d0d; padding: 15px; border-radius: 10px; text-align: center;'>
                <div style='color: #00ff00; font-size: 2rem; font-weight: bold;'>{pos}</div>
                <div style='color: #00ff00;'>🟢 긍정 ({pos_ratio:.0f}%)</div>
            </div>
            <div style='flex: 1; background: #3d0d0d; padding: 15px; border-radius: 10px; text-align: center;'>
                <div style='color: #ff4444; font-size: 2rem; font-weight: bold;'>{neg}</div>
                <div style='color: #ff4444;'>🔴 부정 ({neg_ratio:.0f}%)</div>
            </div>
            <div style='flex: 1; background: #3d3d0d; padding: 15px; border-radius: 10px; text-align: center;'>
                <div style='color: #ffbb33; font-size: 2rem; font-weight: bold;'>{neu}</div>
                <div style='color: #ffbb33;'>⚪ 중립</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _calculate_technical_signals(df: pd.DataFrame) -> dict:
    """기술적 지표 신호 계산"""
    signals = {}

    try:
        close = df['close'].astype(float)

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        signals['rsi'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        signals['macd'] = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0
        signals['macd_signal'] = float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else 0

        # 이평선 추세
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()

        if not pd.isna(ma5.iloc[-1]) and not pd.isna(ma20.iloc[-1]):
            signals['ma_trend'] = '상승세 📈' if ma5.iloc[-1] > ma20.iloc[-1] else '하락세 📉'

        # RSI 상태
        rsi_val = signals.get('rsi', 50)
        if rsi_val > 70:
            signals['rsi_status'] = '과매수 ⚠️'
        elif rsi_val < 30:
            signals['rsi_status'] = '과매도 💡'
        else:
            signals['rsi_status'] = '중립'

    except Exception as e:
        print(f"기술적 지표 계산 오류: {e}")

    return signals


def _display_recommendation_result(
    stock_name: str, stock_code: str, current_price: float, price_change: float,
    technical_signals: dict, news_sentiment: dict, recommendation: dict, is_mobile: bool
):
    """AI 추천 결과 표시 - 검은 배경 스타일"""

    rec = recommendation.get('recommendation', '관망')
    confidence = recommendation.get('confidence', 3)

    if rec == '매수':
        rec_color = '#00ff00'
        rec_bg = '#0d3d0d'
        rec_emoji = '📈'
    elif rec == '매도':
        rec_color = '#ff4444'
        rec_bg = '#3d0d0d'
        rec_emoji = '📉'
    else:
        rec_color = '#ffbb33'
        rec_bg = '#3d3d0d'
        rec_emoji = '⏸️'

    stars = "⭐" * confidence + "☆" * (5 - confidence)
    price_color = '#00ff00' if price_change >= 0 else '#ff4444'

    # 메인 추천 카드 - 검은 배경
    st.markdown(f"""
    <div style='background: #1a1a2e; border: 2px solid {rec_color}; border-radius: 15px;
                padding: {"15px" if is_mobile else "20px"}; margin: 15px 0;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;'>
            <div>
                <h3 style='margin: 0; color: #fff; font-size: 1.5rem;'>{stock_name}</h3>
                <p style='margin: 8px 0; color: #fff; font-size: 1.2rem;'>
                    {current_price:,.0f}원
                    <span style='color: {price_color}; font-weight: bold;'>({price_change:+.2f}%)</span>
                </p>
            </div>
            <div style='text-align: right;'>
                <div style='font-size: {"1.8rem" if is_mobile else "2.5rem"}; color: {rec_color}; font-weight: bold;'>
                    {rec_emoji} {rec}
                </div>
                <div style='color: #fff; font-size: 1rem;'>신뢰도: {stars}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 상세 정보 - 검은 배경 카드
    st.markdown(f"""
    <div style='display: flex; gap: 15px; margin: 15px 0;'>
        <div style='flex: 1; background: #1a1a2e; padding: 15px; border-radius: 10px; border: 1px solid #333;'>
            <h4 style='color: #fff; margin: 0 0 10px 0;'>📊 기술적 분석</h4>
            <div style='color: #fff;'>• RSI: {technical_signals.get('rsi', 50):.1f} ({technical_signals.get('rsi_status', '중립')})</div>
            <div style='color: #fff;'>• 추세: {technical_signals.get('ma_trend', '정보없음')}</div>
        </div>
        <div style='flex: 1; background: #1a1a2e; padding: 15px; border-radius: 10px; border: 1px solid #333;'>
            <h4 style='color: #fff; margin: 0 0 10px 0;'>📰 뉴스 감성</h4>
            <div style='color: #fff;'>• 전체: {_sentiment_korean(news_sentiment.get('overall_sentiment', 'neutral'))}</div>
            <div style='color: #fff;'>• 긍정: {news_sentiment.get('positive_ratio', 0):.0f}% / 부정: {news_sentiment.get('negative_ratio', 0):.0f}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # AI 분석 근거 - 검은 배경
    reason = recommendation.get('reason', '')
    if reason:
        st.markdown(f"""
        <div style='background: #1a1a2e; padding: 15px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #667eea;'>
            <div style='color: #fff;'>🤖 <strong>AI 분석:</strong> {reason}</div>
        </div>
        """, unsafe_allow_html=True)

    if recommendation.get('is_fallback'):
        api_error = recommendation.get('api_error', '')
        error_info = f"<br><small style='color: #ff6b6b;'>API 오류: {api_error[:150]}</small>" if api_error else ""
        st.markdown(f"""
        <div style='background: #2d2d44; padding: 10px 15px; border-radius: 8px; margin-top: 10px;'>
            <span style='color: #aaa;'>ℹ️ 규칙 기반 분석입니다. Gemini API 연결 시 더 정확한 분석이 가능합니다.</span>
            {error_info}
        </div>
        """, unsafe_allow_html=True)
