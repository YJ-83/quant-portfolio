"""
다중 종목 상승 패턴 분석 페이지
여러 종목의 차트 패턴 + 섹터별 뉴스를 종합 분석하여 상승 요인 도출
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# 한국 시간대
KST = timezone(timedelta(hours=9))


def render_pattern_analysis():
    """다중 종목 패턴 분석 메인 렌더링"""

    is_mobile = st.session_state.get('mobile_mode', False)

    # 헤더
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1.5rem; border-radius: 15px; margin-bottom: 1rem;'>
        <h2 style='color: white; margin: 0; font-size: 1.5rem;'>
            📊 다중 종목 패턴 분석
        </h2>
        <p style='color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;'>
            여러 종목의 차트 패턴 · 섹터별 뉴스 · 상승 요인 분석
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 탭 구성
    if is_mobile:
        tabs = st.tabs(["📈 분석", "📰 뉴스", "📋 결과"])
    else:
        tabs = st.tabs(["📈 종목 분석", "📰 섹터 뉴스", "📋 종합 리포트"])

    with tabs[0]:
        _render_stock_input_tab(is_mobile)

    with tabs[1]:
        _render_sector_news_tab(is_mobile)

    with tabs[2]:
        _render_report_tab(is_mobile)


def _render_stock_input_tab(is_mobile: bool):
    """종목 입력 및 개별 분석 탭"""

    st.subheader("🎯 분석할 종목 입력")

    # 종목 입력 방식 선택
    input_method = st.radio(
        "입력 방식",
        ["직접 입력", "목록에서 선택"],
        horizontal=True,
        key="pattern_input_method"
    )

    stock_codes = []
    stock_names = []

    if input_method == "직접 입력":
        st.info("💡 종목코드 또는 종목명을 쉼표(,)로 구분하여 입력하세요")
        user_input = st.text_area(
            "종목 입력",
            placeholder="예: 삼성전자, SK하이닉스, 현대차\n또는: 005930, 000660, 005380",
            height=100,
            key="pattern_stock_input"
        )

        if user_input:
            # 입력값 파싱
            items = [item.strip() for item in user_input.replace('\n', ',').split(',')]
            items = [item for item in items if item]

            # 종목코드/종목명 구분
            from data.stock_list import get_kospi_stocks, get_kosdaq_stocks, get_stock_name
            all_stocks = get_kospi_stocks() + get_kosdaq_stocks()
            stock_dict = {code: name for code, name in all_stocks}
            name_dict = {name: code for code, name in all_stocks}

            for item in items:
                if item.isdigit() and len(item) == 6:
                    # 종목코드
                    if item in stock_dict:
                        stock_codes.append(item)
                        stock_names.append(stock_dict[item])
                else:
                    # 종목명
                    if item in name_dict:
                        stock_codes.append(name_dict[item])
                        stock_names.append(item)

            if stock_codes:
                st.success(f"✅ {len(stock_codes)}개 종목 인식: {', '.join(stock_names)}")
    else:
        # 목록에서 선택
        from data.stock_list import get_kospi_stocks, get_kosdaq_stocks

        col1, col2 = st.columns(2)
        with col1:
            market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="pattern_market")

        stocks = get_kospi_stocks() if market == "KOSPI" else get_kosdaq_stocks()
        stock_options = [f"{name} ({code})" for code, name in stocks[:200]]

        selected = st.multiselect(
            "종목 선택 (최대 10개)",
            stock_options,
            max_selections=10,
            key="pattern_stock_select"
        )

        for sel in selected:
            name = sel.split(' (')[0]
            code = sel.split('(')[1].rstrip(')')
            stock_codes.append(code)
            stock_names.append(name)

    # 세션에 저장
    st.session_state['pattern_stock_codes'] = stock_codes
    st.session_state['pattern_stock_names'] = stock_names

    # 분석 버튼
    st.markdown("---")

    if stock_codes:
        col1, col2 = st.columns([2, 1])
        with col1:
            analyze_btn = st.button(
                "🔍 패턴 분석 시작",
                type="primary",
                use_container_width=True,
                key="start_pattern_analysis"
            )
        with col2:
            clear_btn = st.button(
                "🗑️ 초기화",
                use_container_width=True,
                key="clear_pattern_analysis"
            )
            if clear_btn:
                for key in ['pattern_results', 'pattern_stock_codes', 'pattern_stock_names',
                           'sector_groups', 'sector_news_results']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        if analyze_btn:
            _run_pattern_analysis(stock_codes, stock_names, is_mobile)
    else:
        st.warning("분석할 종목을 입력해주세요.")

    # 분석 결과 표시
    if 'pattern_results' in st.session_state and st.session_state['pattern_results']:
        _display_individual_results(st.session_state['pattern_results'], is_mobile)


def _run_pattern_analysis(stock_codes: List[str], stock_names: List[str], is_mobile: bool):
    """패턴 분석 실행"""

    from data.stock_list import get_sector
    from data.news_crawler import get_crawler, analyze_news_batch

    results = []
    sector_groups = defaultdict(list)

    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(stock_codes)

    for i, (code, name) in enumerate(zip(stock_codes, stock_names)):
        status_text.text(f"분석 중: {name} ({i+1}/{total})")
        progress_bar.progress((i + 1) / total)

        try:
            result = _analyze_single_stock(code, name)
            results.append(result)

            # 섹터별 그룹핑
            sector = result.get('sector', '기타')
            sector_groups[sector].append({
                'code': code,
                'name': name,
                'result': result
            })

        except Exception as e:
            results.append({
                'code': code,
                'name': name,
                'error': str(e),
                'sector': '기타'
            })

    progress_bar.empty()
    status_text.empty()

    # 세션에 저장
    st.session_state['pattern_results'] = results
    st.session_state['sector_groups'] = dict(sector_groups)

    st.success(f"✅ {len(results)}개 종목 분석 완료!")
    st.rerun()


def _analyze_single_stock(code: str, name: str) -> Dict:
    """개별 종목 분석 - 차트전략의 모든 패턴 포함"""

    from data.stock_list import get_sector
    from dashboard.utils.indicators import (
        calculate_rsi, calculate_macd, calculate_bollinger,
        detect_double_bottom, detect_rsi_divergence, analyze_swing_patterns,
        detect_inverse_head_shoulders, detect_pullback_buy, detect_accumulation,
        analyze_volume_profile, detect_box_range, detect_box_breakout,
        detect_macd_divergence, analyze_divergence
    )

    result = {
        'code': code,
        'name': name,
        'sector': get_sector(code),
        'timestamp': datetime.now(KST).isoformat()
    }

    try:
        # 주가 데이터 가져오기
        import FinanceDataReader as fdr
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)

        df = fdr.DataReader(code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

        if df.empty or len(df) < 20:
            result['error'] = "데이터 부족"
            return result

        # 컬럼명 정규화
        df.columns = [col.lower() for col in df.columns]

        # pandas Series로 유지 (지표 함수가 Series를 기대함)
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        volume = df['volume'] if 'volume' in df.columns else pd.Series(np.zeros(len(close)), index=close.index)

        # 기본 정보 (numpy 값으로 변환)
        close_arr = close.values
        volume_arr = volume.values

        result['current_price'] = float(close_arr[-1])
        result['price_change_1d'] = float((close_arr[-1] / close_arr[-2] - 1) * 100) if len(close_arr) >= 2 else 0
        result['price_change_5d'] = float((close_arr[-1] / close_arr[-5] - 1) * 100) if len(close_arr) >= 5 else 0
        result['price_change_20d'] = float((close_arr[-1] / close_arr[-20] - 1) * 100) if len(close_arr) >= 20 else 0

        # 기술적 지표 (pandas Series 전달, Dict 반환)
        result['rsi'] = calculate_rsi(close, 14)

        macd_result = calculate_macd(close)
        result['macd'] = macd_result.get('macd', 0)
        result['macd_signal'] = macd_result.get('signal', 0)
        result['macd_hist'] = macd_result.get('histogram', 0)

        # MACD 크로스 판단
        if macd_result.get('golden_cross', False):
            result['macd_cross'] = 'golden'
        elif macd_result.get('dead_cross', False):
            result['macd_cross'] = 'dead'
        else:
            result['macd_cross'] = 'none'

        bb_result = calculate_bollinger(close)
        upper = bb_result.get('upper', 0)
        middle = bb_result.get('middle', 0)
        lower = bb_result.get('lower', 0)
        result['bb_position'] = 'upper' if close_arr[-1] > upper else ('lower' if close_arr[-1] < lower else 'middle')
        result['bb_width'] = float((upper - lower) / middle * 100) if middle > 0 else 0

        # 거래량 분석
        avg_vol_20 = np.mean(volume_arr[-20:]) if len(volume_arr) >= 20 else np.mean(volume_arr)
        result['volume_ratio'] = float(volume_arr[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0

        # 이동평균
        ma5 = np.mean(close_arr[-5:]) if len(close_arr) >= 5 else close_arr[-1]
        ma20 = np.mean(close_arr[-20:]) if len(close_arr) >= 20 else close_arr[-1]
        ma60 = np.mean(close_arr[-60:]) if len(close_arr) >= 60 else close_arr[-1]

        result['ma_trend'] = 'up' if ma5 > ma20 > ma60 else ('down' if ma5 < ma20 < ma60 else 'sideways')
        result['price_vs_ma20'] = float((close_arr[-1] / ma20 - 1) * 100) if ma20 > 0 else 0

        # ========== 패턴 분석 (차트전략 전체 패턴 포함) ==========

        # 1. 이중바닥 패턴
        try:
            double_bottom = detect_double_bottom(df)
            result['double_bottom'] = double_bottom.get('detected', False) if double_bottom else False
        except:
            result['double_bottom'] = False

        # 2. RSI 다이버전스
        try:
            rsi_div = detect_rsi_divergence(df)
            result['rsi_divergence'] = rsi_div.get('type', 'none') if rsi_div else 'none'
        except:
            result['rsi_divergence'] = 'none'

        # 3. MACD 다이버전스
        try:
            macd_div = detect_macd_divergence(df)
            result['macd_divergence'] = macd_div.get('type', 'none') if macd_div else 'none'
        except:
            result['macd_divergence'] = 'none'

        # 4. 역머리어깨 패턴 (강세 반전)
        try:
            ihs = detect_inverse_head_shoulders(df)
            result['inv_head_shoulders'] = ihs.get('detected', False) if ihs else False
            result['ihs_neckline'] = ihs.get('neckline', 0) if ihs and ihs.get('detected') else 0
        except:
            result['inv_head_shoulders'] = False
            result['ihs_neckline'] = 0

        # 5. 눌림목 매수 (이동평균 지지)
        try:
            pullback = detect_pullback_buy(df)
            result['pullback_buy'] = pullback.get('detected', False) if pullback else False
            result['support_ma'] = pullback.get('support_ma', 0) if pullback and pullback.get('detected') else 0
        except:
            result['pullback_buy'] = False
            result['support_ma'] = 0

        # 6. 세력 매집 패턴
        try:
            accum = detect_accumulation(df)
            result['accumulation'] = accum.get('detected', False) if accum else False
            result['accum_score'] = accum.get('score', 0) if accum else 0
        except:
            result['accumulation'] = False
            result['accum_score'] = 0

        # 7. 매물대 분석 (지지/저항)
        try:
            vol_profile = analyze_volume_profile(df)
            result['near_support'] = vol_profile.get('near_support', False) if vol_profile else False
            result['near_resistance'] = vol_profile.get('near_resistance', False) if vol_profile else False
            result['support_zone'] = vol_profile.get('support_zone', None) if vol_profile else None
            result['resistance_zone'] = vol_profile.get('resistance_zone', None) if vol_profile else None
        except:
            result['near_support'] = False
            result['near_resistance'] = False
            result['support_zone'] = None
            result['resistance_zone'] = None

        # 8. 박스권 분석
        try:
            box = detect_box_range(df)
            result['in_box'] = box.get('detected', False) if box else False
            result['box_upper'] = box.get('upper', 0) if box and box.get('detected') else 0
            result['box_lower'] = box.get('lower', 0) if box and box.get('detected') else 0
        except:
            result['in_box'] = False
            result['box_upper'] = 0
            result['box_lower'] = 0

        # 9. 박스권 돌파
        try:
            breakout = detect_box_breakout(df)
            result['box_breakout'] = breakout.get('breakout', 'none') if breakout else 'none'
        except:
            result['box_breakout'] = 'none'

        # 10. 피보나치 되돌림 분석
        try:
            high_arr = high.values
            low_arr = low.values
            recent_high = float(np.max(high_arr[-60:])) if len(high_arr) >= 60 else float(np.max(high_arr))
            recent_low = float(np.min(low_arr[-60:])) if len(low_arr) >= 60 else float(np.min(low_arr))
            fib_range = recent_high - recent_low

            fib_382 = recent_low + fib_range * 0.382
            fib_500 = recent_low + fib_range * 0.500
            fib_618 = recent_low + fib_range * 0.618

            current = close_arr[-1]
            # 5% 오차 범위 내 체크
            result['fib_level'] = 'none'
            if abs(current - fib_618) / current < 0.05:
                result['fib_level'] = '61.8%'
            elif abs(current - fib_500) / current < 0.05:
                result['fib_level'] = '50%'
            elif abs(current - fib_382) / current < 0.05:
                result['fib_level'] = '38.2%'

            result['fib_382'] = fib_382
            result['fib_500'] = fib_500
            result['fib_618'] = fib_618
        except:
            result['fib_level'] = 'none'
            result['fib_382'] = 0
            result['fib_500'] = 0
            result['fib_618'] = 0

        # 11. 스윙 패턴 종합 분석
        try:
            swing = analyze_swing_patterns(df)
            result['swing_signal'] = swing.get('signal', 'neutral') if swing else 'neutral'
            result['swing_score'] = swing.get('score', 0) if swing else 0
        except:
            result['swing_signal'] = 'neutral'
            result['swing_score'] = 0

        # 12. 깃발/페넌트 패턴 (간이 분석)
        try:
            # 최근 20일 고점/저점 범위
            recent_high_20 = float(np.max(high.values[-20:])) if len(high) >= 20 else float(np.max(high.values))
            recent_low_20 = float(np.min(low.values[-20:])) if len(low) >= 20 else float(np.min(low.values))
            range_20 = (recent_high_20 - recent_low_20) / recent_low_20 * 100

            # 이전 20일 대비 현재 20일 변동폭 축소 = 수렴 패턴
            if len(close_arr) >= 40:
                prev_range = (np.max(high.values[-40:-20]) - np.min(low.values[-40:-20])) / np.min(low.values[-40:-20]) * 100
                if range_20 < prev_range * 0.6:  # 변동폭 40% 이상 축소
                    result['flag_pennant'] = 'pennant'
                elif range_20 < prev_range * 0.8:
                    result['flag_pennant'] = 'flag'
                else:
                    result['flag_pennant'] = 'none'
            else:
                result['flag_pennant'] = 'none'
        except:
            result['flag_pennant'] = 'none'

        # 13. 방향성 변화 (ATR 기반)
        try:
            # ATR 계산
            tr_list = []
            for i in range(1, min(14, len(df))):
                h = high.values[-i]
                l = low.values[-i]
                pc = close_arr[-i-1] if i+1 <= len(close_arr) else close_arr[-i]
                tr = max(h - l, abs(h - pc), abs(l - pc))
                tr_list.append(tr)
            atr = np.mean(tr_list) if tr_list else 0

            # 최근 5일 가격 변화
            if len(close_arr) >= 5:
                price_change_5d_abs = abs(close_arr[-1] - close_arr[-5])
                if atr > 0 and price_change_5d_abs > atr * 2:
                    result['directional_change'] = 'up' if close_arr[-1] > close_arr[-5] else 'down'
                else:
                    result['directional_change'] = 'none'
            else:
                result['directional_change'] = 'none'
            result['atr'] = atr
        except:
            result['directional_change'] = 'none'
            result['atr'] = 0

        # ========== 종합 점수 ==========
        score = 0
        reasons = []

        # RSI 점수
        if result['rsi'] < 30:
            score += 2
            reasons.append("RSI 과매도")
        elif result['rsi'] > 70:
            score -= 2
            reasons.append("RSI 과매수")

        # MACD 점수
        if result['macd_cross'] == 'golden':
            score += 2
            reasons.append("MACD 골든크로스")
        elif result['macd_cross'] == 'dead':
            score -= 2
            reasons.append("MACD 데드크로스")
        elif result['macd_hist'] > 0:
            score += 1
            reasons.append("MACD 양수")

        # 볼린저밴드 점수
        if result['bb_position'] == 'lower':
            score += 1
            reasons.append("볼린저밴드 하단")
        elif result['bb_position'] == 'upper':
            score -= 1
            reasons.append("볼린저밴드 상단")

        # 이동평균 추세
        if result['ma_trend'] == 'up':
            score += 1
            reasons.append("상승 추세")
        elif result['ma_trend'] == 'down':
            score -= 1
            reasons.append("하락 추세")

        # 거래량
        if result['volume_ratio'] > 2:
            score += 1 if result['price_change_1d'] > 0 else -1
            reasons.append(f"거래량 급증 ({result['volume_ratio']:.1f}x)")

        # ===== 기본 패턴 =====
        if result['double_bottom']:
            score += 2
            reasons.append("🔄 이중바닥")

        if result['rsi_divergence'] == 'bullish':
            score += 2
            reasons.append("📈 RSI 상승 다이버전스")
        elif result['rsi_divergence'] == 'bearish':
            score -= 2
            reasons.append("📉 RSI 하락 다이버전스")

        # ===== 차트전략 패턴 추가 =====

        # MACD 다이버전스
        if result.get('macd_divergence') == 'bullish':
            score += 2
            reasons.append("📈 MACD 상승 다이버전스")
        elif result.get('macd_divergence') == 'bearish':
            score -= 2
            reasons.append("📉 MACD 하락 다이버전스")

        # 역머리어깨 (강세 반전)
        if result.get('inv_head_shoulders'):
            score += 3
            reasons.append("👤 역머리어깨 패턴")

        # 눌림목 매수
        if result.get('pullback_buy'):
            score += 2
            ma = result.get('support_ma', 0)
            reasons.append(f"📉 눌림목 매수 ({ma}일선 지지)")

        # 세력 매집
        if result.get('accumulation'):
            score += 2
            reasons.append("🏦 세력 매집 감지")

        # 지지/저항
        if result.get('near_support'):
            score += 1
            reasons.append("🟢 지지선 근접")
        if result.get('near_resistance'):
            score -= 1
            reasons.append("🔴 저항선 근접")

        # 박스권 돌파
        if result.get('box_breakout') == 'up':
            score += 2
            reasons.append("🚀 박스 상단 돌파")
        elif result.get('box_breakout') == 'down':
            score -= 2
            reasons.append("💥 박스 하단 이탈")
        elif result.get('in_box'):
            reasons.append("📦 박스권 횡보")

        # 피보나치 되돌림
        fib = result.get('fib_level', 'none')
        if fib != 'none':
            if fib == '61.8%':
                score += 2
                reasons.append("📐 피보나치 61.8% 지지")
            elif fib == '50%':
                score += 1
                reasons.append("📐 피보나치 50% 지지")
            elif fib == '38.2%':
                score += 1
                reasons.append("📐 피보나치 38.2% 지지")

        # 깃발/페넌트
        fp = result.get('flag_pennant', 'none')
        if fp == 'pennant':
            score += 1
            reasons.append("🔺 페넌트 수렴")
        elif fp == 'flag':
            score += 1
            reasons.append("🚩 깃발 패턴")

        # 방향성 변화
        dc = result.get('directional_change', 'none')
        if dc == 'up':
            score += 2
            reasons.append("⚡ 강한 상승 방향 전환")
        elif dc == 'down':
            score -= 2
            reasons.append("⚡ 강한 하락 방향 전환")

        # 스윙 점수 반영
        swing_score = result.get('swing_score', 0)
        if swing_score >= 3:
            score += 1
            reasons.append(f"🔄 스윙 강세 ({swing_score}점)")
        elif swing_score <= -3:
            score -= 1
            reasons.append(f"🔄 스윙 약세 ({swing_score}점)")

        result['score'] = score
        result['reasons'] = reasons
        result['signal'] = 'buy' if score >= 3 else ('sell' if score <= -3 else 'hold')

        # 차트 데이터 저장 (추세선 그리기용)
        result['chart_data'] = {
            'dates': df.index.tolist(),
            'close': close_arr.tolist(),
            'high': high.values.tolist(),
            'low': low.values.tolist(),
            'open': df['open'].values.tolist() if 'open' in df.columns else close_arr.tolist(),
            'volume': volume_arr.tolist(),
            'ma5': ma5,
            'ma20': ma20,
            'ma60': ma60
        }

    except Exception as e:
        result['error'] = str(e)

    return result


def _display_individual_results(results: List[Dict], is_mobile: bool):
    """개별 분석 결과 표시"""

    valid_results = [r for r in results if 'error' not in r]

    if len(valid_results) < 2:
        st.markdown("---")
        st.subheader("📊 개별 종목 분석 결과")
        for result in valid_results:
            _display_stock_card(result, is_mobile)
        return

    # ========== 차트 비교 분석 섹션 ==========
    st.markdown("---")
    st.subheader("📈 종목 간 차트 비교 분석")

    _display_chart_comparison(valid_results, is_mobile)

    # ========== 공통 패턴 분석 섹션 ==========
    st.markdown("---")
    st.subheader("🔍 공통 패턴 분석")

    _display_common_patterns(valid_results, is_mobile)

    # ========== 개별 종목 결과 ==========
    st.markdown("---")
    st.subheader("📊 개별 종목 분석 결과")

    # 정렬 옵션
    sort_by = st.selectbox(
        "정렬 기준",
        ["점수 높은순", "점수 낮은순", "수익률 높은순", "수익률 낮은순"],
        key="pattern_sort"
    )

    # 정렬
    if sort_by == "점수 높은순":
        valid_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    elif sort_by == "점수 낮은순":
        valid_results.sort(key=lambda x: x.get('score', 0))
    elif sort_by == "수익률 높은순":
        valid_results.sort(key=lambda x: x.get('price_change_5d', 0), reverse=True)
    else:
        valid_results.sort(key=lambda x: x.get('price_change_5d', 0))

    # 결과 표시
    for result in valid_results:
        _display_stock_card(result, is_mobile)

    # 에러 종목
    error_results = [r for r in results if 'error' in r]
    if error_results:
        with st.expander(f"⚠️ 분석 실패 종목 ({len(error_results)}개)"):
            for r in error_results:
                st.write(f"- {r['name']} ({r['code']}): {r.get('error', '알 수 없는 오류')}")


def _display_stock_card(result: Dict, is_mobile: bool):
    """개별 종목 카드 표시 (추세선 차트 포함)"""
    import plotly.graph_objects as go
    from scipy import stats

    score = result.get('score', 0)
    signal = result.get('signal', 'hold')

    if signal == 'buy':
        border_color = '#00ff00'
        signal_text = '📈 매수 신호'
        signal_bg = '#0d3d0d'
    elif signal == 'sell':
        border_color = '#ff4444'
        signal_text = '📉 매도 신호'
        signal_bg = '#3d0d0d'
    else:
        border_color = '#ffbb33'
        signal_text = '⏸️ 관망'
        signal_bg = '#3d3d0d'

    price_change = result.get('price_change_5d', 0)
    price_color = '#00ff00' if price_change >= 0 else '#ff4444'

    reasons_html = "<br>".join([f"• {r}" for r in result.get('reasons', [])[:5]])

    st.markdown(f"""
    <div style='background: #1a1a2e; border: 2px solid {border_color}; border-radius: 12px;
                padding: 15px; margin: 10px 0;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;'>
            <div>
                <h4 style='margin: 0; color: #fff;'>{result['name']} <span style='color: #888; font-size: 0.9rem;'>({result['code']})</span></h4>
                <p style='color: #aaa; margin: 5px 0; font-size: 0.85rem;'>섹터: {result.get('sector', '기타')}</p>
            </div>
            <div style='text-align: right;'>
                <div style='background: {signal_bg}; color: {border_color}; padding: 8px 15px;
                            border-radius: 20px; font-weight: bold;'>{signal_text}</div>
                <p style='color: #fff; margin: 5px 0;'>점수: <strong>{score:+d}</strong></p>
            </div>
        </div>
        <div style='display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap;'>
            <div>
                <span style='color: #888;'>현재가</span><br>
                <span style='color: #fff; font-size: 1.1rem; font-weight: bold;'>{result.get('current_price', 0):,.0f}원</span>
            </div>
            <div>
                <span style='color: #888;'>5일 수익률</span><br>
                <span style='color: {price_color}; font-size: 1.1rem; font-weight: bold;'>{price_change:+.2f}%</span>
            </div>
            <div>
                <span style='color: #888;'>RSI</span><br>
                <span style='color: #fff; font-size: 1.1rem;'>{result.get('rsi', 50):.1f}</span>
            </div>
            <div>
                <span style='color: #888;'>거래량</span><br>
                <span style='color: #fff; font-size: 1.1rem;'>{result.get('volume_ratio', 1):.1f}x</span>
            </div>
        </div>
        <div style='margin-top: 10px; padding-top: 10px; border-top: 1px solid #333;'>
            <span style='color: #888; font-size: 0.85rem;'>분석 근거:</span>
            <p style='color: #aaa; font-size: 0.85rem; margin: 5px 0;'>{reasons_html}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ========== 추세선 차트 추가 ==========
    chart_data = result.get('chart_data', None)
    if chart_data:
        with st.expander(f"📈 {result['name']} 차트 (추세선)", expanded=False):
            _draw_trendline_chart(result, chart_data, is_mobile)


