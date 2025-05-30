import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

# Load environment variables from .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")

# Setup OpenAI-compatible Featherless client
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)

# Helper: Translate message to target language
def translate_text(text, target_lang):
    try:
        if target_lang.lower() in ["en", ""]:
            return text  # No translation needed
        response = client.chat.completions.create(
            model='meta-llama/Meta-Llama-3.1-8B',
            messages=[
                {"role": "system", "content": f"Translate the following message to {target_lang.upper()}."},
                {"role": "user", "content": text}
            ]
        )
        return response.model_dump()['choices'][0]['message']['content']
    except Exception as e:
        return f"Translation error: {str(e)}"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code or "en"
    message = (
        "👋 Hi! I'm your smart assistant.\n"
        "Send me a message to chat, or share your location 📍 to find the nearest smart trash container."
    )
    translated = translate_text(message, lang)
    await update.message.reply_text(translated)

# Chat handler
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    lang = update.effective_user.language_code or "en"

    try:
        response = client.chat.completions.create(
            model='meta-llama/Meta-Llama-3.1-8B',
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.model_dump()['choices'][0]['message']['content']
        translated = translate_text(reply, lang)
    except Exception as e:
        translated = f"⚠️ Error: {str(e)}"

    await update.message.reply_text(translated)

# Location handler for Golemio smart containers
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    latitude = loc.latitude
    longitude = loc.longitude
    lang = update.effective_user.language_code or "en"

    headers = {
        "x-access-token": GOLEMIO_API_KEY
    }

    params = {
        "latlng": f"{latitude},{longitude}",
        "range": 1000,
        "onlyMonitored": "true",
        "limit": 1
    }

    try:
        response = requests.get(
            "https://api.golemio.cz/v2/sortedwastestations",
            headers=headers,
            params=params
        )
        data = response.json()
        features = data.get("features", [])

        if not features:
            await update.message.reply_text(
                translate_text("🚫 No monitored containers nearby.", lang)
            )
            return

        feature = features[0]
        name = feature["properties"]["name"]
        district = feature["properties"].get("district", "Unknown")
        containers = feature["properties"]["containers"]

        if not containers:
            await update.message.reply_text(
                translate_text("🚫 No container data found at the closest location.", lang)
            )
            return

        reply = f"📍 *Closest Smart Trash Container:*\n"
        reply += f"Location: *{name}* ({district})\n\n"

        for container in containers:
            trash_type = container["trash_type"]["description"]
            if container.get("last_measurement") and "percent_calculated" in container["last_measurement"]:
                fullness = f"{container['last_measurement']['percent_calculated']}% full"
            else:
                fullness = "❓ fullness unknown"
            reply += f"• {trash_type}: {fullness}\n"

        translated = translate_text(reply, lang)
        await update.message.reply_text(translated, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(
            translate_text(f"⚠️ Golemio API error: {e}", lang)
        )

# App runner
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.run_polling()
