FROM python:3.13-alpine AS builder
WORKDIR /temp
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r requirements.txt

FROM python:3.13-alpine
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
WORKDIR /bot
COPY . .
ENTRYPOINT ["python3", "/bot/main.py"]