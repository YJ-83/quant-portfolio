"""
섹터 분류 페이지 - 테마/섹터별 종목 탐색 및 상세 정보
레이아웃: 상단(섹터 선택 + 종목 목록) → 하단(차트 및 상세 정보)
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import argrelextrema
import os
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from data.theme_stocks import (
    THEME_STOCKS, THEME_CATEGORIES, get_theme_stocks,
    get_theme_stock_codes, get_all_theme_names, get_stock_themes,
    get_theme_stocks_with_custom, add_stock_to_theme, remove_stock_from_theme,
    get_custom_changes_summary, reset_custom_changes
)

# 공통 API 헬퍼 import
from dashboard.utils.api_helper import get_api_connection


def render_sector():
    """섹터 분류 페이지 렌더링"""

    # CSS
    st.markdown("""
    <style>
        .sector-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
        }
        .theme-chip {
            display: inline-block;
            padding: 0.5rem 1rem;
            margin: 0.25rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .theme-chip:hover {
            transform: scale(1.05);
        }
        .stock-grid-item {
            background: white;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin: 0.25rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            cursor: pointer;
            transition: all 0.2s ease;
            border-left: 3px solid #667eea;
        }
        .stock-grid-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .selected-stock-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.25rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }
        .theme-badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 0.1rem;
        }
        .info-card {
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            height: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

    # 헤더
    st.markdown("""
    <div class='sector-header'>
        <h1 style='color: white; margin: 0; font-size: 1.75rem;'>📂 섹터 분류</h1>
        <p style='color: rgba(255,255,255,0.85); margin: 0.25rem 0 0 0; font-size: 0.9rem;'>테마별 종목을 탐색하고 차트와 정보를 확인하세요</p>
    </div>
    """, unsafe_allow_html=True)

    # API 연결
    api = get_api_connection()

    # ========== 상단: 섹터 선택 + 종목 목록 ==========
    col_theme, col_stocks = st.columns([1, 3])

    with col_theme:
        col_title, col_manage = st.columns([3, 1])
        with col_title:
            st.markdown("#### 🏷️ 테마 선택")
        with col_manage:
            if st.button("⚙️", key="toggle_manage_mode", help="종목 관리 모드"):
                st.session_state['manage_mode'] = not st.session_state.get('manage_mode', False)
                st.rerun()

        # 관리 모드 표시
        if st.session_state.get('manage_mode', False):
            changes = get_custom_changes_summary()
            st.info(f"📝 관리모드 | 추가: {changes['added_count']}개, 제거: {changes['removed_count']}개")

        # 전체 테마를 카테고리별로 표시
        for category, themes in THEME_CATEGORIES.items():
            st.markdown(f"**{category}**")
            for theme in themes:
                # 커스텀 반영된 종목 수 표시
                stock_count = len(get_theme_stocks_with_custom(theme))
                is_selected = st.session_state.get('selected_sector_theme') == theme
                btn_type = "primary" if is_selected else "secondary"

                if st.button(
                    f"{theme} ({stock_count})",
                    key=f"theme_{theme}",
                    use_container_width=True,
                    type=btn_type
                ):
                    st.session_state['selected_sector_theme'] = theme
                    st.session_state['selected_sector_stock'] = None
                    st.rerun()

    with col_stocks:
        current_theme = st.session_state.get('selected_sector_theme')
        manage_mode = st.session_state.get('manage_mode', False)

        if current_theme:
            st.markdown(f"#### 📋 {current_theme} 종목")

            # 관리 모드일 때 추가 UI 표시
            if manage_mode:
                _render_stock_management_ui(current_theme)

            # 커스텀 반영된 종목 가져오기
            stocks = get_theme_stocks_with_custom(current_theme)

            # 검색 및 정렬 옵션
            col_search, col_sort = st.columns([2, 1])

            with col_search:
                search = st.text_input("🔍 종목 검색", placeholder="종목명 또는 코드", key="sector_search")

            with col_sort:
                sort_option = st.selectbox(
                    "📊 정렬",
                    ["기본순", "거래량 많은순", "1개월 수익률순", "6개월 수익률순"],
                    key="sector_sort"
                )

            if search:
                stocks = [(c, n) for c, n in stocks if search.lower() in n.lower() or search in c]

            # 정렬 적용 (API 데이터 기반)
            if sort_option != "기본순" and api:
                stocks = _sort_stocks_by_option(api, stocks, sort_option)

            st.caption(f"총 {len(stocks)}개 종목")

            # 정렬 옵션에 따른 추가 정보 표시
            if sort_option != "기본순":
                _render_sorted_stock_list(api, stocks, sort_option, manage_mode, current_theme)
            else:
                # 종목을 그리드로 표시 (4열 또는 관리모드시 3열)
                num_cols = 3 if manage_mode else 4
                cols = st.columns(num_cols)
                for i, (code, name) in enumerate(stocks):
                    with cols[i % num_cols]:
                        is_selected = st.session_state.get('selected_sector_stock') == (code, name)

                        # 키 중복 방지를 위해 테마명 + 인덱스 추가
                        unique_key = f"stock_{current_theme}_{code}_{i}"

                        if manage_mode:
                            # 관리 모드: 종목 선택 + 제거 버튼
                            col_btn, col_del = st.columns([4, 1])
                            with col_btn:
                                btn_style = "primary" if is_selected else "secondary"
                                if st.button(
                                    f"{name}\n({code})",
                                    key=f"{unique_key}_mgmt",
                                    use_container_width=True,
                                    type=btn_style
                                ):
                                    st.session_state['selected_sector_stock'] = (code, name)
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️", key=f"del_{current_theme}_{code}", help=f"{name} 제거"):
                                    success, msg = remove_stock_from_theme(current_theme, code)
                                    if success:
                                        st.success(msg)
                                    else:
                                        st.warning(msg)
                                    st.rerun()
                        else:
                            # 일반 모드: 종목 선택만
                            btn_style = "primary" if is_selected else "secondary"
                            if st.button(
                                f"{name}\n({code})",
                                key=unique_key,
                                use_container_width=True,
                                type=btn_style
                            ):
                                st.session_state['selected_sector_stock'] = (code, name)
                                st.rerun()
        else:
            # 테마 미선택 시 안내
            st.markdown("""
            <div style='
                background: #f8f9fa;
                border-radius: 12px;
                padding: 3rem;
                text-align: center;
            '>
                <div style='font-size: 3rem; margin-bottom: 1rem;'>👈</div>
                <h3 style='color: #333; margin: 0;'>테마를 선택해주세요</h3>
                <p style='color: #666; margin-top: 0.5rem;'>
                    왼쪽에서 테마를 선택하면<br>해당 종목 목록이 표시됩니다.
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ========== 하단: 선택된 종목의 차트 및 정보 ==========
    st.markdown("---")

    selected_stock = st.session_state.get('selected_sector_stock')

    if selected_stock:
        code, name = selected_stock
        _render_stock_detail_below(api, code, name)
    else:
        # 종목 미선택 시 테마 통계 표시
        if not current_theme:
            _render_theme_stats()


def _render_stock_management_ui(theme_name: str):
    """종목 추가/제거 관리 UI"""

    st.markdown("""
    <div style='background: #fff3cd; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ffc107;'>
        <span style='font-size: 1rem;'>⚙️</span>
        <span style='color: #856404; font-size: 0.9rem; margin-left: 0.5rem;'>
            관리 모드: 종목 추가/제거가 가능합니다
        </span>
    </div>
    """, unsafe_allow_html=True)

    # 종목 추가 폼
    with st.expander("➕ 종목 추가", expanded=True):
        # 종목 검색 - multiselect 실시간 자동완성 방식
        st.markdown("**🔍 종목 검색** (KOSPI/KOSDAQ 전체 종목)")

        # 전체 종목 목록 가져오기 (캐시됨)
        all_stocks = _get_all_searchable_stocks()
        total_count = len(all_stocks)
        st.caption(f"총 {total_count:,}개 종목 검색 가능")

        # multiselect로 종목 선택 (실시간 검색 지원)
        stock_options = [f"{name} ({code})" for code, name in all_stocks]

        selected_stocks = st.multiselect(
            "종목 선택 (검색어 입력 시 자동 필터링)",
            options=stock_options,
            default=[],
            placeholder="종목명 또는 코드 입력...",
            key=f"stock_multiselect_{theme_name}",
            help="입력하면 실시간으로 종목이 필터링됩니다"
        )

        # 선택된 종목들 추가
        if selected_stocks:
            st.markdown(f"**선택된 종목: {len(selected_stocks)}개**")

            for selected in selected_stocks:
                # "삼성전자 (005930)" 형식에서 파싱
                try:
                    name_part = selected.rsplit(" (", 1)[0]
                    code_part = selected.rsplit(" (", 1)[1].rstrip(")")

                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.info(f"📌 {name_part} ({code_part})")
                    with col2:
                        if st.button("➕ 추가", key=f"add_{theme_name}_{code_part}", type="primary"):
                            success, msg = add_stock_to_theme(theme_name, code_part, name_part)
                            if success:
                                st.success(msg)
                            else:
                                st.warning(msg)
                            st.rerun()
                except Exception as e:
                    st.error(f"파싱 오류: {selected}")

        st.markdown("---")
        st.markdown("**✏️ 직접 입력** (검색되지 않는 종목)")
        col1, col2, col3 = st.columns([2, 3, 1])
        with col1:
            new_code = st.text_input("종목코드", placeholder="예: 005930", key="new_stock_code")
        with col2:
            new_name = st.text_input("종목명", placeholder="예: 삼성전자", key="new_stock_name")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("추가", key="add_stock_btn", type="primary"):
                if new_code and new_name:
                    # 코드 정규화 (6자리)
                    code = new_code.strip().zfill(6)
                    name = new_name.strip()
                    success, msg = add_stock_to_theme(theme_name, code, name)
                    if success:
                        st.success(msg)
                    else:
                        st.warning(msg)
                    st.rerun()
                else:
                    st.warning("종목코드와 종목명을 모두 입력하세요.")

    # 변경 사항 요약 및 초기화
    changes = get_custom_changes_summary()
    theme_added = (changes.get('added') or {}).get(theme_name, [])
    theme_removed = (changes.get('removed') or {}).get(theme_name, [])

    if theme_added or theme_removed:
        with st.expander(f"📊 '{theme_name}' 변경 사항", expanded=False):
            if theme_added:
                st.markdown("**➕ 추가된 종목:**")
                for code, name in theme_added:
                    st.markdown(f"- {name} ({code})")

            if theme_removed:
                st.markdown("**➖ 제거된 종목:**")
                # 원본 데이터에서 이름 가져오기
                from data.theme_stocks import THEME_STOCKS
                base_stocks = {code: name for code, name in THEME_STOCKS.get(theme_name, [])}
                for code in theme_removed:
                    name = base_stocks.get(code, code)
                    st.markdown(f"- {name} ({code})")

            if st.button(f"🔄 '{theme_name}' 변경 초기화", key="reset_theme_changes"):
                success, msg = reset_custom_changes(theme_name)
                st.success(msg)
                st.rerun()


def _sort_stocks_by_option(api, stocks: list, sort_option: str) -> list:
    """종목을 옵션에 따라 정렬 (거래량, 1개월/6개월 수익률)"""
    stock_data = []

    # 수익률 계산을 위한 기간 설정
    if "1개월" in sort_option:
        days = 30
    elif "6개월" in sort_option:
        days = 180
    else:
        days = 0  # 거래량만 조회

    for code, name in stocks:
        try:
            info = api.get_stock_info(code) if api else None
            price = info.get('price', 0) if info else 0
            volume = info.get('volume', 0) if info else 0

            # 수익률 계산
            return_rate = 0
            if days > 0 and api:
                try:
                    from datetime import datetime, timedelta
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
                    df = api.get_daily_price(code, start_date=start_date, end_date=end_date)
                    if df is not None and len(df) >= 2:
                        first_price = df.iloc[0]['close']
                        last_price = df.iloc[-1]['close']
                        if first_price > 0:
                            return_rate = ((last_price - first_price) / first_price) * 100
                except:
                    pass

            if price > 0 or volume > 0:
                stock_data.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'volume': volume,
                    'return_rate': return_rate,
                })
            else:
                # 샘플 데이터
                np.random.seed(hash(code) % 2**32)
                stock_data.append({
                    'code': code,
                    'name': name,
                    'price': np.random.randint(10000, 200000),
                    'volume': np.random.randint(10000, 500000),
                    'return_rate': np.random.uniform(-20, 40),
                })
        except:
            np.random.seed(hash(code) % 2**32)
            stock_data.append({
                'code': code,
                'name': name,
                'price': np.random.randint(10000, 200000),
                'volume': np.random.randint(10000, 500000),
                'return_rate': np.random.uniform(-20, 40),
            })

    # 정렬
    if sort_option == "거래량 많은순":
        stock_data.sort(key=lambda x: x['volume'], reverse=True)
    elif "수익률순" in sort_option:
        stock_data.sort(key=lambda x: x['return_rate'], reverse=True)

    # 세션에 데이터 저장 (표시용)
    st.session_state['sorted_stock_data'] = stock_data

    return [(s['code'], s['name']) for s in stock_data]


def _render_sorted_stock_list(api, stocks: list, sort_option: str, manage_mode: bool = False, theme_name: str = None):
    """정렬된 종목 목록을 테이블 형식으로 표시"""

    stock_data = st.session_state.get('sorted_stock_data', [])

    if not stock_data:
        st.info("데이터 로딩 중...")
        return

    # 정렬 타입에 따른 색상/아이콘
    if "거래량" in sort_option:
        highlight_color = "#667eea"
        icon = "📊"
        desc = "거래량이 많은 종목 (관심도 높음)"
    elif "1개월" in sort_option:
        highlight_color = "#11998e"
        icon = "📈"
        desc = "1개월 주가 상승률 높은 종목 (단기 상승)"
    elif "6개월" in sort_option:
        highlight_color = "#f5576c"
        icon = "🚀"
        desc = "6개월 주가 상승률 높은 종목 (중기 상승)"
    else:
        highlight_color = "#667eea"
        icon = "📋"
        desc = "종목 목록"

    st.markdown(f"""
    <div style='background: {highlight_color}15; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid {highlight_color};'>
        <span style='font-size: 1.1rem;'>{icon}</span>
        <span style='color: #333; font-size: 0.9rem; margin-left: 0.5rem;'>{desc}</span>
    </div>
    """, unsafe_allow_html=True)

    # 테이블 형식으로 표시
    for i, data in enumerate(stock_data[:20]):  # 상위 20개만
        code = data['code']
        name = data['name']
        price = data['price']
        volume = data['volume']
        return_rate = data.get('return_rate', 0)

        # 수익률에 따른 색상
        if return_rate > 10:
            rate_color = "#ef5350"  # 강한 상승 (빨강)
        elif return_rate > 0:
            rate_color = "#11998e"  # 상승 (초록)
        elif return_rate > -10:
            rate_color = "#ffc107"  # 약간 하락 (노랑)
        else:
            rate_color = "#26a69a"  # 강한 하락 (청록)

        if manage_mode:
            col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 1.5, 1.5, 0.8, 0.5])
        else:
            col1, col2, col3, col4, col5 = st.columns([0.5, 2, 1.5, 1.5, 1])

        with col1:
            st.markdown(f"**{i+1}**")

        with col2:
            is_selected = st.session_state.get('selected_sector_stock') == (code, name)
            if st.button(f"{name} ({code})", key=f"sorted_{code}", type="primary" if is_selected else "secondary"):
                st.session_state['selected_sector_stock'] = (code, name)
                st.rerun()

        with col3:
            st.markdown(f"**{price:,.0f}**원")

        with col4:
            # 수익률 표시
            rate_sign = "+" if return_rate > 0 else ""
            st.markdown(f"""
            <div style='display: flex; align-items: center; justify-content: center;'>
                <span style='color: {rate_color}; font-size: 0.9rem; font-weight: 700;'>{rate_sign}{return_rate:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            vol_str = f"{volume/10000:,.0f}만" if volume >= 10000 else f"{volume:,.0f}"
            st.caption(vol_str)

        if manage_mode and theme_name:
            with col6:
                if st.button("🗑️", key=f"sorted_del_{code}", help=f"{name} 제거"):
                    success, msg = remove_stock_from_theme(theme_name, code)
                    if success:
                        st.success(msg)
                    else:
                        st.warning(msg)
                    st.rerun()


# _get_api_connection 함수는 dashboard/utils/api_helper.py로 통합됨
# 아래 호출부에서 get_api_connection() 사용


def _render_stock_detail_below(api, code: str, name: str):
    """종목 상세 정보 (하단에 표시)"""

    # 헤더: 종목명 + 테마 배지
    stock_themes = get_stock_themes(code)
    theme_badges = ""
    colors = ['#667eea', '#f5576c', '#11998e', '#ffc107', '#17a2b8', '#6f42c1']
    for i, theme in enumerate(stock_themes):
        color = colors[i % len(colors)]
        theme_badges += f"<span class='theme-badge' style='background: {color}20; color: {color};'>{theme}</span>"

    st.markdown(f"""
    <div class='selected-stock-header'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <h2 style='color: white; margin: 0; font-size: 1.5rem;'>{name}</h2>
                <span style='color: rgba(255,255,255,0.7); font-size: 0.9rem;'>{code}</span>
            </div>
            <div>{theme_badges}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3단 레이아웃: 차트(넓게) | 기본정보 | 재무정보
    col_chart, col_info = st.columns([2, 1])

    with col_chart:
        _render_stock_chart(api, code, name)

    with col_info:
        _render_stock_info_compact(api, code, name)


def _detect_swing_points(data: pd.DataFrame, order: int = 5) -> tuple:
    """
    스윙 고점/저점 탐지 (scipy.signal.argrelextrema 사용)

    Args:
        data: OHLCV 데이터프레임 (high, low 컬럼 필요)
        order: 비교할 이웃 데이터 수 (클수록 덜 민감)

    Returns:
        (swing_high_idx, swing_low_idx) - 각각 numpy 배열
    """
    if data is None or len(data) < order * 2 + 1:
        return np.array([]), np.array([])

    highs = data['high'].values
    lows = data['low'].values

    swing_high_idx = argrelextrema(highs, np.greater, order=order)[0]
    swing_low_idx = argrelextrema(lows, np.less, order=order)[0]

    return swing_high_idx, swing_low_idx


def _render_stock_chart(api, code: str, name: str):
    """종목 차트"""

    # 기간 및 옵션 선택
    opt_col1, opt_col2 = st.columns([1, 1])
    with opt_col1:
        period = st.selectbox(
            "📅 기간",
            ["1개월", "3개월", "6개월", "1년"],
            index=2,
            key=f"chart_period_{code}"
        )
    with opt_col2:
        show_swing_points = st.checkbox("📍 저점/고점", value=True, key=f"swing_{code}", help="스윙 저점/고점 마커 표시")

    period_days = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    days = period_days.get(period, 180)

    # 데이터 로드
    chart_data = _get_chart_data(api, code, days)

    if chart_data is None or len(chart_data) == 0:
        chart_data = _generate_sample_chart_data(code, days)
        is_sample = True
    else:
        is_sample = False

    # 차트 생성
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.75, 0.25]
    )

    # 캔들스틱
    fig.add_trace(
        go.Candlestick(
            x=chart_data['date'],
            open=chart_data['open'],
            high=chart_data['high'],
            low=chart_data['low'],
            close=chart_data['close'],
            name='가격',
            increasing_line_color='#FF3B30',
            decreasing_line_color='#007AFF',
            increasing_fillcolor='#FF3B30',
            decreasing_fillcolor='#007AFF',
            line=dict(width=1),
            whiskerwidth=0.8
        ),
        row=1, col=1
    )

    # 이동평균선
    for ma_period, color, dash in [(5, '#FF6B6B', 'solid'), (20, '#4ECDC4', 'solid'),
                                    (60, '#45B7D1', 'dot'), (120, '#96CEB4', 'dot')]:
        if len(chart_data) >= ma_period:
            ma = chart_data['close'].rolling(ma_period).mean()
            fig.add_trace(
                go.Scatter(
                    x=chart_data['date'],
                    y=ma,
                    mode='lines',
                    name=f'MA{ma_period}',
                    line=dict(color=color, width=1, dash=dash)
                ),
                row=1, col=1
            )

    # 스윙 저점/고점 마커
    if show_swing_points:
        swing_order = 5
        swing_high_idx, swing_low_idx = _detect_swing_points(chart_data, order=swing_order)

        # 스윙 저점 (녹색 삼각형)
        if len(swing_low_idx) > 0:
            recent_low_idx = swing_low_idx[-15:] if len(swing_low_idx) > 15 else swing_low_idx
            low_dates = chart_data['date'].iloc[recent_low_idx]
            low_prices = chart_data['low'].iloc[recent_low_idx]

            price_range = chart_data['high'].max() - chart_data['low'].min()
            marker_offset = price_range * 0.02

            fig.add_trace(
                go.Scatter(
                    x=low_dates,
                    y=low_prices - marker_offset,
                    mode='markers+text',
                    name='스윙 저점',
                    marker=dict(
                        symbol='triangle-up',
                        size=12,
                        color='#00C853',
                        line=dict(color='white', width=1)
                    ),
                    text=[f'{p:,.0f}' for p in low_prices],
                    textposition='bottom center',
                    textfont=dict(size=9, color='#00C853'),
                    showlegend=True
                ),
                row=1, col=1
            )

        # 스윙 고점 (빨간 역삼각형)
        if len(swing_high_idx) > 0:
            recent_high_idx = swing_high_idx[-15:] if len(swing_high_idx) > 15 else swing_high_idx
            high_dates = chart_data['date'].iloc[recent_high_idx]
            high_prices = chart_data['high'].iloc[recent_high_idx]

            price_range = chart_data['high'].max() - chart_data['low'].min()
            marker_offset = price_range * 0.02

            fig.add_trace(
                go.Scatter(
                    x=high_dates,
                    y=high_prices + marker_offset,
                    mode='markers+text',
                    name='스윙 고점',
                    marker=dict(
                        symbol='triangle-down',
                        size=12,
                        color='#FF3B30',
                        line=dict(color='white', width=1)
                    ),
                    text=[f'{p:,.0f}' for p in high_prices],
                    textposition='top center',
                    textfont=dict(size=9, color='#FF3B30'),
                    showlegend=True
                ),
                row=1, col=1
            )

        # ========== 추세선 추가 (저점/고점 연결) ==========
        from scipy import stats

        # 가격 범위 계산 (Y축 클리핑용)
        price_high = chart_data['high'].max()
        price_low = chart_data['low'].min()
        price_margin = (price_high - price_low) * 0.1  # 10% 여유

        # 상승 추세선 (저점 연결)
        if len(swing_low_idx) >= 2:
            recent_lows = swing_low_idx[-5:] if len(swing_low_idx) >= 5 else swing_low_idx
            tl_low_x = list(recent_lows)
            tl_low_y = [chart_data['low'].iloc[i] for i in recent_lows]
            slope, intercept, _, _, _ = stats.linregress(tl_low_x, tl_low_y)

            if slope > 0:
                tl_x_start = min(recent_lows)
                tl_x_end = len(chart_data) - 1
                tl_y_start = slope * tl_x_start + intercept
                tl_y_end = slope * tl_x_end + intercept

                # Y값 클리핑 (차트 범위 내로 제한)
                tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                fig.add_trace(go.Scatter(
                    x=[chart_data['date'].iloc[tl_x_start], chart_data['date'].iloc[tl_x_end]],
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
            tl_high_y = [chart_data['high'].iloc[i] for i in recent_highs]
            slope, intercept, _, _, _ = stats.linregress(tl_high_x, tl_high_y)

            if slope < 0:
                tl_x_start = min(recent_highs)
                tl_x_end = len(chart_data) - 1
                tl_y_start = slope * tl_x_start + intercept
                tl_y_end = slope * tl_x_end + intercept

                # Y값 클리핑 (차트 범위 내로 제한)
                tl_y_start = max(price_low - price_margin, min(price_high + price_margin, tl_y_start))
                tl_y_end = max(price_low - price_margin, min(price_high + price_margin, tl_y_end))

                fig.add_trace(go.Scatter(
                    x=[chart_data['date'].iloc[tl_x_start], chart_data['date'].iloc[tl_x_end]],
                    y=[tl_y_start, tl_y_end],
                    mode='lines',
                    name='하락 추세선',
                    line=dict(color='#FF3B30', width=2, dash='solid'),
                    hovertemplate='하락 추세선<extra></extra>',
                    showlegend=True
                ), row=1, col=1)

    # 거래량
    colors = ['#ef5350' if row['close'] >= row['open'] else '#26a69a'
              for _, row in chart_data.iterrows()]

    fig.add_trace(
        go.Bar(
            x=chart_data['date'],
            y=chart_data['volume'],
            name='거래량',
            marker_color=colors,
            opacity=0.6
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=420,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
        xaxis_rangeslider_visible=False
    )

    fig.update_yaxes(title_text="", row=1, col=1)
    fig.update_yaxes(title_text="", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

    if is_sample:
        st.caption("⚠️ 샘플 데이터입니다.")

    # 최근 가격 요약 (데이터 존재 여부 체크)
    if len(chart_data) == 0:
        st.warning("차트 데이터를 불러올 수 없습니다.")
        return

    latest = chart_data.iloc[-1]
    prev = chart_data.iloc[-2] if len(chart_data) > 1 else latest
    change = latest['close'] - prev['close']
    change_pct = (change / prev['close']) * 100 if prev['close'] > 0 else 0

    # 등락 색상 설정
    badge_bg = "#FF4444" if change >= 0 else "#4444FF"
    rate_sign = "+" if change_pct >= 0 else ""

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
            <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>현재가</div>
            <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{latest['close']:,.0f}원</div>
            <span style='background: {badge_bg}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: bold; font-size: 0.9rem;'>{rate_sign}{change_pct:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
            <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>고가</div>
            <div style='color: #FF4444; font-size: 1.3rem; font-weight: bold;'>{latest['high']:,.0f}원</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
            <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>저가</div>
            <div style='color: #4444FF; font-size: 1.3rem; font-weight: bold;'>{latest['low']:,.0f}원</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        vol = latest['volume']
        vol_str = f"{vol/10000:,.0f}만" if vol >= 10000 else f"{vol:,.0f}"
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid #333;'>
            <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>거래량</div>
            <div style='color: #fff; font-size: 1.3rem; font-weight: bold;'>{vol_str}</div>
        </div>
        """, unsafe_allow_html=True)


def _render_stock_info_compact(api, code: str, name: str):
    """종목 기본정보 (컴팩트)"""

    info = _get_stock_info(api, code)

    if info is None:
        # 샘플 데이터
        np.random.seed(hash(code) % 2**32)
        info = {
            'price': np.random.randint(10000, 300000),
            'change': np.random.randint(-5000, 5000),
            'change_rate': np.random.uniform(-5, 5),
            'market_cap': np.random.randint(1000, 50000) * 1e8,
            'per': np.random.uniform(5, 30),
            'pbr': np.random.uniform(0.5, 3),
            'eps': np.random.randint(500, 10000),
            'bps': np.random.randint(10000, 100000),
        }
        is_sample = True
    else:
        is_sample = False

    st.markdown("#### 📊 투자 지표")

    # PER/PBR
    per = info.get('per', 0)
    pbr = info.get('pbr', 0)
    eps = info.get('eps', 0)
    bps = info.get('bps', 0)
    market_cap = info.get('market_cap', 0)

    # 적자 기업 색상 처리
    deficit_color = "#DC143C"

    # PER 표시 (적자=빨강)
    if per > 0:
        per_display = f"<span style='color: #fff;'>{per:.2f}</span>"
    elif per < 0:
        per_display = f"<span style='color: {deficit_color};'>{per:.2f} (적자)</span>"
    else:
        per_display = "N/A"

    # EPS 표시 (적자=빨강)
    if eps > 0:
        eps_display = f"<span style='color: #fff;'>{eps:,.0f}원</span>"
    elif eps < 0:
        eps_display = f"<span style='color: {deficit_color};'>{eps:,.0f}원</span>"
    else:
        eps_display = "N/A"

    cap_display = f"{market_cap/1e8:,.0f}억" if market_cap > 0 else "N/A"

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 1rem; border-radius: 10px; border: 1px solid #333;'>
        <table style='width: 100%; font-size: 0.9rem;'>
            <tr><td style='color: #888; padding: 0.4rem 0;'>시가총액</td><td style='text-align: right; font-weight: 600; color: #fff;'>{cap_display}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>PER</td><td style='text-align: right; font-weight: 600;'>{per_display}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>PBR</td><td style='text-align: right; font-weight: 600; color: #fff;'>{pbr:.2f}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>EPS</td><td style='text-align: right; font-weight: 600;'>{eps_display}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>BPS</td><td style='text-align: right; font-weight: 600; color: #fff;'>{bps:,.0f}원</td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    if is_sample:
        st.caption("⚠️ 샘플 데이터")

    # 간단한 재무 차트
    st.markdown("#### 💰 실적 추이")

    np.random.seed(hash(code) % 2**32)
    years = ['22', '23', '24', '25E']
    revenue = [np.random.randint(3000, 30000) for _ in range(4)]
    revenue = sorted(revenue)  # 성장 트렌드

    fig = go.Figure(data=[
        go.Bar(x=years, y=revenue, marker_color='#667eea', text=revenue, textposition='outside')
    ])
    fig.update_layout(
        height=180,
        margin=dict(t=20, b=20, l=20, r=20),
        yaxis_title="매출(억)",
        font=dict(size=10)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("⚠️ 샘플 데이터")


def _render_theme_stats():
    """테마 통계 (종목 미선택 시)"""

    st.markdown("### 📊 테마별 종목 현황")

    # 테마별 종목 수
    theme_data = []
    for theme in get_all_theme_names():
        count = len(get_theme_stock_codes(theme))
        theme_data.append({'테마': theme, '종목수': count})

    df = pd.DataFrame(theme_data).sort_values('종목수', ascending=False)

    # 2열로 표시
    col1, col2 = st.columns(2)

    with col1:
        # 가로 막대 차트
        fig = go.Figure(data=[
            go.Bar(
                y=df['테마'],
                x=df['종목수'],
                orientation='h',
                marker_color='#667eea',
                text=df['종목수'],
                textposition='outside'
            )
        ])
        fig.update_layout(
            height=400,
            margin=dict(t=20, b=20, l=20, r=40),
            yaxis=dict(autorange="reversed"),
            xaxis_title="종목 수"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 파이 차트
        fig = go.Figure(data=[
            go.Pie(
                labels=df['테마'],
                values=df['종목수'],
                hole=0.4,
                textinfo='label+percent',
                textposition='outside'
            )
        ])
        fig.update_layout(
            height=400,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)


def _generate_sample_chart_data(code: str, days: int) -> pd.DataFrame:
    """샘플 차트 데이터 생성"""
    np.random.seed(hash(code) % 2**32)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    base_price = np.random.randint(20000, 200000)
    returns = np.random.randn(days) * 0.02
    prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame({
        'date': dates,
        'open': prices * np.random.uniform(0.99, 1.01, days),
        'high': prices * np.random.uniform(1.01, 1.03, days),
        'low': prices * np.random.uniform(0.97, 0.99, days),
        'close': prices,
        'volume': np.random.randint(50000, 500000, days)
    })


def _get_chart_data(api, code: str, days: int) -> pd.DataFrame:
    """차트 데이터 조회"""
    if api is None:
        return None
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        # 올바른 메서드명 사용: get_daily_price (단수)
        data = api.get_daily_price(code, start_date=start_date, end_date=end_date)
        if data is not None and len(data) > 0:
            return data
    except Exception as e:
        print(f"차트 데이터 조회 오류 ({code}): {e}")
    return None


def _get_stock_info(api, code: str) -> dict:
    """종목 정보 조회"""
    if api is None:
        return None
    try:
        info = api.get_stock_info(code)
        return info
    except Exception as e:
        print(f"종목 정보 조회 오류 ({code}): {e}")
        return None


def _search_stocks(query: str) -> list:
    """
    종목 검색 (로컬 데이터 + API)
    Returns: [(code, name), ...]
    """
    results = []
    query_lower = query.lower().strip()

    # 1. 로컬 종목 마스터 데이터에서 검색
    stock_master = _get_stock_master()
    if stock_master:
        for code, name in stock_master:
            if query_lower in name.lower() or query in code:
                results.append((code, name))

    # 2. 기존 테마 데이터에서도 검색
    for theme_name, stocks in THEME_STOCKS.items():
        for code, name in stocks:
            if query_lower in name.lower() or query in code:
                if (code, name) not in results:
                    results.append((code, name))

    # 중복 제거 및 정렬
    seen = set()
    unique_results = []
    for code, name in results:
        if code not in seen:
            seen.add(code)
            unique_results.append((code, name))

    # 이름 기준 정렬
    unique_results.sort(key=lambda x: x[1])

    return unique_results[:50]  # 최대 50개


@st.cache_data(ttl=3600)
def _get_all_searchable_stocks() -> list:
    """
    검색 가능한 전체 종목 목록 반환 (selectbox용)
    테마 데이터 + 기본 종목 마스터 통합
    """
    all_stocks = {}

    # 1. 기본 종목 마스터
    stock_master = _get_stock_master()
    for code, name in stock_master:
        all_stocks[code] = name

    # 2. 테마 데이터의 모든 종목 추가
    for theme_name, stocks in THEME_STOCKS.items():
        for code, name in stocks:
            if code not in all_stocks:
                all_stocks[code] = name

    # 리스트로 변환 및 이름순 정렬
    result = [(code, name) for code, name in all_stocks.items()]
    result.sort(key=lambda x: x[1])

    return result


@st.cache_data(ttl=86400)  # 24시간 캐시 (종목 목록은 자주 변하지 않음)
def _get_stock_master() -> list:
    """
    종목 마스터 데이터 로드 (KOSPI + KOSDAQ 전체)
    FinanceDataReader에서 가져오거나 캐시 파일 사용
    """
    import os

    # 캐시 파일 경로
    cache_path = os.path.join(PROJECT_ROOT, 'data', 'stock_master.csv')

    # 캐시 파일이 있고 최근 7일 이내면 로드
    if os.path.exists(cache_path):
        try:
            import time
            file_age = time.time() - os.path.getmtime(cache_path)
            if file_age < 7 * 24 * 3600:  # 7일 이내
                df = pd.read_csv(cache_path, dtype={'code': str})
                result = [(row['code'].zfill(6), row['name']) for _, row in df.iterrows()]
                if len(result) > 1000:  # 최소 1000개 이상이면 유효
                    return result
        except:
            pass

    # FinanceDataReader로 전체 종목 가져오기
    try:
        import FinanceDataReader as fdr

        stocks = []

        # KOSPI 종목
        kospi = fdr.StockListing('KOSPI')
        for _, row in kospi.iterrows():
            code = str(row.get('Code', row.get('Symbol', ''))).zfill(6)
            name = str(row.get('Name', ''))
            if code and name:
                # 우선주, 스팩, ETF 등 제외
                if not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']):
                    if not name.endswith(('우', '우B', '우C')):
                        stocks.append((code, name))

        # KOSDAQ 종목
        kosdaq = fdr.StockListing('KOSDAQ')
        for _, row in kosdaq.iterrows():
            code = str(row.get('Code', row.get('Symbol', ''))).zfill(6)
            name = str(row.get('Name', ''))
            if code and name:
                # 우선주, 스팩, ETF 등 제외
                if not any(x in name for x in ['스팩', 'ETF', 'ETN', '리츠']):
                    if not name.endswith(('우', '우B', '우C')):
                        stocks.append((code, name))

        # 중복 제거
        seen = set()
        unique_stocks = []
        for code, name in stocks:
            if code not in seen:
                seen.add(code)
                unique_stocks.append((code, name))

        if unique_stocks:
            # 캐시 저장
            df = pd.DataFrame(unique_stocks, columns=['code', 'name'])
            df.to_csv(cache_path, index=False)
            return unique_stocks

    except ImportError:
        print("FinanceDataReader 패키지가 필요합니다: pip install finance-datareader")
    except Exception as e:
        print(f"종목 목록 로드 오류: {e}")

    # 기본 종목 목록 반환 (주요 대형주)
    return _get_default_stock_list()


def _get_default_stock_list() -> list:
    """기본 종목 목록 (API 실패 시 fallback)"""
    return [
        # 대형주 (시가총액 상위)
        ("005930", "삼성전자"),
        ("000660", "SK하이닉스"),
        ("373220", "LG에너지솔루션"),
        ("207940", "삼성바이오로직스"),
        ("005380", "현대차"),
        ("000270", "기아"),
        ("068270", "셀트리온"),
        ("035420", "NAVER"),
        ("051910", "LG화학"),
        ("006400", "삼성SDI"),
        ("035720", "카카오"),
        ("105560", "KB금융"),
        ("055550", "신한지주"),
        ("012330", "현대모비스"),
        ("028260", "삼성물산"),
        ("096770", "SK이노베이션"),
        ("003670", "포스코퓨처엠"),
        ("005490", "POSCO홀딩스"),
        ("034730", "SK"),
        ("000810", "삼성화재"),
        ("015760", "한국전력"),
        ("017670", "SK텔레콤"),
        ("030200", "KT"),
        ("032640", "LG유플러스"),
        ("066570", "LG전자"),
        ("003550", "LG"),
        ("086790", "하나금융지주"),
        ("316140", "우리금융지주"),
        ("018260", "삼성에스디에스"),
        ("009150", "삼성전기"),
        # 반도체
        ("042700", "한미반도체"),
        ("058470", "리노공업"),
        ("036930", "주성엔지니어링"),
        ("403870", "HPSP"),
        ("357780", "솔브레인"),
        ("240810", "원익IPS"),
        ("039030", "이오테크닉스"),
        # 2차전지
        ("247540", "에코프로비엠"),
        ("086520", "에코프로"),
        ("066970", "엘앤에프"),
        # 바이오
        ("196170", "알테오젠"),
        ("000100", "유한양행"),
        ("128940", "한미약품"),
        ("326030", "SK바이오팜"),
        # 방산
        ("012450", "한화에어로스페이스"),
        ("079550", "LIG넥스원"),
        ("047810", "한국항공우주"),
        ("272210", "한화시스템"),
        # 조선
        ("329180", "HD현대중공업"),
        ("009540", "HD한국조선해양"),
        ("042660", "한화오션"),
        # 로봇
        ("277810", "레인보우로보틱스"),
        ("454910", "두산로보틱스"),
        # 엔터
        ("352820", "하이브"),
        ("035900", "JYP Ent."),
        ("041510", "에스엠"),
        # 기타
        ("036570", "엔씨소프트"),
        ("251270", "넷마블"),
        ("259960", "크래프톤"),
        ("034020", "두산에너빌리티"),
        ("052690", "한전기술"),
    ]
