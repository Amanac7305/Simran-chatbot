import os
import random
import re
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from telegram.constants import ChatAction
from openai import OpenAI
from collections import defaultdict, deque

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")
SIMRAN_USERNAME = "simranchatbot"
OWNER_ID = "@loveyouaman"

# NCompass client setup
client = OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY,
)

USER_HISTORY = defaultdict(lambda: deque(maxlen=5))

# --- Witty Replies ---
witty_replies = [
    "Simran hoon main, badi stylish 😎 Song chahiye toh play + name likho!",
    "Kya hua? @Simran tag karo ya naam likho, tabhi reply milega mujhse 😄",
    "Pyaar chahiye ya gaana? Mujhe tag karo fir baat karungi 💃🏻"
]

owner_lines = [
    f"Mujhe Aman ne banaya hai – mera asli owner: {OWNER_ID} 😎",
    f"Code crack karne wale ka naam? Aman, yaani {OWNER_ID} 🤖",
    f"Aman ka dimaag aur Simran ka swag – deadly combo! {OWNER_ID} 💥"
]

def is_simran_mentioned(text, msg) -> bool:
    return (
        "simran" in text.lower()
        or SIMRAN_USERNAME in text.lower()
        or (
            msg.reply_to_message and msg.reply_to_message.from_user and
            msg.reply_to_message.from_user.username and
            msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
        )
    )

def fetch_song(song_query):
    try:
        search_url = f"https://saavn.dev/api/search/songs?query={song_query}"
        res = requests.get(search_url).json()
        results = res.get("data", {}).get("results", [])
        if not results:
            return None
        song_id = results[0]["id"]
        song_info = requests.get(f"https://saavn.dev/api/songs/{song_id}").json()
        download_urls = song_info.get("data", {}).get("downloadUrl", [])
        if download_urls:
            return download_urls[-1]["url"]
        return None
    except Exception as e:
        print("Error fetching song:", e)
        return None

def build_ncompass_context(user_id):
    history = list(USER_HISTORY[user_id])
    return [{"role": "user", "content": msg} for msg in history]

async def ask_ncompass(question: str, user_id=None) -> str:
    try:
        messages = [
            {"role": "system", "content": "Tum Simran ho, witty aur intelligent virtual ladki. Sirf tab reply karo jab tumhe tag kare ya tumhara naam le. Har reply short aur crisp Hinglish me do."},
            *build_ncompass_context(user_id),
            {"role": "user", "content": question}
        ]
        response = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=messages
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("NCompass error:", e)
        return "Simran thoda busy ho gayi hai, baad me try karo ji!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Main Simran hoon 🎧 Song chahiye toh `play` likh ke song name bhejo!")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    user_input = msg.text.strip()
    user_id = msg.from_user.id

    if not is_simran_mentioned(user_input, msg):
        return

    await msg.chat.send_action(action=ChatAction.TYPING)

    if any(word in user_input.lower() for word in ["owner", "creator", "banaya"]):
        await msg.reply_text(random.choice(owner_lines))
        return

    # Music command matching with regex
    pattern = r"(?:(?:^|\s)(play|music)\s+(.*))"
    match = re.search(pattern, user_input, re.IGNORECASE)
    if match:
        song_query = match.group(2).strip()
        if song_query:
            await msg.chat.send_action(action=ChatAction.UPLOAD_AUDIO)
            song_url = fetch_song(song_query)

            if song_url:
                await msg.reply_audio(audio=song_url, title=song_query.title(), caption="Lo ji, gaana mil gaya 🎶")
            else:
                await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎵")
            return

    USER_HISTORY[user_id].append(user_input)
    reply = await ask_ncompass(user_input, user_id=user_id)
    await msg.reply_text(reply)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print("Simran Bot is Live 💫")
    app.run_polling()

if __name__ == "__main__":
    main()
