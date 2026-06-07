from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    WEBHOOK_HOST: str = ""
    WEBHOOK_PORT: int = 8443
    KLIX_WEBHOOK_PORT: int = 8444

    # Bot DB
    BOT_DB_HOST: str = "bot-postgres"
    BOT_DB_PORT: int = 5432
    BOT_DB_NAME: str = "grantsbot"
    BOT_DB_USER: str = "botuser"
    BOT_DB_PASS: str

    # ERP DB (read/write production plan)
    ERP_DB_HOST: str = "postgres"
    ERP_DB_PORT: int = 5432
    ERP_DB_NAME: str = "gbakery"
    ERP_DB_USER: str = "postgres"
    ERP_DB_PASS: str

    # Redis
    REDIS_URL: str = "redis://bot-redis:6379/0"

    # LLM via OpenRouter
    OPENROUTER_API_KEY: str
    LLM_MODEL: str = "google/gemini-flash-1.5"

    # OpenAI (embeddings only — not via OpenRouter)
    OPENAI_API_KEY: str = ""

    # fal.ai (image generation)
    FAL_KEY: str = ""

    # Klix
    KLIX_BRAND_ID: str = ""
    KLIX_SECRET_KEY: str = ""
    KLIX_BASE_URL: str = "https://portal.klix.app/api/v1/"
    KLIX_WEBHOOK_URL: str = ""
    KLIX_SUCCESS_REDIRECT: str = ""
    KLIX_FAILURE_REDIRECT: str = ""

    # ERP Online Shop IDs (set after creating the client in ERP)
    ERP_ONLINE_CLIENT_ID: int = 0
    ERP_ONLINE_ADDR_PICKUP: int = 0
    ERP_ONLINE_ADDR_OMNIVA: int = 0
    ERP_ONLINE_ADDR_COURIER: int = 0

    # Business rules
    FREEZE_CAPACITY_PCT: float = 25.0
    SUBSCRIPTION_DISCOUNT_THRESHOLD: int = 3
    SUBSCRIPTION_DISCOUNT_PCT: float = 5.0
    CHARGE_REMINDER_HOURS: int = 24
    CART_TTL_SECONDS: int = 3600
    SESSION_TTL_SECONDS: int = 86400

    # Misc
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    @property
    def bot_db_url(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"postgresql+asyncpg://{self.BOT_DB_USER}:{quote_plus(self.BOT_DB_PASS)}"
            f"@{self.BOT_DB_HOST}:{self.BOT_DB_PORT}/{self.BOT_DB_NAME}"
        )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.WEBHOOK_HOST)


config = Settings()
