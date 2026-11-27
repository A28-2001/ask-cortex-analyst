FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements-app.txt .
RUN pip install -r requirements-app.txt

COPY --chown=app:app chainlit_app/ ./chainlit_app/
COPY --chown=app:app scripts/ask_cortex_analyst.py scripts/jwt_auth.py scripts/snowflake_auth.py ./scripts/
COPY --chown=app:app semantic_model/ ./semantic_model/
COPY --chown=app:app public/ ./public/
COPY --chown=app:app .chainlit/config.toml ./.chainlit/config.toml
COPY --chown=app:app .chainlit/translations/en-US.json ./.chainlit/translations/en-US.json
COPY --chown=app:app chainlit.md .

# Chainlit writes .files/ and the other translations at startup, so the app
# directory belongs to the unprivileged user the server runs as.
RUN chown app:app /app /app/.chainlit /app/.chainlit/translations
USER app

# Build matplotlib's font cache now instead of during the first chart a
# visitor asks for.
RUN python -c "import matplotlib.font_manager"

EXPOSE 7860

# Render passes the port to listen on in $PORT. Its proxy is the only thing
# that can reach the container, so its forwarded headers are trusted.
CMD ["sh", "-c", "exec uvicorn chainlit_app.server:app --host 0.0.0.0 --port ${PORT:-7860} --forwarded-allow-ips='*'"]
