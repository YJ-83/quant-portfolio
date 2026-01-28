"""
설정 관리 모듈
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
import yaml


@dataclass
class Settings:
    """시스템 설정"""

    # 경로 설정
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data_store")
    CACHE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data_store" / "cache")
    DB_PATH: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data_store" / "stocks.db")

    # 키움 API 설정
    KIWOOM_API_DELAY: float = 0.2  # API 호출 간 딜레이 (초)
    KIWOOM_MAX_RETRY: int = 3  # 최대 재시도 횟수

    # 전략 기본 설정
    DEFAULT_TOP_N: int = 30  # 기본 선정 종목 수
    DEFAULT_REBALANCE_PERIOD: str = "quarterly"  # monthly, quarterly, yearly

    # 팩터 가중치 기본값
    DEFAULT_FACTOR_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "quality": 0.333,
        "value": 0.333,
        "momentum": 0.334
    })

    # 퀄리티 팩터 구성
    QUALITY_FACTORS: List[str] = field(default_factory=lambda: [
        "roe",           # ROE
        "gpa",           # 매출총이익율
        "cfo_ratio"      # 영업현금흐름율
    ])

    # 밸류 팩터 구성
    VALUE_FACTORS: List[str] = field(default_factory=lambda: [
        "per",   # PER (낮을수록 좋음)
        "pbr",   # PBR (낮을수록 좋음)
        "psr",   # PSR (낮을수록 좋음)
        "pcr"    # PCR (낮을수록 좋음)
    ])

    # 모멘텀 팩터 구성
    MOMENTUM_PERIODS: List[int] = field(default_factory=lambda: [3, 6, 12])  # 개월

    # 마법공식 설정
    MAGIC_FORMULA_FACTORS: List[str] = field(default_factory=lambda: [
        "earnings_yield",  # 이익수익률 (EY)
        "roc"              # 투하자본수익률 (ROC)
    ])

    # 이상치 처리 설정
    WINSORIZE_LOWER: float = 0.01  # 하위 1%
    WINSORIZE_UPPER: float = 0.99  # 상위 99%

    # 백테스트 설정
    DEFAULT_INITIAL_CAPITAL: float = 100_000_000  # 1억원
    RISK_FREE_RATE: float = 0.035  # 무위험 수익률 (3.5%)
    TRADING_DAYS_PER_YEAR: int = 252

    # 섹터 리스트 (KRX 업종 기준)
    SECTORS: List[str] = field(default_factory=lambda: [
        "에너지",
        "소재",
        "산업재",
        "경기관련소비재",
        "필수소비재",
        "건강관리",
        "금융",
        "IT",
        "커뮤니케이션서비스",
        "유틸리티"
    ])

    def __post_init__(self):
        """디렉토리 생성"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        """YAML 파일에서 설정 로드"""
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return cls(**config)

    def to_yaml(self, path: str):
        """설정을 YAML 파일로 저장"""
        config = {
            "DEFAULT_TOP_N": self.DEFAULT_TOP_N,
            "DEFAULT_REBALANCE_PERIOD": self.DEFAULT_REBALANCE_PERIOD,
            "DEFAULT_FACTOR_WEIGHTS": self.DEFAULT_FACTOR_WEIGHTS,
            "WINSORIZE_LOWER": self.WINSORIZE_LOWER,
            "WINSORIZE_UPPER": self.WINSORIZE_UPPER,
            "DEFAULT_INITIAL_CAPITAL": self.DEFAULT_INITIAL_CAPITAL,
            "RISK_FREE_RATE": self.RISK_FREE_RATE,
        }
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


# 전역 설정 인스턴스
settings = Settings()
