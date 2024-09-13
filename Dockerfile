FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:0.4.10 /uv /bin/uv
WORKDIR /bot
COPY requirements.txt .
RUN apk add --no-cache libmagic
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system -r requirements.txt
COPY . .
ENTRYPOINT ["python3", "/bot/main.py"]