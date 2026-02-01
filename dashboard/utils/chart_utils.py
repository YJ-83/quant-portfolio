"""
공통 차트 유틸리티 모듈
- chart_strategy.py와 screener.py에서 공유하는 차트 함수
- 코드 중복 제거 및 일관성 유지
- 모바일 반응형 지원
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple, List


# ========== 모바일 감지 ==========

def is_mobile() -> bool:
    """
    간단한 모바일 감지 (session_state 기반)
    실제로는 JS로 화면 너비를 체크해야 하지만, Streamlit에서는 제한적
    수동 설정 또는 기본값 사용
    """
    return st.session_state.get('mobile_mode', False)


def get_chart_config(mobile: bool = None) -> dict:
    """
    차트 설정 (모바일/데스크탑 분기)

    Args:
        mobile: 모바일 여부 (None이면 자동 감지)

    Returns:
        dict: 차트 설정값
    """
    if mobile is None:
        mobile = is_mobile()

    if mobile:
        return {
            'height': 300,
            'show_volume_profile': False,
            'show_swing_points': False,  # 모바일에서 마커 제거
            'ma_periods': [5, 20],  # 이평선 2개만
            'margin': dict(l=30, r=30, t=40, b=30),
            'legend_show': False,
            'font_size': 10
        }
    else:
        return {
            'height': 500,
            'show_volume_profile': True,
            'show_swing_points': True,
            'ma_periods': [5, 20, 60, 120],
            'margin': dict(l=50, r=50, t=80, b=50),
            'legend_show': True,
            'font_size': 12
        }

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from dashboard.utils.indicators import (
    detect_box_range,
    detect_box_breakout,
    calculate_volume_profile
)


# ========== 스윙 포인트 감지 ==========

def detect_swing_points(data: pd.DataFrame, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    스윙 고점/저점 감지 (로컬 extrema)

    Args:
        data: OHLCV 데이터프레임
        order: 좌우 비교 범위 (기본 5)

    Returns:
        (swing_high_indices, swing_low_indices)
    """
    try:
        from scipy.signal import argrelextrema

        highs = data['high'].values
        lows = data['low'].values

        # 고점: 주변 order개 데이터보다 높은 지점
        swing_high_idx = argrelextrema(highs, np.greater, order=order)[0]
        # 저점: 주변 order개 데이터보다 낮은 지점
        swing_low_idx = argrelextrema(lows, np.less, order=order)[0]

        return swing_high_idx, swing_low_idx
    except ImportError:
        # scipy 없으면 간단한 방식으로 대체
        swing_high_idx = []
        swing_low_idx = []

        highs = data['high'].values
        lows = data['low'].values

        for i in range(order, len(highs) - order):
            if all(highs[i] > highs[i-j] for j in range(1, order+1)) and \
               all(highs[i] > highs[i+j] for j in range(1, order+1)):
                swing_high_idx.append(i)
            if all(lows[i] < lows[i-j] for j in range(1, order+1)) and \
               all(lows[i] < lows[i+j] for j in range(1, order+1)):
                swing_low_idx.append(i)

        return np.array(swing_high_idx), np.array(swing_low_idx)


# ========== 공통 차트 렌더링 ==========

