FROM python:3.12-alpine
WORKDIR /bot
COPY requirements.txt .
RUN apk add --no-cache libmagic
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["python3", "/bot/main.py"]