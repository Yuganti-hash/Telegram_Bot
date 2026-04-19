import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")

# Render sets RENDER_EXTERNAL_URL automatically; fallback to manual WEBHOOK_URL
_base_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_URL = f"{_base_url.rstrip('/')}/webhook" if _base_url else ""

PORT = int(os.getenv("PORT", 8000))
MAX_HISTORY = 20
KEEP_ALIVE_INTERVAL = 14 * 60  # 14 minutes — just under Render's 15-min spin-down

SYSTEM_PROMPT = "You are a helpful, concise assistant. Answer clearly and directly."

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

conversation_history: dict[int, list[dict]] = {}


def get_history(chat_id: int) -> list[dict]:
    if chat_id not in conversation_history:
        conversation_history[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return conversation_history[chat_id]


async def get_ai_response(chat_id: int, user_text: str) -> str:
    history = get_history(chat_id)
    history.append({"role": "user", "content": user_text})

    trimmed = [history[0]] + history[-(MAX_HISTORY):]
    conversation_history[chat_id] = trimmed

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost",
                "X-Title": "TelegramBot",
            },
            json={"model": OPENROUTER_MODEL, "messages": trimmed},
        )
        response.raise_for_status()
        data = response.json()

    reply = data["choices"][0]["message"]["content"].strip()
    conversation_history[chat_id].append({"role": "assistant", "content": reply})
    return reply


# ── Telegram handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(
        "Hi! I'm an AI assistant powered by OpenRouter.\n"
        "Send me any message and I'll respond.\n"
        "Use /help for more info."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "  /start — reset conversation and say hello\n"
        "  /help  — show this message\n\n"
        "Just type anything to chat. I remember the last conversation in this session."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = await get_ai_response(chat_id, user_text)
        await update.message.reply_text(reply)
    except httpx.HTTPStatusError as e:
        logger.error("OpenRouter HTTP error: %s", e)
        await update.message.reply_text("Sorry, the AI service returned an error. Try again shortly.")
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        await update.message.reply_text("Something went wrong. Please try again.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update caused error: %s", context.error)


def build_ptb_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    return app


# ── Keep-alive background task ─────────────────────────────────────────────────

async def keep_alive(health_url: str) -> None:
    """Pings the health endpoint to prevent Render free-tier spin-down."""
    await asyncio.sleep(KEEP_ALIVE_INTERVAL)
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(health_url)
            logger.info("Keep-alive ping sent.")
        except Exception as e:
            logger.warning("Keep-alive ping failed: %s", e)
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)


# ── FastAPI app (webhook / production mode) ────────────────────────────────────

ptb_app: Application = None  # initialised in lifespan


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global ptb_app
    ptb_app = build_ptb_app()
    await ptb_app.initialize()
    await ptb_app.bot.set_webhook(WEBHOOK_URL)
    await ptb_app.start()
    logger.info("Webhook set to %s", WEBHOOK_URL)

    health_url = WEBHOOK_URL.replace("/webhook", "/health")
    asyncio.create_task(keep_alive(health_url))

    yield

    await ptb_app.stop()
    await ptb_app.shutdown()


web_app = FastAPI(lifespan=lifespan)


@web_app.get("/")
async def root() -> dict:
    return {"status": "Bot is running", "endpoints": ["/health", "/webhook"]}


@web_app.post("/webhook")
async def webhook(request: Request) -> Response:
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(content="ok")


@web_app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set")

    if WEBHOOK_URL:
        # Production: start the FastAPI webhook server directly
        uvicorn.run("bot:web_app", host="0.0.0.0", port=PORT)
    else:
        # Local development: polling is simpler and needs no public URL
        logger.info("No WEBHOOK_URL found — starting in polling mode.")
        polling_app = build_ptb_app()
        polling_app.run_polling()
