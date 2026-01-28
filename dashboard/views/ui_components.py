"""
공통 UI 컴포넌트 - 카드, 배지, 색상 등 통일된 스타일 제공
중복 코드 제거 및 일관된 시인성(가독성) 확보
"""

# ========== 통일된 색상 정의 ==========
COLORS = {
    # 등락 색상 (상승/하락)
    'up': '#FF4444',        # 빨강 (상승)
    'down': '#4444FF',      # 파랑 (하락)
    'neutral': '#888888',   # 회색 (보합)

    # 등급 색상
    'grade_a_plus': '#00C851',  # A+ 녹색
    'grade_a': '#38ef7d',       # A 연녹색
    'grade_b': '#FFD700',       # B 금색
    'grade_c': '#FFA500',       # C 주황
    'grade_d': '#FF6B6B',       # D 빨강
    'grade_deficit': '#DC143C', # 적자 진홍

    # 차트 관련
    'volume_up': '#ef5350',     # 거래량 급증
    'volume_normal': '#888',    # 거래량 보통

    # 카드 배경
    'card_bg_start': '#1a1a2e',
    'card_bg_end': '#16213e',
    'card_border': '#333',
}

# ========== 카드 컴포넌트 ==========
def render_metric_card(label: str, value: str, change_rate: float = None,
                       show_badge: bool = True, fixed_color: str = None) -> str:
    """
    통일된 메트릭 카드 HTML 생성

    Args:
        label: 라벨 텍스트 (예: "현재가", "시가총액")
        value: 값 텍스트 (예: "50,000원", "100조")
        change_rate: 등락률 (양수=상승, 음수=하락, None=배지 없음)
        show_badge: 등락 배지 표시 여부
        fixed_color: 고정 색상 (고가=빨강, 저가=파랑 등)

    Returns:
        HTML 문자열
    """
    # 값 색상 결정
    if fixed_color:
        value_color = fixed_color
    else:
        value_color = '#fff'

    # 배지 HTML
    badge_html = ""
    if show_badge and change_rate is not None:
        badge_bg = COLORS['up'] if change_rate >= 0 else COLORS['down']
        sign = "+" if change_rate > 0 else ""
        badge_html = f"""
            <span style='background: {badge_bg}; color: white; padding: 0.2rem 0.5rem;
                         border-radius: 4px; font-weight: bold; font-size: 0.9rem;'>
                {sign}{change_rate:.2f}%
            </span>
        """

    return f"""
    <div style='background: linear-gradient(135deg, {COLORS['card_bg_start']} 0%, {COLORS['card_bg_end']} 100%);
                padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid {COLORS['card_border']};'>
        <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>{label}</div>
        <div style='color: {value_color}; font-size: 1.3rem; font-weight: bold;'>{value}</div>
        {badge_html}
    </div>
    """


def render_metric_card_large(label: str, value: str, change_rate: float = None) -> str:
    """
    큰 사이즈 메트릭 카드 (홈 페이지용)
    """
    badge_html = ""
    if change_rate is not None:
        badge_bg = COLORS['up'] if change_rate >= 0 else COLORS['down']
        if change_rate > 0:
            rate_text = f"▲ {change_rate:.2f}%"
        elif change_rate < 0:
            rate_text = f"▼ {change_rate:.2f}%"
        else:
            rate_text = "0.00%"
        badge_html = f"""
            <span style='background: {badge_bg}; color: white; padding: 0.25rem 0.6rem;
                         border-radius: 4px; font-weight: 700; font-size: 0.95rem;'>{rate_text}</span>
        """

    return f"""
    <div style='background: linear-gradient(135deg, {COLORS['card_bg_start']} 0%, {COLORS['card_bg_end']} 100%);
                padding: 1.2rem; border-radius: 16px; border: 1px solid {COLORS['card_border']};'>
        <p style='color: #888; margin: 0; font-size: 0.85rem;'>{label}</p>
        <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{value}</p>
        {badge_html}
    </div>
    """


def render_simple_card(label: str, value: str) -> str:
    """
    심플 카드 (배지 없음)
    """
    return f"""
    <div style='background: linear-gradient(135deg, {COLORS['card_bg_start']} 0%, {COLORS['card_bg_end']} 100%);
                padding: 1.2rem; border-radius: 16px; border: 1px solid {COLORS['card_border']};'>
        <p style='color: #888; margin: 0; font-size: 0.85rem;'>{label}</p>
        <p style='color: white; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0;'>{value}</p>
    </div>
    """


def render_colored_card(label: str, value: str, value_color: str) -> str:
    """
    색상 지정 카드 (고가=빨강, 저가=파랑 등)
    """
    return f"""
    <div style='background: linear-gradient(135deg, {COLORS['card_bg_start']} 0%, {COLORS['card_bg_end']} 100%);
                padding: 1rem; border-radius: 10px; text-align: center; border: 1px solid {COLORS['card_border']};'>
        <div style='color: #888; font-size: 0.85rem; margin-bottom: 0.3rem;'>{label}</div>
        <div style='color: {value_color}; font-size: 1.3rem; font-weight: bold;'>{value}</div>
    </div>
    """


