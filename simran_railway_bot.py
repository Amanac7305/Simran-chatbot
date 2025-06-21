import os, re, logging, random, requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters, ContextTypes
)
from telegram.constants import ChatAction
from openai import OpenAI
from collections import defaultdict, deque

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")
SIMRAN_USERNAME = "simranchatbot"

client = OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY,
)
USER_HISTORY = defaultdict(lambda: deque(maxlen=5))

def is_simran_mentioned(text): return "simran" in text.lower() or "@simranchatbot" in text.lower()
def is_bad_message(text): return any(x in text.lower() for x in ['bhos', 'chu', 'madar', 'lund', 'randi'])
def is_music_command(text): return re.search(r"\b(play|music)\s+(.+)", text.lower())

def simran_style(reply): return reply.strip()

async def ask_ncompass(text, user_id):
    history = list(USER_HISTORY[user_id])
    msgs = [{"role": "system", "content": "Tum Simran ho, witty aur funny Hinglish me reply karo. Reply short, human-style ho."}]
    msgs += [{"role": "user", "content": msg} for msg in history]
    msgs.append({"role": "user", "content": text})
    try:
        out = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-7B-Instruct",
            messages=msgs
        )
        return out.choices[0].message.content
    except Exception as e:
        return "Simran thoda busy hai, baad me puchho 😶"

def get_song_url(query):
    try:
        url = f"https://saavn.dev/api/search/songs?query={query}"
        res = requests.get(url)
        data = res.json()
        results = data.get('data', {}).get('results', [])
        if results:
            return results[0]['downloadUrl'][-1]['link']
        return None
    except:
        return None

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    text = msg.text
    uid = msg.from_user.id

    tagged = is_simran_mentioned(text)
    replied = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()

    if not (tagged or replied): return
    await msg.chat.send_action(action=ChatAction.TYPING)

    # Music command handler
    song_match = is_music_command(text)
    if song_match:
        song_name = song_match.group(2).strip()
        url = get_song_url(song_name)
        if url:
            await msg.reply_audio(audio=url, title=song_name)
        else:
            await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎵")
        return

    if is_bad_message(text):
        await msg.reply_text("Tameez me baat karo warna Simran ignore mode on kar degi 😌")
        return

    USER_HISTORY[uid].append(text)
    reply = await ask_ncompass(text, uid)
    await msg.reply_text(simran_style(reply))

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle))
    print("Simran is live on Railway ✅")
    app.run_polling()

if __name__ == '__main__':
    main()
