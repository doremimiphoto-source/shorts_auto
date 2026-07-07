"""카드 콘텐츠 시스템 전용 설정 (쇼츠 src/config.py와 완전 분리).

분리 원칙:
  - 쇼츠 src/config.py 의 Secrets 를 import 하지 않는다.
  - 동일 .env 파일을 읽되, 카드 전용 CardSecrets 로 독립 로드한다.
  - 쇼츠 키(gemini/groq 등)는 extra='ignore' 로 무시 → 충돌 없음.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# cards/config.py → parent(cards/) → parent(프로젝트 루트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 경로 (쇼츠와 분리) ────────────────────────────────────────────────────────
CARDS_DB_PATH = PROJECT_ROOT / "data" / "cards.db"
CARDS_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
OUTPUT_DIR = PROJECT_ROOT / "output" / "cards"
BG_CACHE_DIR = PROJECT_ROOT / "output" / "cards" / "_bgcache"

VERTICAL_OUTPUT = {
    "v1_shopping": OUTPUT_DIR / "v1_shopping",
    "v2_travel":   OUTPUT_DIR / "v2_travel",
    "v3_kbeauty":  OUTPUT_DIR / "v3_kbeauty",
}

# ── 캔버스 사양 ───────────────────────────────────────────────────────────────
CANVAS = {
    "pinterest": (1000, 1500),
    "instagram": (1080, 1080),
    "tiktok":    (1080, 1920),
}

SLIDE_COUNT = {"v1_shopping": 7, "v2_travel": 8, "v3_kbeauty": 8}

UPLOAD_TIMES = {
    "pinterest": ["14:00", "20:00"],
    "instagram": ["09:00", "19:00"],
    "tiktok":    ["19:00", "21:00"],
}

CHANNEL_TAG = "@HiddenFindsDaily"
LINKTREE_URL = "https://linktr.ee/HiddenFindsDaily_"
AFFILIATE_DISCLOSURE = (
    "#ad • Affiliate links used — I may earn a small commission "
    "at no extra cost to you"
)

HASHTAGS = {
    "v1_shopping": [
        "AliExpress", "AliExpressFinds", "TemuFinds", "DealsOfTheDay",
        "BudgetShopping", "OnlineShopping", "AmazonVsAliExpress",
        "HiddenGems", "ShoppingHacks", "BestDeals", "SaveMoney",
        "AffordableFashion", "CheapFinds", "ShoppingTips", "DealAlert",
        "AliExpressHaul", "TemuHaul", "BargainHunter", "SmartShopping",
        "HiddenFindsDaily",
    ],
    "v2_travel": [
        "HiddenGems", "TravelTips", "SecretBeach", "HiddenTravel",
        "BudgetTravel", "TravelHacks", "OffTheBeatenPath", "TravelInspo",
        "HiddenDestinations", "TravelPhotography", "Wanderlust",
        "TravelGuide", "AsiaTravel", "EuropeTravel", "BackpackerLife",
        "TravelBlogger", "HiddenParadise", "ExploreMore", "TravelLife",
        "HiddenFindsDaily",
    ],
    "v3_kbeauty": [
        "KBeauty", "KoreanSkincare", "KoreanBeauty", "SkincareRoutine",
        "GlassSkin", "KBeautyFinds", "KoreanCosmetics", "SkincareHacks",
        "BeautyTips", "KoreanMakeup", "NaturalSkincare", "SkincareObsessed",
        "BeautyRoutine", "KPopBeauty", "OliveYoung", "YesStyle",
        "AffordableSkincare", "AntiAging", "KBeautySecrets",
        "HiddenFindsDaily",
    ],
}


# ── 카드 전용 시크릿 (쇼츠 Secrets 와 독립) ───────────────────────────────────
class CardSecrets(BaseSettings):
    """카드 시스템 전용 .env 시크릿. 쇼츠 Secrets 와 클래스 자체가 분리됨."""

    # LLM (쇼츠와 동일 키를 공유 — 읽기만, 쇼츠 동작에 영향 없음)
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Pinterest
    pinterest_app_id: str = ""
    pinterest_app_secret: str = ""
    pinterest_access_token: str = ""
    pinterest_board_v1: str = ""
    pinterest_board_v2: str = ""
    pinterest_board_v3: str = ""

    # Instagram / Meta
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_access_token: str = ""
    instagram_business_account_id: str = ""

    # TikTok
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_access_token: str = ""

    # Imgur
    imgur_client_id: str = ""
    imgur_client_secret: str = ""

    # Affiliate — V1
    aliexpress_app_key: str = ""
    aliexpress_app_secret: str = ""
    aliexpress_tracking_id: str = ""
    temu_affiliate_id: str = ""
    amazon_associate_tag: str = ""

    # Affiliate — V2
    booking_affiliate_id: str = ""
    tripdotcom_affiliate_id: str = ""
    klook_affiliate_id: str = ""

    # Affiliate — V3
    yesstyle_affiliate_id: str = ""
    stylekorean_affiliate_id: str = ""

    # Data Sources
    naver_client_id: str = ""
    naver_client_secret: str = ""
    unsplash_access_key: str = ""

    # Telegram (알림 — 쇼츠와 동일 봇 재사용 가능)
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",        # 쇼츠 전용 키(piper/youtube 등)는 무시
    )


@lru_cache(maxsize=1)
def get_card_secrets() -> CardSecrets:
    return CardSecrets()