def render_candlestick_chart(
    data: pd.DataFrame,
    code: str,
    name: str,
    key_prefix: str = "chart",
    title: str = None,
    height: int = 500,
    # 옵션 플래그
    show_ma: bool = True,
    show_volume: bool = True,
    show_volume_profile: bool = False,
    show_swing_points: bool = False,
    show_box_range: bool = False,
    # D+1/D+2 시그널 (screener용)
    d1d2_info: dict = None,
    # 색상 설정
    up_color: str = '#FF3B30',
    down_color: str = '#007AFF',
    # 이동평균선 설정
    ma_periods: List[int] = None
) -> None:
    """
    통합 캔들스틱 차트 렌더링

    Args:
        data: OHLCV 데이터프레임 (index=날짜)
        code: 종목 코드
        name: 종목명
        key_prefix: streamlit 위젯 키 접두사
        title: 차트 제목 (None이면 자동 생성)
        height: 차트 높이
        show_ma: 이동평균선 표시 여부
        show_volume: 거래량 차트 표시 여부
        show_volume_profile: 매물대 프로필 표시 여부
        show_swing_points: 스윙 저점/고점 마커 표시
        show_box_range: 박스권 표시
        d1d2_info: D+1/D+2 시그널 정보 (screener용)
        up_color: 양봉 색상
        down_color: 음봉 색상
        ma_periods: 이동평균선 기간 리스트 (기본 [5, 20, 60, 120])
    """
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly가 설치되어 있지 않습니다. `pip install plotly`를 실행해주세요.")
        return

    if data is None or len(data) == 0:
        st.warning("차트 데이터가 없습니다.")
        return

    # 데이터 정렬
    data = data.sort_index().copy()

    # 이동평균선 기본값
    if ma_periods is None:
        ma_periods = [5, 20, 60, 120]

    # 이동평균선 계산
    ma_colors = {
        5: '#FF9500',    # 주황
        20: '#34C759',   # 녹색
        60: '#5856D6',   # 보라
        120: '#FF2D55'   # 분홍
    }

    for period in ma_periods:
        if len(data) >= period:
            data[f'MA{period}'] = data['close'].rolling(window=period).mean()

    # 서브플롯 구성 결정
    rows = 2 if show_volume else 1
    cols = 2 if show_volume_profile else 1
    row_heights = [0.7, 0.3] if show_volume else [1.0]

    if show_volume_profile:
        fig = make_subplots(
            rows=rows, cols=cols,
            shared_xaxes=True,
            shared_yaxes=True,
            vertical_spacing=0.03,
            horizontal_spacing=0.01,
            row_heights=row_heights,
            column_widths=[0.85, 0.15],
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]] if show_volume else
                  [[{"secondary_y": False}, {"secondary_y": False}]]
        )
    else:
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights
        )

    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name='가격',
            increasing_line_color=up_color,
            decreasing_line_color=down_color,
            increasing_fillcolor=up_color,
            decreasing_fillcolor=down_color,
            line=dict(width=1),
            whiskerwidth=0.8
        ),
        row=1, col=1
    )

    # 이동평균선
    if show_ma:
        for period in ma_periods:
            col_name = f'MA{period}'
            if col_name in data.columns:
                color = ma_colors.get(period, '#888888')
                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data[col_name],
                        name=col_name,
                        line=dict(color=color, width=1),
                        opacity=0.8
                    ),
                    row=1, col=1
                )

    # 스윙 포인트 (저점/고점 마커)
    if show_swing_points:
        swing_order = 3 if len(data) < 100 else 5
        swing_high_idx, swing_low_idx = detect_swing_points(data, order=swing_order)

        price_range = data['high'].max() - data['low'].min()
        marker_offset = price_range * 0.02

        # 저점 마커
        if len(swing_low_idx) > 0:
            recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
            low_dates = data.index[recent_low_idx]
            low_prices = data['low'].iloc[recent_low_idx]

            fig.add_trace(
                go.Scatter(
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
                ),
                row=1, col=1
            )

        # 고점 마커
        if len(swing_high_idx) > 0:
            recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
            high_dates = data.index[recent_high_idx]
            high_prices = data['high'].iloc[recent_high_idx]

            fig.add_trace(
                go.Scatter(
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
                ),
                row=1, col=1
            )

    # 박스권 시각화 (항상 표시)
    if show_box_range:
        try:
            box_result = detect_box_range(data, period=20, tolerance=0.05)
            if box_result and box_result.get('upper') is not None and box_result.get('lower') is not None:
                # numpy 타입을 Python 기본 타입으로 변환
                box_upper = float(box_result['upper'])
                box_lower = float(box_result['lower'])
                box_mid = float(box_result['mid'])

                # 날짜 인덱스 변환 (Plotly 호환성)
                x_start = data.index[0]
                x_end = data.index[-1]

                # 박스 상단선 (shape으로 추가)
                fig.add_shape(
                    type="line",
                    x0=x_start, x1=x_end,
                    y0=box_upper, y1=box_upper,
                    line=dict(color="rgba(255, 59, 48, 0.7)", width=1.5, dash="dash"),
                    row=1, col=1
                )
                fig.add_annotation(
                    x=x_end, y=box_upper,
                    text=f"박스 상단 {box_upper:,.0f}",
                    showarrow=False, xanchor="left",
                    font=dict(size=10, color="rgba(255, 59, 48, 0.9)"),
                    row=1, col=1
                )

                # 박스 하단선
                fig.add_shape(
                    type="line",
                    x0=x_start, x1=x_end,
                    y0=box_lower, y1=box_lower,
                    line=dict(color="rgba(0, 122, 255, 0.7)", width=1.5, dash="dash"),
                    row=1, col=1
                )
                fig.add_annotation(
                    x=x_end, y=box_lower,
                    text=f"박스 하단 {box_lower:,.0f}",
                    showarrow=False, xanchor="left",
                    font=dict(size=10, color="rgba(0, 122, 255, 0.9)"),
                    row=1, col=1
                )

                # 박스 중심선
                fig.add_shape(
                    type="line",
                    x0=x_start, x1=x_end,
                    y0=box_mid, y1=box_mid,
                    line=dict(color="rgba(142, 142, 147, 0.7)", width=1, dash="dot"),
                    row=1, col=1
                )
                fig.add_annotation(
                    x=x_end, y=box_mid,
                    text=f"중심 {box_mid:,.0f}",
                    showarrow=False, xanchor="left",
                    font=dict(size=10, color="rgba(142, 142, 147, 0.9)"),
                    row=1, col=1
                )

                # 박스 영역 채우기
                fig.add_shape(
                    type="rect",
                    x0=x_start, x1=x_end,
                    y0=box_lower, y1=box_upper,
                    fillcolor="rgba(102, 126, 234, 0.1)",
                    line=dict(width=0),
                    row=1, col=1
                )

                # 돌파 시그널
                breakout = detect_box_breakout(data, period=20, volume_confirm=True)
                if breakout and breakout.get('direction'):
                    breakout_dir = breakout['direction']
                    vol_confirmed = bool(breakout.get('volume_confirmed', False))

                    if breakout_dir == 'up':
                        signal_text = "▲ 상향 돌파" + (" (거래량 확인)" if vol_confirmed else "")
                        signal_color = "#00C853"
                    elif breakout_dir == 'down':
                        signal_text = "▼ 하향 이탈" + (" (거래량 확인)" if vol_confirmed else "")
                        signal_color = "#FF3B30"
                    else:
                        signal_text = None

                    if signal_text:
                        latest_date = data.index[-1]
                        latest_high = float(data['high'].iloc[-1])
                        price_range = float(data['high'].max() - data['low'].min())

                        fig.add_annotation(
                            x=latest_date,
                            y=latest_high + price_range * 0.05,
                            text=signal_text,
                            showarrow=True,
                            arrowhead=2,
                            arrowcolor=signal_color,
                            font=dict(size=11, color=signal_color, family="Arial"),
                            bgcolor="rgba(255,255,255,0.9)",
                            bordercolor=signal_color,
                            borderwidth=1,
                            borderpad=4,
                            row=1, col=1
                        )
        except Exception as e:
            # 박스권 표시 에러 시 로그만 남기고 차트는 계속 표시
            import traceback
            print(f"[박스권 표시 오류] {e}")
            traceback.print_exc()

    # D+1/D+2 시그널 라인 (screener용)
    if d1d2_info:
        if d1d2_info.get('has_recent_bullish'):
            bullish_high = d1d2_info.get('bullish_high')
            bullish_mid = d1d2_info.get('bullish_mid')
            bullish_open = d1d2_info.get('bullish_open')

            if bullish_high:
                fig.add_hline(y=bullish_high, line_dash="dash", line_color="red",
                             annotation_text=f"장대양봉 고점: {bullish_high:,.0f}", row=1, col=1)
            if bullish_mid:
                fig.add_hline(y=bullish_mid, line_dash="dot", line_color="orange",
                             annotation_text=f"진입가(중간): {bullish_mid:,.0f}", row=1, col=1)
            if bullish_open:
                fig.add_hline(y=bullish_open, line_dash="dash", line_color="blue",
                             annotation_text=f"손절(시가): {bullish_open:,.0f}", row=1, col=1)

        # 저항선 (전고점 등)
        resistance_line = d1d2_info.get('resistance_line')
        if resistance_line:
            resistance_label = d1d2_info.get('resistance_label', f"저항선: {resistance_line:,.0f}")
            fig.add_hline(y=resistance_line, line_dash="dash", line_color="red",
                         annotation_text=resistance_label, row=1, col=1)

    # 매물대 (Volume Profile)
    if show_volume_profile:
        price_levels, volumes, poc_price = calculate_volume_profile(data, num_bins=25)
        if price_levels and volumes:
            max_vol = max(volumes) if max(volumes) > 0 else 1
            norm_volumes = [v / max_vol * 100 for v in volumes]

            vp_colors = []
            for i, pl in enumerate(price_levels):
                if poc_price and abs(pl - poc_price) < (price_levels[1] - price_levels[0]):
                    vp_colors.append('rgba(255, 193, 7, 0.9)')  # POC - 노란색
                else:
                    vp_colors.append('rgba(102, 126, 234, 0.6)')

            fig.add_trace(
                go.Bar(
                    y=price_levels,
                    x=norm_volumes,
                    orientation='h',
                    name='매물대',
                    marker_color=vp_colors,
                    showlegend=True,
                    hovertemplate='가격: %{y:,.0f}원<br>거래량: %{customdata:,.0f}<extra></extra>',
                    customdata=volumes
                ),
                row=1, col=2
            )

            # POC 라인
            if poc_price:
                fig.add_hline(
                    y=poc_price, line_dash="dash",
                    line_color="rgba(255, 193, 7, 0.8)", line_width=1.5,
                    annotation_text=f"POC {poc_price:,.0f}",
                    annotation_position="left",
                    row=1, col=1
                )

    # 거래량 차트
    if show_volume:
        colors = [up_color if data['close'].iloc[i] >= data['open'].iloc[i] else down_color
                  for i in range(len(data))]

        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data['volume'],
                name='거래량',
                marker_color=colors,
                opacity=0.7
            ),
            row=2, col=1
        )

    # 레이아웃 설정
    chart_title = title if title else f"{name} ({code})"

    # 모바일 대응 레이아웃 설정
    mobile_mode = is_mobile()
    config = get_chart_config(mobile_mode)

    # height 파라미터가 기본값(500)이면 config에서 가져옴
    actual_height = config['height'] if height == 500 else height

    fig.update_layout(
        title=dict(
            text=chart_title,
            font=dict(size=config['font_size'] + 2)
        ),
        height=actual_height,
        xaxis_rangeslider_visible=False,
        showlegend=config['legend_show'],
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=config['font_size'] - 2)
        ) if config['legend_show'] else None,
        margin=config['margin']
    )

    fig.update_yaxes(title_text="가격", row=1, col=1)
    if show_volume:
        fig.update_yaxes(title_text="거래량", row=2, col=1)

    # 매물대 축 설정
    if show_volume_profile:
        fig.update_xaxes(showticklabels=False, showgrid=False, row=1, col=2)
        fig.update_yaxes(showticklabels=False, showgrid=False, row=1, col=2)
        if show_volume:
            fig.update_xaxes(visible=False, row=2, col=2)
            fig.update_yaxes(visible=False, row=2, col=2)

    # 차트 렌더링 - 키 없이 렌더링 (체크박스 변경 시 키 충돌 방지)
    # Streamlit은 같은 위치의 위젯을 자동으로 추적하므로 key 없이도 작동
    try:
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        import traceback
        print(f"[차트 렌더링 오류] {code}: {e}")
        traceback.print_exc()
        st.error(f"차트 표시 오류: {e}")


