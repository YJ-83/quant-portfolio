"""
백테스트 리포트 모듈
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
import pandas as pd
import numpy as np

from utils.helpers import format_currency, format_percent


@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    mdd: float
    volatility: float
    win_rate: float
    calmar_ratio: float
    portfolio_history: pd.DataFrame
    trade_history: pd.DataFrame
    metrics: Dict = field(default_factory=dict)

    def summary(self) -> str:
        """결과 요약 문자열"""
        lines = [
            "=" * 60,
            f"백테스트 결과: {self.strategy_name}",
            "=" * 60,
            f"기간: {self.start_date} ~ {self.end_date}",
            "",
            "[ 수익률 ]",
            f"  초기 자본: {format_currency(self.initial_capital)}",
            f"  최종 자산: {format_currency(self.final_value)}",
            f"  총 수익률: {format_percent(self.total_return)}",
            f"  CAGR: {format_percent(self.cagr)}",
            "",
            "[ 위험 지표 ]",
            f"  변동성: {format_percent(self.volatility)}",
            f"  MDD: {format_percent(self.mdd)}",
            "",
            "[ 위험조정 수익 ]",
            f"  샤프 비율: {self.sharpe_ratio:.2f}",
            f"  소르티노 비율: {self.sortino_ratio:.2f}",
            f"  칼마 비율: {self.calmar_ratio:.2f}",
            "",
            "[ 거래 통계 ]",
            f"  승률: {format_percent(self.win_rate)}",
            f"  총 거래 횟수: {len(self.trade_history)}",
            "=" * 60
        ]

        # 벤치마크 대비 (있는 경우)
        if 'benchmark_return' in self.metrics:
            lines.insert(-1, "")
            lines.insert(-1, "[ 벤치마크 대비 ]")
            lines.insert(-1, f"  벤치마크 수익률: {format_percent(self.metrics['benchmark_return'])}")
            lines.insert(-1, f"  초과 수익률: {format_percent(self.metrics['excess_return'])}")
            if 'alpha' in self.metrics:
                lines.insert(-1, f"  알파: {format_percent(self.metrics['alpha'])}")
            if 'beta' in self.metrics:
                lines.insert(-1, f"  베타: {self.metrics['beta']:.2f}")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'strategy_name': self.strategy_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_value': self.final_value,
            'total_return': self.total_return,
            'cagr': self.cagr,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'mdd': self.mdd,
            'volatility': self.volatility,
            'win_rate': self.win_rate,
            'calmar_ratio': self.calmar_ratio,
            **self.metrics
        }

    def get_monthly_returns(self) -> pd.Series:
        """월간 수익률"""
        values = self.portfolio_history['total_value']
        monthly = values.resample('ME').last()
        returns = monthly.pct_change().dropna()
        return returns

    def get_yearly_returns(self) -> pd.Series:
        """연간 수익률"""
        values = self.portfolio_history['total_value']
        yearly = values.resample('YE').last()
        returns = yearly.pct_change().dropna()
        return returns

    def get_drawdown_series(self) -> pd.Series:
        """낙폭 시리즈"""
        values = self.portfolio_history['total_value']
        running_max = values.expanding().max()
        drawdown = (values - running_max) / running_max
        return drawdown


def generate_report(result: BacktestResult,
                    output_path: Optional[str] = None,
                    format: str = 'text') -> str:
    """
    백테스트 리포트 생성

    Args:
        result: BacktestResult 객체
        output_path: 출력 파일 경로
        format: 출력 포맷 ('text', 'html', 'json')

    Returns:
        리포트 문자열
    """
    if format == 'text':
        report = _generate_text_report(result)
    elif format == 'html':
        report = _generate_html_report(result)
    elif format == 'json':
        import json
        report = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"Unknown format: {format}")

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

    return report


def _generate_text_report(result: BacktestResult) -> str:
    """텍스트 리포트 생성"""
    lines = [result.summary()]

    # 월간 수익률 통계
    monthly_returns = result.get_monthly_returns()

    if not monthly_returns.empty:
        lines.append("")
        lines.append("[ 월간 수익률 통계 ]")
        lines.append(f"  평균: {format_percent(monthly_returns.mean())}")
        lines.append(f"  표준편차: {format_percent(monthly_returns.std())}")
        lines.append(f"  최대: {format_percent(monthly_returns.max())}")
        lines.append(f"  최소: {format_percent(monthly_returns.min())}")
        lines.append(f"  양수 개월: {(monthly_returns > 0).sum()}개월")
        lines.append(f"  음수 개월: {(monthly_returns < 0).sum()}개월")

    # 연간 수익률
    yearly_returns = result.get_yearly_returns()

    if not yearly_returns.empty:
        lines.append("")
        lines.append("[ 연간 수익률 ]")
        for date, ret in yearly_returns.items():
            year = date.year
            lines.append(f"  {year}: {format_percent(ret)}")

    return "\n".join(lines)


def _generate_html_report(result: BacktestResult) -> str:
    """HTML 리포트 생성"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>백테스트 리포트 - {result.strategy_name}</title>
    <style>
        body {{
            font-family: 'Nanum Gothic', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #666;
            margin-top: 30px;
        }}
        .summary-box {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .metric {{
            display: inline-block;
            width: 200px;
            margin: 10px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 4px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
        }}
        .positive {{
            color: #4CAF50;
        }}
        .negative {{
            color: #f44336;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
    </style>
</head>
<body>
    <h1>백테스트 리포트: {result.strategy_name}</h1>
    <p>기간: {result.start_date} ~ {result.end_date}</p>

    <div class="summary-box">
        <h2>핵심 지표</h2>
        <div class="metric">
            <div class="metric-value {('positive' if result.total_return >= 0 else 'negative')}">
                {format_percent(result.total_return)}
            </div>
            <div class="metric-label">총 수익률</div>
        </div>
        <div class="metric">
            <div class="metric-value {('positive' if result.cagr >= 0 else 'negative')}">
                {format_percent(result.cagr)}
            </div>
            <div class="metric-label">CAGR</div>
        </div>
        <div class="metric">
            <div class="metric-value">{result.sharpe_ratio:.2f}</div>
            <div class="metric-label">샤프 비율</div>
        </div>
        <div class="metric">
            <div class="metric-value negative">{format_percent(result.mdd)}</div>
            <div class="metric-label">MDD</div>
        </div>
    </div>

    <div class="summary-box">
        <h2>수익률 상세</h2>
        <table>
            <tr>
                <th>지표</th>
                <th>값</th>
            </tr>
            <tr>
                <td>초기 자본</td>
                <td>{format_currency(result.initial_capital)}</td>
            </tr>
            <tr>
                <td>최종 자산</td>
                <td>{format_currency(result.final_value)}</td>
            </tr>
            <tr>
                <td>변동성 (연율)</td>
                <td>{format_percent(result.volatility)}</td>
            </tr>
            <tr>
                <td>소르티노 비율</td>
                <td>{result.sortino_ratio:.2f}</td>
            </tr>
            <tr>
                <td>칼마 비율</td>
                <td>{result.calmar_ratio:.2f}</td>
            </tr>
            <tr>
                <td>승률</td>
                <td>{format_percent(result.win_rate)}</td>
            </tr>
        </table>
    </div>
</body>
</html>
    """

    return html


def compare_results(results: list) -> pd.DataFrame:
    """
    여러 백테스트 결과 비교

    Args:
        results: BacktestResult 리스트

    Returns:
        비교 DataFrame
    """
    comparison = []

    for result in results:
        comparison.append({
            '전략': result.strategy_name,
            '총 수익률': result.total_return,
            'CAGR': result.cagr,
            '변동성': result.volatility,
            '샤프': result.sharpe_ratio,
            '소르티노': result.sortino_ratio,
            'MDD': result.mdd,
            '칼마': result.calmar_ratio,
            '승률': result.win_rate
        })

    df = pd.DataFrame(comparison)

    # 포맷팅
    percent_cols = ['총 수익률', 'CAGR', '변동성', 'MDD', '승률']
    for col in percent_cols:
        df[col] = df[col].apply(lambda x: f"{x:.2%}")

    ratio_cols = ['샤프', '소르티노', '칼마']
    for col in ratio_cols:
        df[col] = df[col].apply(lambda x: f"{x:.2f}")

    return df
