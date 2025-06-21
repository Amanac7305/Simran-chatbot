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

REMOVE_LINE_PATTERNS = [
    r"padhai[^\n]*pasand hain\.?", r"padha[^\n]*pasand hain\.?", r"pad[^\n]*pasand hain\.?", r"sabse zyada pasand hain\.?"
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_bad_message(text: str) -> bool:
    return any(bad in text.lower() for bad in BAD_WORDS)

def is_simran_mentioned(text: str) -> bool:
    text = text.lower()
    return "simran" in text or "simranchatbot" in text or "@simranchatbot" in text

def is_aman_mentioned(text: str) -> bool:
    return any(name in text.lower() for name in AMAN_NAMES)

def is_owner_question(text: str) -> bool:
    return any(word in text.lower() for word in OWNER_KEYWORDS)

def is_identity_question(text: str) -> bool:
    return any(q in text.lower() for q in IDENTITY_QUESTIONS)

def detect_lang_mode(user_text):
    txt = user_text.lower()
    if "hindi me" in txt or "hindi mein" in txt:
        return "hindi"
    if "english me" in txt or "english mein" in txt:
        return "english"
    if "details me" in txt or "long answer" in txt or "detail" in txt or "explain" in txt:
        return "details"
    return "default"

def simran_style(user_text="", ai_reply=None, is_intro=False, is_credit=False,
                 is_bad=False, is_aman=False, is_owner=False, is_identity=False) -> str:
    if is_intro:
        return (
            "Namaste ji! Main Simran hoon, aapki sanskari, funny virtual dost 👧🏻. "
            "Kuch bhi batao, puchho ya bas baat karo – main yahin hoon aapki wait me! \n\n"
            "Mujhe Aman ne banaya hai. Credit @loveyouaman ko jaata hai! 😄"
        )
    if is_credit or is_owner:
        return (
            "Suno ji! Main Simran hoon, aur mujhe Aman ji ne banaya hai! 😎\n"
            "Kuch bhi puchhna ho toh bina jhijhak Simran se baat karo!"
        )
    if is_bad:
        return random.choice([
            "Aap app karke baat karo ji, galat baat nahi chalegi! 🙅‍♀️",
            "Sanskari bano ji, warna Simran ignore kar degi! 😌",
            "Arre, tameez se baat karo, varna Simran ka gussa dekhoge! 👧🏻"
        ])
    if is_aman:
        return random.choice([
            "Aman abhi busy hai ji, main hoon na yahan! Batao kya chal raha hai? 😄",
            "Aman ji ka wait mat karo, Simran se baat karo – free hi hoon appke liye! 😏",
            "Aman ko tag kiya, par main zyada funny hoon, kyun Aman? 😜"
        ])
    if is_identity:
        return (
            "Suno toh ji! Main Simran hoon, ek virtual dost 👧🏻. Masti, pyaar, aur full sanskaar – sab mere paas hai! "
            "Aap app karke baat karo, Simran aapki friend hai – koi AI, agent ya robot nahi! 😇"
        )
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply: str) -> str:
    for pattern in REMOVE_LINE_PATTERNS:
        reply = re.sub(pattern, '', reply, flags=re.IGNORECASE)
    return re.sub(r'\n\s*\n', '\n', reply, flags=re.MULTILINE).strip()

def smart_emoji(user_text, ai_reply):
    if any(q in user_text.lower() for q in IDENTITY_QUESTIONS) or "simran hoon" in ai_reply.lower():
        if "👧" not in ai_reply and "👧🏻" not in ai_reply:
            return ai_reply + " 👧🏻"
    return ai_reply

def build_ncompass_context(user_id):
    return [{"role": "user", "content": msg} for msg in USER_HISTORY[user_id]]

async def ask_ncompass(question: str, user_mode: str, user_id=None) -> str:
    if user_mode == "hindi":
        system_prompt = (
            "Tumhara naam Simran hai. Tum ek virtual dost ho, koi AI ya agent nahi. Funny, crisp, chhota, sanskari jawab do – pure Hindi me."
        )
    elif user_mode == "english":
        system_prompt = (
            "Your name is Simran, a virtual chat friend (not AI/agent). Reply in short, funny, friendly English only. Never use Hindi/Hinglish."
        )
    elif user_mode == "details":
        system_prompt = (
            "Tum Simran ho, ek virtual dost. Answer thoda detail me funny/relatable Hinglish me do. Practical aur masti bhara jawab do."
        )
    else:
        system_prompt = (
            "Tumhara naam Simran hai. Tum ek virtual dost ho. Har reply short, crisp, funny, sanskari Hinglish me ho. "
            "Never say you're AI, chatbot, OpenAI, or agent. Jab user bole 'tum ho kon', tab bolo: 'Main Simran hoon, ek virtual dost 👧🏻.'"
        )
    try:
        messages = [{"role": "system", "content": system_prompt}]
        if user_id:
            messages += build_ncompass_context(user_id)
        messages.append({"role": "user", "content": question})

        completion = client.chat.completions.create(
            model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=messages
        )
        reply = completion.choices[0].message.content.strip()
        reply = remove_boring_lines(reply)
        return smart_emoji(question, reply)
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

    if msg.chat.type in ["group", "supergroup"]:
        trigger = is_simran_mentioned(user_message) or is_aman_mentioned(user_message)
        reply_to_simran = (
            msg.reply_to_message
            and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.is_bot
            and msg.reply_to_message.from_user.username
            and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
        )
        if not (trigger or reply_to_simran):
            return

    # Aman mention
    if is_aman_mentioned(user_message):
        await msg.chat.send_action(ChatAction.TYPING)
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown")
        return

    # Owner/credit
    if is_owner_question(user_message):
        await msg.chat.send_action(ChatAction.TYPING)
        await msg.reply_text(simran_style(is_owner=True), parse_mode="Markdown")
        return

    # Identity
    if is_identity_question(user_message):
        await msg.chat.send_action(ChatAction.TYPING)
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown")
        return

    # Bad words
    if is_bad_message(user_message):
        await msg.chat.send_action(ChatAction.TYPING)
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown")
        return

    # Memory save
    USER_HISTORY[user_id].append(user_message)

    # Now typing... since reply is expected
    await msg.chat.send_action(ChatAction.TYPING)

    # Ask AI
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