# ========== 간단한 차트 렌더링 (screener용) ==========

def render_simple_chart(
    api,
    code: str,
    name: str,
    key_prefix: str = "simple_chart",
    days: int = 60,
    d1d2_info: dict = None,
    resistance_line: float = None,
    resistance_label: str = None,
    show_swing_points: bool = True
) -> None:
    """
    간단한 차트 렌더링 (screener용)

    Args:
        api: API 연결 객체
        code: 종목 코드
        name: 종목명
        key_prefix: streamlit 위젯 키 접두사
        days: 표시할 일수
        d1d2_info: D+1/D+2 시그널 정보
        resistance_line: 저항선 가격 (전고점 등)
        resistance_label: 저항선 라벨 텍스트
    """
    if api is None:
        st.warning("API 연결이 필요합니다.")
        return

    try:
        df = api.get_daily_price(code, period="D")
        if df is None or df.empty:
            st.warning("차트 데이터를 불러올 수 없습니다.")
            return

        # 최근 N일 데이터
        df = df.tail(days).copy()

        # 저항선 정보를 d1d2_info에 추가
        chart_info = d1d2_info.copy() if d1d2_info else {}
        if resistance_line:
            chart_info['resistance_line'] = resistance_line
            chart_info['resistance_label'] = resistance_label or f"저항선: {resistance_line:,.0f}"

        # 모바일 대응 설정
        mobile_mode = is_mobile()
        config = get_chart_config(mobile_mode)

        render_candlestick_chart(
            data=df,
            code=code,
            name=name,
            key_prefix=key_prefix,
            height=config['height'],
            show_ma=True,
            show_volume=True,
            show_volume_profile=config['show_volume_profile'],
            show_swing_points=show_swing_points if not mobile_mode else False,
            show_box_range=True,  # 박스권 항상 표시
            d1d2_info=chart_info if chart_info else None,
            ma_periods=config['ma_periods']
        )

    except Exception as e:
        st.error(f"차트 로드 오류: {e}")


