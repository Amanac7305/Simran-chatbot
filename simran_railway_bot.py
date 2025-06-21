import os, re, logging, requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from openai import OpenAI
from collections import defaultdict, deque

load_dotenv()

BOT_USERNAME = "simranchatbot"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")

client = OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY,
)

USER_HISTORY = defaultdict(lambda: deque(maxlen=5))

def is_mentioned(update: Update):
    if update.message is None or update.message.text is None:
        return False
    text = update.message.text.lower()
    return ("simran" in text or f"@{BOT_USERNAME}" in text or (
        update.message.reply_to_message and update.message.reply_to_message.from_user and
        update.message.reply_to_message.from_user.username and
        update.message.reply_to_message.from_user.username.lower() == BOT_USERNAME
    ))

def clean(text): return text.strip() if text else ""

def is_music_command(text):
    return bool(re.match(r"^(play|/play)\s+(.+)", text.strip(), re.IGNORECASE))

def extract_song_name(text):
    match = re.match(r"^(play|/play)\s+(.+)", text.strip(), re.IGNORECASE)
    return match.group(2).strip() if match else None

def get_song_url(query):
    try:
        url = f"https://saavn.dev/api/search/songs?query={query}"
        res = requests.get(url, timeout=10)
        results = res.json().get("data", {}).get("results", [])
        if results:
            return results[0]["downloadUrl"][-1]["link"]
        return None
    except:
        return None

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return

    text = msg.text
    uid = msg.from_user.id

    if not is_mentioned(update):
        return

    await msg.chat.send_action(action=ChatAction.TYPING)

    # If music command
    if is_music_command(text):
        song = extract_song_name(text)
        if song:
            song_url = get_song_url(song)
            if song_url:
                await msg.reply_audio(audio=song_url, title=song)
            else:
                await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎵")
        return

    # Else chat with Simran (fun, Hinglish)
    USER_HISTORY[uid].append(text)
    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-7B-Instruct",
            messages=[
                {"role": "system", "content": "Tum Simran ho, Ranchi ki funny ladki. Hinglish mein short, witty replies do."},
                *[
                    {"role": "user", "content": q}
                    for q in USER_HISTORY[uid]
                ]
            ]
        )
        reply = response.choices[0].message.content.strip()
        await msg.reply_text(reply)
    except Exception as e:
        await msg.reply_text("Simran thoda busy hai, baad me puchho 😶")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle))
    print("Simran Bot Live ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
