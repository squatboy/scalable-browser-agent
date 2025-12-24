FROM python:3.11-slim-bookworm


WORKDIR /app

RUN python -m pip install --upgrade pip

COPY services/worker/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

RUN python -m playwright install --with-deps chromium

COPY services/worker/app /app/app
COPY agents /agents

CMD ["python", "-m", "app.worker"]
