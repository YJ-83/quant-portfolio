"""
공통 CSS 스타일 모듈
- 모든 뷰에서 사용하는 CSS 애니메이션과 스타일 통합
- 중복 코드 제거 및 일관성 유지
"""
import streamlit as st


# ========== 색상 팔레트 ==========
COLOR_PALETTE = {
    # 기본 색상
    'primary': '#667eea',
    'secondary': '#764ba2',
    'success': '#2ed573',
    'danger': '#ff4757',
    'warning': '#ffa502',
    'info': '#3498db',

    # 다크 테마 색상
    'dark_bg': '#1a1a2e',
    'dark_bg_secondary': '#16213e',
    'dark_card': '#2d2d3a',
    'dark_card_secondary': '#1e1e2e',

    # 텍스트 색상
    'text_primary': '#333',
    'text_secondary': '#666',
    'text_muted': '#95a5a6',
    'text_white': '#ffffff',

    # 그라디언트
    'gradient_purple': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'gradient_blue': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    'gradient_green': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
    'gradient_red': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'gradient_orange': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    'gradient_dark': 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
    'gradient_dark_card': 'linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%)',

    # 차트 색상
    'up_color': '#ff4757',  # 상승 (빨간색)
    'down_color': '#3498db',  # 하락 (파란색)
    'neutral_color': '#95a5a6',  # 보합 (회색)
}


# ========== 공통 CSS 애니메이션 ==========
COMMON_ANIMATIONS = """
@keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes rotateGear {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
}

@keyframes glow {
    0%, 100% { box-shadow: 0 0 5px rgba(102, 126, 234, 0.3); }
    50% { box-shadow: 0 0 20px rgba(102, 126, 234, 0.5); }
}
"""


# ========== 공통 카드 스타일 ==========
COMMON_CARD_STYLES = """
/* 기본 카드 스타일 */
.base-card {
    background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.08);
    animation: slideUp 0.3s ease-out;
}

/* 히어로 카드 (페이지 헤더용) */
.hero-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    animation: slideUp 0.5s ease-out;
}

.hero-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at 20% 50%, rgba(255,255,255,0.1) 0%, transparent 50%);
}

/* 메트릭 카드 */
.metric-card {
    background: linear-gradient(135deg, #2d2d3a 0%, #1e1e2e 100%);
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.08);
    text-align: center;
}

/* 설정 카드 */
.settings-card {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid #dee2e6;
    margin-bottom: 0.75rem;
}

/* API 카드 */
.api-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem;
    border-radius: 12px;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
}

/* 섹션 헤더 */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    padding: 0.5rem 0;
}

/* 다크 테마 카드 */
.dark-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    padding: 1.5rem;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
}

/* 상태 뱃지 */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}

.status-badge.success { background: rgba(46, 213, 115, 0.2); color: #2ed573; }
.status-badge.danger { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
.status-badge.warning { background: rgba(255, 165, 2, 0.2); color: #ffa502; }
.status-badge.info { background: rgba(52, 152, 219, 0.2); color: #3498db; }
.status-badge.neutral { background: rgba(149, 165, 166, 0.2); color: #95a5a6; }

/* 테이블 스타일 */
.styled-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}

.styled-table th {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.75rem;
    text-align: left;
}

.styled-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #eee;
}

.styled-table tr:hover {
    background: rgba(102, 126, 234, 0.05);
}

/* 로딩 스피너 */
.loading-spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

/* 프로그레스 바 */
.progress-bar {
    width: 100%;
    height: 8px;
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}
"""


def inject_common_styles():
    """공통 CSS 스타일을 페이지에 주입"""
    st.markdown(f"""
    <style>
    {COMMON_ANIMATIONS}
    {COMMON_CARD_STYLES}
    </style>
    """, unsafe_allow_html=True)


