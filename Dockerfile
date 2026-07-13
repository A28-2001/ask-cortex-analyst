FROM python:3.11-slim

WORKDIR /app

COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY chainlit_app/ ./chainlit_app/
COPY scripts/ask_cortex_analyst.py scripts/jwt_auth.py scripts/snowflake_auth.py ./scripts/
COPY semantic_model/ ./semantic_model/
COPY public/ ./public/
COPY .chainlit/config.toml ./.chainlit/config.toml
COPY chainlit.md .

EXPOSE 7860

CMD ["uvicorn", "chainlit_app.server:app", "--host", "0.0.0.0", "--port", "7860"]