def _draw_trendline_chart(result: Dict, chart_data: Dict, is_mobile: bool):
    """추세선이 포함된 캔들 차트 그리기"""
    import plotly.graph_objects as go
    from scipy import stats

    dates = chart_data['dates']
    closes = chart_data['close']
    highs = chart_data['high']
    lows = chart_data['low']
    opens = chart_data['open']

    # 최근 60일 데이터만 사용
    display_days = min(60, len(dates))
    dates = dates[-display_days:]
    closes = closes[-display_days:]
    highs = highs[-display_days:]
    lows = lows[-display_days:]
    opens = opens[-display_days:]

    fig = go.Figure()

    # 1. 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=dates,
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        name='가격',
        increasing_line_color='#ff4444',  # 상승 - 빨강 (한국식)
        decreasing_line_color='#0066ff',  # 하락 - 파랑 (한국식)
        increasing_fillcolor='#ff4444',
        decreasing_fillcolor='#0066ff'
    ))

    # 2. 이동평균선
    ma20 = chart_data.get('ma20', 0)
    ma60 = chart_data.get('ma60', 0)

    # MA20 라인 (전체 기간 계산)
    ma20_values = []
    for i in range(len(closes)):
        if i >= 19:
            ma20_values.append(np.mean(closes[max(0, i-19):i+1]))
        else:
            ma20_values.append(None)

    fig.add_trace(go.Scatter(
        x=dates,
        y=ma20_values,
        mode='lines',
        name='MA20',
        line=dict(color='#ffbb33', width=1.5, dash='dot')
    ))

    # 3. 상승 추세선 계산 (저점 연결)
    try:
        lows_arr = np.array(lows)
        x_indices = np.arange(len(lows_arr))

        # 저점 찾기 (로컬 최소값)
        swing_lows = []
        for i in range(2, len(lows_arr) - 2):
            if lows_arr[i] <= lows_arr[i-1] and lows_arr[i] <= lows_arr[i-2] and \
               lows_arr[i] <= lows_arr[i+1] and lows_arr[i] <= lows_arr[i+2]:
                swing_lows.append((i, lows_arr[i]))

        # 최소 2개 저점이 있으면 상승 추세선 그리기
        if len(swing_lows) >= 2:
            # 최근 저점들 사용
            recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
            low_x = [p[0] for p in recent_lows]
            low_y = [p[1] for p in recent_lows]

            # 선형 회귀로 추세선 계산
            slope, intercept, _, _, _ = stats.linregress(low_x, low_y)

            # 상승 추세선만 표시 (기울기 > 0)
            if slope > 0:
                trendline_y = [slope * i + intercept for i in range(len(dates))]
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=trendline_y,
                    mode='lines',
                    name='상승 추세선 (지지)',
                    line=dict(color='#00ff00', width=2, dash='solid')
                ))
    except:
        pass

    # 4. 하락 추세선 계산 (고점 연결)
    try:
        highs_arr = np.array(highs)

        # 고점 찾기 (로컬 최대값)
        swing_highs = []
        for i in range(2, len(highs_arr) - 2):
            if highs_arr[i] >= highs_arr[i-1] and highs_arr[i] >= highs_arr[i-2] and \
               highs_arr[i] >= highs_arr[i+1] and highs_arr[i] >= highs_arr[i+2]:
                swing_highs.append((i, highs_arr[i]))

        # 최소 2개 고점이 있으면 하락 추세선 그리기
        if len(swing_highs) >= 2:
            recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
            high_x = [p[0] for p in recent_highs]
            high_y = [p[1] for p in recent_highs]

            slope, intercept, _, _, _ = stats.linregress(high_x, high_y)

            # 하락 추세선만 표시 (기울기 < 0)
            if slope < 0:
                trendline_y = [slope * i + intercept for i in range(len(dates))]
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=trendline_y,
                    mode='lines',
                    name='하락 추세선 (저항)',
                    line=dict(color='#ff4444', width=2, dash='solid')
                ))
    except:
        pass

    # 5. 지지/저항 수평선 (매물대)
    support_zone = result.get('support_zone')
    resistance_zone = result.get('resistance_zone')

    if support_zone:
        fig.add_hline(
            y=support_zone[0],
            line_dash="dash",
            line_color="#00ff00",
            annotation_text=f"지지 {support_zone[0]:,.0f}",
            annotation_position="left"
        )

    if resistance_zone:
        fig.add_hline(
            y=resistance_zone[0],
            line_dash="dash",
            line_color="#ff4444",
            annotation_text=f"저항 {resistance_zone[0]:,.0f}",
            annotation_position="left"
        )

    # 6. 레이아웃 설정
    fig.update_layout(
        title=f"{result['name']} - 추세선 분석",
        plot_bgcolor='#1a1a2e',
        paper_bgcolor='#1a1a2e',
        font=dict(color='white'),
        height=400 if not is_mobile else 300,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(
            gridcolor='#333',
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            gridcolor='#333',
            title='가격 (원)'
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    # 추세선 해석 텍스트
    interpretation = []

    # 현재가 vs 추세선 위치
    current_price = result.get('current_price', 0)
    ma20_val = chart_data.get('ma20', 0)

    if current_price > ma20_val:
        interpretation.append("✅ 현재가가 20일선 위 (상승 추세)")
    else:
        interpretation.append("⚠️ 현재가가 20일선 아래 (주의)")

    if result.get('near_support'):
        interpretation.append("🟢 지지선 근접 - 반등 가능성")
    if result.get('near_resistance'):
        interpretation.append("🔴 저항선 근접 - 돌파 여부 확인")

    if interpretation:
        st.markdown(f"<p style='color: #aaa; font-size: 0.85rem;'>{'  |  '.join(interpretation)}</p>", unsafe_allow_html=True)


def _render_sector_news_tab(is_mobile: bool):
    """섹터별 뉴스 분석 탭"""

    st.subheader("📰 섹터별 뉴스 분석")

    sector_groups = st.session_state.get('sector_groups', {})

    if not sector_groups:
        st.info("먼저 '종목 분석' 탭에서 종목을 분석해주세요.")
        return

    # 섹터별 뉴스 수집 버튼
    if st.button("📰 섹터 뉴스 수집", type="primary", key="fetch_sector_news"):
        _fetch_sector_news(sector_groups, is_mobile)

    # 뉴스 결과 표시
    if 'sector_news_results' in st.session_state:
        _display_sector_news(st.session_state['sector_news_results'], is_mobile)


def _fetch_sector_news(sector_groups: Dict, is_mobile: bool):
    """섹터별 뉴스 수집"""

    from data.news_crawler import get_crawler, analyze_news_batch

    crawler = get_crawler()
    sector_news = {}

    progress = st.progress(0)
    status = st.empty()

    sectors = list(sector_groups.keys())
    total = len(sectors)

    for i, sector in enumerate(sectors):
        status.text(f"뉴스 수집 중: {sector} ({i+1}/{total})")
        progress.progress((i + 1) / total)

        # 해당 섹터 종목들의 뉴스 수집
        all_news = []
        for stock_info in sector_groups[sector][:3]:  # 섹터당 최대 3종목
            code = stock_info['code']
            news_list = crawler.get_stock_news(code, 5)
            for news in news_list:
                news['stock_name'] = stock_info['name']
            all_news.extend(news_list)

        if all_news:
            # 감성 분석
            sentiment_result = analyze_news_batch(all_news)
            sector_news[sector] = {
                'news_list': all_news[:10],
                'sentiment': sentiment_result,
                'stocks': [s['name'] for s in sector_groups[sector]]
            }

    progress.empty()
    status.empty()

    st.session_state['sector_news_results'] = sector_news
    st.success("✅ 섹터 뉴스 수집 완료!")
    st.rerun()


def _display_sector_news(sector_news: Dict, is_mobile: bool):
    """섹터별 뉴스 표시"""

    for sector, data in sector_news.items():
        sentiment = data['sentiment']
        overall = sentiment.get('overall_sentiment', 'neutral')

        if overall == 'positive':
            emoji = '🟢'
            color = '#00ff00'
        elif overall == 'negative':
            emoji = '🔴'
            color = '#ff4444'
        else:
            emoji = '⚪'
            color = '#ffbb33'

        with st.expander(f"{emoji} {sector} - {', '.join(data['stocks'][:3])}", expanded=False):
            # 감성 요약
            st.markdown(f"""
            <div style='background: #1a1a2e; padding: 15px; border-radius: 10px; margin-bottom: 10px;'>
                <div style='display: flex; gap: 20px;'>
                    <div><span style='color: #00ff00;'>긍정:</span> {sentiment.get('positive_ratio', 0):.0f}%</div>
                    <div><span style='color: #ff4444;'>부정:</span> {sentiment.get('negative_ratio', 0):.0f}%</div>
                    <div><span style='color: #ffbb33;'>중립:</span> {sentiment.get('neutral_ratio', 0):.0f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 뉴스 목록
            for news in data['news_list'][:5]:
                detail = next((d for d in sentiment.get('details', []) if d['title'] == news['title']), {})
                news_sentiment = detail.get('sentiment', 'neutral')

                if news_sentiment == 'positive':
                    news_color = '#00ff00'
                    news_emoji = '🟢'
                elif news_sentiment == 'negative':
                    news_color = '#ff4444'
                    news_emoji = '🔴'
                else:
                    news_color = '#ffbb33'
                    news_emoji = '⚪'

                st.markdown(f"""
                <div style='background: #252540; padding: 10px; border-radius: 8px; margin: 5px 0;
                            border-left: 3px solid {news_color};'>
                    <div style='color: #fff; font-size: 0.9rem;'>{news_emoji} {news['title']}</div>
                    <div style='color: #888; font-size: 0.75rem; margin-top: 5px;'>
                        {news.get('stock_name', '')} · {news.get('source', '')} · {news.get('date', '')}
                    </div>
                </div>
                """, unsafe_allow_html=True)


def _render_report_tab(is_mobile: bool):
    """종합 리포트 탭"""

    st.subheader("📋 종합 패턴 리포트")

    results = st.session_state.get('pattern_results', [])
    sector_groups = st.session_state.get('sector_groups', {})
    sector_news = st.session_state.get('sector_news_results', {})

    if not results:
        st.info("먼저 '종목 분석' 탭에서 종목을 분석해주세요.")
        return

    valid_results = [r for r in results if 'error' not in r]

    if not valid_results:
        st.warning("분석된 종목이 없습니다.")
        return

    # 1. 전체 요약
    st.markdown("### 📊 전체 요약")

    buy_signals = [r for r in valid_results if r.get('signal') == 'buy']
    sell_signals = [r for r in valid_results if r.get('signal') == 'sell']
    hold_signals = [r for r in valid_results if r.get('signal') == 'hold']

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("분석 종목", f"{len(valid_results)}개")
    with col2:
        st.metric("매수 신호", f"{len(buy_signals)}개", delta=None)
    with col3:
        st.metric("매도 신호", f"{len(sell_signals)}개", delta=None)
    with col4:
        st.metric("관망", f"{len(hold_signals)}개", delta=None)

    # 2. 공통 패턴 분석
    st.markdown("---")
    st.markdown("### 🔍 공통 패턴 분석")

    # 패턴 통계
    all_reasons = []
    for r in valid_results:
        all_reasons.extend(r.get('reasons', []))

    if all_reasons:
        from collections import Counter
        reason_counts = Counter(all_reasons)
        common_patterns = reason_counts.most_common(10)

        st.markdown("**자주 나타난 패턴:**")
        for pattern, count in common_patterns:
            pct = count / len(valid_results) * 100
            st.markdown(f"- {pattern}: **{count}개** ({pct:.0f}%)")

    # 3. 섹터별 분석
    if sector_groups:
        st.markdown("---")
        st.markdown("### 🏭 섹터별 분석")

        for sector, stocks in sector_groups.items():
            sector_results = [s['result'] for s in stocks if 'error' not in s['result']]
            if not sector_results:
                continue

            avg_score = np.mean([r.get('score', 0) for r in sector_results])
            avg_change = np.mean([r.get('price_change_5d', 0) for r in sector_results])

            # 섹터 뉴스 감성
            news_sentiment = "정보 없음"
            if sector in sector_news:
                sentiment = sector_news[sector]['sentiment']
                overall = sentiment.get('overall_sentiment', 'neutral')
                if overall == 'positive':
                    news_sentiment = "🟢 긍정적"
                elif overall == 'negative':
                    news_sentiment = "🔴 부정적"
                else:
                    news_sentiment = "⚪ 중립"

            score_color = '#00ff00' if avg_score > 0 else ('#ff4444' if avg_score < 0 else '#ffbb33')
            change_color = '#00ff00' if avg_change > 0 else '#ff4444'

            st.markdown(f"""
            <div style='background: #1a1a2e; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                <h4 style='color: #fff; margin: 0 0 10px 0;'>{sector} ({len(sector_results)}개 종목)</h4>
                <div style='display: flex; gap: 30px; flex-wrap: wrap;'>
                    <div>
                        <span style='color: #888;'>평균 점수</span><br>
                        <span style='color: {score_color}; font-size: 1.2rem; font-weight: bold;'>{avg_score:+.1f}</span>
                    </div>
                    <div>
                        <span style='color: #888;'>평균 5일 수익률</span><br>
                        <span style='color: {change_color}; font-size: 1.2rem; font-weight: bold;'>{avg_change:+.2f}%</span>
                    </div>
                    <div>
                        <span style='color: #888;'>뉴스 감성</span><br>
                        <span style='font-size: 1.2rem;'>{news_sentiment}</span>
                    </div>
                </div>
                <p style='color: #aaa; margin: 10px 0 0 0; font-size: 0.85rem;'>
                    종목: {', '.join([s['name'] for s in stocks])}
                </p>
            </div>
            """, unsafe_allow_html=True)

    # 4. 상승 예상 종목
    st.markdown("---")
    st.markdown("### 🚀 상승 기대 종목 TOP 5")

    top_stocks = sorted(valid_results, key=lambda x: x.get('score', 0), reverse=True)[:5]

    for i, stock in enumerate(top_stocks, 1):
        score = stock.get('score', 0)
        reasons = stock.get('reasons', [])[:3]

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e, #2d2d44); padding: 15px;
                    border-radius: 10px; margin: 10px 0; border-left: 4px solid #667eea;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <span style='color: #667eea; font-size: 1.5rem; font-weight: bold;'>#{i}</span>
                    <span style='color: #fff; font-size: 1.2rem; margin-left: 10px;'>{stock['name']}</span>
                    <span style='color: #888;'>({stock['code']})</span>
                </div>
                <div style='text-align: right;'>
                    <span style='color: #00ff00; font-size: 1.3rem; font-weight: bold;'>점수: {score:+d}</span>
                </div>
            </div>
            <p style='color: #aaa; margin: 10px 0 0 0; font-size: 0.85rem;'>
                {' | '.join(reasons)}
            </p>
        </div>
        """, unsafe_allow_html=True)


def _display_chart_comparison(results: List[Dict], is_mobile: bool):
    """종목 간 차트 비교 분석 표시"""

    import plotly.graph_objects as go

    # 비교 테이블 데이터 준비 (Streamlit DataFrame용)
    comparison_data = []
    for r in results:
        change_1d = r.get('price_change_1d', 0)
        change_5d = r.get('price_change_5d', 0)
        change_20d = r.get('price_change_20d', 0)
        rsi = r.get('rsi', 50)
        score = r.get('score', 0)
        trend = r.get('ma_trend', 'sideways')

        # 추세 텍스트 변환
        trend_text = '📈상승' if trend == 'up' else ('📉하락' if trend == 'down' else '➡️횡보')
        # MACD 신호
        macd_text = '🔼' if r.get('macd_hist', 0) > 0 else '🔽'
        # RSI 상태
        rsi_status = '🔴' if rsi > 70 else ('🟢' if rsi < 30 else '⚪')

        # 패턴 정보 수집
        patterns = []
        if r.get('double_bottom'):
            patterns.append('이중바닥')
        if r.get('inv_head_shoulders'):
            patterns.append('역머리어깨')
        if r.get('pullback_buy'):
            patterns.append(f"눌림목({r.get('support_ma', 0)})")
        if r.get('accumulation'):
            patterns.append('매집')
        if r.get('box_breakout') == 'up':
            patterns.append('박스돌파')
        if r.get('fib_level', 'none') != 'none':
            patterns.append(f"피보{r.get('fib_level')}")
        if r.get('flag_pennant') == 'pennant':
            patterns.append('페넌트')
        elif r.get('flag_pennant') == 'flag':
            patterns.append('깃발')
        if r.get('directional_change') == 'up':
            patterns.append('방향전환↑')
        elif r.get('directional_change') == 'down':
            patterns.append('방향전환↓')

        # 다이버전스
        if r.get('rsi_divergence') == 'bullish':
            patterns.append('RSI다이버+')
        elif r.get('rsi_divergence') == 'bearish':
            patterns.append('RSI다이버-')
        if r.get('macd_divergence') == 'bullish':
            patterns.append('MACD다이버+')
        elif r.get('macd_divergence') == 'bearish':
            patterns.append('MACD다이버-')

        # 지지/저항
        if r.get('near_support'):
            patterns.append('지지선')
        if r.get('near_resistance'):
            patterns.append('저항선')

        pattern_text = ', '.join(patterns[:3]) if patterns else '-'

        comparison_data.append({
            '종목': r['name'],
            '현재가': f"{r.get('current_price', 0):,.0f}",
            '5일%': f"{change_5d:+.2f}",
            'RSI': f"{rsi_status}{rsi:.1f}",
            'MACD': macd_text,
            '추세': trend_text,
            '패턴': pattern_text,
            '점수': f"{score:+d}"
        })

    # 비교 테이블 표시 (Streamlit DataFrame)
    st.markdown("#### 📋 지표 비교표")

    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(
        df_comparison,
        use_container_width=True,
        hide_index=True,
        column_config={
            '종목': st.column_config.TextColumn('종목', width='medium'),
            '현재가': st.column_config.TextColumn('현재가', width='small'),
            '5일%': st.column_config.TextColumn('5일', width='small'),
            'RSI': st.column_config.TextColumn('RSI', width='small'),
            'MACD': st.column_config.TextColumn('MACD', width='small'),
            '추세': st.column_config.TextColumn('추세', width='small'),
            '패턴': st.column_config.TextColumn('패턴', width='large'),
            '점수': st.column_config.TextColumn('점수', width='small'),
        }
    )

    # 수익률 비교 차트
    st.markdown("#### 📊 수익률 비교 차트")

    fig = go.Figure()

    names = [r['name'] for r in results]
    changes_1d = [r.get('price_change_1d', 0) for r in results]
    changes_5d = [r.get('price_change_5d', 0) for r in results]
    changes_20d = [r.get('price_change_20d', 0) for r in results]

    fig.add_trace(go.Bar(
        name='1일',
        x=names,
        y=changes_1d,
        marker_color=['#00C851' if v >= 0 else '#ff4444' for v in changes_1d],
        text=[f'{v:+.1f}%' for v in changes_1d],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        name='5일',
        x=names,
        y=changes_5d,
        marker_color=['#00E676' if v >= 0 else '#ff6666' for v in changes_5d],
        text=[f'{v:+.1f}%' for v in changes_5d],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        name='20일',
        x=names,
        y=changes_20d,
        marker_color=['#69F0AE' if v >= 0 else '#ff8888' for v in changes_20d],
        text=[f'{v:+.1f}%' for v in changes_20d],
        textposition='outside'
    ))

    fig.update_layout(
        barmode='group',
        plot_bgcolor='#1a1a2e',
        paper_bgcolor='#1a1a2e',
        font=dict(color='white'),
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(title='수익률 (%)', gridcolor='#333', zerolinecolor='#666'),
        xaxis=dict(title='')
    )

    st.plotly_chart(fig, use_container_width=True)

    # RSI 비교 차트
    st.markdown("#### 📉 RSI 비교")

    fig_rsi = go.Figure()

    rsi_values = [r.get('rsi', 50) for r in results]
    colors = ['#ff4444' if v > 70 else ('#00ff00' if v < 30 else '#ffbb33') for v in rsi_values]

    fig_rsi.add_trace(go.Bar(
        x=names,
        y=rsi_values,
        marker_color=colors,
        text=[f'{v:.1f}' for v in rsi_values],
        textposition='outside'
    ))

    # 과매수/과매도 라인
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ff4444", annotation_text="과매수 (70)")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="#00ff00", annotation_text="과매도 (30)")

    fig_rsi.update_layout(
        plot_bgcolor='#1a1a2e',
        paper_bgcolor='#1a1a2e',
        font=dict(color='white'),
        height=300,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(title='RSI', range=[0, 100], gridcolor='#333'),
        xaxis=dict(title='')
    )

    st.plotly_chart(fig_rsi, use_container_width=True)


def _display_common_patterns(results: List[Dict], is_mobile: bool):
    """공통 패턴 분석 표시"""

    from collections import Counter

    # 모든 패턴 수집
    all_reasons = []
    for r in results:
        all_reasons.extend(r.get('reasons', []))

    if not all_reasons:
        st.info("분석된 패턴이 없습니다.")
        return

    # 패턴 빈도 계산
    reason_counts = Counter(all_reasons)
    total_stocks = len(results)

    # 공통 패턴 (50% 이상 종목에서 발견)
    common_patterns = [(p, c) for p, c in reason_counts.most_common() if c >= total_stocks * 0.5]

    if common_patterns:
        st.markdown("**✅ 공통 패턴 (50% 이상 종목)**")

        for pattern, count in common_patterns:
            pct = count / total_stocks * 100
            # 패턴 종류에 따라 색상
            if any(kw in pattern for kw in ['상승', '골든', '과매도', '양수', '이중바닥']):
                color = '#00ff00'
                emoji = '📈'
            elif any(kw in pattern for kw in ['하락', '데드', '과매수', '음수']):
                color = '#ff4444'
                emoji = '📉'
            else:
                color = '#ffbb33'
                emoji = '📊'

            st.markdown(f"""
            <div style='background: #1a1a2e; padding: 12px 15px; border-radius: 8px;
                        margin: 8px 0; border-left: 4px solid {color};
                        display: flex; justify-content: space-between; align-items: center;'>
                <span style='color: #fff;'>{emoji} {pattern}</span>
                <span style='background: {color}33; color: {color}; padding: 5px 12px;
                             border-radius: 15px; font-weight: bold;'>{count}/{total_stocks} ({pct:.0f}%)</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("50% 이상 종목에서 공통으로 발견된 패턴이 없습니다.")

    # 전체 패턴 빈도
    st.markdown("---")
    st.markdown("**📊 전체 패턴 빈도**")

    for pattern, count in reason_counts.most_common(10):
        pct = count / total_stocks * 100
        bar_width = pct

        # 색상 결정
        if any(kw in pattern for kw in ['상승', '골든', '과매도', '양수', '이중바닥']):
            bar_color = '#00ff00'
        elif any(kw in pattern for kw in ['하락', '데드', '과매수', '음수']):
            bar_color = '#ff4444'
        else:
            bar_color = '#ffbb33'

        st.markdown(f"""
        <div style='margin: 8px 0;'>
            <div style='display: flex; justify-content: space-between; margin-bottom: 4px;'>
                <span style='color: #fff; font-size: 0.9rem;'>{pattern}</span>
                <span style='color: #888; font-size: 0.85rem;'>{count}개 ({pct:.0f}%)</span>
            </div>
            <div style='background: #333; border-radius: 4px; height: 8px; overflow: hidden;'>
                <div style='background: {bar_color}; width: {bar_width}%; height: 100%;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 종합 분석 요약
    st.markdown("---")
    st.markdown("**🎯 종합 분석 요약**")

    # 긍정적/부정적 신호 개수
    positive_signals = sum(1 for p in all_reasons if any(kw in p for kw in ['상승', '골든', '과매도', '양수', '이중바닥', '다이버전스']))
    negative_signals = sum(1 for p in all_reasons if any(kw in p for kw in ['하락', '데드', '과매수', '음수']))
    neutral_signals = len(all_reasons) - positive_signals - negative_signals

    total_signals = len(all_reasons)
    pos_pct = positive_signals / total_signals * 100 if total_signals > 0 else 0
    neg_pct = negative_signals / total_signals * 100 if total_signals > 0 else 0

    # 종합 판단
    if pos_pct > neg_pct + 20:
        overall = "🟢 긍정적"
        overall_color = "#00ff00"
        overall_msg = "전반적으로 상승 신호가 우세합니다."
    elif neg_pct > pos_pct + 20:
        overall = "🔴 부정적"
        overall_color = "#ff4444"
        overall_msg = "전반적으로 하락 신호가 우세합니다."
    else:
        overall = "⚪ 중립"
        overall_color = "#ffbb33"
        overall_msg = "상승/하락 신호가 혼재되어 있습니다."

    st.markdown(f"""
    <div style='background: #1a1a2e; padding: 20px; border-radius: 12px; margin: 10px 0;
                border: 2px solid {overall_color};'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
            <h4 style='margin: 0; color: #fff;'>종합 판단</h4>
            <span style='color: {overall_color}; font-size: 1.3rem; font-weight: bold;'>{overall}</span>
        </div>
        <p style='color: #aaa; margin: 0 0 15px 0;'>{overall_msg}</p>
        <div style='display: flex; gap: 20px;'>
            <div style='flex: 1; background: #0d3d0d; padding: 10px; border-radius: 8px; text-align: center;'>
                <div style='color: #00ff00; font-size: 1.5rem; font-weight: bold;'>{positive_signals}</div>
                <div style='color: #00ff00; font-size: 0.85rem;'>긍정 신호 ({pos_pct:.0f}%)</div>
            </div>
            <div style='flex: 1; background: #3d0d0d; padding: 10px; border-radius: 8px; text-align: center;'>
                <div style='color: #ff4444; font-size: 1.5rem; font-weight: bold;'>{negative_signals}</div>
                <div style='color: #ff4444; font-size: 0.85rem;'>부정 신호 ({neg_pct:.0f}%)</div>
            </div>
            <div style='flex: 1; background: #3d3d0d; padding: 10px; border-radius: 8px; text-align: center;'>
                <div style='color: #ffbb33; font-size: 1.5rem; font-weight: bold;'>{neutral_signals}</div>
                <div style='color: #ffbb33; font-size: 0.85rem;'>중립 신호</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
