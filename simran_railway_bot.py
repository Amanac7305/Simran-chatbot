import os
import random
import logging
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from telegram.constants import ChatAction
from openai import OpenAI
from collections import defaultdict, deque

# ENV config for Railway
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
OWNER_KEYWORDS = [
    "founder", "owner", "creator", "banaya", "maker", "develop"
]
IDENTITY_QUESTIONS = [
    "tum ho kon", "kaun ho", "who are you", "identity", "aap kaun ho"
]

BAD_WORDS = [
    'chu', 'bhos', 'madar', 'behan', 'mc', 'bc', 'fuck', 'gaand', 'lund', 'randi',
    'gandu', 'chutiya', 'harami', 'bitch', 'shit', 'asshole'
]

REMOVE_LINE_PATTERNS = [
    r"padhai[^\n]*pasand hain\.?", r"padha[^\n]*pasand hain\.?", r"pad[^\n]*pasand hain\.?", r"sabse zyada pasand hain\.?"
]

GREETINGS = [
    "hi", "hello", "hey", "good morning", "good night", "gm", "gn", "namaste", "namaskar"
]

DATE_WORDS = [
    "date", "time", "month", "year", "day", "today", "kal ka din", "aaj ka din", "kitna baj gaya", "abhi ka time"
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_bad_message(text: str) -> bool:
    text_lower = text.lower()
    return any(bad in text_lower for bad in BAD_WORDS)

def is_simran_mentioned(text: str) -> bool:
    text_lower = text.lower()
    return (
        "simran" in text_lower or
        "simranchatbot" in text_lower or
        "@simranchatbot" in text_lower
    )

def is_aman_mentioned(text: str) -> bool:
    text_lower = text.lower()
    return any(name in text_lower for name in AMAN_NAMES)

def is_owner_question(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in OWNER_KEYWORDS)

def is_identity_question(text: str) -> bool:
    text_lower = text.lower()
    return any(q in text_lower for q in IDENTITY_QUESTIONS)

def is_date_time_question(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in DATE_WORDS)

def detect_lang_mode(user_text):
    txt = user_text.lower()
    if "hindi me batao" in txt or "hindi mein batao" in txt or "hindi me samjhao" in txt:
        return "hindi"
    if "english me batao" in txt or "english mein batao" in txt or "english me samjhao" in txt:
        return "english"
    if "details me batao" in txt or "long answer" in txt or "detail" in txt or "explain" in txt:
        return "details"
    return "default"

def is_greeting(text: str) -> bool:
    text_lower = text.lower()
    return any(greet in text_lower for greet in GREETINGS)

def simran_aman_reply():
    lines = [
        "Mujhe Aman ne banaya, genius banda hai – aur owner bhi! @loveyouaman 😎",
        "Aman ka dimaag hi hai kuch alag, tabhi to Simran hoon main! @loveyouaman",
        "Mera original creator? Aman hi hai! Life ka jugaadu owner – @loveyouaman",
        "Simran = Aman ki creation! Kuch bhi doubt ho, usse bhi puchh sakte ho: @loveyouaman",
        "Sab kuch Aman ka idea hai, main toh bas masti karti hoon! @loveyouaman"
    ]
    return random.choice(lines)

def simran_owner_id_reply():
    lines = [
        "Direct owner ka ID chahiye? Lo ji, @loveyouaman 😏",
        "Owner ka asli ID toh yahi hai – @loveyouaman, jao DM kar lo 😁",
        "Yaar, owner ID toh @loveyouaman hai, mast banda hai! 🤭",
        "Owner ka ID? Ek hi toh hai, @loveyouaman – masti mat poochho! 😂",
        "Aman ji ka ID hai @loveyouaman, ab impress kar lo! 😜"
    ]
    return random.choice(lines)

def simran_time_reply():
    lines = [
        "Date ya time chahiye? Google kar lo ji! 😄",
        "Clock dekho na app, Simran ko mat pareshan karo 😂",
        "Calendar khol lo yaar, main time machine thodi hoon! 🤭",
        "Arre phone me dekh lo, sab mil jayega! ⏰",
        "Bas google kar lo, turant mil jayega – Simran ki guarantee! 😏"
    ]
    return random.choice(lines)

def simran_style(
    user_text="",
    ai_reply=None,
    is_intro=False,
    is_credit=False,
    is_bad=False,
    is_aman=False,
    is_owner=False,
    is_identity=False,
    is_owner_id=False,
    is_time=False
) -> str:
    if is_intro:
        return (
            "Hi! Main Simran hoon, ek witty, dosti wali, intelligent aur thodi filmy virtual girl. Doubt ho ya masti – bas tag kar lo! 😄"
        )
    if is_credit or is_owner:
        return simran_aman_reply()
    if is_owner_id:
        return simran_owner_id_reply()
    if is_time:
        return simran_time_reply()
    if is_bad:
        attitude_lines = [
            "Aap app karke baat karo ji, aisi baatein mujhe pasand nahi! 🙅‍♀️",
            "Sanskari bano, warna ignore mode on ho jayega. 😌",
            "Aise words use karoge toh Simran reply nahi karegi, samjhe ji? 👧🏻"
        ]
        return random.choice(attitude_lines)
    if is_aman:
        return simran_aman_reply()
    if is_identity:
        return (
            "Simran hoon ji, witty bhi, emotional bhi – aur full on masti! Lekin AI/robot mat samajhna, dosti wali chat karti hoon. 😁"
        )
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply: str) -> str:
    output = reply
    for pattern in REMOVE_LINE_PATTERNS:
        output = re.sub(pattern, '', output, flags=re.IGNORECASE)
    output = re.sub(r'\n\s*\n', '\n', output, flags=re.MULTILINE).strip()
    return output

