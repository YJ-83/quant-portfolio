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
        st.markdown("### 🤖 AI 분석")
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

    # Gemini API 키 확인
    gemini_key = os.getenv('GEMINI_API_KEY', '')

    # API 상태 표시
    analyzer = get_analyzer(gemini_key if gemini_key else None)
    crawler = get_crawler()

    if is_mobile:
        if analyzer.is_available():
            st.success("✅ Gemini AI 연결됨", icon="🤖")
        else:
            st.warning("⚠️ Gemini API 키 필요")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            if analyzer.is_available():
                st.success("✅ Gemini AI 연결됨")
            else:
                st.warning("⚠️ Gemini API 키 설정 필요")
        with col2:
            st.info("📰 뉴스 크롤링 준비됨")
        with col3:
            kst_now = datetime.now(KST)
            st.info(f"🕐 {kst_now.strftime('%H:%M')} 기준")

    # 탭 구성
    if is_mobile:
        tabs = st.tabs(["📰 뉴스", "🎯 종목분석", "📊 시장"])
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

    st.subheader("📰 종목별 뉴스 감성 분석")

    # 종목 선택
    if is_mobile:
        col1, col2 = st.columns([1, 2])
    else:
        col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        market = st.selectbox(
            "시장",
            ["KOSPI", "KOSDAQ"],
            key="ai_news_market"
        )

    with col2:
        stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
        stock_options = [f"{name} ({code})" for code, name in stocks[:100]]

        selected = st.selectbox(
            "종목 선택",
            stock_options,
            key="ai_news_stock"
        )

    if not is_mobile:
        with col3:
            news_count = st.slider("뉴스 수", 5, 20, 10, key="ai_news_count")
    else:
        news_count = 10

    # 분석 버튼
    if st.button("🔍 뉴스 분석", key="analyze_news_btn", use_container_width=True):
        if selected:
            # 종목코드 추출
            stock_code = selected.split("(")[1].replace(")", "").strip()
            stock_name = selected.split("(")[0].strip()

            with st.spinner(f"{stock_name} 뉴스 분석 중..."):
                # 뉴스 크롤링
                news_list = crawler.get_stock_news(stock_code, news_count)

                if news_list:
                    # 감성 분석
                    st.markdown(f"#### 📋 {stock_name} 최신 뉴스 ({len(news_list)}건)")

                    # 키워드 기반 분석 (토큰 절약)
                    batch_result = analyze_news_batch(news_list)

                    # 감성 요약 표시
                    _display_sentiment_summary(batch_result, is_mobile)

                    # 개별 뉴스 목록
                    st.markdown("---")
                    st.markdown("##### 📰 뉴스 상세")

                    for i, detail in enumerate(batch_result['details'][:news_count]):
                        sentiment = detail['sentiment']
                        emoji = "🟢" if sentiment == 'positive' else ("🔴" if sentiment == 'negative' else "⚪")

                        with st.expander(f"{emoji} {detail['title'][:50]}...", expanded=(i < 3)):
                            st.caption(f"📅 {detail.get('date', '')}")
                            st.write(f"감성: **{_sentiment_korean(sentiment)}**")
                            if detail['keywords']:
                                kw_text = ", ".join([k[0] for k in detail['keywords'][:3]])
                                st.caption(f"🏷️ 키워드: {kw_text}")

                    # AI 심층 분석 (Gemini 사용 가능시)
                    if analyzer.is_available():
                        st.markdown("---")
                        if st.button("🤖 AI 심층 분석 요청", key="ai_deep_analysis"):
                            with st.spinner("Gemini AI 분석 중..."):
                                titles = [n['title'] for n in news_list]
                                ai_result = analyzer.analyze_news_sentiment(titles, stock_name)

                                if 'error' not in ai_result:
                                    st.success("AI 분석 완료")
                                    st.markdown(f"""
                                    **AI 감성 분석 결과:**
                                    - 감성: {_sentiment_korean(ai_result['sentiment'])}
                                    - 점수: {ai_result['score']:.2f}
                                    - 요약: {ai_result['analysis']}
                                    """)
                                else:
                                    st.error(f"AI 분석 실패: {ai_result['error']}")
                else:
                    st.warning("해당 종목의 뉴스를 찾을 수 없습니다.")


