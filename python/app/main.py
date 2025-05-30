import os
import base64
import tempfile
import requests
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from openai import OpenAI
import math

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")
VISION_API_KEY = os.getenv("VISION_API_KEY")

# OpenAI client for DeepSeek
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)
MODEL = "deepseek-ai/DeepSeek-V3-0324"

# API configuration
GOLEMIO_HEADERS = {"x-access-token": GOLEMIO_API_KEY}

# Utility functions
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates and return Google Maps link"""
    # Haversine formula
    R = 6371000  # Earth's radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    # Google Maps link
    maps_link = f"https://www.google.com/maps/dir/{lat1},{lon1}/{lat2},{lon2}"
    
    return distance, maps_link

def translate_text(text, target_lang):
    """Basic translation function - can be enhanced with actual translation API"""
    # For now, return original text. Can be enhanced with Google Translate API
    return text

# Image classification functions
def classify_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            content = base64.b64encode(image_file.read()).decode("utf-8")

        url = "https://vision.googleapis.com/v1/images:annotate"
        params = {"key": VISION_API_KEY}
        headers = {"Content-Type": "application/json"}
        body = {
            "requests": [{
                "image": {"content": content},
                "features": [{"type": "LABEL_DETECTION", "maxResults": 5}]
            }]
        }

        response = requests.post(url, params=params, headers=headers, json=body)
        result = response.json()

        labels = [l['description'].lower() for l in result['responses'][0].get('labelAnnotations', [])]
        for label in labels:
            category, color = map_to_bin(label)
            if category != "Mixed waste":
                return label  # Return first useful match
        
        return labels[0] if labels else "unknown"

    except Exception as e:
        raise Exception(f"Error classifying image: {str(e)}")

def map_to_bin(label):
    label = label.lower()

    if any(x in label for x in ["plastic", "bottle", "pet", "packaging", "bag"]):
        return ("Plastics", "yellow")

    elif any(x in label for x in ["paper", "cardboard", "newspaper", "magazine", "envelope"]):
        return ("Paper", "blue")

    elif any(x in label for x in ["glass", "jar", "bottle"]):
        return ("Glass", "green")

    elif any(x in label for x in ["can", "tin", "metal", "aluminum", "foil"]):
        return ("Metals", "gray")

    elif any(x in label for x in ["fruit", "vegetable", "food", "organic", "peel", "compost"]):
        return ("Biodegradable waste", "brown")

    elif any(x in label for x in ["carton", "tetrapak", "juice box", "milk carton"]):
        return ("Beverage cartons", "orange")

    elif any(x in label for x in ["phone", "battery", "cable", "electronic", "charger"]):
        return ("Electronic waste", "drop-off")

    elif any(x in label for x in ["chemical", "paint", "medicine", "hazardous", "toxic"]):
        return ("Hazardous waste", "drop-off")

    elif any(x in label for x in ["clothes", "textile", "fabric", "shoes"]):
        return ("Textile", "drop-off")

    else:
        return ("Mixed waste", "black")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 **Welcome to Prague Waste Assistant Bot!**\n\n"
        "I can help you find:\n"
        "♻️ Smart trash containers\n"
        "📦 Bulky waste collection points\n"
        "🏭 Waste collection yards\n\n"
        "Just type **/findtrash** to get started!"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def findtrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("♻️ Smart Bins", callback_data="smarttrash")],
        [InlineKeyboardButton("📦 Bulky Waste", callback_data="bulkytrash")],
        [InlineKeyboardButton("🏭 Collection Yards", callback_data="wasteyard")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "🗑️ **What type of waste disposal are you looking for?**\n\nChoose an option below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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
                f"Please share your location so I can find the nearest *{bin_color[1]}* bin."
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

# Handle waste type selection
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    context.user_data["mode"] = choice

    location_button = KeyboardButton("📍 Share My Location", request_location=True)
    reply_markup = ReplyKeyboardMarkup(
        [[location_button]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

    messages = {
        "smarttrash": "📍 **Smart Bins Selected**\n\nPlease share your location to find the nearest smart trash containers with fill levels.",
        "bulkytrash": "📍 **Bulky Waste Selected**\n\nPlease share your location to find the nearest bulky waste collection points.",
        "wasteyard": "📍 **Collection Yards Selected**\n\nPlease share your location to find the nearest waste collection yards."
    }
    
    message = messages.get(choice, "📍 Please share your location to continue.")
    await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

# Waste handling functions
async def handle_smart_trash(latitude, longitude):
    url = "https://api.golemio.cz/v2/sortedwastestations"
    params = {
        "latlng": f"{latitude},{longitude}", 
        "range": 1000, 
        "onlyMonitored": "true", 
        "limit": 3
    }
    
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("features"):
        return "❌ **No smart containers found within 1km of your location.**\n\nTry moving closer to a residential area or check back later."

    reply = "♻️ **Smart Trash Containers Near You:**\n\n"

    for i, feature in enumerate(data["features"], 1):
        props = feature["properties"]
        name = props.get("name", "Unknown")
        district = props.get("district", "Unknown area")

        reply += f"**{i}. {name}**\n📍 {district}\n"

        containers = props.get("containers", [])
        if containers:
            reply += "📊 **Fill Levels:**\n"
            for container in containers:
                trash_type = container.get("trash_type", {}).get("description", "Unknown")
                fill_level = container.get("last_measurement", {}).get("percent_calculated", "Unknown")

                if isinstance(fill_level, (int, float)):
                    if fill_level < 30:
                        emoji = "🟢"
                    elif fill_level < 70:
                        emoji = "🟡"
                    else:
                        emoji = "🔴"
                    reply += f"   {emoji} {trash_type}: {fill_level}% full\n"
                else:
                    reply += f"   ⚪ {trash_type}: Status unknown\n"

        reply += "\n"

    return reply

async def handle_bulky_waste(latitude, longitude):
    url = "https://api.golemio.cz/v1/bulky-waste/stations"
    params = {
        "latlng": f"{latitude},{longitude}", 
        "range": 2,
        "limit": 3
    }
    
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("features"):
        return "❌ **No bulky waste collection points found within 2km.**"

    reply = "📦 **Bulky Waste Collection Points:**\n\n"
    for i, feature in enumerate(data["features"], 1):
        props = feature["properties"]
        street = props.get('street', 'Unknown street')
        district = props.get('cityDistrict', 'Unknown district')

        reply += (
            f"**{i}. {street}**\n"
            f"📅 Date: {props.get('date', 'TBD')}\n"
            f"🕐 Time: {props.get('timeFrom', 'TBD')} - {props.get('timeTo', 'TBD')}\n"
            f"📍 District: {district}\n\n"
        )

    return reply

async def handle_waste_yards(latitude, longitude):
    url = "https://api.golemio.cz/v2/wastecollectionyards"
    params = {
        "latlng": f"{latitude},{longitude}", 
        "range": 5000,
        "limit": 3
    }
    
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("features"):
        return "❌ **No waste collection yards found within 5km.**"

    reply = "🏭 **Waste Collection Yards Near You:**\n\n"
    for i, feature in enumerate(data["features"], 1):
        props = feature["properties"]
        address = props.get("address", {}).get("address_formatted", "Address not available")
        hours = props.get("operating_hours", "Hours not available")
        name = props.get("name", "Unnamed facility")
        contact = props.get("contact", "No contact info")

        reply += (
            f"**{i}. {name}**\n"
            f"📍 {address}\n"
            f"🕒 {hours}\n"
            f"📞 {contact}\n\n"
        )

    return reply

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
                    message = f"🚫 No {bin_color[1]} bins found within 500m for {item}."
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
                    )[0]
                )

                properties = closest_feature["properties"]
                name = properties.get("name", "Unknown")
                address = properties.get("address", "Address not available")
                street = properties.get("street", "")
                district = properties.get("district", "Unknown")
                city = properties.get("city", "Prague")
                
                # Calculate exact distance
                distance, maps_link = calculate_distance(
                    latitude,
                    longitude,
                    closest_feature["geometry"]["coordinates"][1],
                    closest_feature["geometry"]["coordinates"][0]
                )

                message = (
                    f"🗑️ *Nearest {bin_color[1]} bin for {item}:*\n\n"
                    f"*{name}*\n"
                    f"📍 Address: {address}\n"
                )
                if street:
                    message += f"Street: {street}\n"
                message += (
                    f"District: {district}\n"
                    f"City: {city}\n"
                    f"Distance: {distance:.0f}m\n"
                    f"[🗺️ Open in Google Maps]({maps_link})"
                )

                translated = translate_text(message, lang)
                await update.message.reply_text(translated, parse_mode='Markdown')

            except requests.exceptions.RequestException as e:
                message = f"⚠️ Error finding recycling bin: {str(e)}"
                translated = translate_text(message, lang)
                await update.message.reply_text(translated)
            return

        # Check if mode is set for findtrash functionality
        mode = context.user_data.get("mode")
        if mode:
            remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("🔍 **Searching nearby...**", reply_markup=remove_keyboard)

            try:
                if mode == "smarttrash":
                    result = await handle_smart_trash(latitude, longitude)
                elif mode == "bulkytrash":
                    result = await handle_bulky_waste(latitude, longitude)
                elif mode == "wasteyard":
                    result = await handle_waste_yards(latitude, longitude)
                else:
                    result = "❌ **Unknown request type.**\n\nPlease use /findtrash."

                await update.message.reply_text(result, parse_mode='Markdown')
                context.user_data.pop("mode", None)
                return

            except requests.RequestException:
                await update.message.reply_text(
                    "⚠️ **Service temporarily unavailable.**\n\nPlease try again later."
                )
                return
            except Exception as e:
                await update.message.reply_text(
                    f"❌ **Something went wrong.**\n\nError: {str(e)}"
                )
                return

        # If no photo was sent and no mode set, show nearest smart container
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
                )[0]
            )

            properties = closest_feature["properties"]
            name = properties.get("name", "Unknown")
            district = properties.get("district", "Unknown")
            address = properties.get("address", "Address not available")
            street = properties.get("street", "")
            city = properties.get("city", "Prague")
            containers = properties.get("containers", [])
            
            # Calculate exact distance
            distance, maps_link = calculate_distance(
                latitude,
                longitude,
                closest_feature["geometry"]["coordinates"][1],
                closest_feature["geometry"]["coordinates"][0]
            )
            
            message = f"🗑️ *Closest Smart Trash Container (within 500m):*\n\n"
            message += f"*{name}*\n"
            message += f"Distance: {distance:.0f}m\n"
            message += f"[🗺️ Open in Google Maps]({maps_link})\n\n"
            
            if containers:
                message += "*Containers:*\n"
                for container in containers:
                    trash_type = container.get("trash_type", {}).get("description", "Unknown")
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

# General chat handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()

    if any(word in message_text.lower() for word in ['help', 'info', 'what']):
        await update.message.reply_text(
            "ℹ️ **How to use this bot:**\n\n"
            "1️⃣ Type /findtrash\n"
            "2️⃣ Choose your waste type\n"
            "3️⃣ Share your location\n"
            "4️⃣ Get nearby disposal options!\n\n"
            "📸 Or send a photo of waste to identify the correct bin!"
        )
        return

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a friendly assistant who helps users with waste management in Prague and can talk about anything."},
                {"role": "user", "content": message_text}
            ],
            max_tokens=300,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("⚠️ Sorry, I couldn't process your message right now.")
        print(f"[DeepSeek Error]: {e}")

# Main function
def main():
    if not all([TELEGRAM_TOKEN, GOLEMIO_API_KEY, FEATHERLESS_API_KEY]):
        raise ValueError("Missing one or more environment variables.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("findtrash", findtrash))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot started and ready!")
    app.run_polling()

if __name__ == '__main__':
    main()