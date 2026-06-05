from bot.handlers import start, catalog, order, fallback

def register_all(app):
    start.register(app)
    catalog.register(app)
    order.register(app)
    fallback.register(app)