def _render_ai_recommendation_tab(analyzer: GeminiAnalyzer, crawler: NewsCrawler, is_mobile: bool):
    """AI 종합 추천 탭"""

    st.subheader("🎯 AI 종합 매매 추천")

    if not analyzer.is_available():
        st.warning("""
        ⚠️ Gemini API 키가 설정되지 않았습니다.

        설정 방법:
        1. [Google AI Studio](https://makersuite.google.com/app/apikey)에서 API 키 발급
        2. `.env` 파일에 `GEMINI_API_KEY=your_key` 추가
        3. 또는 설정 탭에서 직접 입력
        """)

        st.info("💡 API 없이도 **키워드 기반 분석**은 사용 가능합니다.")

    # 종목 선택
    col1, col2 = st.columns([1, 2])

    with col1:
        market = st.selectbox(
            "시장",
            ["KOSPI", "KOSDAQ"],
            key="ai_rec_market"
        )

    with col2:
        stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
        stock_options = [f"{name} ({code})" for code, name in stocks[:100]]

        selected = st.selectbox(
            "분석할 종목",
            stock_options,
            key="ai_rec_stock"
        )

    # 분석 버튼
    if st.button("🤖 AI 분석 시작", key="start_ai_analysis", use_container_width=True, type="primary"):
        if selected:
            stock_code = selected.split("(")[1].replace(")", "").strip()
            stock_name = selected.split("(")[0].strip()

            with st.spinner(f"{stock_name} 종합 분석 중..."):
                # 1. 주가 데이터 가져오기
                try:
                    api = get_api_connection()
                    if api:
                        # 일봉 데이터 (get_daily_price 사용)
                        end_date = datetime.now().strftime("%Y%m%d")
                        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
                        df = api.get_daily_price(stock_code, start_date=start_date, end_date=end_date, period='D')
                        if df is not None and len(df) > 0:
                            # 최신 데이터가 맨 앞에 있을 수 있으므로 정렬
                            if 'date' in df.columns:
                                df = df.sort_values('date')
                            current_price = float(df.iloc[-1]['close'])
                            prev_price = float(df.iloc[-2]['close']) if len(df) > 1 else current_price
                            price_change = ((current_price - prev_price) / prev_price) * 100

                            # 기술적 지표 계산
                            technical_signals = _calculate_technical_signals(df)
                        else:
                            current_price = 0
                            price_change = 0
                            technical_signals = {}
                    else:
                        current_price = 0
                        price_change = 0
                        technical_signals = {}
                except Exception as e:
                    st.warning(f"가격 데이터 조회 실패: {e}")
                    current_price = 0
                    price_change = 0
                    technical_signals = {}

                # 2. 뉴스 감성 분석
                news_list = crawler.get_stock_news(stock_code, 10)
                if news_list:
                    news_sentiment = analyze_news_batch(news_list)
                else:
                    news_sentiment = {'overall_sentiment': 'neutral', 'analysis': '뉴스 없음'}

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

    st.subheader("📊 실시간 시장 뉴스")

    if st.button("🔄 새로고침", key="refresh_market_news"):
        clear_news_cache()

    with st.spinner("시장 뉴스 로딩..."):
        market_news = crawler.get_market_news(15)

        if market_news:
            # 감성 분석
            batch_result = analyze_news_batch(market_news)

            # 요약 표시
            _display_sentiment_summary(batch_result, is_mobile)

            st.markdown("---")

            # 뉴스 목록
            for i, news in enumerate(market_news[:15]):
                sentiment_result = simple_sentiment_analysis(news['title'])
                sentiment = sentiment_result['sentiment']
                emoji = "🟢" if sentiment == 'positive' else ("🔴" if sentiment == 'negative' else "⚪")

                if is_mobile:
                    st.markdown(f"{emoji} **{news['title'][:40]}...**")
                    st.caption(f"{news.get('date', '')} | {news.get('source', '')}")
                else:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"{emoji} {news['title']}")
                    with col2:
                        st.caption(news.get('date', ''))

                if i < 14:
                    st.markdown("---")
        else:
            st.info("시장 뉴스를 불러오는 중...")

    # 섹터별 뉴스 (PC만)
    if not is_mobile:
        st.markdown("---")
        st.subheader("🏭 섹터별 뉴스")

        sectors = ["반도체", "자동차", "바이오", "2차전지", "AI"]
        selected_sector = st.selectbox("섹터 선택", sectors, key="sector_news_select")

        if st.button("섹터 뉴스 검색", key="search_sector_news"):
            with st.spinner(f"{selected_sector} 관련 뉴스 검색 중..."):
                sector_news = crawler.get_sector_news(selected_sector, 10)

                if sector_news:
                    for news in sector_news:
                        sentiment = simple_sentiment_analysis(news['title'])['sentiment']
                        emoji = "🟢" if sentiment == 'positive' else ("🔴" if sentiment == 'negative' else "⚪")
                        st.markdown(f"{emoji} {news['title']}")
                else:
                    st.info("관련 뉴스가 없습니다.")


