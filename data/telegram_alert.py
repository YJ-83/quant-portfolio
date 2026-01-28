"""
텔레그램 알림 모듈
조건 충족 시 텔레그램으로 알림 전송
"""
import os
import json
import requests
from datetime import datetime
from typing import Optional, List, Dict
import threading
import time

# 설정 파일 경로
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'telegram_config.json')


class TelegramAlert:
    """텔레그램 알림 클래스"""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        초기화

        Args:
            bot_token: 텔레그램 봇 토큰 (없으면 환경변수에서 로드)
            chat_id: 채팅 ID (없으면 환경변수에서 로드)
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        self._alert_history = []

    def is_configured(self) -> bool:
        """텔레그램 설정 여부 확인"""
        return self.enabled

    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        텔레그램 메시지 전송

        Args:
            message: 전송할 메시지 (HTML 또는 Markdown)
            parse_mode: 파싱 모드 ('HTML' 또는 'Markdown')

        Returns:
            성공 여부
        """
        if not self.enabled:
            print("[Telegram] 설정되지 않음 - 메시지 전송 건너뜀")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                self._alert_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': message[:100],
                    'success': True
                })
                return True
            else:
                print(f"[Telegram] 전송 실패: {response.text}")
                return False

        except Exception as e:
            print(f"[Telegram] 오류: {e}")
            return False

    def send_price_alert(self, stock_code: str, stock_name: str,
                         current_price: float, target_price: float,
                         alert_type: str = 'target') -> bool:
        """
        가격 알림 전송

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            current_price: 현재가
            target_price: 목표가
            alert_type: 알림 유형 ('target', 'stop_loss', 'breakout')
        """
        type_emoji = {
            'target': '🎯',
            'stop_loss': '🔴',
            'breakout': '🚀'
        }

        type_text = {
            'target': '목표가 도달',
            'stop_loss': '손절가 도달',
            'breakout': '돌파 신호'
        }

        emoji = type_emoji.get(alert_type, '📢')
        title = type_text.get(alert_type, '가격 알림')

        message = f"""
{emoji} <b>{title}</b>

<b>{stock_name}</b> ({stock_code})
━━━━━━━━━━━━━━━
현재가: <b>{current_price:,.0f}원</b>
목표가: {target_price:,.0f}원
도달률: {(current_price / target_price * 100):.1f}%
━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message(message)

    def send_signal_alert(self, stock_code: str, stock_name: str,
                          signal_type: str, signal_name: str,
                          current_price: float, change_rate: float,
                          additional_info: dict = None) -> bool:
        """
        기술적 시그널 알림 전송

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            signal_type: 시그널 유형 ('buy', 'sell')
            signal_name: 시그널명 (예: 'RSI 과매도 탈출')
            current_price: 현재가
            change_rate: 등락률
            additional_info: 추가 정보 (RSI, MACD 등)
        """
        if signal_type == 'buy':
            emoji = '📈'
            title = '매수 시그널'
            color_text = '🟢'
        else:
            emoji = '📉'
            title = '매도 시그널'
            color_text = '🔴'

        change_sign = '+' if change_rate > 0 else ''

        message = f"""
{emoji} <b>{title}</b>

<b>{stock_name}</b> ({stock_code})
━━━━━━━━━━━━━━━
{color_text} <b>{signal_name}</b>

현재가: <b>{current_price:,.0f}원</b> ({change_sign}{change_rate:.2f}%)
"""

        if additional_info:
            if 'rsi' in additional_info:
                message += f"RSI: {additional_info['rsi']:.1f}\n"
            if 'macd' in additional_info:
                message += f"MACD: {additional_info['macd']:.2f}\n"
            if 'volume_ratio' in additional_info:
                message += f"거래량비: {additional_info['volume_ratio']:.1f}배\n"

        message += f"""━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message(message)

    def send_portfolio_summary(self, portfolio_data: dict) -> bool:
        """
        포트폴리오 일일 요약 전송

        Args:
            portfolio_data: 포트폴리오 데이터
        """
        total_value = portfolio_data.get('total_value', 0)
        total_return = portfolio_data.get('total_return', 0)
        daily_return = portfolio_data.get('daily_return', 0)
        positions = portfolio_data.get('positions', [])

        return_emoji = '📈' if daily_return >= 0 else '📉'
        return_sign = '+' if daily_return >= 0 else ''

        message = f"""
📊 <b>일일 포트폴리오 요약</b>

{return_emoji} 오늘의 수익률: <b>{return_sign}{daily_return:.2f}%</b>
━━━━━━━━━━━━━━━
💰 총 평가금액: <b>{total_value:,.0f}원</b>
📈 누적 수익률: {return_sign if total_return >= 0 else ''}{total_return:.2f}%
📊 보유 종목 수: {len(positions)}개

<b>상위 종목</b>
"""
        for i, pos in enumerate(positions[:5], 1):
            pos_sign = '+' if pos.get('return', 0) >= 0 else ''
            message += f"{i}. {pos.get('name', '?')}: {pos_sign}{pos.get('return', 0):.2f}%\n"

        message += f"""