# ========== 투자자 매매동향 컴포넌트 ==========

def render_investor_trend(api, code: str, name: str = "", days: int = 5, key_prefix: str = "inv") -> None:
    """
    투자자별 매매동향 표시 컴포넌트 (개인/기관/외국인) - 일별 표시

    Args:
        api: KIS API 인스턴스
        code: 종목코드
        name: 종목명 (옵션)
        days: 조회 기간 (기본 5일)
        key_prefix: 위젯 키 접두어
    """
    # 기본 검증
    if api is None:
        st.info("API 연결이 필요합니다.")
        return

    # API에 get_investor_trading 메서드가 있는지 확인
    if not hasattr(api, 'get_investor_trading'):
        # 세션 API 객체가 오래된 경우 - 자동 갱신 시도
        try:
            from data.kis_api import KoreaInvestmentAPI
            new_api = KoreaInvestmentAPI()
            if new_api.connect():
                st.session_state['kis_api'] = new_api
                api = new_api
            else:
                st.info("API 재연결이 필요합니다. 페이지를 새로고침해주세요.")
                return
        except Exception:
            st.info("API 초기화 실패")
            return

    try:
        # 일별 투자자 동향 조회
        df = api.get_investor_trading(code, count=days)

        if df is None or df.empty:
            st.caption("투자자 동향 데이터가 없습니다.")
            return

        # 모바일 대응
        mobile_mode = is_mobile()

        if mobile_mode:
            _render_investor_daily_compact(df, key_prefix)
        else:
            _render_investor_daily_full(df, key_prefix)

    except Exception as e:
        st.caption(f"데이터 조회 중 오류: {str(e)[:30]}")