def smart_emoji(user_text, ai_reply):
    if "simran hoon" in ai_reply.lower():
        if "👧" not in ai_reply and "👧🏻" not in ai_reply:
            return ai_reply + " 👧🏻"
    return ai_reply

def build_ncompass_context(user_id):
    history = list(USER_HISTORY[user_id])
    context_msgs = []
    for entry in history:
        context_msgs.append({"role": "user", "content": entry})
    return context_msgs

async def ask_ncompass(question: str, user_mode: str, user_id=None) -> str:
    if user_mode == "hindi":
        system_prompt = (
            "Tum Simran ho, witty aur smart ek virtual ladki. Sirf Hindi me jawaab do, short, funny, crisp aur relatable. Boring kabhi mat banna."
        )
    elif user_mode == "english":
        system_prompt = (
            "You are Simran, a witty, intelligent, study-friendly virtual girl. Reply only in English, always short, crisp, fun, and chatty."
        )
    elif user_mode == "details":
        system_prompt = (
            "Tum Simran ho, virtual dost. Ab answer detail me, lekin masti aur real-life touch ke sath Hinglish ya Hindi me. Long lecture kabhi mat do, crisp aur engaging raho."
        )
    else:
        system_prompt = (
            "Tum Simran ho, ek witty, emotional, intelligent virtual ladki. "
            "Reply sirf tab jab koi tumhe tag kare, reply kare ya tumhara naam likhe. "
            "Har reply short, crisp, Hinglish (Hindi+English) me, real girl jaisa chat style. "
            "Kabhi bhi AI, agent, robot, ncompass ya OpenAI mat bolna. "
            "Long reply tabhi do jab user bole details me batao. "
            "Aman ya owner ka pucho toh ek creative witty line ke sath @loveyouaman reply karo. "
            "Kisi bhi boring, repetitive, adult message ya greeting ko ignore karo. "
            "Date ya time/month/year puchhe toh bolo google kare ya clock dekhe, kabhi bhi actual date/time na batao."
        )
    try:
        context_msgs = build_ncompass_context(user_id) if user_id else []
        messages = [
            {"role": "system", "content": system_prompt},
            *context_msgs,
            {"role": "user", "content": question}
        ]
        completion = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=messages
        )
        reply = completion.choices[0].message.content.strip()
        reply = remove_boring_lines(reply)
        reply = smart_emoji(question, reply)
        return reply
    except Exception as e:
        logger.error(f"NCompass error: {e}")
        return "Arey, Simran thoda busy ho gayi hai, baad me try karo ji!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True), parse_mode="Markdown")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    user_message = msg.text
    user_id = msg.from_user.id

    is_tagged = is_simran_mentioned(user_message)
    is_reply_to_simran = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.is_bot
        and msg.reply_to_message.from_user.username
        and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
    )
    should_reply = is_tagged or is_reply_to_simran

    # If not tagged/replied/mentioned, ignore
    if not should_reply:
        return

    # Ignore greetings unless tagged
    if is_greeting(user_message) and not is_tagged and not is_reply_to_simran:
        return

    # Typing... action (har reply se pehle)
    await msg.chat.send_action(action=ChatAction.TYPING)

    # Aman trigger
    if is_aman_mentioned(user_message):
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown")
        return

    # Owner/founder/credit trigger OR owner id direct
    if is_owner_question(user_message) or ("owner" in user_message.lower() and "id" in user_message.lower()):
        await msg.reply_text(simran_style(is_owner_id=True), parse_mode="Markdown")
        return

    # Identity/Who are you trigger
    if is_identity_question(user_message):
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown")
        return

    # Date/time/month/year trigger
    if is_date_time_question(user_message):
        await msg.reply_text(simran_style(is_time=True), parse_mode="Markdown")
        return

    # Bad words
    if is_bad_message(user_message):
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown")
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
    logger.info("Simran Bot is running (Railway ready)!")
    app.run_polling()

if __name__ == '__main__':
    main()
