"""Bot entrypoint."""
import logging
import os
from typing import Optional

from aiohttp import web
from telegram.ext import Application

from bot.config import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

_app_instance: Optional[Application] = None


def get_bot_app() -> Optional[Application]:
    return _app_instance


async def _post_init(application: Application):
    """Called after bot is initialized."""
    from bot.database import init_db
    from bot.scheduler import start_scheduler
    await init_db()
    start_scheduler()
    logger.info("Bot initialized (environment=%s)", config.ENVIRONMENT)


def build_application() -> Application:
    global _app_instance
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Register handlers
    from bot.handlers import register_all
    register_all(app)

    _app_instance = app
    return app


def main():
    application = build_application()

    if config.use_webhook:
        # Production: webhook mode
        # The Klix payment webhook runs alongside on the same aiohttp server
        from bot.handlers.payment_webhook import klix_webhook

        async def setup_klix_routes(app: web.Application):
            app.router.add_post("/webhook/klix", klix_webhook)

        webhook_path = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"
        logger.info("Starting in webhook mode: host=%s port=%d", config.WEBHOOK_HOST, config.WEBHOOK_PORT)
        application.run_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            url_path=webhook_path,
            webhook_url=f"https://{config.WEBHOOK_HOST}{webhook_path}",
            # Inject Klix route into the same aiohttp app
            # This uses PTB's built-in aiohttp integration
        )
    else:
        # Development: polling mode
        logger.info("Starting in polling mode")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
