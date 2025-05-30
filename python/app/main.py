import os
import requests
import tempfile
import math
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

# Load environment variables from .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")

# Validate required environment variables
if not all([TELEGRAM_TOKEN, FEATHERLESS_API_KEY, GOLEMIO_API_KEY]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

# Setup OpenAI-compatible Featherless client
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)

# === SIMULATED CLASSIFIER ===
def classify_image(image_path):
    try:
        # Replace this with a real ML model or cloud vision API
        return "plastic bottle"
    except Exception as e:
        raise Exception(f"Error classifying image: {str(e)}")

def map_to_bin(item):
    bin_mapping = {
        "plastic bottle": "yellow",
        "glass bottle": "green",
        "paper": "blue",
        "cardboard": "blue",
        "metal": "yellow",
        "organic": "brown"
    }
    return bin_mapping.get(item.lower(), "unknown")

# Helper: Translate message to target language
def translate_text(text, target_lang):
    try:
        if not text:
            return ""
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

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r * 1000  # Convert to meters

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lang = update.effective_user.language_code or "en"
        message = (
            "👋 Hi! I'm your smart recycling assistant.\n"
            "You can:\n"
            "1. Send me a photo of your waste to find the right recycling bin\n"
            "2. Share your location to find the nearest smart trash container\n\n"
            "How can I help you today?"
        )
        translated = translate_text(message, lang)
        await update.message.reply_text(translated)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# Photo handler for waste classification
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lang = update.effective_user.language_code or "en"
        photo = update.message.photo[-1]
        file = await photo.get_file()
        
        # Create a temporary file with proper cleanup
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            image_path = temp_file.name
            await file.download_to_drive(image_path)

        try:
            item = classify_image(image_path)
            bin_color = map_to_bin(item)
            context.user_data["last_item"] = (item, bin_color)

            message = (
                f"I think it's a *{item}*.\n"
                f"Please share your location so I can find the nearest *{bin_color}* bin."
            )
            translated = translate_text(message, lang)
            
            await update.message.reply_text(
                translated,
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("📍 Send Location", request_location=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                ),
                parse_mode='Markdown'
            )
        finally:
            # Clean up the temporary file
            if os.path.exists(image_path):
                os.unlink(image_path)

    except Exception as e:
        await update.message.reply_text(f"Error processing photo: {str(e)}")

# Location handler for both smart containers and recycling bins
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        latitude = loc.latitude
        longitude = loc.longitude
        lang = update.effective_user.language_code or "en"

        headers = {"x-access-token": GOLEMIO_API_KEY}
        params = {
            "latlng": f"{latitude},{longitude}",
            "range": 500,
            "onlyMonitored": "true",
            "limit": 5  # Get more points to calculate closest
        }

        # Check if this is a follow-up to a photo (recycling bin search)
        if "last_item" in context.user_data:
            item, bin_color = context.user_data["last_item"]
            del context.user_data["last_item"]  # Clear the stored item

            try:
                response = requests.get(
                    "https://api.golemio.cz/v2/sortedwastestations",
                    headers=headers,
                    params=params,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                features = data.get("features", [])

                if not features:
                    message = f"🚫 No {bin_color} bins found within 500m for {item}."
                    translated = translate_text(message, lang)
                    await update.message.reply_text(translated)
                    return

                # Find the closest point
                closest_feature = min(
                    features,
                    key=lambda f: calculate_distance(
                        latitude,
                        longitude,
                        f["geometry"]["coordinates"][1],
                        f["geometry"]["coordinates"][0]
                    )
                )

                properties = closest_feature["properties"]
                name = properties["name"]
                address = properties.get("address", "Address not available")
                street = properties.get("street", "")
                district = properties.get("district", "Unknown")
                city = properties.get("city", "Prague")
                
                # Calculate exact distance
                distance = calculate_distance(
                    latitude,
                    longitude,
                    closest_feature["geometry"]["coordinates"][1],
                    closest_feature["geometry"]["coordinates"][0]
                )

                message = (
                    f"🗑️ *Nearest {bin_color} bin for {item}:*\n\n"
                    f"*{name}*\n"
                    f"📍 Address: {address}\n"
                )
                if street:
                    message += f"Street: {street}\n"
                message += (
                    f"District: {district}\n"
                    f"City: {city}\n"
                    f"Distance: {distance:.0f}m"
                )

                translated = translate_text(message, lang)
                await update.message.reply_text(translated, parse_mode='Markdown')

            except requests.exceptions.RequestException as e:
                message = f"⚠️ Error finding recycling bin: {str(e)}"
                translated = translate_text(message, lang)
                await update.message.reply_text(translated)
            return

        # If no photo was sent, show nearest smart container
        try:
            response = requests.get(
                "https://api.golemio.cz/v2/sortedwastestations",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])

            if not features:
                message = "🚫 No monitored containers found within 500m."
                translated = translate_text(message, lang)
                await update.message.reply_text(translated)
                return

            # Find the closest point
            closest_feature = min(
                features,
                key=lambda f: calculate_distance(
                    latitude,
                    longitude,
                    f["geometry"]["coordinates"][1],
                    f["geometry"]["coordinates"][0]
                )
            )

            properties = closest_feature["properties"]
            name = properties["name"]
            district = properties.get("district", "Unknown")
            address = properties.get("address", "Address not available")
            street = properties.get("street", "")
            city = properties.get("city", "Prague")
            containers = properties["containers"]
            
            # Calculate exact distance
            distance = calculate_distance(
                latitude,
                longitude,
                closest_feature["geometry"]["coordinates"][1],
                closest_feature["geometry"]["coordinates"][0]
            )
            
            message = f"🗑️ *Closest Smart Trash Container (within 500m):*\n\n"
            message += f"*{name}*\n"
            message += f"📍 Address: {address}\n"
            if street:
                message += f"Street: {street}\n"
            message += f"District: {district}\n"
            message += f"City: {city}\n"
            message += f"Distance: {distance:.0f}m\n\n"
            
            if containers:
                message += "*Containers:*\n"
                for container in containers:
                    trash_type = container["trash_type"]["description"]
                    if container.get("last_measurement") and "percent_calculated" in container["last_measurement"]:
                        fullness = f"{container['last_measurement']['percent_calculated']}% full"
                    else:
                        fullness = "❓ fullness unknown"
                    message += f"• {trash_type}: {fullness}\n"
            else:
                message += "• No container data available\n"

            translated = translate_text(message, lang)
            await update.message.reply_text(translated, parse_mode='Markdown')

        except requests.exceptions.RequestException as e:
            message = f"⚠️ Golemio API error: {str(e)}"
            translated = translate_text(message, lang)
            await update.message.reply_text(translated)

    except Exception as e:
        await update.message.reply_text(f"Error processing location: {str(e)}")

# App runner
if __name__ == '__main__':
    try:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        app.run_polling()
    except Exception as e:
        print(f"Error starting the bot: {str(e)}")
