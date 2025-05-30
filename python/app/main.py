import os
import requests
import tempfile
import math
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, decode_predictions, preprocess_input
from tensorflow.keras.preprocessing import image
import numpy as np

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")

if not TELEGRAM_TOKEN or not GOLEMIO_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GOLEMIO_API_KEY in environment variables.")

# Load MobileNetV2 model once
mobilenet_model = MobileNetV2(weights='imagenet')

def classify_image(image_path):
    try:
        img = image.load_img(image_path, target_size=(224, 224))
        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0)
        x = preprocess_input(x)
        preds = mobilenet_model.predict(x)
        decoded = decode_predictions(preds, top=1)[0][0]
        label = decoded[1].replace("_", " ").lower()
        return label
    except Exception as e:
        raise Exception(f"ML classification failed: {str(e)}")

def map_to_bin(item):
    if any(word in item for word in ["plastic", "bottle", "can"]):
        return "yellow"
    elif any(word in item for word in ["glass"]):
        return "green"
    elif any(word in item for word in ["paper", "newspaper", "cardboard"]):
        return "blue"
    elif any(word in item for word in ["organic", "banana", "food", "apple"]):
        return "brown"
    elif any(word in item for word in ["metal"]):
        return "yellow"
    return "unknown"

def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371
    return c * r * 1000

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📷 Send Waste Photo", callback_data="sendphoto")],
        [InlineKeyboardButton("♻️ Find Trash Location", callback_data="findtrash")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "👋 Hi! I'm your smart recycling assistant.\nChoose what you want to do:",
        reply_markup=reply_markup
    )

async def handle_main_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "sendphoto":
        await query.message.reply_text("Please send me a photo of your waste.")
    elif query.data == "findtrash":
        await findtrash(update, context)

async def findtrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("♻️ Smart Bin", callback_data="smarttrash")],
        [InlineKeyboardButton("📦 Bulky Waste", callback_data="bulkytrash")],
        [InlineKeyboardButton("🏭 Collection Yard", callback_data="wasteyard")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    msg = "What type of trash do you want to dispose of?"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    context.user_data["mode"] = choice

    button = KeyboardButton(text="📍 Send Location", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

    prompt = {
        "smarttrash": "Please send your location to find a smart trash container.",
        "bulkytrash": "Please send your location to find a bulky waste station.",
        "wasteyard": "Please send your location to find a collection yard."
    }.get(choice, "Please send your location.")

    await query.message.reply_text(prompt, reply_markup=reply_markup)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
        image_path = temp_file.name
        await file.download_to_drive(image_path)

    try:
        item = classify_image(image_path)
        bin_color = map_to_bin(item)
        context.user_data["last_item"] = (item, bin_color)
        message = (
            f"I think it's a *{item}* (AI classified).\n"
            f"Please share your location so I can find the nearest *{bin_color}* bin."
        )
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📍 Send Location", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            ),
            parse_mode='Markdown'
        )
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    latitude = loc.latitude
    longitude = loc.longitude
    mode = context.user_data.get("mode", "smarttrash")
    headers = {"x-access-token": GOLEMIO_API_KEY}

    if "last_item" in context.user_data:
        item, bin_color = context.user_data.pop("last_item")
        params = {"latlng": f"{latitude},{longitude}", "range": 500, "onlyMonitored": "true", "limit": 5}
        response = requests.get("https://api.golemio.cz/v2/sortedwastestations", headers=headers, params=params)
        data = response.json()
        features = data.get("features", [])

        if not features:
            await update.message.reply_text(f"🚫 No {bin_color} bins found within 500m for {item}.")
            return

        closest = min(features, key=lambda f: calculate_distance(
            latitude, longitude, f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]))

        props = closest["properties"]
        name = props["name"]
        address = props.get("address", "Unknown")
        dist = calculate_distance(latitude, longitude, closest["geometry"]["coordinates"][1], closest["geometry"]["coordinates"][0])

        message = (
            f"🗑️ *Nearest {bin_color} bin for {item}:*\n\n*{name}*\n📍 Address: {address}\nDistance: {dist:.0f}m"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    if mode == "smarttrash":
        url = "https://api.golemio.cz/v2/sortedwastestations"
        params = {"latlng": f"{latitude},{longitude}", "range": 1000, "onlyMonitored": "true", "limit": 1}
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if not data.get("features"):
            await update.message.reply_text("🚫 No smart containers nearby.")
            return
        f = data["features"][0]
        name = f["properties"]["name"]
        district = f["properties"].get("district", "Unknown")
        reply = f"📍 *Smart Trash Container*\nLocation: *{name}* ({district})\n"
        for c in f["properties"]["containers"]:
            t = c["trash_type"]["description"]
            fullness = c.get("last_measurement", {}).get("percent_calculated", "?")
            reply += f"• {t}: {fullness}% full\n"
        await update.message.reply_text(reply, parse_mode='Markdown')

    elif mode == "bulkytrash":
        url = "https://api.golemio.cz/v1/bulky-waste/stations"
        params = {"latlng": f"{latitude},{longitude}", "range": 1, "limit": 1}
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if not data.get("features"):
            await update.message.reply_text("🚫 No bulky waste containers nearby.")
            return
        p = data["features"][0]["properties"]
        reply = f"📦 *Bulky Waste Container*\nStreet: *{p['street']}*\nDate: {p['date']} {p['timeFrom']}–{p['timeTo']}\nDistrict: {p['cityDistrict']}"
        await update.message.reply_text(reply, parse_mode='Markdown')

    elif mode == "wasteyard":
        url = "https://api.golemio.cz/v2/wastecollectionyards"
        params = {"latlng": f"{latitude},{longitude}", "range": 5000, "limit": 1}
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        if not data.get("features"):
            await update.message.reply_text("🚫 No waste collection yards nearby.")
            return
        y = data["features"][0]["properties"]
        reply = f"🏭 *Waste Collection Yard*\n{y['name']}\n📍 {y['address']['address_formatted']}\n🕒 {y.get('operating_hours', 'Unknown')}\n📞 {y.get('contact', '')}"
        await update.message.reply_text(reply, parse_mode='Markdown')
    else:
        await update.message.reply_text("Unknown request mode.")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please use /start and choose an action.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("findtrash", findtrash))
    app.add_handler(CallbackQueryHandler(handle_main_choice, pattern="^(sendphoto|findtrash)$"))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.LOCATION, unknown))
    app.run_polling()
