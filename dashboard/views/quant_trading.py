"""
실제 퀀트 매매 뷰
- 계좌현황: 잔고, 보유종목, 수익률
- 수동매매: 종목 검색 후 직접 매수/매도
- 자동매매: 차트 전략 신호 기반 자동 주문
- 주문내역: 체결 내역 조회
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 스윙 포인트 감지 함수 import
from dashboard.utils.chart_utils import detect_swing_points

# 데이터 파일 경로
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
AUTO_TRADING_CONFIG_FILE = os.path.join(DATA_DIR, "auto_trading_config.json")
ORDER_HISTORY_FILE = os.path.join(DATA_DIR, "order_history.json")


def _get_api():
    """KIS API 인스턴스 반환"""
    try:
        from data.kis_api import KoreaInvestmentAPI
        import os

        # 환경변수 또는 설정에서 API 정보 로드
        app_key = os.getenv("KIS_APP_KEY")
        app_secret = os.getenv("KIS_APP_SECRET")
        account_no = os.getenv("KIS_ACCOUNT_NO")
        is_mock = os.getenv("KIS_IS_MOCK", "false").lower() == "true"

        if not app_key or not app_secret:
            return None

        api = KoreaInvestmentAPI(
            app_key=app_key,
            app_secret=app_secret,
            account_no=account_no,
            is_mock=is_mock
        )

        # 연결 시도
        if api.connect():
            return api
        return api  # 연결 실패해도 API 객체 반환 (상태 확인용)
    except Exception as e:
        return None


def _get_all_stocks_for_selection(market: str = "전체") -> list:
    """드롭다운용 전체 종목 리스트"""
    try:
        from data.stock_list import get_kospi_stocks, get_kosdaq_stocks
        stocks = []
        if market in ["전체", "KOSPI"]:
            kospi = get_kospi_stocks()
            for code, name in kospi:
                stocks.append((code, name, "KOSPI"))
        if market in ["전체", "KOSDAQ"]:
            kosdaq = get_kosdaq_stocks()
            for code, name in kosdaq:
                stocks.append((code, name, "KOSDAQ"))
        return stocks
    except Exception as e:
        return []


def _get_stock_price_with_history(api, code: str, days: int = 60):
    """종목 현재가 및 과거 주가 데이터 조회"""
    current_price = 0
    price_data = None
    api_connected = False

    if api:
        try:
            price_info = api.get_stock_price(code)
            current_price = float(price_info.get('stck_prpr', 0))
            if current_price > 0:
                api_connected = True

            # 과거 데이터 조회
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            df = api.get_daily_price(code, start_date, end_date)
            if df is not None and len(df) > 0:
                price_data = df
        except Exception as e:
            pass

    return current_price, price_data, api_connected


def _load_auto_trading_config():
    """자동매매 설정 로드"""
    if os.path.exists(AUTO_TRADING_CONFIG_FILE):
        try:
            with open(AUTO_TRADING_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "enabled": False,
        "strategies": [],
        "max_invest_per_stock": 1000000,
        "max_total_invest": 10000000,
        "stop_loss_pct": 5.0,
        "take_profit_pct": 10.0
    }


def _save_auto_trading_config(config):
    """자동매매 설정 저장"""
    with open(AUTO_TRADING_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _load_order_history():
    """주문내역 로드"""
    if os.path.exists(ORDER_HISTORY_FILE):
        try:
            with open(ORDER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []


def _save_order_history(orders):
    """주문내역 저장"""
    with open(ORDER_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def _add_order_history(order_type, code, name, quantity, price, status, message=""):
    """주문내역 추가"""
    orders = _load_order_history()
    orders.insert(0, {
        "timestamp": datetime.now().isoformat(),
        "order_type": order_type,
        "code": code,
        "name": name,
        "quantity": quantity,
        "price": price,
        "total_amount": quantity * price,
        "status": status,
        "message": message
    })
    # 최근 1000개만 유지
    orders = orders[:1000]
    _save_order_history(orders)


def render_quant_trading():
    """퀀트 매매 메인 렌더링"""
    st.title("💹 실제 퀀트 매매")

    api = _get_api()

    # API 연결 상태 표시
    if api:
        # 상세 상태 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            if api.access_token:
                st.success("✅ API 토큰: 발급됨")
            else:
                st.warning("⚠️ API 토큰: 미발급")
        with col2:
            if api.account_no:
                masked_account = f"{api.account_no[:4]}****-**"
                st.success(f"✅ 계좌: {masked_account}")
            else:
                st.error("❌ 계좌: 미설정")
        with col3:
            mode = "모의투자" if api.is_mock else "실전투자"
            st.info(f"📌 모드: {mode}")
    else:
        st.error("❌ KIS API 연결 실패")
        st.markdown("""
        **설정 방법:**
        1. 환경변수 설정 또는 `.env` 파일 생성
        2. 필요한 환경변수:
           - `KIS_APP_KEY`: 한국투자증권 앱 키
           - `KIS_APP_SECRET`: 한국투자증권 앱 시크릿
           - `KIS_ACCOUNT_NO`: 계좌번호 (예: 12345678-01)
           - `KIS_IS_MOCK`: 모의투자 여부 (true/false)
        """)

    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 계좌현황", "🛒 수동매매", "🤖 자동매매", "📋 주문내역"])

    with tab1:
        _render_account_status(api)

    with tab2:
        _render_manual_trading(api)

    with tab3:
        _render_auto_trading(api)

    with tab4:
        _render_order_history(api)


def _render_account_status(api):
    """계좌현황 탭 렌더링"""
    st.subheader("계좌 잔고 및 보유 종목")

    if not api:
        st.warning("API 연결이 필요합니다.")
        return

    # 계좌번호 확인
    if not api.account_no:
        st.error("❌ 계좌번호가 설정되지 않았습니다.")
        st.info("💡 설정 메뉴에서 계좌번호를 설정해주세요. (예: 12345678-01)")
        return

    # API 모드 표시
    mode_text = "🟡 모의투자" if api.is_mock else "🟢 실전투자"
    st.caption(f"계좌: {api.account_no[:8]}-** | {mode_text}")

    # 잔고 조회
    with st.spinner("잔고 조회 중..."):
        try:
            balance = api.get_balance()
        except Exception as e:
            st.error(f"잔고 조회 중 오류 발생: {e}")
            balance = None

    if not balance:
        st.error("❌ 잔고 조회 실패")
        st.markdown("""
        **가능한 원인:**
        1. 계좌번호 형식 오류 (올바른 형식: 12345678-01)
        2. API 키가 해당 계좌에 대한 권한이 없음
        3. 모의투자/실전투자 설정 불일치
        4. 토큰 만료 (앱 재시작 필요)

        **해결 방법:**
        - 설정 메뉴에서 계좌 정보 확인
        - 한국투자증권 KIS Developers에서 API 권한 확인
        """)
        return

    holdings = balance.get("holdings", [])
    summary = balance.get("summary", [])

    # 요약 정보
    if summary and len(summary) > 0:
        sum_data = summary[0] if isinstance(summary, list) else summary

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_eval = int(float(sum_data.get("tot_evlu_amt", 0)))
            st.metric("총 평가금액", f"{total_eval:,}원")

        with col2:
            deposit = int(float(sum_data.get("dnca_tot_amt", 0)))
            st.metric("예수금", f"{deposit:,}원")

        with col3:
            purchase = int(float(sum_data.get("pchs_amt_smtl_amt", 0)))
            st.metric("매입금액", f"{purchase:,}원")

        with col4:
            profit = int(float(sum_data.get("evlu_pfls_smtl_amt", 0)))
            profit_rate = float(sum_data.get("evlu_pfls_rt", 0))
            color = "normal" if profit >= 0 else "inverse"
            st.metric("평가손익", f"{profit:,}원", f"{profit_rate:+.2f}%", delta_color=color)

    st.markdown("---")

    # 보유 종목 테이블
    st.subheader("보유 종목")

    if holdings and len(holdings) > 0:
        df_holdings = []
        for h in holdings:
            qty = int(h.get("hldg_qty", 0))
            if qty > 0:
                df_holdings.append({
                    "종목코드": h.get("pdno", ""),
                    "종목명": h.get("prdt_name", ""),
                    "보유수량": qty,
                    "매입가": int(float(h.get("pchs_avg_pric", 0))),
                    "현재가": int(float(h.get("prpr", 0))),
                    "평가금액": int(float(h.get("evlu_amt", 0))),
                    "평가손익": int(float(h.get("evlu_pfls_amt", 0))),
                    "수익률": float(h.get("evlu_pfls_rt", 0))
                })

        if df_holdings:
            df = pd.DataFrame(df_holdings)

            # 스타일 적용
            def color_profit(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return 'color: red'
                    elif val < 0:
                        return 'color: blue'
                return ''

            styled_df = df.style.applymap(color_profit, subset=['평가손익', '수익률'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            # 포트폴리오 차트
            st.subheader("포트폴리오 구성")
            fig = go.Figure(data=[go.Pie(
                labels=df['종목명'].tolist(),
                values=df['평가금액'].tolist(),
                hole=0.4,
                textinfo='label+percent',
                textposition='outside'
            )])
            fig.update_layout(height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("보유 종목이 없습니다.")
    else:
        st.info("보유 종목이 없습니다.")


def _render_manual_trading(api):
    """수동매매 탭 렌더링"""
    st.subheader("수동 매매")

    if not api:
        st.warning("API 연결이 필요합니다.")
        return

    # 시장 선택
    col1, col2 = st.columns([1, 3])
    with col1:
        market = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ"], key="manual_market")

    # 종목 검색
    stocks = _get_all_stocks_for_selection(market)
    stock_options = ["선택하세요..."] + [f"{name} ({code}) - {mkt}" for code, name, mkt in stocks]

    with col2:
        selected = st.selectbox(
            "종목 선택",
            stock_options,
            key="manual_stock_select"
        )

    if selected and selected != "선택하세요...":
        # 종목코드 추출
        try:
            code = selected.split("(")[1].split(")")[0]
            name = selected.split(" (")[0]
        except:
            st.error("종목 선택 오류")
            return

        # 현재가 및 차트 조회
        with st.spinner("종목 정보 조회 중..."):
            current_price, price_data, api_connected = _get_stock_price_with_history(api, code)

        col1, col2 = st.columns([2, 3])

        with col1:
            st.markdown(f"### {name}")

            if api_connected and current_price > 0:
                st.metric("현재가", f"{int(current_price):,}원")
            else:
                st.warning("현재가 조회 실패")

            st.markdown("---")

            # 매매 주문 폼
            trade_type = st.radio("주문 유형", ["매수", "매도"], horizontal=True, key="manual_trade_type")

            order_method = st.selectbox(
                "주문 방식",
                ["지정가", "시장가"],
                key="manual_order_method"
            )

            if order_method == "지정가":
                price = st.number_input(
                    "주문 가격",
                    min_value=0,
                    value=int(current_price) if current_price > 0 else 0,
                    step=100,
                    key="manual_price"
                )
            else:
                price = 0
                st.info("시장가 주문은 현재 시장 가격으로 체결됩니다.")

            quantity = st.number_input(
                "주문 수량",
                min_value=1,
                value=1,
                step=1,
                key="manual_quantity"
            )

            # 예상 금액
            if order_method == "지정가" and price > 0:
                total = price * quantity
            elif current_price > 0:
                total = int(current_price) * quantity
            else:
                total = 0

            st.info(f"예상 주문금액: **{total:,}원**")

            # 주문 실행 버튼
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button(
                    f"{'🔴 매수' if trade_type == '매수' else '🔵 매도'} 주문",
                    type="primary",
                    use_container_width=True,
                    key="manual_order_btn"
                ):
                    order_type = "00" if order_method == "지정가" else "01"

                    with st.spinner("주문 처리 중..."):
                        try:
                            if trade_type == "매수":
                                result = api.buy_stock(code, quantity, price, order_type)
                            else:
                                result = api.sell_stock(code, quantity, price, order_type)

                            if result and result.get("rt_cd") == "0":
                                st.success(f"✅ {trade_type} 주문 완료!")
                                st.json(result.get("output", {}))
                                _add_order_history(
                                    trade_type, code, name, quantity,
                                    price if price > 0 else int(current_price),
                                    "완료", result.get("msg1", "")
                                )
                            else:
                                msg = result.get("msg1", "주문 실패") if result else "주문 실패"
                                st.error(f"❌ {trade_type} 주문 실패: {msg}")
                                _add_order_history(
                                    trade_type, code, name, quantity,
                                    price if price > 0 else int(current_price),
                                    "실패", msg
                                )
                        except Exception as e:
                            st.error(f"주문 오류: {e}")
                            _add_order_history(
                                trade_type, code, name, quantity,
                                price if price > 0 else int(current_price),
                                "오류", str(e)
                            )

            with col_btn2:
                if st.button("취소", use_container_width=True, key="manual_cancel_btn"):
                    st.rerun()

        with col2:
            # 차트 표시
            if price_data is not None and len(price_data) > 0:
                st.markdown("### 주가 차트")

                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    row_heights=[0.7, 0.3]
                )

                # 캔들스틱
                fig.add_trace(
                    go.Candlestick(
                        x=price_data['date'],
                        open=price_data['open'],
                        high=price_data['high'],
                        low=price_data['low'],
                        close=price_data['close'],
                        name='주가',
                        increasing_line_color='#FF3B30',
                        decreasing_line_color='#007AFF',
                        increasing_fillcolor='#FF3B30',
                        decreasing_fillcolor='#007AFF',
                        line=dict(width=1),
                        whiskerwidth=0.8
                    ),
                    row=1, col=1
                )

                # 이동평균선 (5, 20, 60, 120일)
                if len(price_data) >= 5:
                    ma5 = price_data['close'].rolling(window=5).mean()
                    fig.add_trace(
                        go.Scatter(x=price_data['date'], y=ma5, name='MA5',
                                  line=dict(color='orange', width=1)),
                        row=1, col=1
                    )

                if len(price_data) >= 20:
                    ma20 = price_data['close'].rolling(window=20).mean()
                    fig.add_trace(
                        go.Scatter(x=price_data['date'], y=ma20, name='MA20',
                                  line=dict(color='blue', width=1)),
                        row=1, col=1
                    )

                if len(price_data) >= 60:
                    ma60 = price_data['close'].rolling(window=60).mean()
                    fig.add_trace(
                        go.Scatter(x=price_data['date'], y=ma60, name='MA60',
                                  line=dict(color='#9C27B0', width=1)),
                        row=1, col=1
                    )

                if len(price_data) >= 120:
                    ma120 = price_data['close'].rolling(window=120).mean()
                    fig.add_trace(
                        go.Scatter(x=price_data['date'], y=ma120, name='MA120',
                                  line=dict(color='#E91E63', width=1)),
                        row=1, col=1
                    )

                # 스윙 포인트 (저점/고점 마커)
                if len(price_data) >= 10:
                    swing_order = 3 if len(price_data) < 100 else 5
                    swing_high_idx, swing_low_idx = detect_swing_points(price_data, order=swing_order)

                    price_range = price_data['high'].max() - price_data['low'].min()
                    marker_offset = price_range * 0.02

                    # 저점 마커
                    if len(swing_low_idx) > 0:
                        recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
                        low_dates = price_data['date'].iloc[recent_low_idx]
                        low_prices = price_data['low'].iloc[recent_low_idx]

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
                        high_dates = price_data['date'].iloc[recent_high_idx]
                        high_prices = price_data['high'].iloc[recent_high_idx]

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

                    # 상승 추세선 (저점 연결)
                    if len(swing_low_idx) >= 2:
                        recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
                        tl_low_x = list(recent_lows)
                        tl_low_y = [price_data['low'].iloc[i] for i in recent_lows]
                        slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

                        if slope > 0:
                            tl_x_start = min(recent_lows)
                            tl_x_end = len(price_data) - 1
                            tl_y_start = slope * tl_x_start + intercept
                            tl_y_end = slope * tl_x_end + intercept

                            fig.add_trace(go.Scatter(
                                x=[price_data['date'].iloc[tl_x_start], price_data['date'].iloc[tl_x_end]],
                                y=[tl_y_start, tl_y_end],
                                mode='lines',
                                name='상승 추세선',
                                line=dict(color='#00C853', width=2, dash='solid'),
                                hovertemplate='상승 추세선<extra></extra>',
                                showlegend=True
                            ), row=1, col=1)

                    # 하락 추세선 (고점 연결)
                    if len(swing_high_idx) >= 2:
                        recent_highs = swing_high_idx[-5:] if len(swing_high_idx) >= 5 else swing_high_idx
                        tl_high_x = list(recent_highs)
                        tl_high_y = [price_data['high'].iloc[i] for i in recent_highs]
                        slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

                        if slope < 0:
                            tl_x_start = min(recent_highs)
                            tl_x_end = len(price_data) - 1
                            tl_y_start = slope * tl_x_start + intercept
                            tl_y_end = slope * tl_x_end + intercept

                            fig.add_trace(go.Scatter(
                                x=[price_data['date'].iloc[tl_x_start], price_data['date'].iloc[tl_x_end]],
                                y=[tl_y_start, tl_y_end],
                                mode='lines',
                                name='하락 추세선',
                                line=dict(color='#FF3B30', width=2, dash='solid'),
                                hovertemplate='하락 추세선<extra></extra>',
                                showlegend=True
                            ), row=1, col=1)

                # 거래량
                colors = ['red' if row['close'] >= row['open'] else 'blue'
                         for _, row in price_data.iterrows()]
                fig.add_trace(
                    go.Bar(x=price_data['date'], y=price_data['volume'],
                          name='거래량', marker_color=colors),
                    row=2, col=1
                )

                fig.update_layout(
                    height=500,
                    xaxis_rangeslider_visible=False,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                fig.update_xaxes(row=2, col=1, title_text="")
                fig.update_yaxes(row=1, col=1, title_text="가격")
                fig.update_yaxes(row=2, col=1, title_text="거래량")

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("차트 데이터를 불러올 수 없습니다.")


def _render_auto_trading(api):
    """자동매매 탭 렌더링"""
    st.subheader("전략 기반 자동매매")

    if not api:
        st.warning("API 연결이 필요합니다.")
        return

    config = _load_auto_trading_config()

    # 자동매매 활성화 토글
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### ⚙️ 자동매매 설정")
    with col2:
        enabled = st.toggle("자동매매 활성화", value=config.get("enabled", False), key="auto_enabled")
        config["enabled"] = enabled

    if enabled:
        st.success("🟢 자동매매가 활성화되어 있습니다.")
    else:
        st.info("🔴 자동매매가 비활성화되어 있습니다.")

    st.markdown("---")

    # 투자 한도 설정
    col1, col2 = st.columns(2)

    with col1:
        max_per_stock = st.number_input(
            "종목당 최대 투자금액",
            min_value=100000,
            max_value=100000000,
            value=config.get("max_invest_per_stock", 1000000),
            step=100000,
            key="auto_max_per_stock"
        )
        config["max_invest_per_stock"] = max_per_stock

    with col2:
        max_total = st.number_input(
            "총 최대 투자금액",
            min_value=1000000,
            max_value=1000000000,
            value=config.get("max_total_invest", 10000000),
            step=1000000,
            key="auto_max_total"
        )
        config["max_total_invest"] = max_total

    # 손절/익절 설정
    col1, col2 = st.columns(2)

    with col1:
        stop_loss = st.number_input(
            "손절 비율 (%)",
            min_value=1.0,
            max_value=30.0,
            value=config.get("stop_loss_pct", 5.0),
            step=0.5,
            key="auto_stop_loss"
        )
        config["stop_loss_pct"] = stop_loss

    with col2:
        take_profit = st.number_input(
            "익절 비율 (%)",
            min_value=1.0,
            max_value=100.0,
            value=config.get("take_profit_pct", 10.0),
            step=0.5,
            key="auto_take_profit"
        )
        config["take_profit_pct"] = take_profit

    st.markdown("---")

    # 전략 선택
    st.markdown("### 📈 매매 전략 선택")

    available_strategies = [
        {"id": "flag_pennant", "name": "깃발/페넌트 패턴", "desc": "상승/하락 깃발 및 페넌트 패턴 돌파 시 매수"},
        {"id": "golden_cross", "name": "골든크로스", "desc": "5일선이 20일선 상향 돌파 시 매수"},
        {"id": "dead_cross", "name": "데드크로스 매도", "desc": "5일선이 20일선 하향 돌파 시 매도"},
        {"id": "support_breakout", "name": "지지선 돌파", "desc": "주요 지지선 돌파 시 매수"},
        {"id": "rsi_oversold", "name": "RSI 과매도 반등", "desc": "RSI 30 이하에서 반등 시 매수"},
        {"id": "volume_spike", "name": "거래량 급증", "desc": "평균 거래량 대비 3배 이상 급증 시 매수"},
        {"id": "fibonacci_retracement", "name": "피보나치 되돌림", "desc": "38.2%, 50%, 61.8% 되돌림 시 매수"},
        {"id": "bollinger_squeeze", "name": "볼린저 밴드 스퀴즈", "desc": "밴드 수축 후 확장 시 방향 매매"},
    ]

    selected_strategies = config.get("strategies", [])

    for strat in available_strategies:
        is_selected = strat["id"] in selected_strategies

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{strat['name']}**")
            st.caption(strat['desc'])
        with col2:
            if st.checkbox("활성화", value=is_selected, key=f"strat_{strat['id']}"):
                if strat["id"] not in selected_strategies:
                    selected_strategies.append(strat["id"])
            else:
                if strat["id"] in selected_strategies:
                    selected_strategies.remove(strat["id"])

    config["strategies"] = selected_strategies

    st.markdown("---")

    # 설정 저장 버튼
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("💾 설정 저장", type="primary", use_container_width=True, key="auto_save"):
            _save_auto_trading_config(config)
            st.success("설정이 저장되었습니다!")

    with col2:
        if st.button("🔄 초기화", use_container_width=True, key="auto_reset"):
            config = {
                "enabled": False,
                "strategies": [],
                "max_invest_per_stock": 1000000,
                "max_total_invest": 10000000,
                "stop_loss_pct": 5.0,
                "take_profit_pct": 10.0
            }
            _save_auto_trading_config(config)
            st.rerun()

    # 현재 활성화된 전략 표시
    if selected_strategies:
        st.markdown("---")
        st.markdown("### 🎯 현재 활성화된 전략")

        for strat_id in selected_strategies:
            strat = next((s for s in available_strategies if s["id"] == strat_id), None)
            if strat:
                st.success(f"✅ {strat['name']}")

    # 자동매매 로그 (최근 신호)
    st.markdown("---")
    st.markdown("### 📝 최근 자동매매 신호")

    # TODO: 실제 신호 로그 표시
    st.info("자동매매 신호가 발생하면 여기에 표시됩니다.")
    st.caption("참고: 자동매매 기능은 장 중에만 동작합니다. (09:00 ~ 15:30)")


def _render_order_history(api):
    """주문내역 탭 렌더링"""
    st.subheader("주문 내역")

    # 저장된 주문 내역 로드
    orders = _load_order_history()

    if not orders:
        st.info("주문 내역이 없습니다.")
        return

    # 필터
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_type = st.selectbox(
            "주문 유형",
            ["전체", "매수", "매도"],
            key="order_filter_type"
        )

    with col2:
        filter_status = st.selectbox(
            "주문 상태",
            ["전체", "완료", "실패", "오류"],
            key="order_filter_status"
        )

    with col3:
        filter_days = st.selectbox(
            "기간",
            ["전체", "오늘", "최근 7일", "최근 30일"],
            key="order_filter_days"
        )

    # 필터 적용
    filtered_orders = orders.copy()

    if filter_type != "전체":
        filtered_orders = [o for o in filtered_orders if o.get("order_type") == filter_type]

    if filter_status != "전체":
        filtered_orders = [o for o in filtered_orders if o.get("status") == filter_status]

    if filter_days != "전체":
        now = datetime.now()
        if filter_days == "오늘":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif filter_days == "최근 7일":
            cutoff = now - timedelta(days=7)
        else:  # 최근 30일
            cutoff = now - timedelta(days=30)

        filtered_orders = [
            o for o in filtered_orders
            if datetime.fromisoformat(o.get("timestamp", "2000-01-01")) >= cutoff
        ]

    if not filtered_orders:
        st.info("조건에 맞는 주문 내역이 없습니다.")
        return

    # 테이블로 표시
    df_orders = []
    for o in filtered_orders:
        df_orders.append({
            "시간": datetime.fromisoformat(o.get("timestamp", "")).strftime("%Y-%m-%d %H:%M:%S"),
            "유형": o.get("order_type", ""),
            "종목코드": o.get("code", ""),
            "종목명": o.get("name", ""),
            "수량": o.get("quantity", 0),
            "가격": f"{o.get('price', 0):,}",
            "금액": f"{o.get('total_amount', 0):,}",
            "상태": o.get("status", ""),
            "메시지": o.get("message", "")[:50]
        })

    df = pd.DataFrame(df_orders)

    # 스타일 적용
    def color_type(val):
        if val == "매수":
            return 'background-color: #ffebee; color: red'
        elif val == "매도":
            return 'background-color: #e3f2fd; color: blue'
        return ''

    def color_status(val):
        if val == "완료":
            return 'background-color: #e8f5e9; color: green'
        elif val == "실패":
            return 'background-color: #fff3e0; color: orange'
        elif val == "오류":
            return 'background-color: #ffebee; color: red'
        return ''

    styled_df = df.style.applymap(color_type, subset=['유형']).applymap(color_status, subset=['상태'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # 통계
    st.markdown("---")
    st.markdown("### 📊 주문 통계")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_orders = len(filtered_orders)
        st.metric("총 주문 수", f"{total_orders}건")

    with col2:
        buy_orders = len([o for o in filtered_orders if o.get("order_type") == "매수"])
        st.metric("매수 주문", f"{buy_orders}건")

    with col3:
        sell_orders = len([o for o in filtered_orders if o.get("order_type") == "매도"])
        st.metric("매도 주문", f"{sell_orders}건")

    with col4:
        success_orders = len([o for o in filtered_orders if o.get("status") == "완료"])
        success_rate = (success_orders / total_orders * 100) if total_orders > 0 else 0
        st.metric("성공률", f"{success_rate:.1f}%")

    # 내역 삭제 버튼
    st.markdown("---")
    if st.button("🗑️ 전체 내역 삭제", key="clear_orders"):
        if st.checkbox("정말 삭제하시겠습니까?", key="confirm_clear"):
            _save_order_history([])
            st.success("주문 내역이 삭제되었습니다.")
            st.rerun()
