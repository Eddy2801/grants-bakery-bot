from pydantic_settings import BaseSettings


class KlixSettings(BaseSettings):
    KLIX_BRAND_ID: str
    KLIX_SECRET_KEY: str
    KLIX_BASE_URL: str = "https://portal.klix.app/api/v1/"
    KLIX_WEBHOOK_URL: str = ""
    KLIX_SUCCESS_REDIRECT: str = ""
    KLIX_FAILURE_REDIRECT: str = ""

    class Config:
        env_file = ".env"
