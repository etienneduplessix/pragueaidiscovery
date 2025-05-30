import os
import requests
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from openai import OpenAI

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")

client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)
MODEL = "deepseek-ai/DeepSeek-V3-0324"

# Translation using DeepSeek
def translate_text(text, target_lang):
    try:
        if target_lang.lower() in ["en", ""]:
            return text
        response = client.chat.completions.create(
            model=MODEL,
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
    msg = "👋 Hi! I'm your waste assistant.\nUse /findtrash and share your location 📍 to get disposal info."
    await update.message.reply_text(translate_text(msg, lang))

# /findtrash command - asks what type of trash user has
async def findtrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code or "en"
    buttons = [
        [InlineKeyboardButton("♻️ Smart Bin", callback_data="smarttrash")],
        [InlineKeyboardButton("📦 Bulky Waste", callback_data="bulkytrash")],
        [InlineKeyboardButton("🏭 Collection Yard", callback_data="wasteyard")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    msg = "What type of trash do you want to dispose of?"
    await update.message.reply_text(translate_text(msg, lang), reply_markup=reply_markup)

# Handles trash type choice and asks for location
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code or "en"
    query = update.callback_query
    await query.answer()
    choice = query.data
    context.user_data["mode"] = choice

    button = KeyboardButton(text=translate_text("📍 Send Location", lang), request_location=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

    prompt = {
        "smarttrash": "Please send your location to find a smart trash container.",
        "bulkytrash": "Please send your location to find a bulky waste station.",
        "wasteyard": "Please send your location to find a collection yard."
    }.get(choice, "Please send your location.")

    await query.message.reply_text(translate_text(prompt, lang), reply_markup=reply_markup)

# Location handler: uses mode from user_data
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    latitude, longitude = loc.latitude, loc.longitude
    lang = update.effective_user.language_code or "en"
    mode = context.user_data.get("mode", "smarttrash")

    try:
        if mode == "smarttrash":
            url = "https://api.golemio.cz/v2/sortedwastestations"
            params = {"latlng": f"{latitude},{longitude}", "range": 1000, "onlyMonitored": "true", "limit": 1}
            r = requests.get(url, headers={"x-access-token": GOLEMIO_API_KEY}, params=params)
            data = r.json()
            if not data.get("features"):
                raise Exception("No smart containers nearby.")
            feature = data["features"][0]
            name = feature["properties"]["name"]
            district = feature["properties"].get("district", "Unknown")
            reply = f"📍 *Smart Trash Container*\nLocation: *{name}* ({district})\n"
            for c in feature["properties"]["containers"]:
                t = c["trash_type"]["description"]
                f = c.get("last_measurement", {}).get("percent_calculated", "?")
                reply += f"• {t}: {f}% full\n"

        elif mode == "bulkytrash":
            url = "https://api.golemio.cz/v1/bulky-waste/stations"
            params = {"latlng": f"{latitude},{longitude}", "range": 1, "limit": 1}
            r = requests.get(url, headers={"x-access-token": GOLEMIO_API_KEY}, params=params)
            data = r.json()
            if not data.get("features"):
                raise Exception("No bulky waste containers nearby.")
            p = data["features"][0]["properties"]
            reply = f"📦 *Bulky Waste Container*\nStreet: *{p['street']}*\nDate: {p['date']} {p['timeFrom']}–{p['timeTo']}\nDistrict: {p['cityDistrict']}"

        elif mode == "wasteyard":
            url = "https://api.golemio.cz/v2/wastecollectionyards"
            params = {"latlng": f"{latitude},{longitude}", "range": 5000, "limit": 1}
            r = requests.get(url, headers={"x-access-token": GOLEMIO_API_KEY}, params=params)
            data = r.json()
            if not data.get("features"):
                raise Exception("No waste collection yards nearby.")
            yard = data["features"][0]["properties"]
            addr = yard["address"]["address_formatted"]
            hours = yard.get("operating_hours", "Unknown hours")
            name = yard["name"]
            contact = yard.get("contact", "")
            reply = f"🏭 *Waste Collection Yard*\n{name}\n📍 {addr}\n🕒 {hours}\n📞 {contact}"

        else:
            reply = "Unknown request mode."

        await update.message.reply_text(translate_text(reply, lang), parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(translate_text(f"⚠️ Error: {e}", lang))

# Fallback for unsupported content
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code or "en"
    msg = "Please use /findtrash and share your location 📍."
    await update.message.reply_text(translate_text(msg, lang))

# Main app
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("findtrash", findtrash))

    # Choice and response handlers
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.LOCATION, unknown))

    app.run_polling()
