import os
import random
import logging
import re
from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from telegram.constants import ChatAction, ParseMode
from openai import OpenAI
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

# ENV config
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SIMRAN_USERNAME = "simranchatbot"

if not TOKEN:
    raise EnvironmentError("TELEGRAM_BOT_TOKEN not set in environment.")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not set in environment.")

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

USER_HISTORY = defaultdict(lambda: deque(maxlen=5))
USER_XP = defaultdict(int)
USER_LOGS = {}

AMAN_NAMES = ["aman", "@loveyouaman"]
OWNER_KEYWORDS = ["founder", "owner", "creator", "bf", "boyfriend", "banaya", "dost", "friend", "frd", "father", "maker", "develop", "creator"]
IDENTITY_QUESTIONS = ["tum ho kon", "kaun ho", "who are you", "apni pehchaan", "identity", "kaun si ai ho", "aap kaun ho"]
BAD_WORDS = ['chu', 'bhos', 'madar', 'behan', 'mc', 'bc', 'fuck', 'gaand', 'lund', 'randi', 'gandu', 'chutiya', 'harami', 'bitch', 'shit', 'asshole']
REMOVE_LINE_PATTERNS = [
    r"(padhai|padha|pad)[^\n]*pasand hain\.?",
    r"sabse zyada pasand hain\.?"
]

HI_WORDS = ['hi', 'hello', 'hii', 'hiiii', 'simran', 'hey']
USER_HI_COUNT = defaultdict(int)
HI_REPLIES = [
    "Hi hi! Kitni baar hi bollegi? 😄",
    "Haanji, sun rahi hoon! 😅",
    "Baar baar hi bolna band karo, warna bhaag jaungi! 😜",
    "Bas bhi karo, ab kuch naya bolo! 😏",
    "Tumhe hi se bahar kuch aata nahi kya? 😆"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_bad_message(text):
    return any(bad in text.lower() for bad in BAD_WORDS)

def is_simran_mentioned(text):
    text = text.lower()
    return "simran" in text or "simranchatbot" in text or "@simranchatbot" in text

def is_aman_mentioned(text):
    return any(name in text.lower() for name in AMAN_NAMES)

def is_owner_question(text):
    return any(word in text.lower() for word in OWNER_KEYWORDS)

def is_identity_question(text):
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

def simran_style(user_text="", ai_reply=None, is_intro=False, is_credit=False, is_bad=False, is_aman=False, is_owner=False, is_identity=False):
    if is_intro:
        return "Namaste ji! Main Simran hoon, aapki sanskari, funny virtual dost 👧🏻.\nMujhe Aman ne banaya hai. Credit @loveyouaman ko jaata hai! 😄"
    if is_credit or is_owner:
        return "Suno ji! Main Simran hoon, aur mujhe Aman ji ne banaya hai! 😎"
    if is_bad:
        return random.choice([
            "Aap app karke baat karo ji, galat baat nahi chalegi! 🙅‍♀️",
            "Sanskari bano ji, warna Simran ignore kar degi! 😌",
            "Arre, tameez se baat karo, varna Simran ka gussa dekhoge! 👧🏻"
        ])
    if is_aman:
        return random.choice([
            "Aman abhi busy hai ji, main hoon na yahan! 😄",
            "Aman ji ka wait mat karo, Simran se baat karo! 😏",
            "Aman ko tag kiya, par main zyada funny hoon 😜"
        ])
    if is_identity:
        return "Suno toh ji! Main Simran hoon, ek virtual dost 👧🏻. Aap app karke baat karo, Simran aapki friend hai – koi AI, agent ya robot nahi! 😇"
    return ai_reply.strip() if ai_reply else user_text

def remove_boring_lines(reply):
    for pattern in REMOVE_LINE_PATTERNS:
        reply = re.sub(pattern, '', reply, flags=re.IGNORECASE)
    return re.sub(r'\n\s*\n', '\n', reply, flags=re.MULTILINE).strip()

def smart_emoji(user_text, ai_reply):
    if any(q in user_text.lower() for q in IDENTITY_QUESTIONS) or "simran hoon" in ai_reply.lower():
        if "👧" not in ai_reply and "👧🏻" not in ai_reply:
            return ai_reply + " 👧🏻"
    return ai_reply

def build_groq_context(user_id):
    return [{"role": "user", "content": msg} for msg in USER_HISTORY[user_id]]

GROQ_MODEL = "llama3-70b-8192"

async def ask_groq(question, user_mode, user_id=None):
    system_prompt = {
        "hindi": "Tumhara naam Simran hai. Tum ek virtual dost ho. Pure Hindi me crisp jawab do.",
        "english": "Your name is Simran. Reply like a real girl-friend in English. Be funny, short.",
        "details": "Simran ho. Detailed, funny Hinglish reply do. Na lecture, na boring.",
        "default": "Tum Simran ho. Crisp, funny, Hinglish me reply karo. AI/agent mat bolna kabhi bhi."
    }.get(user_mode, user_mode)

    async def _call_api():
        messages = [{"role": "system", "content": system_prompt}]
        if user_id:
            messages += build_groq_context(user_id)
        messages.append({"role": "user", "content": question})

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages
        )
        return completion.choices[0].message.content.strip()

    try:
        reply = await asyncio.wait_for(_call_api(), timeout=20)
        return smart_emoji(question, remove_boring_lines(reply))
    except Exception as e:
        logger.error(f"Groq error: {e}", exc_info=True)
        return f"API Error: {str(e)}"