━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message(message)

    def send_rebalancing_reminder(self, next_date: str, portfolio_info: dict = None) -> bool:
        """
        리밸런싱 알림 전송

        Args:
            next_date: 다음 리밸런싱 날짜
            portfolio_info: 포트폴리오 정보
        """
        message = f"""
🔄 <b>리밸런싱 알림</b>

다음 리밸런싱 예정일: <b>{next_date}</b>
━━━━━━━━━━━━━━━
"""
        if portfolio_info:
            message += f"""
현재 포트폴리오 상태:
• 총 평가금액: {portfolio_info.get('total_value', 0):,.0f}원
• 보유 종목 수: {portfolio_info.get('position_count', 0)}개
• 최근 수익률: {portfolio_info.get('recent_return', 0):.2f}%
"""

        message += f"""
━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message(message)

    def get_alert_history(self, limit: int = 10) -> List[Dict]:
        """최근 알림 내역 조회"""
        return self._alert_history[-limit:]


class AlertManager:
    """알림 관리자 - 조건 모니터링 및 알림 발송"""

    def __init__(self, telegram: TelegramAlert = None):
        self.telegram = telegram or TelegramAlert()
        self.price_alerts = []  # 가격 알림 목록
        self.signal_alerts = []  # 시그널 알림 설정
        self._running = False
        self._thread = None

        # 설정 로드
        self._load_config()

    def _load_config(self):
        """설정 파일 로드"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.price_alerts = config.get('price_alerts', [])
                    self.signal_alerts = config.get('signal_alerts', [])
            except Exception as e:
                print(f"[AlertManager] 설정 로드 실패: {e}")

    def _save_config(self):
        """설정 파일 저장"""
        try:
            config = {
                'price_alerts': self.price_alerts,
                'signal_alerts': self.signal_alerts
            }
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AlertManager] 설정 저장 실패: {e}")

    def add_price_alert(self, stock_code: str, stock_name: str,
                        target_price: float, alert_type: str = 'target',
                        condition: str = 'above') -> bool:
        """
        가격 알림 추가

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            target_price: 목표가
            alert_type: 알림 유형 ('target', 'stop_loss', 'breakout')
            condition: 조건 ('above' = 이상, 'below' = 이하)
        """
        alert = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'target_price': target_price,
            'alert_type': alert_type,
            'condition': condition,
            'created_at': datetime.now().isoformat(),
            'triggered': False
        }
        self.price_alerts.append(alert)
        self._save_config()
        return True

    def remove_price_alert(self, stock_code: str, target_price: float) -> bool:
        """가격 알림 제거"""
        self.price_alerts = [
            a for a in self.price_alerts
            if not (a['stock_code'] == stock_code and a['target_price'] == target_price)
        ]
        self._save_config()
        return True

    def add_signal_alert(self, signal_type: str, enabled: bool = True) -> bool:
        """
        시그널 알림 추가

        Args:
            signal_type: 시그널 유형 (예: 'rsi_oversold', 'macd_golden_cross')
            enabled: 활성화 여부
        """
        # 중복 체크
        for alert in self.signal_alerts:
            if alert['signal_type'] == signal_type:
                alert['enabled'] = enabled
                self._save_config()
                return True

        self.signal_alerts.append({
            'signal_type': signal_type,
            'enabled': enabled
        })
        self._save_config()
        return True

    def check_price_alerts(self, api) -> List[Dict]:
        """가격 알림 조건 체크"""
        triggered = []

        for alert in self.price_alerts:
            if alert.get('triggered'):
                continue

            try:
                # 현재가 조회
                info = api.get_stock_info(alert['stock_code'])
                if not info:
                    continue

                current_price = info.get('stck_prpr', 0)
                if not current_price:
                    continue

                current_price = float(current_price)
                target_price = alert['target_price']

                # 조건 체크
                condition_met = False
                if alert['condition'] == 'above' and current_price >= target_price:
                    condition_met = True
                elif alert['condition'] == 'below' and current_price <= target_price:
                    condition_met = True

                if condition_met:
                    alert['triggered'] = True
                    triggered.append({
                        **alert,
                        'current_price': current_price
                    })

                    # 텔레그램 알림 발송
                    self.telegram.send_price_alert(
                        alert['stock_code'],
                        alert['stock_name'],
                        current_price,
                        target_price,
                        alert['alert_type']
                    )

            except Exception as e:
                print(f"[AlertManager] 가격 체크 오류: {e}")

        self._save_config()
        return triggered

    def get_price_alerts(self) -> List[Dict]:
        """등록된 가격 알림 목록 조회"""
        return self.price_alerts

    def get_signal_alerts(self) -> List[Dict]:
        """등록된 시그널 알림 목록 조회"""
        return self.signal_alerts


def save_telegram_config(bot_token: str, chat_id: str) -> bool:
    """텔레그램 설정 저장"""
    try:
        config_data = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

        config_data['bot_token'] = bot_token
        config_data['chat_id'] = chat_id

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 환경변수에도 설정
        os.environ['TELEGRAM_BOT_TOKEN'] = bot_token
        os.environ['TELEGRAM_CHAT_ID'] = chat_id

        return True
    except Exception as e:
        print(f"설정 저장 오류: {e}")
        return False


def load_telegram_config() -> Dict:
    """텔레그램 설정 로드"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    'bot_token': config.get('bot_token', ''),
                    'chat_id': config.get('chat_id', '')
                }
        except:
            pass
    return {'bot_token': '', 'chat_id': ''}


def test_telegram_connection(bot_token: str, chat_id: str) -> tuple:
    """
    텔레그램 연결 테스트

    Returns:
        (success: bool, message: str)
    """
    try:
        alert = TelegramAlert(bot_token, chat_id)
        success = alert.send_message("🔔 퀀트 포트폴리오 텔레그램 연결 테스트 성공!")
        if success:
            return True, "연결 성공! 텔레그램에서 메시지를 확인하세요."
        else:
            return False, "메시지 전송 실패. 봇 토큰과 채팅 ID를 확인하세요."
    except Exception as e:
        return False, f"연결 오류: {str(e)}"
