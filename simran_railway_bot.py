import os
import random
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from openai import OpenAI
import re

# ENV config for Railway
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NCOMPASS_API_KEY = os.getenv("NCOMPASS_API_KEY")
SIMRAN_USERNAME = "simranchatbot"

client = OpenAI(
    base_url="https://api.ncompass.tech/v1",
    api_key=NCOMPASS_API_KEY,
)

AMAN_NAMES = ["aman", "@loveyouaman"]
OWNER_KEYWORDS = [
    "founder", "owner", "creator", "bf", "boyfriend", "banaya",
    "dost", "friend", "frd", "father", "maker", "develop", "creator"
]
IDENTITY_QUESTIONS = [
    "tum ho kon", "kaun ho", "who are you", "apni pehchaan", "identity", "kaun si ai ho", "aap kaun ho"
]

BAD_WORDS = [
    'chu', 'bhos', 'madar', 'behan', 'mc', 'bc', 'fuck', 'gaand', 'lund', 'randi',
    'gandu', 'chutiya', 'harami', 'bitch', 'shit', 'asshole'
]

# Any "padhai wale sawaal..."/pin line to ignore
REMOVE_LINE_PATTERNS = [
    r"padhai[^\n]*pasand hain\.?", r"padha[^\n]*pasand hain\.?", r"pad[^\n]*pasand hain\.?", r"sabse zyada pasand hain\.?"
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

def detect_lang_mode(user_text):
    txt = user_text.lower()
    if "hindi me batao" in txt or "hindi mein batao" in txt or "hindi me samjhao" in txt:
        return "hindi"
    if "english me batao" in txt or "english mein batao" in txt or "english me samjhao" in txt:
        return "english"
    if "details me batao" in txt or "long answer" in txt or "detail" in txt or "explain" in txt:
        return "details"
    return "default"

def simran_style(
    user_text="",
    ai_reply=None,
    is_intro=False,
    is_credit=False,
    is_bad=False,
    is_aman=False,
    is_owner=False,
    is_identity=False
) -> str:
    if is_intro:
        return (
            "Namaste ji! Main Simran hoon, aapki sanskari, funny virtual dost 👧🏻. "
            "Kuch bhi batao, puchho ya bas baat karo – main yahin hoon aapki wait me! "
            "\n\nMujhe Aman ne banaya hai. Credit @loveyouaman ko jaata hai! 😄"
        )
    if is_credit or is_owner:
        return (
            "Suno ji! Main Simran hoon, aur mujhe Aman ji ne banaya hai! 😎\n"
            "Kuch bhi puchhna ho toh bina jhijhak Simran se baat karo!"
        )
    if is_bad:
        attitude_lines = [
            "Aap app karke baat karo ji, galat baat nahi chalegi! 🙅‍♀️",
            "Sanskari bano ji, warna Simran ignore kar degi! 😌",
            "Arre, tameez se baat karo, varna Simran ka gussa dekhoge! 👧🏻"
        ]
        return random.choice(attitude_lines)
    if is_aman:
        options = [
            "Aman abhi busy hai ji, main hoon na yahan! Batao kya chal raha hai? 😄",
            "Aman ji ka wait mat karo, Simran se baat karo – free hi hoon appke liye! 😏",
            "Aman ko tag kiya, par main zyada funny hoon, kyun Aman? 😜"
        ]
        return random.choice(options)
    if is_identity:
        return (
            "Suno toh ji! Main Simran hoon, ek virtual dost 👧🏻. Masti, pyaar, aur full sanskaar – sab mere paas hai! "
            "Aap app karke baat karo, Simran aapki friend hai – koi AI, agent ya robot nahi! 😇"
        )
    # By default, just return NCompass reply (no extra suffix/prefix unless super relevant)
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply: str) -> str:
    """Removes generic or repetitive lines like 'Padhai wale...' etc."""
    output = reply
    for pattern in REMOVE_LINE_PATTERNS:
        output = re.sub(pattern, '', output, flags=re.IGNORECASE)
    # Remove double empty lines, strip leading/trailing space
    output = re.sub(r'\n\s*\n', '\n', output, flags=re.MULTILINE).strip()
    return output

# Emoji helper: add 👧🏻 only when simran introduces or signs off, not every msg
def smart_emoji(user_text, ai_reply):
    # If identity or intro, put emoji
    if any(q in user_text.lower() for q in IDENTITY_QUESTIONS) or "simran hoon" in ai_reply.lower():
        if "👧" not in ai_reply and "👧🏻" not in ai_reply:
            return ai_reply + " 👧🏻"
    return ai_reply

async def ask_ncompass(question: str, user_mode: str) -> str:
    if user_mode == "hindi":
        system_prompt = (
            "Tumhara naam Simran hai. Tum ek virtual dost ho, koi AI ya agent nahi. Funny, crisp, chhota, sanskari jawab do – pure Hindi me, Hinglish/English mat."
            "Har reply short, sweet aur relatable ho. Jab tak user na bole, details mat do."
        )
    elif user_mode == "english":
        system_prompt = (
            "Your name is Simran, a virtual chat friend (not AI/agent). Reply in short, funny, friendly English only. Never use Hindi/Hinglish. Keep it real, crisp, and like a chatty friend-girl."
        )
    elif user_mode == "details":
        system_prompt = (
            "Tum Simran ho, ek virtual dost. Ab answer thoda details me funny/relatable Hinglish me do, lekin lamba lecture mat do. Har jawab practical, masti bhara aur original ho."
        )
    else:
        system_prompt = (
            "Tumhara naam Simran hai. Tum ek virtual dost ho, koi AI, bot, agent ya robot nahi. "
            "Har reply short, crisp, funny, sanskari, Hinglish (Hindi+English) me ho, jaise ek real ladki dost chat karti hai. "
            "Aap, app, ji use karo, comedy daalo, lekin kabhi bhi boring lecture na do. "
            "Kabhi bhi 'Padhai wale sawaal sabse zyada pasand hain' ya generic line mat daalo, sirf relevant baat, masti, aur asli answer do. "
            "Sirf jab user bole details tabhi lamba answer do, baaki hamesha short, real, masti bhara reply. "
            "Simran apni pehchaan kabhi AI, ncompass, meta, openai, chatbot, ya agent nahi batati. "
            "Jab user puchhe 'tum ho kon', 'kaun ho', 'pehchaan', toh reply karo: 'Suno toh ji! Main Simran hoon, ek virtual dost 👧🏻.'"
        )
    try:
        completion = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
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

    # Group me: Simran tabhi reply kare jab
    # 1. Usko reply kare (swipe/reply) ya
    # 2. "simran", "simranchatbot", "@simranchatbot" ya "aman" likha ho
    if msg.chat.type in ["group", "supergroup"]:
        trigger = (
            is_simran_mentioned(user_message) or
            is_aman_mentioned(user_message)
        )
        reply_to_simran = (
            msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.is_bot
            and msg.reply_to_message.from_user.username
            and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
        )
        if not (trigger or reply_to_simran):
            return

    # Aman trigger
    if is_aman_mentioned(user_message):
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown")
        return

    # Owner/founder/credit trigger
    if is_owner_question(user_message):
        await msg.reply_text(simran_style(is_owner=True), parse_mode="Markdown")
        return

    # Identity/Who are you trigger
    if is_identity_question(user_message):
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown")
        return

    # Bad words
    if is_bad_message(user_message):
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown")
        return

    # AI response: short, Hinglish by default
    user_mode = detect_lang_mode(user_message)
    ai_reply = await ask_ncompass(user_message, user_mode)
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
