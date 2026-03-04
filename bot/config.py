import os
from pathlib import Path

# Cargar .env si existe
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            if val and not os.environ.get(key.strip()):
                os.environ[key.strip()] = val.strip()

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
