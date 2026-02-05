"""
차트 매매 전략 로직 모듈
- strategy.py에서 분리된 차트매매전략 관련 함수
- chart_strategy.py에서 탭으로 import하여 사용
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import os
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from strategies.chart_strategies import (
    CHART_STRATEGIES, get_chart_strategy, scan_all_strategies,
    GoldenCrossStrategy, VolumeBreakoutStrategy, AccumulationStrategy,
    MABounceStrategy, BoxBreakoutStrategy, TripleMAStrategy, ChartSignal
)
from data.stock_list import get_kospi_stocks, get_kosdaq_stocks

# 스윙 포인트 감지 함수 import
from dashboard.utils.chart_utils import detect_swing_points


def _render_chart_strategy_section(api):
    """차트 매매 전략 섹션 렌더링"""

    st.markdown("""
    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 2rem; border-radius: 20px; margin: 2rem 0;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>📊</div>
        <h2 style='color: white; margin: 0; font-size: 1.75rem;'>차트 매매 전략</h2>
        <p style='color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;'>기술적 분석 기반 매매 시그널 탐색</p>
    </div>
    """, unsafe_allow_html=True)

    # 전략 설명 카드
    st.markdown("### 🎯 사용 가능한 전략")

    chart_strategies_info = [
        {"key": "golden_cross", "name": "골든크로스", "icon": "✨",
         "desc": "5일선이 20일선을 상향 돌파시 매수, 하향 돌파시 매도"},
        {"key": "volume_breakout", "name": "거래량 급증", "icon": "📈",
         "desc": "평균 대비 2배 이상 거래량 + 가격 상승시 매수"},
        {"key": "accumulation", "name": "매집봉 탐지", "icon": "🔍",
         "desc": "거래량 증가 + 짧은 양봉 = 세력 매집 신호"},
        {"key": "ma_bounce", "name": "이평선 지지", "icon": "📐",
         "desc": "20/60/120일선에서 지지받고 반등시 매수"},
        {"key": "box_breakout", "name": "박스권 돌파", "icon": "📦",
         "desc": "20일간 고점을 거래량 동반 돌파시 매수"},
        {"key": "triple_ma", "name": "3중 정배열", "icon": "📊",
         "desc": "5일 > 20일 > 60일선 정배열 시작시 매수"},
    ]

    # 3열로 전략 카드 표시
    cols = st.columns(3)
    for i, strat in enumerate(chart_strategies_info):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='background: white; border-radius: 12px; padding: 1rem;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1rem;
                        border-left: 4px solid #11998e;'>
                <div style='font-size: 1.5rem;'>{strat["icon"]}</div>
                <h4 style='margin: 0.5rem 0; color: #333;'>{strat["name"]}</h4>
                <p style='color: #666; font-size: 0.8rem; margin: 0;'>{strat["desc"]}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 전략 선택 및 스캔 설정
    st.markdown("### ⚙️ 스캔 설정")

    # 전체 종목 수 가져오기
    all_kospi = get_kospi_stocks()
    all_kosdaq = get_kosdaq_stocks()
    total_kospi = len(all_kospi)
    total_kosdaq = len(all_kosdaq)

    col1, col2 = st.columns(2)

    with col1:
        selected_chart_strategies = st.multiselect(
            "적용할 전략",
            options=[s["key"] for s in chart_strategies_info],
            default=["golden_cross", "volume_breakout"],
            format_func=lambda x: next((s["name"] for s in chart_strategies_info if s["key"] == x), x),
            key="chart_trade_strategies"
        )

    with col2:
        scan_market = st.selectbox("스캔 대상", ["전체", "KOSPI만", "KOSDAQ만"], key="chart_trade_market")

    # KOSPI/KOSDAQ 종목 수 개별 설정
    st.markdown("#### 📊 스캔 종목 수 설정")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style='background: #667eea15; padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <span style='color: #667eea; font-weight: 600;'>KOSPI</span>
            <span style='color: #888; font-size: 0.85rem;'> (전체 {total_kospi}개)</span>
        </div>
        """, unsafe_allow_html=True)
        kospi_scan_count = st.slider(
            "KOSPI 스캔 종목 수",
            min_value=0,
            max_value=total_kospi,
            value=min(100, total_kospi),
            key="ct_kospi_scan_count",
            disabled=(scan_market == "KOSDAQ만")
        )
        if scan_market != "KOSDAQ만":
            st.caption(f"선택: {kospi_scan_count}개 / 전체: {total_kospi}개")

    with col2:
        st.markdown(f"""
        <div style='background: #f5576c15; padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <span style='color: #f5576c; font-weight: 600;'>KOSDAQ</span>
            <span style='color: #888; font-size: 0.85rem;'> (전체 {total_kosdaq}개)</span>
        </div>
        """, unsafe_allow_html=True)
        kosdaq_scan_count = st.slider(
            "KOSDAQ 스캔 종목 수",
            min_value=0,
            max_value=total_kosdaq,
            value=min(100, total_kosdaq),
            key="ct_kosdaq_scan_count",
            disabled=(scan_market == "KOSPI만")
        )
        if scan_market != "KOSPI만":
            st.caption(f"선택: {kosdaq_scan_count}개 / 전체: {total_kosdaq}개")

    # 전체 스캔 종목 수 표시
    if scan_market == "전체":
        total_scan = kospi_scan_count + kosdaq_scan_count
    elif scan_market == "KOSPI만":
        total_scan = kospi_scan_count
    else:
        total_scan = kosdaq_scan_count

    st.info(f"📌 총 스캔 대상: **{total_scan}개** 종목")

    # 전략별 상세 설정
    with st.expander("🔧 전략별 상세 설정", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**골든크로스 설정**")
            gc_short = st.number_input("단기 이평선", 3, 20, 5, key="ct_gc_short")
            gc_long = st.number_input("장기 이평선", 10, 60, 20, key="ct_gc_long")

            st.markdown("**거래량 급증 설정**")
            vol_mult = st.slider("거래량 배수", 1.5, 5.0, 2.0, 0.5, key="ct_vol_mult")
            vol_min_change = st.slider("최소 가격 변동(%)", 0.5, 5.0, 2.0, 0.5, key="ct_vol_min_change")

        with col2:
            st.markdown("**박스권 돌파 설정**")
            box_days = st.number_input("박스권 기간(일)", 10, 60, 20, key="ct_box_days")
            box_threshold = st.slider("돌파 기준(%)", 1.0, 5.0, 2.0, 0.5, key="ct_box_threshold")

            st.markdown("**이평선 지지 설정**")
            ma_periods = st.multiselect("지지 확인 이평선", [20, 60, 120, 240], default=[20, 60, 120], key="ct_ma_periods")

    st.markdown("---")

    # 실시간 모드 선택 (거래량 급증 전략에만 적용)
    realtime_mode = False
    if "volume_breakout" in selected_chart_strategies:
        st.markdown("#### ⚡ 거래량 급증 - 실시간 모드")
        col1, col2 = st.columns([2, 3])
        with col1:
            realtime_mode = st.checkbox("실시간 데이터 사용", value=False, key="ct_realtime_mode",
                                       help="장중에 실시간 현재가/거래량을 조회하여 분석합니다")
        with col2:
            if realtime_mode:
                st.markdown("""
                <div style='background: #fff3cd; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;'>
                    ⚠️ <strong>실시간 모드</strong>: 종목당 API 호출이 추가되어 스캔 시간이 길어집니다.<br>
                    예상 시간: 약 {:.0f}분 (종목당 ~0.3초)
                </div>
                """.format(total_scan * 0.3 / 60), unsafe_allow_html=True)
            else:
                st.caption("📊 일봉 기준: 전일 종가 기준 분석 (빠름)")

        st.markdown("---")

    # 스캔 실행 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_label = "🔍 실시간 시그널 스캔" if realtime_mode else "🔍 차트 시그널 스캔"
        scan_button = st.button(btn_label, type="primary", use_container_width=True, key="ct_scan_button")

    if scan_button:
        if not selected_chart_strategies:
            st.warning("최소 1개 이상의 전략을 선택해주세요.")
            return

        if not api:
            st.error("API 연결이 필요합니다.")
            return

        if total_scan == 0:
            st.warning("스캔할 종목 수를 1개 이상 설정해주세요.")
            return

        _run_chart_scan(
            api=api,
            strategies=selected_chart_strategies,
            market=scan_market,
            kospi_count=kospi_scan_count,
            kosdaq_count=kosdaq_scan_count,
            gc_short=gc_short,
            gc_long=gc_long,
            vol_mult=vol_mult,
            vol_min_change=vol_min_change / 100,
            box_days=box_days,
            box_threshold=box_threshold / 100,
            ma_periods=ma_periods,
            realtime_mode=realtime_mode
        )

    # 스캔 결과 표시
    if 'chart_scan_result' in st.session_state and st.session_state['chart_scan_result']:
        _display_chart_signals(st.session_state['chart_scan_result'], api)


def _run_chart_scan(api, strategies, market, kospi_count, kosdaq_count, **kwargs):
    """차트 시그널 스캔 실행"""
    from datetime import datetime, timedelta

    realtime_mode = kwargs.get('realtime_mode', False)

    # 종목 리스트 가져오기
    kospi_stocks = get_kospi_stocks()
    kosdaq_stocks = get_kosdaq_stocks()

    # 시장 선택에 따른 종목 리스트 구성
    stock_list = []
    if market == "KOSPI만":
        stock_list = kospi_stocks[:kospi_count]
    elif market == "KOSDAQ만":
        stock_list = kosdaq_stocks[:kosdaq_count]
    else:  # 전체
        stock_list = kospi_stocks[:kospi_count] + kosdaq_stocks[:kosdaq_count]

    # 전략 인스턴스 생성
    strategy_instances = []
    volume_strategy = None  # 실시간 모드용 거래량 전략 분리

    for strat_key in strategies:
        if strat_key == "golden_cross":
            strategy_instances.append(GoldenCrossStrategy(
                short_period=kwargs.get('gc_short', 5),
                long_period=kwargs.get('gc_long', 20)
            ))
        elif strat_key == "volume_breakout":
            volume_strategy = VolumeBreakoutStrategy(
                volume_mult=kwargs.get('vol_mult', 2.0),
                min_change=kwargs.get('vol_min_change', 0.02)
            )
            if not realtime_mode:
                strategy_instances.append(volume_strategy)
        elif strat_key == "accumulation":
            strategy_instances.append(AccumulationStrategy())
        elif strat_key == "ma_bounce":
            strategy_instances.append(MABounceStrategy(
                ma_periods=kwargs.get('ma_periods', [20, 60, 120])
            ))
        elif strat_key == "box_breakout":
            strategy_instances.append(BoxBreakoutStrategy(
                lookback_days=kwargs.get('box_days', 20),
                breakout_threshold=kwargs.get('box_threshold', 0.02)
            ))
        elif strat_key == "triple_ma":
            strategy_instances.append(TripleMAStrategy())

    signals = []
    progress = st.progress(0)
    status = st.empty()

    # 일봉 데이터 기간 설정 (120일)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=150)).strftime("%Y%m%d")

    # 실시간 모드 안내
    if realtime_mode:
        st.info("⚡ 실시간 모드: 각 종목의 현재가/거래량을 API로 조회합니다...")

    for i, (code, name) in enumerate(stock_list):
        try:
            if realtime_mode:
                status.text(f"🔄 실시간 스캔... {name} ({code}) [{i+1}/{len(stock_list)}]")
            else:
                status.text(f"스캔 중... {name} ({code}) [{i+1}/{len(stock_list)}]")

            # 일봉 데이터 로드 (모든 전략에 필요)
            ohlcv = api.get_daily_price(code, start_date, end_date)
            if ohlcv is None or len(ohlcv) < 30:
                continue

            # 일반 전략 분석
            for strategy in strategy_instances:
                try:
                    signal = strategy.analyze(ohlcv, code, name)
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    continue

            # 실시간 모드: 거래량 급증 전략
            if realtime_mode and volume_strategy:
                try:
                    # 실시간 현재가 조회
                    realtime_info = api.get_stock_info(code)
                    if realtime_info:
                        rt_data = {
                            'price': realtime_info.get('price', 0),
                            'volume': realtime_info.get('volume', 0),
                            'change_rate': realtime_info.get('change_rate', 0),
                            'prev_close': realtime_info.get('prev_close', 0)
                        }
                        signal = volume_strategy.analyze_realtime(ohlcv, rt_data, code, name)
                        if signal:
                            signals.append(signal)
                except Exception as e:
                    continue

        except Exception as e:
            continue

        progress.progress((i + 1) / len(stock_list))

    progress.empty()
    status.empty()

    # 결과 저장
    st.session_state['chart_scan_result'] = signals

    if signals:
        buy_signals = [s for s in signals if s.signal_type == 'BUY']
        sell_signals = [s for s in signals if s.signal_type == 'SELL']
        realtime_count = sum(1 for s in signals if s.indicators and s.indicators.get('realtime'))
        mode_text = f" (실시간 {realtime_count}개 포함)" if realtime_mode and realtime_count > 0 else ""
        st.success(f"✅ 스캔 완료! 매수 시그널 {len(buy_signals)}개, 매도 시그널 {len(sell_signals)}개 발견{mode_text}")
    else:
        st.info("시그널을 발견하지 못했습니다. 설정을 조정해보세요.")


def _display_chart_signals(signals: list, api):
    """차트 시그널 결과 표시"""
    import plotly.graph_objects as go
    from datetime import datetime, timedelta

    if not signals:
        return

    st.markdown("### 📋 발견된 시그널")

    # 매수/매도 분리
    buy_signals = [s for s in signals if s.signal_type == 'BUY']
    sell_signals = [s for s in signals if s.signal_type == 'SELL']

    # 강도순 정렬
    buy_signals.sort(key=lambda x: x.signal_strength, reverse=True)
    sell_signals.sort(key=lambda x: x.signal_strength, reverse=True)

    # 탭으로 분리
    tab1, tab2 = st.tabs([f"🟢 매수 시그널 ({len(buy_signals)})", f"🔴 매도 시그널 ({len(sell_signals)})"])

    with tab1:
        if buy_signals:
            _render_signal_cards(buy_signals, "BUY", api)
        else:
            st.info("매수 시그널이 없습니다.")

    with tab2:
        if sell_signals:
            _render_signal_cards(sell_signals, "SELL", api)
        else:
            st.info("매도 시그널이 없습니다.")


def _render_signal_cards(signals: list, signal_type: str, api):
    """시그널 카드 렌더링"""
    import plotly.graph_objects as go
    from datetime import datetime, timedelta

    color = "#11998e" if signal_type == "BUY" else "#f5576c"
    icon = "🟢" if signal_type == "BUY" else "🔴"

    for idx, signal in enumerate(signals[:20]):  # 상위 20개만 표시
        with st.container():
            col1, col2, col3, col4 = st.columns([0.3, 2, 1.5, 1])

            with col1:
                # 강도 표시
                strength_color = "#38ef7d" if signal.signal_strength >= 70 else "#FFA500" if signal.signal_strength >= 50 else "#f5576c"
                st.markdown(f"""
                <div style='text-align: center;'>
                    <div style='font-size: 1.5rem;'>{icon}</div>
                    <div style='background: {strength_color}; color: white; border-radius: 12px;
                                padding: 0.25rem 0.5rem; font-size: 0.75rem; font-weight: 700;'>
                        {signal.signal_strength:.0f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div>
                    <strong style='font-size: 1.1rem;'>{signal.name}</strong>
                    <span style='color: #888;'>({signal.code})</span>
                    <br>
                    <span style='color: #666; font-size: 0.85rem;'>{signal.description}</span>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style='font-size: 0.9rem;'>
                    <div><span style='color: #888;'>현재가</span> <strong>{signal.price:,.0f}원</strong></div>
                    {'<div><span style="color: #888;">목표가</span> <strong style="color: #11998e;">' + f'{signal.target_price:,.0f}원</strong></div>' if signal.target_price else ''}
                    {'<div><span style="color: #888;">손절가</span> <strong style="color: #f5576c;">' + f'{signal.stop_loss:,.0f}원</strong></div>' if signal.stop_loss else ''}
                </div>
                """, unsafe_allow_html=True)

            with col4:
                if st.button("📈 차트", key=f"ct_signal_chart_{signal_type}_{idx}_{signal.code}"):
                    st.session_state['ct_signal_chart_code'] = signal.code
                    st.session_state['ct_signal_chart_name'] = signal.name

            st.markdown("<hr style='margin: 0.5rem 0; border-color: #eee;'>", unsafe_allow_html=True)

    # 선택된 종목 차트 표시
    if 'ct_signal_chart_code' in st.session_state and st.session_state.get('ct_signal_chart_code'):
        code = st.session_state['ct_signal_chart_code']
        name = st.session_state.get('ct_signal_chart_name', code)

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    padding: 1.5rem; border-radius: 16px; margin: 1rem 0;
                    border: 1px solid #667eea30;'>
            <h3 style='margin: 0; color: #667eea;'>📈 {name} ({code}) 차트</h3>
        </div>
        """, unsafe_allow_html=True)

        # 차트 데이터 로드
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")

        with st.spinner("차트 로딩 중..."):
            chart_data = api.get_daily_price(code, start_date, end_date)

        if chart_data is not None and len(chart_data) > 0:
            from plotly.subplots import make_subplots

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                vertical_spacing=0.03, row_heights=[0.7, 0.3])

            # 캔들스틱
            fig.add_trace(go.Candlestick(
                x=chart_data['date'],
                open=chart_data['open'],
                high=chart_data['high'],
                low=chart_data['low'],
                close=chart_data['close'],
                name='주가',
                increasing_line_color='#FF3B30',
                decreasing_line_color='#007AFF',
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#007AFF',
                line=dict(width=1),
                whiskerwidth=0.8
            ), row=1, col=1)

            # 이동평균선 (5, 20, 60, 120일)
            for period, color, label in [(5, '#FF6B6B', '5일'), (20, '#FFE66D', '20일'), (60, '#95E1D3', '60일'), (120, '#E91E63', '120일')]:
                if len(chart_data) >= period:
                    ma = chart_data['close'].rolling(window=period).mean()
                    fig.add_trace(go.Scatter(
                        x=chart_data['date'], y=ma,
                        mode='lines', name=label,
                        line=dict(color=color, width=1.5)
                    ), row=1, col=1)

            # 스윙 포인트 (저점/고점 마커)
            if len(chart_data) >= 10:
                swing_order = 3 if len(chart_data) < 100 else 5
                swing_high_idx, swing_low_idx = detect_swing_points(chart_data, order=swing_order)

                price_range = chart_data['high'].max() - chart_data['low'].min()
                marker_offset = price_range * 0.02

                # 저점 마커
                if len(swing_low_idx) > 0:
                    recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                    low_dates = chart_data['date'].iloc[recent_low_idx]
                    low_prices = chart_data['low'].iloc[recent_low_idx]

                    fig.add_trace(go.Scatter(
                        x=low_dates,
                        y=low_prices - marker_offset,
                        mode='markers+text',
                        name='스윙 저점',
                        marker=dict(symbol='triangle-up', size=12, color='#00C853',
                                   line=dict(color='white', width=1)),
                        text=[f'{p:,.0f}' for p in low_prices],
                        textposition='bottom center',
                        textfont=dict(size=9, color='#00C853'),
                        hovertemplate='저점: %{text}<extra></extra>',
                        showlegend=True
                    ), row=1, col=1)

                # 고점 마커
                if len(swing_high_idx) > 0:
                    recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
                    high_dates = chart_data['date'].iloc[recent_high_idx]
                    high_prices = chart_data['high'].iloc[recent_high_idx]

                    fig.add_trace(go.Scatter(
                        x=high_dates,
                        y=high_prices + marker_offset,
                        mode='markers+text',
                        name='스윙 고점',
                        marker=dict(symbol='triangle-down', size=12, color='#FF3B30',
                                   line=dict(color='white', width=1)),
                        text=[f'{p:,.0f}' for p in high_prices],
                        textposition='top center',
                        textfont=dict(size=9, color='#FF3B30'),
                        hovertemplate='고점: %{text}<extra></extra>',
                        showlegend=True
                    ), row=1, col=1)

                # ========== 추세선 추가 (저점/고점 연결) ==========
                from scipy import stats

                # 가격 범위 계산 (Y축 클리핑용)
                price_high = chart_data['high'].max()
                price_low = chart_data['low'].min()
                price_margin = (price_high - price_low) * 0.1  # 10% 여유

                # 상승 추세선 (저점 연결) - 최근 5개 저점 사용
                if len(swing_low_idx) >= 2:
                    recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                    low_x = list(recent_lows)
                    low_y = [chart_data['low'].iloc[i] for i in recent_lows]
                    slope, intercept, _, _, _ = stats.linregress(low_x, low_y)

                    if slope > 0:  # 상승 추세일 때만 표시
                        x_start = min(recent_lows)
                        x_end = len(chart_data) - 1
                        y_start = slope * x_start + intercept
                        y_end = slope * x_end + intercept

                        # Y값 클리핑 (차트 범위 내로 제한)
                        y_start = max(price_low - price_margin, min(price_high + price_margin, y_start))
                        y_end = max(price_low - price_margin, min(price_high + price_margin, y_end))

                        fig.add_trace(go.Scatter(
                            x=[chart_data['date'].iloc[x_start], chart_data['date'].iloc[x_end]],
                            y=[y_start, y_end],
                            mode='lines',
                            name='상승 추세선',
                            line=dict(color='#00C853', width=2, dash='solid'),
                            hovertemplate='상승 추세선<extra></extra>',
                            showlegend=True
                        ), row=1, col=1)

                # 하락 추세선 (고점 연결) - 최근 5개 고점 사용
                if len(swing_high_idx) >= 2:
                    recent_highs = swing_high_idx[-5:] if len(swing_high_idx) >= 5 else swing_high_idx
                    high_x = list(recent_highs)
                    high_y = [chart_data['high'].iloc[i] for i in recent_highs]
                    slope, intercept, _, _, _ = stats.linregress(high_x, high_y)

                    if slope < 0:  # 하락 추세일 때만 표시
                        x_start = min(recent_highs)
                        x_end = len(chart_data) - 1
                        y_start = slope * x_start + intercept
                        y_end = slope * x_end + intercept

                        # Y값 클리핑 (차트 범위 내로 제한)
                        y_start = max(price_low - price_margin, min(price_high + price_margin, y_start))
                        y_end = max(price_low - price_margin, min(price_high + price_margin, y_end))

                        fig.add_trace(go.Scatter(
                            x=[chart_data['date'].iloc[x_start], chart_data['date'].iloc[x_end]],
                            y=[y_start, y_end],
                            mode='lines',
                            name='하락 추세선',
                            line=dict(color='#FF3B30', width=2, dash='solid'),
                            hovertemplate='하락 추세선<extra></extra>',
                            showlegend=True
                        ), row=1, col=1)

            # 거래량
            colors = ['#FF3B30' if chart_data['close'].iloc[i] >= chart_data['open'].iloc[i] else '#007AFF'
                      for i in range(len(chart_data))]
            fig.add_trace(go.Bar(
                x=chart_data['date'], y=chart_data['volume'],
                marker_color=colors, name='거래량',
                showlegend=False, opacity=0.7
            ), row=2, col=1)

            fig.update_layout(
                height=500,
                margin=dict(t=30, b=30, l=60, r=30),
                xaxis_rangeslider_visible=False,
                plot_bgcolor='#FAFAFA',
                paper_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
            )

            st.plotly_chart(fig, use_container_width=True, key=f"ct_signal_chart_{signal_type}_{code}")

            # ========== 매매 신호 세분화 표시 (새로 추가) ==========
            st.markdown("---")
            st.markdown("#### 💡 상세 매매 신호 (AI 기술적 분석)")

            # 보유 평균가 입력 UI
            col_hold1, col_hold2 = st.columns([3, 1])
            with col_hold1:
                holding_price_input = st.number_input(
                    "📊 보유 평균가 입력 (선택사항)",
                    min_value=0,
                    value=0,
                    step=100,
                    help="보유 중인 종목이라면 평균 매수가를 입력하세요. 익절/손절 가이드가 제공됩니다.",
                    key=f"ct_holding_price_{code}"
                )
            with col_hold2:
                st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
                if holding_price_input > 0:
                    st.success(f"✅ {holding_price_input:,.0f}원")

            # 보유가 입력 여부에 따라 분석
            holding_price = holding_price_input if holding_price_input > 0 else None

            try:
                from dashboard.utils.indicators import get_enhanced_trading_signal

                signal_result = get_enhanced_trading_signal(chart_data, holding_price=holding_price)
            except Exception as e:
                st.error(f"매매 신호 분석 오류: {str(e)}")
                signal_result = None

            if signal_result:
                # 신호 타입별 색상 및 이모지
                signal_colors = {
                    'strong_buy': ('#00C853', '🟢', 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'),
                    'buy': ('#4CAF50', '🟢', 'linear-gradient(135deg, #56ab2f 0%, #a8e063 100%)'),
                    'stable_buy': ('#8BC34A', '🟡', 'linear-gradient(135deg, #7f7fd5 0%, #86a8e7 100%)'),
                    'hold': ('#FFC107', '⚪', 'linear-gradient(135deg, #FFB75E 0%, #ED8F03 100%)'),
                    'sell': ('#FF5722', '🔴', 'linear-gradient(135deg, #f12711 0%, #f5af19 100%)'),
                    'strong_sell': ('#F44336', '🔴', 'linear-gradient(135deg, #c31432 0%, #240b36 100%)')
                }

                sig_type = signal_result['signal_type']
                sig_name = signal_result['signal_name']
                confidence = signal_result['confidence']
                strategy = signal_result['strategy']
                indicators = signal_result['indicators']

                color, emoji, gradient = signal_colors.get(sig_type, ('#888', '⚪', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'))

                # 신호 카드
                col1, col2, col3 = st.columns([2, 2, 3])

                with col1:
                    st.markdown(f"""
                    <div style='background: {gradient}; padding: 1.5rem; border-radius: 16px; text-align: center; border: 2px solid {color};'>
                        <p style='color: white; margin: 0; font-size: 1rem; opacity: 0.9;'>매매 신호</p>
                        <p style='color: white; font-size: 2.5rem; font-weight: 700; margin: 0.5rem 0;'>{emoji} {sig_name}</p>
                        <p style='color: white; margin: 0; font-size: 0.9rem; opacity: 0.8;'>신뢰도: {confidence:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    # 가격 정보 (분할 매수)
                    entry_price = signal_result.get('entry_price')
                    entry_price_2 = signal_result.get('entry_price_2')
                    entry_price_3 = signal_result.get('entry_price_3')
                    stop_loss = signal_result.get('stop_loss')
                    target_price = signal_result.get('target_price')

                    price_html = "<div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.5rem; border-radius: 16px; border: 1px solid #333;'>"
                    if entry_price:
                        price_html += f"<p style='color: #888; margin: 0 0 0.5rem 0; font-size: 0.85rem;'>📊 분할 매수 전략</p>"
                        price_html += f"<p style='color: #11998e; font-size: 1.2rem; font-weight: 700; margin: 0.2rem 0;'>1차: {entry_price:,.0f}원</p>"
                        if entry_price_2:
                            price_html += f"<p style='color: #38ef7d; font-size: 1.1rem; font-weight: 600; margin: 0.2rem 0;'>2차: {entry_price_2:,.0f}원</p>"
                        if entry_price_3:
                            price_html += f"<p style='color: #56ab2f; font-size: 1.0rem; font-weight: 500; margin: 0.2rem 0;'>3차: {entry_price_3:,.0f}원</p>"
                        price_html += "<hr style='border: none; border-top: 1px solid #333; margin: 0.8rem 0;'>"
                    if stop_loss:
                        price_html += f"<p style='color: #f5576c; font-size: 0.95rem; margin: 0.2rem 0;'>🛑 손절가: {stop_loss:,.0f}원</p>"
                    if target_price:
                        price_html += f"<p style='color: #667eea; font-size: 0.95rem; margin: 0.2rem 0;'>🎯 목표가: {target_price:,.0f}원</p>"
                    if not entry_price:
                        price_html += f"<p style='color: #888; margin: 0; text-align: center; padding: 1rem 0;'>매수 신호 아님</p>"
                    price_html += "</div>"
                    st.markdown(price_html, unsafe_allow_html=True)

                with col3:
                    # 전략 설명 및 지표
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1.5rem; border-radius: 16px; border: 1px solid #333;'>
                        <p style='color: white; font-weight: 600; margin: 0 0 0.5rem 0; font-size: 0.95rem;'>{strategy}</p>
                        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.85rem;'>
                            <div><span style='color: #888;'>RSI:</span> <span style='color: white;'>{indicators['rsi']:.1f}</span></div>
                            <div><span style='color: #888;'>MACD:</span> <span style='color: white;'>{indicators['macd']:.2f}</span></div>
                            <div><span style='color: #888;'>BB위치:</span> <span style='color: white;'>{indicators['bb_position']:.1f}%</span></div>
                            <div><span style='color: #888;'>거래량:</span> <span style='color: white;'>{indicators['volume_ratio']:.1f}배</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # === 추가 정보: 시장 환경 & 거래량 추세 ===
                st.markdown("---")
                col_m1, col_m2, col_m3 = st.columns(3)

                with col_m1:
                    # 시장 리스크
                    market_risk_kr = signal_result.get('market_risk_kr', '➖ 중립')
                    market_comment = signal_result.get('market_comment', '시장 방향성 확인')
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                        <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>시장 환경</p>
                        <p style='color: white; font-size: 1.1rem; font-weight: 600; margin: 0.3rem 0;'>{market_risk_kr}</p>
                        <p style='color: #95a5a6; margin: 0; font-size: 0.75rem;'>{market_comment}</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col_m2:
                    # 거래량 추세
                    volume_trend_kr = signal_result.get('volume_trend_kr', '거래량 안정')
                    volume_change_3d = signal_result.get('volume_change_3d', 0)
                    volume_trend = signal_result.get('volume_trend', 'stable')

                    trend_color = '#11998e' if volume_trend in ['surge', 'increasing'] else '#f5576c' if volume_trend == 'decreasing' else '#888'

                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                        <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>거래량 추세</p>
                        <p style='color: {trend_color}; font-size: 1.1rem; font-weight: 600; margin: 0.3rem 0;'>{volume_trend_kr}</p>
                        <p style='color: #95a5a6; margin: 0; font-size: 0.75rem;'>3일 평균 변화</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col_m3:
                    # 매도 가이드 (보유 중인 경우만)
                    sell_guide_kr = signal_result.get('sell_guide_kr')

                    if sell_guide_kr:
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                            <p style='color: #ecf0f1; margin: 0; font-size: 0.85rem;'>보유 가이드</p>
                            <p style='color: white; font-size: 1.0rem; font-weight: 600; margin: 0.3rem 0;'>{sell_guide_kr}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%); padding: 1rem; border-radius: 12px; text-align: center;'>
                            <p style='color: #95a5a6; margin: 0; font-size: 0.85rem;'>보유 가이드</p>
                            <p style='color: #7f8c8d; font-size: 0.9rem; font-weight: 500; margin: 0.3rem 0;'>신규 매매 분석</p>
                        </div>
                        """, unsafe_allow_html=True)

                # 출처 표시
                st.caption("📚 **신호 출처:** [볼린저밴드 가이드](https://www.xs.com/ko/blog/볼린저밴드/), [RSI/MACD 분석](https://moneyrecipe.blog/rsi-macd-bollingerband-limitations/), [기술적 분석 지표](https://jackerlab.com/futures-trading-technical-indicators-timeframe-guide/) | 💡 **개선:** ChatGPT 전문가 인사이트 반영")

        if st.button("❌ 차트 닫기", key=f"ct_close_signal_chart_{signal_type}"):
            st.session_state['ct_signal_chart_code'] = None
            st.rerun()
