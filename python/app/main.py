import os
import base64
import tempfile
import requests
from dotenv import load_dotenv
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI
import math

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
GOLEMIO_API_KEY = os.getenv("GOLEMIO_API_KEY")
VISION_API_KEY = os.getenv("VISION_API_KEY")

# OpenAI client for DeepSeek / translation
client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=FEATHERLESS_API_KEY
)
MODEL = "deepseek-ai/DeepSeek-V3-0324"

# API configuration
GOLEMIO_HEADERS = {"x-access-token": GOLEMIO_API_KEY}


# ── Utility Functions ───────────────────────────────────────────────────────────

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate Haversine distance (in meters) between two lat/lon pairs,
    and also return a Google Maps "directions" URL.
    """
    R = 6371000  # Earth's radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    maps_link = f"https://www.google.com/maps/dir/{lat1},{lon1}/{lat2},{lon2}"
    return distance, maps_link


def translate_text(text: str, target_lang: str = "en") -> str:
    """
    If target_lang starts with "en", return text unchanged.
    Otherwise, send a translation prompt to the LLM to translate text
    into `target_lang`, returning the translated result.
    """
    if target_lang.lower().startswith("en"):
        return text

    resp = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a translation assistant. "
                    f"Translate the user’s text into fluent, idiomatic {target_lang}."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        max_tokens=len(text.split()) * 2,
    )
    return resp.choices[0].message.content.strip()


def classify_image(image_path):
    """
    Classify an image using Google Vision API (LABEL_DETECTION). 
    Return the first “useful” label that maps to a non–“Mixed waste” category,
    or fallback to the first label if none match.
    """
    try:
        with open(image_path, "rb") as image_file:
            content = base64.b64encode(image_file.read()).decode("utf-8")

        url = "https://vision.googleapis.com/v1/images:annotate"
        params = {"key": VISION_API_KEY}
        headers = {"Content-Type": "application/json"}
        body = {
            "requests": [
                {
                    "image": {"content": content},
                    "features": [{"type": "LABEL_DETECTION", "maxResults": 5}],
                }
            ]
        }

        response = requests.post(url, params=params, headers=headers, json=body)
        result = response.json()

        labels = [
            l["description"].lower()
            for l in result["responses"][0].get("labelAnnotations", [])
        ]
        for label in labels:
            category, _color = map_to_bin(label)
            if category != "Mixed waste":
                return label  # Return first “useful” match
        return labels[0] if labels else "unknown"

    except Exception as e:
        raise Exception(f"Error classifying image: {str(e)}")


def map_to_bin(label):
    """
    Assign a waste category + bin color based on the label.
    """
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
    return ("Mixed waste", "black")


# ── Command Handlers ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start → send a welcome message. Translate it according to the user’s language_code.
    """
    lang = update.effective_user.language_code or "en"
    welcome_msg = (
        "👋 **Welcome to Prague Waste Assistant Bot!**\n\n"
        "I can help you find:\n"
        "♻️ Smart trash containers\n"
        "📦 Bulky waste collection points\n"
        "🏭 Waste collection yards\n\n"
        "Just type **/findtrash** to get started!"
    )
    translated = translate_text(welcome_msg, lang)
    await update.message.reply_text(translated, parse_mode="Markdown")


