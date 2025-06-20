import os
import random
import logging
from dotenv import load_dotenv
from aiohttp import ClientSession, ClientTimeout
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SIMRAN_USERNAME = "simranchatbot"
AMAN_CREDIT = (
    "Mujhe banaya hai Aman ne! Agar credit dena ho toh uska Telegram ID hai: @loveyouaman 😉"
)

BAD_WORDS = [
    'chu', 'bhos', 'madar', 'behan', 'mc', 'bc', 'fuck', 'gaand', 'lund', 'randi',
    'gandu', 'chutiya', 'harami', 'bitch', 'shit', 'asshole'
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_bad_message(text: str) -> bool:
    text_lower = text.lower()
    return any(bad in text_lower for bad in BAD_WORDS)

def is_simran_mentioned(update: Update) -> bool:
    msg = update.message
    if not msg or not msg.text:
        return False
    text = msg.text.lower()
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention" and f"@{SIMRAN_USERNAME}" in text:
                return True
    if "simran" in text:
        return True
    return False

def simran_style(
    user_text="",
    ai_reply=None,
    is_intro=False,
    is_credit=False,
    is_bad=False
) -> str:
    if is_intro:
        return (
            "Namaste ji! Main Simran hoon, aapki dost, thodi natkhat, thodi sanskari. "
            "Life, padhai, ya kisi bhi topic par baat karni ho toh bas tag kar lo! "
            "Main hamesha aapki help ke liye yahin hoon. "
            "\n\n" + AMAN_CREDIT
        )
    if is_credit:
        return AMAN_CREDIT
    if is_bad:
        attitude_lines = [
            "Arey, aise baat nahi karte. Life me kuch bada karo, bot ko pareshan karne se ghar nahi chalega! Samjhe ji?",
            "Tameez se baat karo na, Simran sabko izzat deti hai. Tum bhi dusron ko do. Varna Simran ignore kar degi! 😌",
            "Dekho beta, yahan gandi baatein allowed nahi. Focus karo apni growth pe, Simran tumhari help karne ke liye hai – pareshan karne ke liye nahi."
        ]
        return random.choice(attitude_lines)
    prefix_choices = [
        "Arey suno ji, ", "Waah, kya sawaal hai! ", "Bilkul sahi pucha aapne ji! ",
        "Hmm, dekho ji, ", "Arre, bataun? ", "Suno toh, ", "Sahi pakde ho ji, "
    ]
    suffix_choices = [
        "Samjhe? 😏", "Bas ye baat yaad rakhna.", "Yahi hai Simran ka suggestion!",
        "Aur kuch puchhna ho toh poochh lo, main yahin hoon (par natkhat hoon ji).",
        "Life me aage badho, tension mat lo!", "Padhai waale sawaal sabse zyada pasand hain.",
        "Bina wajah pareshan mat karo, warna ignore kar dungi! 😌"
    ]
    prefix = random.choice(prefix_choices)
    suffix = random.choice(suffix_choices)
    if not ai_reply:
        ai_reply = user_text
    return f"{prefix}{ai_reply}\n\n{suffix}"

async def ask_deepseek(question: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": question}],
        "max_tokens": 200,
        "temperature": 0.7
    }
    try:
        async with ClientSession(timeout=ClientTimeout(total=20)) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error(f"DeepSeek error: {e}")
        return "Arey, Simran thoda busy ho gayi hai, baad me try karo ji!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True))

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    user_message = msg.text

    if msg.chat.type in ["group", "supergroup"]:
        if not is_simran_mentioned(update):
            return

    ask_credit = any(word in user_message.lower() for word in ["creator", "banaya", "credit", "aman"])
    if ask_credit:
        await msg.reply_text(simran_style(is_credit=True))
        return

    if is_bad_message(user_message):
        await msg.reply_text(simran_style(is_bad=True))
        return

    ai_reply = await ask_deepseek(user_message)
    stylish_reply = simran_style(user_message, ai_reply=ai_reply)
    await msg.reply_text(stylish_reply)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    logger.info("Simran Bot is running (Railway ready)!")
    app.run_polling()

if __name__ == '__main__':
    main()