# ========== 투자 지표 테이블 ==========
def render_investment_table(per: float, pbr: float, eps: float, bps: float,
                           market_cap: float = 0, is_sample: bool = False) -> str:
    """
    투자 지표 테이블 HTML 생성

    Args:
        per, pbr, eps, bps: 투자 지표
        market_cap: 시가총액 (선택)
        is_sample: 샘플 데이터 여부
    """
    # PER 표시 (적자 기업 처리)
    if per > 0:
        per_display = f"{per:.2f}"
    elif per < 0:
        per_display = f"<span style='color: {COLORS['grade_deficit']};'>{per:.2f} (적자)</span>"
    else:
        per_display = "N/A"

    # EPS 표시 (적자 기업도 음수로 표시)
    if eps != 0:
        eps_color = COLORS['grade_deficit'] if eps < 0 else '#fff'
        eps_display = f"<span style='color: {eps_color};'>{eps:,.0f}원</span>"
    else:
        eps_display = "N/A"

    # 시가총액 표시
    if market_cap > 0:
        cap_display = f"{market_cap/1e8:,.0f}억"
        cap_row = f"<tr><td style='color: #888; padding: 0.4rem 0;'>시가총액</td><td style='text-align: right; font-weight: 600; color: #fff;'>{cap_display}</td></tr>"
    else:
        cap_row = ""

    sample_note = "<br><span style='color: #888; font-size: 0.75rem;'>⚠️ 샘플 데이터</span>" if is_sample else ""

    return f"""
    <div style='background: linear-gradient(135deg, {COLORS['card_bg_start']} 0%, {COLORS['card_bg_end']} 100%);
                padding: 1rem; border-radius: 10px; border: 1px solid {COLORS['card_border']};'>
        <table style='width: 100%; font-size: 0.9rem;'>
            {cap_row}
            <tr><td style='color: #888; padding: 0.4rem 0;'>PER</td><td style='text-align: right; font-weight: 600; color: #fff;'>{per_display}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>PBR</td><td style='text-align: right; font-weight: 600; color: #fff;'>{pbr:.2f}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>EPS</td><td style='text-align: right; font-weight: 600;'>{eps_display}</td></tr>
            <tr><td style='color: #888; padding: 0.4rem 0;'>BPS</td><td style='text-align: right; font-weight: 600; color: #fff;'>{bps:,.0f}원</td></tr>
        </table>
        {sample_note}
    </div>
    """


# ========== 등급 배지 ==========
def get_grade_style(score: float, is_deficit: bool = False) -> tuple:
    """
    점수에 따른 등급, 색상, 설명 반환

    Returns:
        (grade, color, description)
    """
    if is_deficit:
        return "적자", COLORS['grade_deficit'], "적자 기업"
    elif score >= 70:
        return "A", COLORS['grade_a'], "매우 우수"
    elif score >= 50:
        return "B", COLORS['grade_b'], "양호"
    elif score >= 30:
        return "C", COLORS['grade_c'], "보통"
    else:
        return "D", COLORS['grade_d'], "미흡"


def get_chart_grade_style(score: float) -> tuple:
    """
    차트 기술분석 등급 반환

    Returns:
        (grade, color, description)
    """
    if score >= 70:
        return "A", COLORS['grade_a'], "강세"
    elif score >= 50:
        return "B", COLORS['grade_b'], "중립"
    elif score >= 30:
        return "C", COLORS['grade_c'], "약세"
    else:
        return "D", COLORS['grade_d'], "매우약세"


# ========== 유틸리티 함수 ==========
def format_price(price: float) -> str:
    """가격 포맷팅"""
    return f"{price:,.0f}원"


def format_volume(volume: float) -> str:
    """거래량 포맷팅"""
    if volume >= 100000000:
        return f"{volume/100000000:.1f}억"
    elif volume >= 10000:
        return f"{volume/10000:,.0f}만"
    else:
        return f"{volume:,.0f}"


def format_market_cap(cap: float) -> str:
    """시가총액 포맷팅"""
    if cap >= 1e12:
        return f"{cap/1e12:.1f}조"
    elif cap >= 1e8:
        return f"{cap/1e8:,.0f}억"
    else:
        return f"{cap:,.0f}"


def format_change_rate(rate: float) -> tuple:
    """
    등락률 포맷팅

    Returns:
        (text, color, sign)
    """
    color = COLORS['up'] if rate > 0 else COLORS['down'] if rate < 0 else COLORS['neutral']
    sign = "+" if rate > 0 else ""

    if rate > 0:
        text = f"▲ {rate:.2f}%"
    elif rate < 0:
        text = f"▼ {rate:.2f}%"
    else:
        text = "0.00%"

    return text, color, sign