async def findtrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /findtrash → show three inline buttons (Smart Bins, Bulky Waste, Collection Yards).
    The prompt itself is translated.
    """
    lang = update.effective_user.language_code or "en"
    buttons = [
        [InlineKeyboardButton("♻️ Smart Bins", callback_data="smarttrash")],
        [InlineKeyboardButton("📦 Bulky Waste", callback_data="bulkytrash")],
        [InlineKeyboardButton("🏭 Collection Yards", callback_data="wasteyard")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    prompt = (
        "🗑️ **What type of waste disposal are you looking for?**\n\n"
        "Choose an option below:"
    )
    translated = translate_text(prompt, lang)
    await update.message.reply_text(translated, reply_markup=reply_markup, parse_mode="Markdown")


# ── Photo Handler ──────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When a user sends a photo, download it, classify it, store (item, bin_color) in user_data,
    then ask the user for location. All prompts are passed through translate_text(…, lang).
    """
    try:
        lang = update.effective_user.language_code or "en"
        photo = update.message.photo[-1]
        file = await photo.get_file()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            image_path = temp_file.name
            await file.download_to_drive(image_path)

        try:
            item = classify_image(image_path)
            _, bin_color = map_to_bin(item)
            context.user_data["last_item"] = (item, bin_color)

            message = (
                f"I think it's a *{item}*.\n"
                f"Please share your location so I can find the nearest *{bin_color}* bin."
            )
            translated = translate_text(message, lang)
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("📍 Send Location", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await update.message.reply_text(translated, reply_markup=keyboard, parse_mode="Markdown")
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)

    except Exception as e:
        err_msg = f"Error processing photo: {str(e)}"
        lang = update.effective_user.language_code or "en"
        await update.message.reply_text(translate_text(err_msg, lang))