def _render_settings_tab(analyzer: GeminiAnalyzer):
    """설정 탭"""

    st.subheader("⚙️ AI 분석 설정")

    # Gemini API 키 설정
    st.markdown("#### 🔑 Gemini API 키")

    current_key = os.getenv('GEMINI_API_KEY', '')
    masked_key = current_key[:10] + "..." if len(current_key) > 10 else "(미설정)"

    st.info(f"현재 키: {masked_key}")

    new_key = st.text_input(
        "새 API 키 입력",
        type="password",
        placeholder="Gemini API 키를 입력하세요",
        key="gemini_api_key_input"
    )

    if st.button("API 키 적용", key="apply_gemini_key"):
        if new_key:
            os.environ['GEMINI_API_KEY'] = new_key
            st.session_state['gemini_api_key'] = new_key
            clear_analysis_cache()
            st.success("API 키가 적용되었습니다. 페이지를 새로고침하세요.")
            st.rerun()
        else:
            st.warning("API 키를 입력해주세요.")

    st.markdown("---")

    # 캐시 관리
    st.markdown("#### 🗑️ 캐시 관리")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("뉴스 캐시 삭제", key="clear_news_cache"):
            clear_news_cache()
            st.success("뉴스 캐시가 삭제되었습니다.")

    with col2:
        if st.button("분석 캐시 삭제", key="clear_analysis_cache"):
            clear_analysis_cache()
            st.success("분석 캐시가 삭제되었습니다.")

    st.markdown("---")

    # API 키 발급 안내
    st.markdown("""
    #### 📚 Gemini API 키 발급 방법

    1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
    2. Google 계정으로 로그인
    3. "Create API Key" 클릭
    4. 생성된 API 키 복사
    5. 위 입력란에 붙여넣기

    **참고:**
    - Gemini 1.5 Flash 모델 사용 (빠르고 저렴)
    - 무료 티어: 분당 15회, 일일 1,500회 요청 가능
    - 분석 결과는 1시간 캐싱됨 (토큰 절약)
    """)


# ============================================================
# 헬퍼 함수들
# ============================================================

def _sentiment_korean(sentiment: str) -> str:
    """감성을 한글로 변환"""
    mapping = {
        'positive': '긍정 🟢',
        'negative': '부정 🔴',
        'neutral': '중립 ⚪',
        'unknown': '알수없음 ❓'
    }
    return mapping.get(sentiment, sentiment)


