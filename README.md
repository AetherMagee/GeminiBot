# GeminiBot
### ...not just Gemini
GeminiBot is a Telegram bot that allows seamless use of various LLMs, primarily Gemini by Google.

## Features
- Supports Gemini API and OpenAI API (including [oai-reverse-proxy](https://gitgud.io/khanon/oai-reverse-proxy))
- Gemini API features: 
- - DM and group chats support
- - Vision (working with images)
- - Working with additional file types (including but not limited to mp4, mp3, ogg, pdf)
- OpenAI API features:
- - DM and group chats support
- - Vision (working with images)

## Setup
1) Clone the repository:
```shell
https://github.com/AetherMagee/GeminiBot --depth 1 && cd GeminiBot
```
2) Copy the example configuration:
```shell
cp .env.example .env
```

3) Make changes to the configuration file (.env)
4) Run the bot:
```shell
docker compose up -d --build
```
#### If experiencing error 403:
If you are trying to host the bot somewhere where Gemini API region restrictions apply, use ControlD as the DNS for the bot instead:
```shell
docker compose -f docker-compose-ctrld.yml up -d --build
```