# ── CallbackQuery / Button Handler for findtrash ─────────────────────────────────

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User tapped one of the inline buttons under /findtrash.
    We record context.user_data["mode"], then ask for location. The prompt is translated.
    """
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code or "en"

    choice = query.data
    context.user_data["mode"] = choice

    location_button = KeyboardButton("📍 Share My Location", request_location=True)
    reply_markup = ReplyKeyboardMarkup(
        [[location_button]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    messages = {
        "smarttrash": (
            "📍 **Smart Bins Selected**\n\n"
            "Please share your location to find the nearest smart trash containers with fill levels."
        ),
        "bulkytrash": (
            "📍 **Bulky Waste Selected**\n\n"
            "Please share your location to find the nearest bulky waste collection points."
        ),
        "wasteyard": (
            "📍 **Collection Yards Selected**\n\n"
            "Please share your location to find the nearest waste collection yards."
        ),
    }
    prompt = messages.get(choice, "📍 Please share your location to continue.")
    translated = translate_text(prompt, lang)
    await query.message.reply_text(translated, reply_markup=reply_markup, parse_mode="Markdown")


# ── Waste-Handling Helper Functions (Return English text) ───────────────────────

async def handle_smart_trash(latitude, longitude) -> str:
    """
    Query Golemio's sortedwastestations for “onlyMonitored” smart bins.
    Return an English-formatted string of up to 3 results.
    """
    url = "https://api.golemio.cz/v2/sortedwastestations"
    params = {
        "latlng": f"{latitude},{longitude}",
        "range": 1000,
        "onlyMonitored": "true",
        "limit": 1,
    }
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()

    if not data.get("features"):
        return "❌ **No smart containers found within 1km of your location.**\n\nTry moving closer to a residential area or check back later."

    reply = "♻️ **Smart Trash Containers Near You:**\n\n"
    for i, feature in enumerate(data["features"], start=1):
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


async def handle_bulky_waste(latitude, longitude) -> str:
    """
    Query Golemio’s bulky-waste/stations. Return up to 3 points in English.
    """
    url = "https://api.golemio.cz/v1/bulky-waste/stations"
    params = {
        "latlng": f"{latitude},{longitude}",
        "range": 2,
        "limit": 1,
    }
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()

    if not data.get("features"):
        return "❌ **No bulky waste collection points found within 2km.**"

    reply = "📦 **Bulky Waste Collection Points:**\n\n"
    for i, feature in enumerate(data["features"], start=1):
        props = feature["properties"]
        street = props.get("street", "Unknown street")
        district = props.get("cityDistrict", "Unknown district")
        date = props.get("date", "TBD")
        time_from = props.get("timeFrom", "TBD")
        time_to = props.get("timeTo", "TBD")
        reply += (
            f"**{i}. {street}**\n"
            f"📅 Date: {date}\n"
            f"🕐 Time: {time_from} - {time_to}\n"
            f"📍 District: {district}\n\n"
        )
    return reply


async def handle_waste_yards(latitude, longitude) -> str:
    """
    Query Golemio’s wastecollectionyards. Return up to 3 results in English.
    """
    url = "https://api.golemio.cz/v2/wastecollectionyards"
    params = {
        "latlng": f"{latitude},{longitude}",
        "range": 5000,
        "limit": 2,
    }
    response = requests.get(url, headers=GOLEMIO_HEADERS, params=params)
    response.raise_for_status()
    data = response.json()

    if not data.get("features"):
        return "❌ **No waste collection yards found within 5km.**"

    reply = "🏭 **Waste Collection Yards Near You:**\n\n"
    for i, feature in enumerate(data["features"], start=1):
        props = feature["properties"]
        name = props.get("name", "Unnamed facility")
        address = props.get("address", {}).get("address_formatted", "Address not available")
        hours = props.get("operating_hours", "Hours not available")
        contact = props.get("contact", "No contact info")
        reply += (
            f"**{i}. {name}**\n"
            f"📍 {address}\n"
            f"🕒 {hours}\n"
            f"📞 {contact}\n\n"
        )
    return reply


# ── Location Handler ──────────────────────────────────────────────────────────

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When the user shares a location:
      • If they had just sent a photo (and we stored last_item), find the closest bin for that item.
      • Else if context.user_data["mode"] is set (smarttrash / bulkytrash / wasteyard), call the appropriate helper.
      • Otherwise, show the single closest “monitored” container (500m).
    All outgoing strings are translated via translate_text(…, lang).
    """
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
            "limit": 5,  # fetch up to 5 to pick the closest
        }

        # ─ If user had just sent a photo (we want a specific color bin)
        if "last_item" in context.user_data:
            item, bin_color = context.user_data["last_item"]
            del context.user_data["last_item"]

            try:
                response = requests.get(
                    "https://api.golemio.cz/v2/sortedwastestations",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()
                features = data.get("features", [])

                if not features:
                    message = f"🚫 No {bin_color} bins found within 500m for {item}."
                    await update.message.reply_text(translate_text(message, lang))
                    return

                # Find the very closest feature
                closest_feature = min(
                    features,
                    key=lambda f: calculate_distance(
                        latitude,
                        longitude,
                        f["geometry"]["coordinates"][1],
                        f["geometry"]["coordinates"][0],
                    )[0],
                )
                props = closest_feature["properties"]
                name = props.get("name", "Unknown")
                address = props.get("address", "Address not available")
                street = props.get("street", "")
                district = props.get("district", "Unknown")
                city = props.get("city", "Prague")

                # Compute exact distance + link
                distance, maps_link = calculate_distance(
                    latitude,
                    longitude,
                    closest_feature["geometry"]["coordinates"][1],
                    closest_feature["geometry"]["coordinates"][0],
                )

                msg = (
                    f"🗑️ *Nearest {bin_color} bin for {item}:*\n\n"
                    f"*{name}*\n"
                )
                if street:
                    msg += f"Street: {street}\n"
                msg += (
                    f"Distance: {distance:.0f}m\n"
                    f"[🗺️ Open in Google Maps]({maps_link})"
                )
                await update.message.reply_text(translate_text(msg, lang), parse_mode="Markdown")

            except requests.exceptions.RequestException as e:
                err = f"⚠️ Error finding recycling bin: {str(e)}"
                await update.message.reply_text(translate_text(err, lang))
            return

        # ─ If user tapped one of the “/findtrash” options (mode is set)
        mode = context.user_data.get("mode")
        if mode:
            remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True, one_time_keyboard=True)
            searching_msg = "🔍 **Searching nearby...**"
            await update.message.reply_text(translate_text(searching_msg, lang), reply_markup=remove_keyboard)

            try:
                if mode == "smarttrash":
                    result_en = await handle_smart_trash(latitude, longitude)
                elif mode == "bulkytrash":
                    result_en = await handle_bulky_waste(latitude, longitude)
                elif mode == "wasteyard":
                    result_en = await handle_waste_yards(latitude, longitude)
                else:
                    result_en = "❌ **Unknown request type.**\n\nPlease use /findtrash."

                await update.message.reply_text(translate_text(result_en, lang), parse_mode="Markdown")
                context.user_data.pop("mode", None)
                return

            except requests.RequestException:
                msg = "⚠️ **Service temporarily unavailable.**\n\nPlease try again later."
                await update.message.reply_text(translate_text(msg, lang))
                return
            except Exception as e:
                err = f"❌ **Something went wrong.**\n\nError: {str(e)}"
                await update.message.reply_text(translate_text(err, lang))
                return

        # ─ If no photo, no mode: show the single closest monitored container (within 500m)
        try:
            response = requests.get(
                "https://api.golemio.cz/v2/sortedwastestations",
                headers=headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])

            if not features:
                msg = "🚫 No monitored containers found within 500m."
                await update.message.reply_text(translate_text(msg, lang))
                return

            # Find the closest feature
            closest_feature = min(
                features,
                key=lambda f: calculate_distance(
                    latitude,
                    longitude,
                    f["geometry"]["coordinates"][1],
                    f["geometry"]["coordinates"][0],
                )[0],
            )
            props = closest_feature["properties"]
            name = props.get("name", "Unknown")
            district = props.get("district", "Unknown")
            address = props.get("address", "Address not available")
            street = props.get("street", "")
            city = props.get("city", "Prague")
            containers = props.get("containers", [])

            distance, maps_link = calculate_distance(
                latitude,
                longitude,
                closest_feature["geometry"]["coordinates"][1],
                closest_feature["geometry"]["coordinates"][0],
            )

            msg = f"🗑️ *Closest Smart Trash Container (within 500m):*\n\n"
            msg += f"*{name}*\n"
            msg += f"Distance: {distance:.0f}m\n"
            msg += f"[🗺️ Open in Google Maps]({maps_link})\n\n"

            if containers:
                msg += "*Containers:*\n"
                for container in containers:
                    trash_type = container.get("trash_type", {}).get("description", "Unknown")
                    if (
                        container.get("last_measurement")
                        and "percent_calculated" in container["last_measurement"]
                    ):
                        fullness = f"{container['last_measurement']['percent_calculated']}% full"
                    else:
                        fullness = "❓ fullness unknown"
                    msg += f"• {trash_type}: {fullness}\n"
            else:
                msg += "• No container data available\n"

            await update.message.reply_text(translate_text(msg, lang), parse_mode="Markdown")

        except requests.exceptions.RequestException as e:
            msg = f"⚠️ Golemio API error: {str(e)}"
            await update.message.reply_text(translate_text(msg, lang))

    except Exception as e:
        err = f"Error processing location: {str(e)}"
        lang = update.effective_user.language_code or "en"
        await update.message.reply_text(translate_text(err, lang))


