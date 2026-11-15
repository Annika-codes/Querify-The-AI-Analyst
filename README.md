# Querify

## Setup

1. `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in your MySQL credentials.
3. `python generate_password_hash.py` and paste the output into `.env` as `QUERIFY_APP_PASSWORD_HASH`.
4. `streamlit run app.py`

## What changed from the original script, and why

- **`security.py`** — every AI-generated query is parsed and checked before
  it touches your database: single statement only, SELECT only, no
  DDL/write keywords, and an automatic row cap. This is the single most
  important addition for passing a security review.
- **`config.py`** — no more hardcoded DB password in source. Everything
  comes from environment variables, so the same code deploys safely
  across dev/staging/prod without editing files.
- **`auth.py`** — a login gate. Not real SSO yet, but it's the seam
  where you'd wire in SAML/OIDC for an enterprise buyer later.
- **`audit.py`** — every question, the SQL it produced, row count, and
  outcome (success/blocked/error) is logged to SQLite and viewable from
  an admin panel in the sidebar. This is what a compliance team will
  ask for before they'll even look at pricing.
- **Multi-dataset support** — `app.py` now tracks every uploaded table
  in `st.session_state["tables"]` with a selector, instead of only
  remembering the most recent upload.
- **`config.SEMANTIC_LAYER`** — a dict of business-term definitions
  injected into every prompt, so "revenue" or "active customer" resolve
  the same way for every user instead of the model guessing a fresh
  join each time. Empty by default — fill it in per customer.
- Modules are split out (`db.py`, `llm.py`, `charts.py`, `theme.py`) so
  the codebase reads like a real product rather than one long script —
  this matters more than it sounds like in a technical review.

## Still manual / not yet built

- Real SSO (SAML/OIDC) — `auth.py` is the integration point.
- Multi-source connectors (Postgres, Snowflake, BigQuery) — `db.py` is
  MySQL-only right now.
- Row/column-level permissions tied to individual users.
- Query timeout enforcement depends on your MySQL version supporting
  the `MAX_EXECUTION_TIME` optimizer hint (5.7.8+ with the InnoDB
  storage engine); verify on your target deployment.
