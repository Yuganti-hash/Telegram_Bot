# Telegram AI Bot

A Telegram chatbot powered by the [OpenRouter](https://openrouter.ai) API. Replies to messages with AI-generated responses, remembers conversation history per chat session, and runs 24/7 on Render's free tier.

---

## Features

- Conversational AI via OpenRouter (free models, no credit card needed)
- Per-chat conversation memory (last 20 messages)
- Automatic model fallback if the primary model is rate-limited
- Runs locally with polling, on Render with webhooks — same codebase
- Keep-alive ping to prevent Render free-tier spin-down

---

## Quick Start (local)

**1. Clone and install dependencies**
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
```

**2. Configure environment variables**
```bash
cp .env.example .env
```
Edit `.env` and fill in your keys:
```
TELEGRAM_BOT_TOKEN=your_token_here
OPENROUTER_API_KEY=your_api_key_here
```

**3. Run**
```bash
python bot.py
```

---

## Getting API Keys

### Telegram Bot Token
1. Open Telegram → search **@BotFather**
2. Send `/newbot`, choose a name and username (must end in `bot`)
3. Copy the token BotFather sends you

### OpenRouter API Key
1. Sign up free at [openrouter.ai](https://openrouter.ai)
2. Go to **openrouter.ai/keys** → create a key
3. No credit card required for free-tier models

**Free models used (in fallback order):**
- `mistralai/mistral-7b-instruct:free`
- `meta-llama/llama-3-8b-instruct:free`
- `google/gemma-3-4b-it:free`

Override the primary model via `OPENROUTER_MODEL` in `.env`.

---

## Deploy to Render (free, 24/7)

**1. Push to GitHub**
```bash
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

**2. Create a Web Service on Render**
- Go to [render.com](https://render.com) → **New → Web Service**
- Connect your GitHub repo
- Render picks up `render.yaml` automatically

**3. Set environment variables in Render dashboard**

Under your service → **Environment**, add:

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | your Telegram token |
| `OPENROUTER_API_KEY` | your OpenRouter key |

`RENDER_EXTERNAL_URL` is injected automatically — no action needed.

**4. Deploy**

Render builds and deploys on every push. Check the **Logs** tab for:
```
Webhook set to https://your-service.onrender.com/webhook
```

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Reset conversation and say hello |
| `/help` | Show available commands |
| _(any text)_ | Chat with the AI |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | From BotFather |
| `OPENROUTER_API_KEY` | Yes | — | From openrouter.ai |
| `OPENROUTER_MODEL` | No | `mistralai/mistral-7b-instruct:free` | Primary model |

---

## Project Structure

```
bot.py            # All bot logic — handlers, webhook server, keep-alive
requirements.txt  # Python dependencies
render.yaml       # Render deployment config
.env.example      # Environment variable template
.gitignore        # Excludes .env and cache files
```
