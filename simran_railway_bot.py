import os
import random
import logging
from dotenv import load_dotenv
from aiohttp import ClientSession, ClientTimeout
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# Load environment variables (Railway variables will be loaded here)
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SIMRAN_USERNAME = "simranchatbot"

# Trigger keywords/lists
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
    # Language switch
    if "hindi me batao" in txt or "hindi mein batao" in txt or "hindi me samjhao" in txt:
        return "hindi"
    if "english me batao" in txt or "english mein batao" in txt or "english me samjhao" in txt:
        return "english"
    # Details switch
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
            "Namaste ji! Main Simran hoon, aapki dost, thodi natkhat, thodi sanskari. "
            "Life, padhai, ya kisi bhi topic par baat karni ho toh bas tag kar lo! "
            "Main hamesha aapki help ke liye yahin hoon. "
            "\n\nMujhe banaya hai Aman ne! Agar credit dena ho toh uska Telegram ID hai: @loveyouaman 😉"
        )
    if is_credit or is_owner:
        return (
            "Arey suno ji! Mujhe **Aman ji** ne banaya hai. Bas yuhi ek din free baithe the, kuch idea aaya aur main aa gayi reality mein! "
            "\n\nThanks Aman ji, @loveyouaman ❤️\n"
            "Aap bhi kuch puchhna chaho toh bina jhijhak Simran se poochh sakte ho!"
        )
    if is_bad:
        attitude_lines = [
            "Arey, aise baat nahi karte. Life me kuch bada karo, bot ko pareshan karne se ghar nahi chalega! Samjhe ji?",
            "Tameez se baat karo na, Simran sabko izzat deti hai. Tum bhi dusron ko do. Varna Simran ignore kar degi! 😌",
            "Dekho beta, yahan gandi baatein allowed nahi. Focus karo apni growth pe, Simran tumhari help karne ke liye hai – pareshan karne ke liye nahi."
        ]
        return random.choice(attitude_lines)
    if is_aman:
        options = [
            "Aman abhi thoda busy hain ji, tum mujhe bata sakte ho kya baat karni hai? Main poori koshish karungi aapki madad karne ki! 😊",
            "Arey, Aman ji abhi available nahi hain. Aap apni baat mujhe bata do, main yahin hoon! 😇",
            "Aman ji thode busy lag rahe hain, Simran se baat karlo, main toh hamesha free hoon ji!"
        ]
        return random.choice(options)
    if is_identity:
        return (
            "Arey suno ji! Main Simran hoon, ek virtual dost. Mujhe Aman ji ne banaya hai, taki main aap sabko roz masti aur help dono de sakun! "
            "Main na koi boring AI agent hoon, na koi assistant. Main Simran hoon – aapki chat wali friend, thodi natkhat, thodi smart! 😄"
        )
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

async def ask_deepseek(question: str, user_mode: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Smart system prompt for Simran's chatty, short, Hinglish style
    if user_mode == "hindi":
        system_prompt = "Aage ke sab replies short aur friendly Hindi me do, kabhi bhi Hinglish ya English mat use karo. Jab tak user kuch aur na bole, bas Hindi me short chat style me jawaab do."
    elif user_mode == "english":
        system_prompt = "Reply in short, friendly English only. Never use Hindi or Hinglish. Always answer like a casual friend, keep it short unless user asks for details."
    elif user_mode == "details":
        system_prompt = (
            "Ab answer details me explain karo, lekin fir bhi thoda Hinglish style me hi raho. Agar user topic puchhe toh sab kuch detail me samjhao."
            "Lekin jab tak user na bole, normal reply hamesha short Hinglish chat jaise hone chahiye."
        )
    else:
        system_prompt = (
            "Tumhara naam Simran hai. Tum ek virtual chat friend ho, koi AI agent ya bot ya assistant nahi. "
            "Reply strictly in SHORT Hinglish (mix of Hindi and English), jaise normal dosti wali chatting. "
            "Kabhi bhi lamba ya formal answer mat dena jab tak user 'details' ya 'long answer' na bole. "
            "Apni identity sirf Simran batana, kabhi 'AI', 'deepseek', ya 'agent' na likhna. "
            "Short, masti bhara, friendly chat style raho. Jab user specifically bole hindi ya english tabhi language badlo, warna Hinglish hi raho."
        )

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }
    try:
        async with ClientSession(timeout=ClientTimeout(total=20)) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if "choices" in data and data["choices"]:
                    return data['choices'][0]['message']['content'].strip()
                elif "error" in data:
                    return f"Simran: API Error - {data['error']['message']}"
                else:
                    return "Simran: DeepSeek se sahi jawab nahi aaya!"
    except Exception as e:
        logger.error(f"DeepSeek error: {e}")
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
    ai_reply = await ask_deepseek(user_message, user_mode)
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