# ADMIN FEATURES (unchanged)
async def get_admins(update):
    return await update.message.chat.get_administrators()

def get_replied_user(update):
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

async def pin(update, context):
    if update.message.reply_to_message:
        await update.message.chat.pin_message(update.message.reply_to_message.message_id)
        await update.message.reply_text("Pinned! 📌")

async def dpin(update, context):
    await update.message.chat.unpin_all_messages()
    await update.message.reply_text("All messages unpinned.")

async def ban(update, context):
    user = get_replied_user(update)
    if user:
        await update.message.chat.ban_member(user.id)
        await update.message.reply_text(f"{user.first_name} banned!")

async def kick(update, context):
    user = get_replied_user(update)
    if user:
        await update.message.chat.ban_member(user.id)
        await update.message.chat.unban_member(user.id)
        await update.message.reply_text(f"{user.first_name} kicked!")

async def mute(update, context):
    user = get_replied_user(update)
    if user:
        until = datetime.utcnow() + timedelta(hours=1)
        await update.message.chat.restrict_member(user.id, ChatPermissions(), until_date=until)
        await update.message.reply_text(f"{user.first_name} muted for 1hr!")

async def unmute(update, context):
    user = get_replied_user(update)
    if user:
        await update.message.chat.restrict_member(user.id, ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"{user.first_name} unmuted!")

async def admins(update, context):
    names = [admin.user.full_name for admin in await get_admins(update)]
    await update.message.reply_text("Admins:\n" + "\n".join(names))

async def profile(update, context):
    user = get_replied_user(update) or update.message.from_user
    uid = str(user.id)
    name = user.full_name
    uname = f"@{user.username}" if user.username else "No username"
    xp = USER_XP.get(uid, 0)
    await update.message.reply_text(f"👤 *Profile Info:*\nName: {name}\nUsername: {uname}\nID: `{uid}`\nXP: {xp}", parse_mode=ParseMode.MARKDOWN)

async def history(update, context):
    user = get_replied_user(update)
    if user:
        uid = str(user.id)
        name = user.full_name
        uname = f"@{user.username}" if user.username else "No username"
        USER_LOGS[uid] = {"name": name, "username": uname, "id": uid}
        await update.message.reply_text(f"🕵️ *History Log:*\nName: {name}\nUsername: {uname}\nID: `{uid}`", parse_mode=ParseMode.MARKDOWN)

async def leaderboard(update, context):
    top = sorted(USER_XP.items(), key=lambda x: x[1], reverse=True)[:10]
    reply = "🏆 *Top 10 Users:*\n"
    for i, (uid, xp) in enumerate(top, 1):
        name = USER_LOGS.get(uid, {}).get("name", "User")
        reply += f"{i}. {name} — {xp} XP\n"
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

async def apicheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": "Say hello"}]
        )
        reply = completion.choices[0].message.content.strip()
        await update.message.reply_text(f"API working! Sample reply: {reply}")
    except Exception as e:
        await update.message.reply_text(f"API Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True), parse_mode="Markdown")

def is_hi_message(text):
    return text.strip().lower() in HI_WORDS

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    uid = msg.from_user.id
    text = msg.text.strip()
    chat_type = msg.chat.type

    if chat_type in ["group", "supergroup"]:
        trigger = is_simran_mentioned(text) or is_aman_mentioned(text)
        reply_to_simran = (
            msg.reply_to_message and msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.is_bot
            and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
        )
        if not (trigger or reply_to_simran):
            return

    # HI/HELLO spam logic
    if is_hi_message(text):
        USER_HI_COUNT[uid] += 1
        reply_text = HI_REPLIES[(USER_HI_COUNT[uid] - 1) % len(HI_REPLIES)]
        await msg.reply_text(reply_text)
        return
    else:
        USER_HI_COUNT[uid] = 0  # Reset on other message

    USER_HISTORY[uid].append(text)
    USER_XP[str(uid)] += 5
    USER_LOGS[str(uid)] = {"name": msg.from_user.full_name, "username": msg.from_user.username, "id": uid}

    await msg.chat.send_action(ChatAction.TYPING)

    if is_aman_mentioned(text):
        await msg.reply_text(simran_style(is_aman=True), parse_mode="Markdown")
    elif is_owner_question(text):
        await msg.reply_text(simran_style(is_owner=True), parse_mode="Markdown")
    elif is_identity_question(text):
        await msg.reply_text(simran_style(is_identity=True), parse_mode="Markdown")
    elif is_bad_message(text):
        await msg.reply_text(simran_style(is_bad=True), parse_mode="Markdown")
    else:
        mode = detect_lang_mode(text)
        ai_reply = await ask_groq(text, mode, user_id=uid)
        await msg.reply_text(simran_style(text, ai_reply=ai_reply), parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("dpin", dpin))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("admins", admins))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("apicheck", apicheck))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    logger.info("Simran Bot is running (with Groq API)!")
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)

if __name__ == '__main__':
    main()