# ── General Chat Handler (powered by DeepSeek) ─────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Any text message (that isn’t a command) goes here. We forward it to the LLM (DeepSeek-V3-0324),
    and return the reply. We also maintain a small conversation history.
    """
    message_text = update.message.text.strip()
    lang = update.effective_user.language_code or "en"

    # If user explicitly asks for “help” or “info”
    if any(word in message_text.lower() for word in ["help", "info", "what can you do"]):
        help_text = (
            "ℹ️ **How to use this bot:**\n\n"
            "**🗑️ Waste Management:**\n"
            "• Type /findtrash to locate disposal points\n"
            "• Send a 📸 photo of waste for bin identification\n"
            "• Share 📍 location for nearest containers\n\n"
            "**💬 General Chat:**\n"
            "• Ask me anything - I'm powered by AI!\n"
            "• Get help with questions about Prague\n"
            "• Chat about any topic you're interested in\n\n"
            "**Commands:**\n"
            "• /start - Welcome message\n"
            "• /findtrash - Find waste disposal points\n"
            "• /chat - Toggle chat mode (always on by default)"
        )
        await update.message.reply_text(translate_text(help_text, lang))
        return

    # Otherwise, forward the conversation to the LLM
    try:
        await update.message.reply_chat_action("typing")
        if "chat_history" not in context.user_data:
            context.user_data["chat_history"] = []

        # Add user’s message
        context.user_data["chat_history"].append({"role": "user", "content": message_text})

        # Keep only last 10 messages total
        if len(context.user_data["chat_history"]) > 10:
            context.user_data["chat_history"] = context.user_data["chat_history"][-10:]

        messages = [
            {
                "role": "system",
                "content": """You are a helpful and friendly AI assistant integrated into a Prague Waste Management Telegram bot.