def get_gradient_style(gradient_type: str = 'purple') -> str:
    """그라디언트 스타일 문자열 반환"""
    gradients = {
        'purple': COLOR_PALETTE['gradient_purple'],
        'blue': COLOR_PALETTE['gradient_blue'],
        'green': COLOR_PALETTE['gradient_green'],
        'red': COLOR_PALETTE['gradient_red'],
        'orange': COLOR_PALETTE['gradient_orange'],
        'dark': COLOR_PALETTE['gradient_dark'],
        'dark_card': COLOR_PALETTE['gradient_dark_card'],
    }
    return gradients.get(gradient_type, gradients['purple'])


def get_card_html(
    title: str,
    content: str,
    icon: str = "",
    card_type: str = "base",
    extra_style: str = ""
) -> str:
    """카드 HTML 생성"""
    if card_type == "hero":
        return f"""
        <div class='hero-card' style='{extra_style}'>
            <div style='position: relative; z-index: 1;'>
                {f"<div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>{icon}</div>" if icon else ""}
                <h2 style='color: white; margin: 0 0 0.5rem 0; font-weight: 700;'>{title}</h2>
                <p style='color: rgba(255,255,255,0.9); margin: 0;'>{content}</p>
            </div>
        </div>
        """
    elif card_type == "dark":
        return f"""
        <div class='dark-card' style='{extra_style}'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;'>
                {f"<span style='font-size: 1.5rem;'>{icon}</span>" if icon else ""}
                <h4 style='margin: 0; color: white; font-weight: 700;'>{title}</h4>
            </div>
            <p style='margin: 0; color: rgba(255,255,255,0.7);'>{content}</p>
        </div>
        """
    else:  # base
        return f"""
        <div class='base-card' style='{extra_style}'>
            <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
                {f"<span style='font-size: 1.25rem;'>{icon}</span>" if icon else ""}
                <span style='font-weight: 600; color: white;'>{title}</span>
            </div>
            <p style='color: rgba(255,255,255,0.7); margin: 0;'>{content}</p>
        </div>
        """


def get_metric_card_html(
    label: str,
    value: str,
    sub_value: str = "",
    sub_color: str = "",
    icon: str = ""
) -> str:
    """메트릭 카드 HTML 생성"""
    sub_html = ""
    if sub_value:
        color = sub_color or COLOR_PALETTE['text_muted']
        sub_html = f"<p style='color: {color}; font-size: 0.85rem; margin: 0;'>{sub_value}</p>"

    return f"""
    <div class='metric-card'>
        <p style='color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;'>
            {f"{icon} " if icon else ""}{label}
        </p>
        <p style='color: white; font-size: 1.75rem; font-weight: 700; margin: 0.25rem 0;'>{value}</p>
        {sub_html}
    </div>
    """


def get_status_badge_html(text: str, status: str = "neutral") -> str:
    """상태 뱃지 HTML 생성

    Args:
        text: 뱃지 텍스트
        status: 상태 (success, danger, warning, info, neutral)
    """
    return f"<span class='status-badge {status}'>{text}</span>"


def get_change_color(change: float) -> str:
    """변동률에 따른 색상 반환"""
    if change > 0:
        return COLOR_PALETTE['up_color']
    elif change < 0:
        return COLOR_PALETTE['down_color']
    return COLOR_PALETTE['neutral_color']


def get_change_icon(change: float) -> str:
    """변동률에 따른 아이콘 반환"""
    if change > 0:
        return "▲"
    elif change < 0:
        return "▼"
    return "─"


def get_signal_color(signal: str) -> str:
    """시그널에 따른 색상 반환"""
    signal_colors = {
        'buy': COLOR_PALETTE['success'],
        'strong_buy': '#00d26a',
        'sell': COLOR_PALETTE['danger'],
        'strong_sell': '#ff3838',
        'watch': COLOR_PALETTE['warning'],
        'neutral': COLOR_PALETTE['neutral_color'],
    }
    return signal_colors.get(signal.lower(), COLOR_PALETTE['neutral_color'])
