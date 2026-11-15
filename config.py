import os
from dotenv import load_dotenv

load_dotenv()

# ---- Database -------------------------------------------------------
DB_HOST = os.getenv("QUERIFY_DB_HOST", "localhost")
DB_USER = os.getenv("QUERIFY_DB_USER", "root")
DB_PASSWORD = os.getenv("QUERIFY_DB_PASSWORD", "")
DB_NAME = os.getenv("QUERIFY_DB_NAME", "querify")

# ---- Model -----------------------------------------------------------
OLLAMA_MODEL = os.getenv("QUERIFY_MODEL", "llama3")

# ---- Safety limits ----------------------------------------------------
MAX_ROWS_RETURNED = int(os.getenv("QUERIFY_MAX_ROWS", "500"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERIFY_QUERY_TIMEOUT", "10"))

# ---- Login (swap for real SSO / a user table in production) ----------
APP_USERNAME = os.getenv("QUERIFY_APP_USER", "admin")
APP_PASSWORD_HASH = os.getenv("QUERIFY_APP_PASSWORD_HASH", "")
ADMIN_USERNAMES = {u.strip() for u in os.getenv("QUERIFY_ADMINS", "admin").split(",")}

# ---- Semantic layer ----------------------------------------------------
# Canonical business-term definitions injected into every SQL-generation
# prompt, so the model resolves an ambiguous term ("revenue", "active
# customer") the same way every time instead of guessing a fresh
# interpretation per question. Fill this in per customer deployment —
# it's the main thing that makes results consistent across a whole team.
SEMANTIC_LAYER = {
    # "revenue": "SUM(orders.total) WHERE orders.status = 'completed'",
    # "active_customer": "customers.last_order_date >= CURDATE() - INTERVAL 90 DAY",
}
