"""Bot entrypoint."""
import asyncio
import logging
import signal
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


def build_application() -> Application:
    global _app_instance
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    from bot.handlers import register_all
    register_all(app)

    _app_instance = app
    return app


async def _run_webhook(application: Application) -> None:
    """Run PTB webhook + Klix aiohttp server concurrently."""
    from bot.database import init_db
    from bot.scheduler import start_scheduler
    from bot.handlers.payment_webhook import klix_webhook

    webhook_path = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"

    # Klix webhook on a separate port (proxied by nginx at /webhook/klix)
    klix_app = web.Application()
    klix_app.router.add_post("/webhook/klix", klix_webhook)
    runner = web.AppRunner(klix_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.KLIX_WEBHOOK_PORT)
    await site.start()
    logger.info("Klix webhook listening on port %d", config.KLIX_WEBHOOK_PORT)

    async with application:
        await init_db()
        start_scheduler()
        logger.info("Bot initialized (environment=%s)", config.ENVIRONMENT)

        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            url_path=webhook_path,
            webhook_url=f"https://{config.WEBHOOK_HOST}{webhook_path}",
            drop_pending_updates=True,
        )
        await application.start()
        logger.info("Webhook started: https://%s%s", config.WEBHOOK_HOST, webhook_path)

        stop_event = asyncio.Event()

        def _handle_signal():
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except NotImplementedError:
                pass  # Windows

        await stop_event.wait()

        await application.updater.stop()
        await application.stop()

    await runner.cleanup()


def main():
    application = build_application()

    if config.use_webhook:
        logger.info("Starting in webhook mode: host=%s port=%d", config.WEBHOOK_HOST, config.WEBHOOK_PORT)
        asyncio.run(_run_webhook(application))
    else:
        logger.info("Starting in polling mode")

        async def _run_polling(app: Application) -> None:
            from bot.database import init_db
            from bot.scheduler import start_scheduler
            async with app:
                await init_db()
                start_scheduler()
                await app.updater.start_polling(drop_pending_updates=True)
                await app.start()
                await asyncio.Event().wait()

        asyncio.run(_run_polling(application))


if __name__ == "__main__":
    main()
