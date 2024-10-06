FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:0.4.18 /uv /bin/uv
WORKDIR /bot
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system -r requirements.txt uvloop
COPY . .
ENTRYPOINT ["python3", "/bot/main.py"]