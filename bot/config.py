import os

# Groq AI
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")  # @OfertasFlashES o chat_id

# Amazon
AMAZON_TAG = "topactual-21"

# Cuantas ofertas publicar por ronda
OFFERS_PER_RUN = 5

# Directorio de ofertas publicadas (para no repetir)
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), "products.json")