def _display_sentiment_summary(batch_result: dict, is_mobile: bool):
    """감성 분석 요약 표시"""
    overall = batch_result['overall_sentiment']
    pos_ratio = batch_result['positive_ratio']
    neg_ratio = batch_result['negative_ratio']
    neu_ratio = batch_result['neutral_ratio']

    if is_mobile:
        st.markdown(f"""
        **감성 요약:** {_sentiment_korean(overall)}

        🟢 긍정 {pos_ratio:.0f}% | 🔴 부정 {neg_ratio:.0f}% | ⚪ 중립 {neu_ratio:.0f}%
        """)
    else:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("전체 감성", _sentiment_korean(overall))

        with col2:
            st.metric("🟢 긍정", f"{pos_ratio:.0f}%")

        with col3:
            st.metric("🔴 부정", f"{neg_ratio:.0f}%")

        with col4:
            st.metric("⚪ 중립", f"{neu_ratio:.0f}%")


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
        ma60 = close.rolling(60).mean() if len(close) >= 60 else ma20

        if not pd.isna(ma5.iloc[-1]) and not pd.isna(ma20.iloc[-1]):
            if ma5.iloc[-1] > ma20.iloc[-1]:
                signals['ma_trend'] = '단기 상승세'
            else:
                signals['ma_trend'] = '단기 하락세'

        # 볼린저밴드 위치
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std

        current = close.iloc[-1]
        if not pd.isna(bb_upper.iloc[-1]):
            if current > bb_upper.iloc[-1]:
                signals['bb_position'] = '상단 돌파 (과매수)'
            elif current < bb_lower.iloc[-1]:
                signals['bb_position'] = '하단 돌파 (과매도)'
            else:
                signals['bb_position'] = '밴드 내'

        # 거래량 추세
        if 'volume' in df.columns:
            vol = df['volume'].astype(float)
            vol_ma = vol.rolling(20).mean()
            if not pd.isna(vol_ma.iloc[-1]):
                if vol.iloc[-1] > vol_ma.iloc[-1] * 1.5:
                    signals['volume_trend'] = '거래량 급증'
                elif vol.iloc[-1] < vol_ma.iloc[-1] * 0.5:
                    signals['volume_trend'] = '거래량 감소'
                else:
                    signals['volume_trend'] = '평균 수준'

    except Exception as e:
        print(f"기술적 지표 계산 오류: {e}")

    return signals


def _display_recommendation_result(
    stock_name: str, stock_code: str, current_price: float, price_change: float,
    technical_signals: dict, news_sentiment: dict, recommendation: dict, is_mobile: bool
):
    """AI 추천 결과 표시"""

    # 추천 색상
    rec = recommendation.get('recommendation', '관망')
    if rec == '매수':
        rec_color = '#00C851'
        rec_bg = 'rgba(0, 200, 81, 0.1)'
    elif rec == '매도':
        rec_color = '#ff4444'
        rec_bg = 'rgba(255, 68, 68, 0.1)'
    else:
        rec_color = '#ffbb33'
        rec_bg = 'rgba(255, 187, 51, 0.1)'

    confidence = recommendation.get('confidence', 3)
    stars = "⭐" * confidence + "☆" * (5 - confidence)

    if is_mobile:
        st.markdown(f"""
        ### {stock_name} ({stock_code})

        **현재가:** {current_price:,.0f}원 ({price_change:+.2f}%)

        ---

        **🤖 AI 추천: {rec}**

        신뢰도: {stars}

        {recommendation.get('reason', '')}
        """)
    else:
        st.markdown(f"""
        <div style='background: {rec_bg}; border: 2px solid {rec_color}; border-radius: 15px; padding: 1.5rem; margin: 1rem 0;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='margin: 0; color: white;'>{stock_name} ({stock_code})</h3>
                    <p style='color: rgba(255,255,255,0.7); margin: 0.5rem 0;'>
                        현재가: <strong>{current_price:,.0f}원</strong>
                        (<span style='color: {"#00C851" if price_change > 0 else "#ff4444"}'>{price_change:+.2f}%</span>)
                    </p>
                </div>
                <div style='text-align: right;'>
                    <span style='font-size: 2rem; color: {rec_color}; font-weight: bold;'>{rec}</span>
                    <p style='margin: 0; color: rgba(255,255,255,0.7);'>신뢰도: {stars}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 상세 분석
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📊 기술적 분석")
            for key, value in technical_signals.items():
                if key not in ['macd', 'macd_signal']:
                    st.write(f"• **{key}:** {value}")

        with col2:
            st.markdown("#### 📰 뉴스 감성")
            st.write(f"• 전체: {_sentiment_korean(news_sentiment.get('overall_sentiment', 'neutral'))}")
            st.write(f"• 긍정: {news_sentiment.get('positive_ratio', 0):.0f}%")
            st.write(f"• 부정: {news_sentiment.get('negative_ratio', 0):.0f}%")

        # AI 분석 근거
        st.markdown("---")
        st.markdown("#### 🤖 AI 분석 근거")
        st.info(recommendation.get('reason', '분석 정보 없음'))

        if recommendation.get('is_fallback'):
            st.caption("ℹ️ 이 분석은 규칙 기반입니다. Gemini API 연결 시 더 정확한 분석이 가능합니다.")