Your primary expertise is helping users with waste disposal and recycling in Prague, but you can chat about absolutely anything else too!

Key capabilities:
- Help with waste management questions (bins, recycling, disposal)
- Provide information about Prague city services
- Engage in general conversation on any topic
- Be conversational, helpful, and knowledgeable

Guidelines:
- Keep responses concise but informative (under 300 words)
- Be friendly and conversational
- If asked about waste/recycling, mention the bot's photo and location features
- For Prague-specific questions, provide helpful local context
- For general topics, be engaging and informative

Remember: Users can send photos of waste for identification and share location for finding nearby disposal points."""
            }
        ]
        messages.extend(context.user_data["chat_history"])

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.8,
            top_p=0.9,
        )
        reply = response.choices[0].message.content.strip()
        context.user_data["chat_history"].append({"role": "assistant", "content": reply})

        # Finally, translate the LLM’s reply into the user’s language before sending
        await update.message.reply_text(translate_text(reply, lang))

    except Exception as e:
        error_messages = [
            "🤔 Hmm, I'm having trouble thinking right now. Try asking me something else!",
            "⚡ My brain circuits are a bit overloaded. Give me a moment and try again!",
            "🔄 Something went wrong on my end. Could you rephrase that?",
            "💭 I'm experiencing some technical difficulties. Let's try that again!",
        ]
        import random

        await update.message.reply_text(translate_text(random.choice(error_messages), lang))
        print(f"[LLM Chat Error]: {e}")


# ── /chat Info Command ─────────────────────────────────────────────────────────

async def chat_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /chat → explain how chat mode works. Entire reply is translated.
    """
    lang = update.effective_user.language_code or "en"
    info_text = (
        "💬 **Chat Mode Information**\n\n"
        "I'm always ready to chat! You can ask me about:\n\n"
        "🗑️ **Waste & Recycling:**\n"
        "• 'How do I dispose of electronics?'\n"
        "• 'What bin for plastic bottles?'\n"
        "• 'Where can I throw away furniture?'\n\n"
        "🏙️ **Prague Questions:**\n"
        "• 'Best places to visit in Prague'\n"
        "• 'How does public transport work?'\n"
        "• 'Prague weather information'\n\n"
        "🤖 **General Topics:**\n"
        "• Technology, science, cooking, travel\n"
        "• Explain complex topics simply\n"
        "• Creative writing and brainstorming\n"
        "• And much more!\n\n"
        "Just type your message and I'll respond! 😊"
    )
    await update.message.reply_text(translate_text(info_text, lang))


# ── Main Application Setup ─────────────────────────────────────────────────────

def main():
    if not all([TELEGRAM_TOKEN, GOLEMIO_API_KEY, FEATHERLESS_API_KEY]):
        raise ValueError("Missing one or more environment variables.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("findtrash", findtrash))
    app.add_handler(CommandHandler("chat", chat_info))

    # CallbackQuery (for /findtrash buttons)
    app.add_handler(CallbackQueryHandler(handle_choice))

    # Photo & Location & Text message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot started and ready!")
    app.run_polling()


if __name__ == "__main__":
    main()
