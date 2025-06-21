import os, re, requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from telegram.constants import ChatAction
from collections import defaultdict, deque
import openai

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")

BOT_USERNAME = "simranchatbot"

client = openai.OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY
)

USER_HISTORY = defaultdict(lambda: deque(maxlen=5))

def is_mentioned(update: Update) -> bool:
    if not update.message or not update.message.text:
        return False
    text = update.message.text.lower()
    return "simran" in text or f"@{BOT_USERNAME}" in text or (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user.username.lower() == BOT_USERNAME
    )

def is_play_command(text):
    return re.match(r"^(play|/play)\s+.+", text.strip(), re.IGNORECASE)

def extract_song_name(text):
    match = re.match(r"^(play|/play)\s+(.+)", text.strip(), re.IGNORECASE)
    return match.group(2).strip() if match else None

def get_song_url(song):
    try:
        r = requests.get(f"https://saavn.dev/api/search/songs?query={song}", timeout=10)
        res = r.json()
        songs = res.get("data", {}).get("results", [])
        if not songs:
            return None
        return songs[0]["downloadUrl"][-1]["link"]
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    user_id = msg.from_user.id

    if not is_mentioned(update):
        return

    await msg.chat.send_action(action=ChatAction.TYPING)

    if is_play_command(text):
        song_name = extract_song_name(text)
        if song_name:
            url = get_song_url(song_name)
            if url:
                await msg.reply_audio(audio=url, title=song_name)
            else:
                await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎵")
        return

    USER_HISTORY[user_id].append(text)

    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3-8B-Instruct",
            messages=[
                {"role": "system", "content": "Tum Simran ho — Ranchi ki fun, witty ladki ho. Hamesha Hinglish mein short, crisp aur funny replies do. Respectful aur thoda masti bhari tone mein answer do. Boring kabhi nahi banna."},
                *[
                    {"role": "user", "content": x}
                    for x in USER_HISTORY[user_id]
                ]
            ]
        )
        reply = completion.choices[0].message.content.strip()
        await msg.reply_text(reply)
    except Exception as e:
        await msg.reply_text("Simran thoda busy hai, baad me puchho 😶")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("Simran is online ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