def _render_investor_daily_compact(df, key_prefix: str) -> None:
    """투자자 동향 일별 컴팩트 표시 (모바일용)"""
    def format_num(n):
        if abs(n) >= 1_000_000:
            return f"{n/1_000_000:+.1f}M"
        elif abs(n) >= 1_000:
            return f"{n/1_000:+.1f}K"
        else:
            return f"{n:+,}"

    def get_color(n):
        return "#11998e" if n > 0 else "#f5576c" if n < 0 else "#888"

    rows_html = ""
    for _, row in df.iterrows():
        date_str = row['date'].replace('2026.', '')  # 연도 제거
        inst = row['institution']
        frgn = row['foreign']

        rows_html += f"""
        <div style='display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.1);'>
            <span style='color: #888; font-size: 0.75rem;'>{date_str}</span>
            <span style='color: {get_color(inst)}; font-size: 0.75rem;'>기관 {format_num(inst)}</span>
            <span style='color: {get_color(frgn)}; font-size: 0.75rem;'>외인 {format_num(frgn)}</span>
        </div>
        """

    st.markdown(f"""
    <div style='background: rgba(0,0,0,0.2); border-radius: 8px; padding: 8px; margin: 4px 0;'>
        <div style='color: #aaa; font-size: 0.75rem; margin-bottom: 4px;'>📊 투자자 동향</div>
        {rows_html}
    </div>
    """, unsafe_allow_html=True)


