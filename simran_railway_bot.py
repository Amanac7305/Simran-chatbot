import os
import random
import logging
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

# ENV config
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")
SIMRAN_USERNAME = "simranchatbot"

client = OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY,
)

USER_HISTORY = defaultdict(lambda: deque(maxlen=5))

AMAN_NAMES = ["aman", "@loveyouaman"]
OWNER_KEYWORDS = ["founder", "owner", "creator", "banaya", "maker", "develop"]
IDENTITY_QUESTIONS = ["tum ho kon", "kaun ho", "who are you", "identity", "aap kaun ho"]
BAD_WORDS = ['chu', 'bhos', 'madar', 'behan', 'mc', 'bc', 'fuck', 'gaand', 'lund', 'randi', 'gandu', 'chutiya', 'harami', 'bitch', 'shit', 'asshole']
REMOVE_LINE_PATTERNS = [r"padhai[^\n]*pasand hain\.?"]
GREETINGS = ["hi", "hello", "hey", "good morning", "good night", "gm", "gn", "namaste", "namaskar"]
DATE_WORDS = ["date", "time", "month", "year", "day", "today", "kal ka din", "aaj ka din", "kitna baj gaya", "abhi ka time"]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def is_bad_message(text: str) -> bool:
    return any(bad in text.lower() for bad in BAD_WORDS)

def is_simran_mentioned(text: str) -> bool:
    txt = text.lower()
    return "simran" in txt or "@simranchatbot" in txt or "simranchatbot" in txt

def is_aman_mentioned(text: str) -> bool:
    return any(name in text.lower() for name in AMAN_NAMES)

def is_owner_question(text: str) -> bool:
    return any(word in text.lower() for word in OWNER_KEYWORDS)

def is_identity_question(text: str) -> bool:
    return any(q in text.lower() for q in IDENTITY_QUESTIONS)

def is_date_time_question(text: str) -> bool:
    return any(word in text.lower() for word in DATE_WORDS)

def detect_lang_mode(user_text):
    txt = user_text.lower()
    if "hindi" in txt: return "hindi"
    if "english" in txt: return "english"
    if "details" in txt or "explain" in txt: return "details"
    return "default"

def is_greeting(text: str) -> bool:
    return any(greet in text.lower() for greet in GREETINGS)

def simran_aman_reply():
    return random.choice([
        "Mujhe Aman ne banaya, genius banda hai – aur owner bhi! @loveyouaman 😎",
        "Aman ka dimaag hi hai kuch alag, tabhi to Simran hoon main! @loveyouaman"
    ])

def simran_owner_id_reply():
    return random.choice([
        "Owner ka asli ID toh yahi hai – @loveyouaman 😁",
        "@loveyouaman hi owner hai, DM kar lo 😄"
    ])

def simran_time_reply():
    return random.choice([
        "Time ke liye phone dekho ji! 😄",
        "Clock dekho na app, Simran busy hai 😂"
    ])

def simran_style(user_text="", ai_reply=None, is_intro=False, is_credit=False, is_bad=False, is_aman=False, is_owner=False, is_identity=False, is_owner_id=False, is_time=False) -> str:
    if is_intro:
        return "Hi! Main Simran hoon – intelligent, witty aur thodi masti wali. Doubt ho ya baat, bas tag kar lo! 😄"
    if is_credit or is_owner: return simran_aman_reply()
    if is_owner_id: return simran_owner_id_reply()
    if is_time: return simran_time_reply()
    if is_bad: return random.choice(["Sanskari bano, warna ignore mode on ho jayega. 😌"])
    if is_aman: return simran_aman_reply()
    if is_identity: return "Simran hoon ji – witty bhi, emotional bhi – AI mat samajhna, dosti wali hoon 😁"
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply: str) -> str:
    for pattern in REMOVE_LINE_PATTERNS:
        reply = re.sub(pattern, '', reply, flags=re.IGNORECASE)
    return re.sub(r'\n\s*\n', '\n', reply).strip()

def build_ncompass_context(user_id):
    return [{"role": "user", "content": m} for m in USER_HISTORY[user_id]]

async def ask_ncompass(question: str, user_mode: str, user_id=None) -> str:
    system_prompt = "Tum Simran ho, witty aur helpful virtual ladki. Reply short Hinglish me."
    if user_mode == "hindi":
        system_prompt = "Tum Simran ho, smart aur witty ladki. Sirf Hindi me reply do, short and fun."
    elif user_mode == "english":
        system_prompt = "You are Simran – intelligent and fun, reply only in English."
    elif user_mode == "details":
        system_prompt = "Explain in Hinglish with details and relatable tone, never robotic."
    try:
        messages = [{"role": "system", "content": system_prompt}] + build_ncompass_context(user_id) + [{"role": "user", "content": question}]
        completion = client.chat.completions.create(model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", messages=messages)
        reply = completion.choices[0].message.content.strip()
        return remove_boring_lines(reply)
    except Exception as e:
        logger.error(f"NCompass error: {e}")
        return "Simran thodi busy ho gayi hai, baad me try karo ji!"

# Music API
def fetch_song(song_query):
    try:
        res = requests.get(f"https://saavn.me/search/songs?query={song_query}").json()
        song_id = res['data']['results'][0]['id']
        song_data = requests.get(f"https://saavn.me/songs?id={song_id}").json()['data'][0]
        return song_data['downloadUrl'][-1]['link']
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True), parse_mode="Markdown")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    user_msg = msg.text
    user_id = msg.from_user.id
    is_tagged = is_simran_mentioned(user_msg)
    is_reply_to_simran = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
    should_reply = is_tagged or is_reply_to_simran

    if not should_reply:
        return

    if is_greeting(user_msg) and not should_reply:
        return

    await msg.chat.send_action(action=ChatAction.TYPING)

    if any(word in user_msg.lower() for word in ['play ', 'music ']):
        query = user_msg.lower().split('play ', 1)[-1] if 'play ' in user_msg.lower() else user_msg.lower().split('music ', 1)[-1]
        query = query.strip()
        mp3_link = fetch_song(query)
        if mp3_link:
            await msg.reply_audio(audio=mp3_link)
        else:
            await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎶")
        return

    if is_aman_mentioned(user_msg):
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown")
        return

    if is_owner_question(user_msg) or ("owner" in user_msg.lower() and "id" in user_msg.lower()):
        await msg.reply_text(simran_style(is_owner_id=True), parse_mode="Markdown")
        return

    if is_identity_question(user_msg):
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown")
        return

    if is_date_time_question(user_msg):
        await msg.reply_text(simran_style(is_time=True), parse_mode="Markdown")
        return

    if is_bad_message(user_msg):
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown")
        return

    USER_HISTORY[user_id].append(user_msg)
    user_mode = detect_lang_mode(user_msg)
    ai_reply = await ask_ncompass(user_msg, user_mode, user_id=user_id)
    await msg.reply_text(simran_style(user_msg, ai_reply=ai_reply), parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    logger.info("Simran Bot with music is running!")
    app.run_polling()

if __name__ == '__main__':
    main()

