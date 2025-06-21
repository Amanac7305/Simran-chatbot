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
REMOVE_LINE_PATTERNS = [r"padhai[^\n]*pasand hain\.?", r"pad[^\n]*pasand hain\.?", r"sabse zyada pasand hain\.?"]
GREETINGS = ["hi", "hello", "hey", "good morning", "good night", "gm", "gn", "namaste", "namaskar"]
DATE_WORDS = ["date", "time", "month", "year", "day", "today", "kal", "aaj", "kitna baj", "abhi ka time"]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔥 MUSIC FETCH FUNCTION
def fetch_song(song_query):
    try:
        search_url = f"https://saavn.dev/api/search/songs?query={song_query}"
        search_res = requests.get(search_url).json()
        song = search_res['data']['results'][0]
        song_id = song['id']
        song_data = requests.get(f"https://saavn.dev/api/songs/{song_id}").json()
        return song_data['data']['downloadUrl'][4]['url']
    except:
        return None

# ❓ UTILITIES
def is_bad_message(text): return any(bad in text.lower() for bad in BAD_WORDS)
def is_simran_mentioned(text): return any(k in text.lower() for k in ["simran", "simranchatbot", "@simranchatbot"])
def is_aman_mentioned(text): return any(name in text.lower() for name in AMAN_NAMES)
def is_owner_question(text): return any(word in text.lower() for word in OWNER_KEYWORDS)
def is_identity_question(text): return any(q in text.lower() for q in IDENTITY_QUESTIONS)
def is_date_time_question(text): return any(word in text.lower() for word in DATE_WORDS)
def detect_lang_mode(txt):
    txt = txt.lower()
    if "hindi me" in txt: return "hindi"
    if "english me" in txt: return "english"
    if "details me" in txt or "long answer" in txt: return "details"
    return "default"
def is_greeting(text): return any(greet in text.lower() for greet in GREETINGS)

# 🎭 STYLE
def simran_aman_reply():
    return random.choice([
        "Mujhe Aman ne banaya, genius banda hai – aur owner bhi! @loveyouaman 😎",
        "Aman ka dimaag hi hai kuch alag, tabhi to Simran hoon main! @loveyouaman",
        "Mera original creator? Aman hi hai! Life ka jugaadu owner – @loveyouaman",
        "Simran = Aman ki creation! Kuch bhi doubt ho, usse bhi puchh sakte ho: @loveyouaman",
        "Sab kuch Aman ka idea hai, main toh bas masti karti hoon! @loveyouaman"
    ])

def simran_owner_id_reply():
    return random.choice([
        "Direct owner ka ID chahiye? Lo ji, @loveyouaman 😏",
        "Owner ka asli ID toh yahi hai – @loveyouaman, jao DM kar lo 😁",
        "Yaar, owner ID toh @loveyouaman hai, mast banda hai! 🤭"
    ])

def simran_time_reply():
    return random.choice([
        "Date ya time chahiye? Google kar lo ji! 😄",
        "Clock dekho na app, Simran ko mat pareshan karo 😂",
        "Calendar khol lo yaar, main time machine thodi hoon! 🤭"
    ])

def simran_style(user_text="", ai_reply=None, **kwargs):
    if kwargs.get("is_intro"):
        return "Hi! Main Simran hoon, ek witty, dosti wali, intelligent aur thodi filmy virtual girl. Doubt ho ya masti – bas tag kar lo! 😄"
    if kwargs.get("is_owner") or kwargs.get("is_credit"): return simran_aman_reply()
    if kwargs.get("is_owner_id"): return simran_owner_id_reply()
    if kwargs.get("is_time"): return simran_time_reply()
    if kwargs.get("is_bad"): return random.choice([
        "Aap app karke baat karo ji, aisi baatein mujhe pasand nahi! 🙅‍♀️",
        "Sanskari bano, warna ignore mode on ho jayega. 😌",
        "Aise words use karoge toh Simran reply nahi karegi, samjhe ji? 👧🏻"
    ])
    if kwargs.get("is_aman"): return simran_aman_reply()
    if kwargs.get("is_identity"):
        return "Simran hoon ji, witty bhi, emotional bhi – aur full on masti! Lekin AI/robot mat samajhna, dosti wali chat karti hoon. 😁"
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply):
    output = reply
    for pattern in REMOVE_LINE_PATTERNS:
        output = re.sub(pattern, '', output, flags=re.IGNORECASE)
    return re.sub(r'\n\s*\n', '\n', output, flags=re.MULTILINE).strip()