def _render_investor_daily_full(df, key_prefix: str) -> None:
    """투자자 동향 일별 전체 표시 (데스크탑용) - Streamlit 네이티브 사용"""
    def format_num(n):
        if abs(n) >= 1_000_000:
            return f"{n/1_000_000:+.1f}M"
        elif abs(n) >= 1_000:
            return f"{n/1_000:+,.0f}K"
        else:
            return f"{n:+,}"

    def get_color(n):
        return "🟢" if n > 0 else "🔴" if n < 0 else "⚪"

    # Streamlit 컬럼으로 헤더 표시
    cols = st.columns([1, 1.2, 1.2, 1.2])
    cols[0].markdown("**날짜**")
    cols[1].markdown("**👤 개인**")
    cols[2].markdown("**🏢 기관**")
    cols[3].markdown("**🌍 외국인**")

    # 데이터 행 표시
    for _, row in df.iterrows():
        date_str = row['date'].replace('2026.', '').replace('2025.', '')
        ind = row['individual']
        inst = row['institution']
        frgn = row['foreign']

        cols = st.columns([1, 1.2, 1.2, 1.2])
        cols[0].caption(date_str)
        cols[1].markdown(f"{get_color(ind)} {format_num(ind)}")
        cols[2].markdown(f"{get_color(inst)} {format_num(inst)}")
        cols[3].markdown(f"{get_color(frgn)} {format_num(frgn)}")


def render_investor_badge(api, code: str, key_prefix: str = "badge") -> None:
    """
    투자자 동향 인라인 배지 (카드 내 표시용)

    Args:
        api: KIS API 인스턴스
        code: 종목코드
        key_prefix: 위젯 키 접두어
    """
    try:
        summary = api.get_investor_summary(code, days=5)
        if not summary:
            return

        trend = summary.get('trend', '')
        trend_color = summary.get('trend_color', '#888')
        frgn = summary.get('foreign_sum', 0)
        inst = summary.get('institution_sum', 0)

        # 간단한 배지
        frgn_sign = "+" if frgn > 0 else ""
        inst_sign = "+" if inst > 0 else ""

        st.markdown(f"""
        <span style='background: {trend_color}20; color: {trend_color};
                     padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px;'>
            {trend}
        </span>
        <span style='color: #888; font-size: 0.7rem;'>
            외인 {frgn_sign}{frgn/1000:.0f}K | 기관 {inst_sign}{inst/1000:.0f}K
        </span>
        """, unsafe_allow_html=True)

    except:
        pass
