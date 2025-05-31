markdown

# Prague Waste Assistant Bot

A Telegram bot to help Prague residents identify waste items via photo classification and locate nearby waste-disposal points (smart bins, bulky-waste collection, waste yards) using the Golemio API. The bot integrates with an AI backend (Featherless API + Meta-Llama) for translation and general chat.

## Table of Contents

1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Environment Variables](#environment-variables)
5. [Local Development (Without Docker)](#local-development)
6. [Docker Setup](#docker-setup)
   - [Dockerfile (python:3.10-slim)](#dockerfile-python310-slim)
   - [Building & Running the Container](#building--running-the-container)
   - [Docker Compose](#docker-compose)
7. [Usage](#usage)
8. [Troubleshooting & Tips](#troubleshooting--tips)
9. [Contributing](#contributing)
10. [License](#license)

## Features

- **Image Classification**: Upload a photo of a waste item (e.g., plastic bottle, cardboard box), and the bot uses Google Vision API to identify it and map it to a colored bin (e.g., yellow for plastics, blue for paper).
- **Bin Locator**: After classification, share your location to find the nearest bin of the appropriate type within 500 meters.
- **Smart Bin Monitor**: Use `/findtrash → Smart Bins`, share your location, and view up to 3 nearby smart bins with fill-level indicators (🟢 green, 🟡 yellow, 🔴 red, or ⚪ unknown).
- **Bulky Waste & Waste Yards**: Use `/findtrash` to locate scheduled bulky-waste pickup points or permanent waste yards in Prague via the Golemio API.
- **Multilingual Support**: Messages are translated via Meta-Llama into the user’s Telegram language (if not English).
- **General AI Chat**: Non-command messages are sent to DeepSeek for AI responses, translated back to the user’s language if needed.

## Prerequisites

- **Docker** (≥ 20.10) and **Docker Compose** (≥ 1.29) for containerized deployment.
- **Python** (≥ 3.10) and **pip** for local development.
- **API Keys**:
  - **Telegram Bot Token**: Obtain from [@BotFather](https://telegram.me/BotFather).
  - **Featherless API Key**: Sign up at [Featherless](https://featherless.ai) for LLM access.
  - **Golemio API Key**: Register at [Golemio](https://golemio.cz) for Prague waste data.
  - **Google Cloud Vision API Key**: Enable at [Google Cloud Console](https://console.cloud.google.com) with billing.

## Project Structure

.
├── .env                    # Environment variables (never commit to Git)
├── docker-compose.yml      # Docker Compose configuration
├── python/
│   ├── Dockerfile          # Docker image definition
│   └── requirements.txt    # Python dependencies
├── app/
│   ├── main.py             # Bot entry point
│   ├── helpers.py         # Utility functions
│   ├── commands.py        # Command handlers
│   ├── utils.py           # Additional utilities
│   └── init.py        # Python package init
└── README.md              # Project documentation

## Environment Variables

Create a `.env` file in the project root with the following:

```env
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
FEATHERLESS_API_KEY=your-featherless-api-key
GOLEMIO_API_KEY=your-golemio-api-key
VISION_API_KEY=your-google-vision-api-key

Ensure .env is listed in .gitignore.

Replace placeholders with your actual API keys.

Local Development
Clone the Repository:
bash

git clone https://github.com/yourusername/prague-waste-bot.git
cd prague-waste-bot

Set Up Virtual Environment:
bash

python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

Install Dependencies:
bash

pip install --no-cache-dir -r python/requirements.txt

Configure .env:
bash

cp .env.example .env
# Edit .env with your API keys

Run the Bot:
bash

python app/main.py

Output:  Bot started and ready!

Test the Bot:
Open Telegram, find your bot, and send /start.

Test /findtrash or send a photo to classify waste.

Stop the bot with Ctrl+C.

Docker Setup
Dockerfile (python:3.10-slim)
dockerfile

FROM python:3.10-slim
WORKDIR /app
COPY python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .
CMD ["python", "main.py"]

Building & Running the Container
Build the Image:
bash

cd python
docker build -t prague-waste-bot:latest .

Run the Container:
bash

docker run -d --name prague-waste-bot --env-file ../.env prague-waste-bot:latest

Check Logs:
bash

docker logs -f prague-waste-bot

Stop & Remove:
bash

docker stop prague-waste-bot
docker rm prague-waste-bot

Docker Compose
yaml

version: '3.8'
services:
  telegram-bot:
    build: ./python
    env_file: .env
    restart: unless-stopped

Start the Service:
bash

docker-compose up -d --build

View Logs:
bash

docker-compose logs -f telegram-bot

Stop & Remove:
bash

docker-compose down
# Optional: Remove images
docker-compose down --rmi local

Usage
Open Telegram and search for your bot.

Send /start for a welcome message.

Use /findtrash to:
Smart Bins: Share location to see up to 3 nearby smart bins with fill levels.

Bulky Waste: Find scheduled pickup points (street, date, district).

Collection Yards: Locate waste yards (address, hours, contact).

Send a photo of a waste item to classify it and find the nearest bin.

Send any text (non-command) for an AI-powered response, translated to your Telegram language if needed.

Troubleshooting & Tips
Missing Environment Variables:
Verify .env contains all required keys.

Ensure no trailing spaces or quotes in .env.

Docker Container Fails:
Check logs: docker logs prague-waste-bot.

Common issues: Invalid API keys or missing .env.

Golemio API Errors (401/403):
Confirm GOLEMIO_API_KEY is valid and not expired.

Check Golemio documentation for JWT renewal.

Google Vision API Errors:
Ensure VISION_API_KEY has billing enabled and vision.googleapis.com is active.

Check quota limits in Google Cloud Console.

Slow LLM Responses:
Translation/chat involves API calls. Disable translation in translate_text() for testing.

Verify FEATHERLESS_API_KEY and check rate limits.

Improve Classification:
Adjust maxResults in Vision API requests.

Update map_to_bin() with more keywords or use a custom model.

Verbose Logging:
Add logging module to main.py for detailed debugging.

Contributing
Contributions are welcome! To contribute:
Fork the repository.

Create a branch (git checkout -b feature/your-feature).

Commit changes (git commit -m "Add your feature").

Push to your fork (git push origin feature/your-feature).

Open a pull request.

Report issues or suggest features via GitHub Issues.
License
This project is licensed under the MIT License. See LICENSE for details.

---

### How to Use This

1. **Save the README**:
   - Copy the above content into a file named `README.md` in your project root.
   - Replace `yourusername` in the repository URL with your actual GitHub username or remove it if the repo isn't public.

2. **Verify Formatting**:
   - Open `README.md` in a Markdown viewer (e.g., GitHub, VS Code, or a Markdown editor) to ensure it renders correctly.
   - Check for consistent headers, code blocks, and links.

3. **Push to Repository**:
   ```bash
   git add README.md
   git commit -m "Update README with improved formatting and content"
   git push origin main

Clarifications Needed
If you have specific edits in mind, please provide details, such as:
Content Changes: Add new sections, update API instructions, or modify specific text.

Repository Info: Provide the actual GitHub repo URL or confirm if it's private.

Additional Sections: E.g., deployment to a cloud service, testing instructions, or specific API setup steps.

Formatting Preferences: Any specific Markdown style (e.g., different header levels, bullet styles)?

I can also generate a diff to show changes from your original README or assist with related tasks (e.g., editing requirements.txt or main.py). Let me know how you'd like to proceed!

explain Docker Compose

other waste management bots

more concise instructions

DeepSearch

Think