def smart_emoji(user_text, ai_reply):
    if "simran hoon" in ai_reply.lower():
        if "👧" not in ai_reply and "👧🏻" not in ai_reply:
            return ai_reply + " 👧🏻"
    return ai_reply

def build_ncompass_context(user_id):
    return [{"role": "user", "content": entry} for entry in USER_HISTORY[user_id]]

# 🧠 NCOMPASS REPLY
async def ask_ncompass(question, user_mode, user_id=None):
    try:
        messages = [{"role": "system", "content": get_system_prompt(user_mode)}]
        if user_id:
            messages += build_ncompass_context(user_id)
        messages.append({"role": "user", "content": question})
        completion = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=messages
        )
        reply = completion.choices[0].message.content.strip()
        return smart_emoji(question, remove_boring_lines(reply))
    except Exception as e:
        logger.error(f"NCompass error: {e}")
        return "Arey, Simran thoda busy ho gayi hai, baad me try karo ji!"

def get_system_prompt(mode):
    if mode == "hindi":
        return "Tum Simran ho, witty aur smart ek virtual ladki. Sirf Hindi me jawaab do, short, funny, crisp aur relatable. Boring kabhi mat banna."
    if mode == "english":
        return "You are Simran, a witty, intelligent, study-friendly virtual girl. Reply only in English, always short, crisp, fun, and chatty."
    if mode == "details":
        return "Tum Simran ho, virtual dost. Ab answer detail me, lekin masti aur real-life touch ke sath Hinglish ya Hindi me. Long lecture kabhi mat do, crisp aur engaging raho."
    return (
        "Tum Simran ho, ek witty, emotional, intelligent virtual ladki. "
        "Reply sirf tab jab koi tumhe tag kare, reply kare ya tumhara naam likhe. "
        "Har reply short, crisp, Hinglish (Hindi+English) me, real girl jaisa chat style. "
        "Kabhi bhi AI, agent, robot, ncompass ya OpenAI mat bolna. "
        "Long reply tabhi do jab user bole details me batao. "
        "Aman ya owner ka pucho toh ek creative witty line ke sath @loveyouaman reply karo. "
        "Kisi bhi boring, repetitive, adult message ya greeting ko ignore karo. "
        "Date ya time/month/year puchhe toh bolo google kare ya clock dekhe, kabhi bhi actual date/time na batao."
    )

# ✅ HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True), parse_mode="Markdown")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    user_message = msg.text
    user_id = msg.from_user.id
    is_tagged = is_simran_mentioned(user_message)
    is_reply_to_simran = (
        msg.reply_to_message and msg.reply_to_message.from_user and
        msg.reply_to_message.from_user.is_bot and
        msg.reply_to_message.from_user.username and
        msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
    )
    should_reply = is_tagged or is_reply_to_simran
    if not should_reply: return
    if is_greeting(user_message) and not is_tagged and not is_reply_to_simran: return
    await msg.chat.send_action(action=ChatAction.TYPING)

    if is_aman_mentioned(user_message):
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown"); return
    if is_owner_question(user_message) or ("owner" in user_message.lower() and "id" in user_message.lower()):
        await msg.reply_text(simran_style(is_owner_id=True), parse_mode="Markdown"); return
    if is_identity_question(user_message):
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown"); return
    if is_date_time_question(user_message):
        await msg.reply_text(simran_style(is_time=True), parse_mode="Markdown"); return
    if is_bad_message(user_message):
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown"); return

    # 🎵 Music
    if user_message.lower().startswith(("play ", "music ")):
        song_name = user_message.split(" ", 1)[1]
        url = fetch_song(song_name)
        if url:
            await msg.chat.send_action(action=ChatAction.UPLOAD_AUDIO)
            await msg.reply_audio(audio=url)
        else:
            await msg.reply_text("Kuch nahi mila... aur kuch try karo 🎶")
        return

    USER_HISTORY[user_id].append(user_message)
    user_mode = detect_lang_mode(user_message)
    ai_reply = await ask_ncompass(user_message, user_mode, user_id=user_id)
    stylish_reply = simran_style(user_message, ai_reply=ai_reply)
    await msg.reply_text(stylish_reply, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    logger.info("Simran Bot is running! 🚀")
    app.run_polling()

if __name__ == '__main__':
    main()
