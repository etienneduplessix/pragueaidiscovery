import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")

# Set up OpenAI client with Featherless endpoint
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)

# Enable logging
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I’m your LLaMA-powered AI assistant. Ask me anything!")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    try:
        response = client.chat.completions.create(
            model='meta-llama/Meta-Llama-3.1-8B-Instruct',
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input}
            ],
        )
        reply = response.model_dump()['choices'][0]['message']['content']
    except Exception as e:
        reply = f"Error: {str(e)}"

    await update.message.reply_text(reply)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.run_polling()
