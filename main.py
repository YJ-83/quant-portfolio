#!/usr/bin/env python3
"""
퀀트 포트폴리오 시스템 - 메인 CLI

사용법:
    python main.py collect --all          # 전체 데이터 수집
    python main.py collect --daily        # 일일 업데이트
    python main.py run --strategy magic   # 마법공식 전략 실행
    python main.py backtest --strategy magic --start 2020-01-01 --end 2023-12-31
    python main.py dashboard              # 대시보드 실행
"""
import argparse
import sys
from datetime import datetime, timedelta


def main():
    parser = argparse.ArgumentParser(
        description="퀀트 포트폴리오 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
    python main.py collect --all
    python main.py run --strategy magic_formula --top-n 30
    python main.py backtest --strategy multifactor --start 2021-01-01
    python main.py dashboard
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # collect 명령어
    collect_parser = subparsers.add_parser('collect', help='데이터 수집')
    collect_parser.add_argument('--all', action='store_true', help='전체 데이터 수집')
    collect_parser.add_argument('--daily', action='store_true', help='일일 업데이트')
    collect_parser.add_argument('--market', choices=['KOSPI', 'KOSDAQ', 'ALL'],
                                default='ALL', help='시장 선택')
    collect_parser.add_argument('--use-alternative', action='store_true',
                                help='대안 데이터 소스 사용 (FinanceDataReader)')

    # run 명령어
    run_parser = subparsers.add_parser('run', help='전략 실행')
    run_parser.add_argument('--strategy', required=True,
                            choices=['magic_formula', 'multifactor', 'sector_neutral'],
                            help='전략 선택')
    run_parser.add_argument('--top-n', type=int, default=30, help='선정 종목 수')
    run_parser.add_argument('--min-market-cap', type=float, default=1000,
                            help='최소 시가총액 (억원)')
    run_parser.add_argument('--output', type=str, help='결과 저장 경로')

    # backtest 명령어
    backtest_parser = subparsers.add_parser('backtest', help='백테스트 실행')
    backtest_parser.add_argument('--strategy', required=True,
                                 choices=['magic_formula', 'multifactor', 'sector_neutral'],
                                 help='전략 선택')
    backtest_parser.add_argument('--start', type=str, required=True, help='시작일 (YYYY-MM-DD)')
    backtest_parser.add_argument('--end', type=str, default=None, help='종료일 (YYYY-MM-DD)')
    backtest_parser.add_argument('--initial-capital', type=float, default=100000000,
                                 help='초기 자본금')
    backtest_parser.add_argument('--rebalance', choices=['monthly', 'quarterly', 'yearly'],
                                 default='quarterly', help='리밸런싱 주기')
    backtest_parser.add_argument('--benchmark', type=str, default=None,
                                 help='벤치마크 코드')

    # dashboard 명령어
    dashboard_parser = subparsers.add_parser('dashboard', help='대시보드 실행')
    dashboard_parser.add_argument('--port', type=int, default=8501, help='포트 번호')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == 'collect':
        run_collect(args)
    elif args.command == 'run':
        run_strategy(args)
    elif args.command == 'backtest':
        run_backtest(args)
    elif args.command == 'dashboard':
        run_dashboard(args)


def run_collect(args):
    """데이터 수집 실행"""
    print("=" * 50)
    print("데이터 수집")
    print("=" * 50)

    if args.use_alternative:
        print("대안 데이터 소스 사용 (FinanceDataReader)")
        from data.data_collector import AlternativeDataCollector

        collector = AlternativeDataCollector()

        if args.all:
            collector.collect_all(args.market)
        elif args.daily:
            print("일일 업데이트 실행...")
            collector.collect_price_data()
    else:
        print("한국투자증권 API 사용")
        from data.data_collector import DataCollector

        collector = DataCollector()

        if not collector.connect():
            print("한국투자증권 API 연결 실패")
            print("환경변수를 확인하세요: KIS_APP_KEY, KIS_APP_SECRET")
            print("또는 --use-alternative 옵션으로 대안 데이터 소스를 사용하세요.")
            return

        if args.all:
            collector.collect_all(args.market)
        elif args.daily:
            collector.update_daily()


def run_strategy(args):
    """전략 실행"""
    print("=" * 50)
    print(f"전략 실행: {args.strategy}")
    print("=" * 50)

    from strategies import MagicFormulaStrategy, MultifactorStrategy, SectorNeutralStrategy
    from data.database import Database

    # 전략 인스턴스 생성
    if args.strategy == 'magic_formula':
        strategy = MagicFormulaStrategy(
            top_n=args.top_n,
            min_market_cap=args.min_market_cap * 1e8
        )
    elif args.strategy == 'multifactor':
        strategy = MultifactorStrategy(
            top_n=args.top_n,
            min_market_cap=args.min_market_cap * 1e8
        )
    elif args.strategy == 'sector_neutral':
        strategy = SectorNeutralStrategy(
            top_n=args.top_n,
            min_market_cap=args.min_market_cap * 1e8
        )

    print(f"전략: {strategy.name}")
    print(f"설명: {strategy.description}")
    print(f"선정 종목 수: {args.top_n}")
    print(f"최소 시가총액: {args.min_market_cap}억원")
    print()

    # 데이터 로드
    db = Database()
    stocks = db.get_stocks()

    if stocks.empty:
        print("종목 데이터가 없습니다. 먼저 'collect' 명령을 실행하세요.")
        return

    # 재무 데이터 병합
    year = datetime.now().year - 1
    financials = db.get_financials(year=year)
    data = stocks.merge(financials, on='code', how='left')

    print(f"분석 대상 종목: {len(data)}개")

    # 전략 실행
    result = strategy.select_stocks(data)

    # 결과 출력
    print()
    print("=" * 50)
    print("선정 결과")
    print("=" * 50)
    print(f"후보 종목: {result.total_candidates}개")
    print(f"선정 종목: {result.selected_count}개")
    print()

    print("상위 10개 종목:")
    top10 = result.stocks.head(10)
    for _, row in top10.iterrows():
        print(f"  {int(row['rank']):2d}. {row.get('name', row.get('code'))} (점수: {row['score']:.4f})")

    # 결과 저장
    if args.output:
        result.stocks.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n결과 저장: {args.output}")


def run_backtest(args):
    """백테스트 실행"""
    print("=" * 50)
    print(f"백테스트: {args.strategy}")
    print("=" * 50)

    from strategies import MagicFormulaStrategy, MultifactorStrategy, SectorNeutralStrategy
    from backtest.engine import BacktestEngine

    # 전략 인스턴스 생성
    if args.strategy == 'magic_formula':
        strategy = MagicFormulaStrategy()
    elif args.strategy == 'multifactor':
        strategy = MultifactorStrategy()
    elif args.strategy == 'sector_neutral':
        strategy = SectorNeutralStrategy()

    end_date = args.end or datetime.now().strftime('%Y-%m-%d')

    print(f"전략: {strategy.name}")
    print(f"기간: {args.start} ~ {end_date}")
    print(f"초기 자본: {args.initial_capital:,.0f}원")
    print(f"리밸런싱: {args.rebalance}")
    print()

    # 백테스트 엔진
    engine = BacktestEngine(
        strategy=strategy,
        start_date=args.start,
        end_date=end_date,
        initial_capital=args.initial_capital,
        rebalance_period=args.rebalance,
        benchmark=args.benchmark
    )

    # 실행
    result = engine.run()

    # 결과 출력
    print()
    print(result.summary())


def run_dashboard(args):
    """대시보드 실행"""
    import subprocess

    print("=" * 50)
    print("대시보드 실행")
    print("=" * 50)
    print(f"포트: {args.port}")
    print()
    print("브라우저에서 http://localhost:{args.port} 을 열어주세요.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print()

    subprocess.run([
        sys.executable, '-m', 'streamlit', 'run',
        'dashboard/app.py',
        '--server.port', str(args.port)
    ])


if __name__ == '__main__':
    main()
