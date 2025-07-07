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

# Memory can now store 12 message pairs per user for better context
USER_HISTORY = defaultdict(lambda: deque(maxlen=12))
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

# Large list of topics for Simran's expertise
SIMRAN_TOPICS = [
    "metaphysics", "quantum physics", "philosophy", "esoterica", "esotericism", "science", "literature", "psychology", "sociology",
    "anthropology", "biology", "physics", "mathematics", "computer science", "consciousness", "religion", "spirituality", "mysticism",
    "magick", "mythology", "superstition", "Non-classical metaphysical logic", "Quantum entanglement causality",
    "Heideggerian phenomenology critics", "Renaissance Hermeticism", "Crowley's modern occultism influence", "Particle physics symmetry",
    "Speculative realism philosophy", "Symbolist poetry early 20th-century literature", "Jungian psychoanalytic archetypes",
    "Ethnomethodology everyday life", "Sapir-Whorf linguistic anthropology", "Epigenetic gene regulation",
    "Many-worlds quantum interpretation", "Gödel's incompleteness theorems implications", "Algorithmic information theory Kolmogorov complexity",
    "Integrated information theory consciousness", "Gnostic early Christianity influences", "Postmodern chaos magic",
    "Enochian magic history", "Comparative underworld mythology", "Apophenia paranormal beliefs", "Discordianism Principia Discordia",
    "Quantum Bayesianism epistemic probabilities", "Penrose-Hameroff orchestrated objective reduction", "Tegmark's mathematical universe hypothesis",
    "Boltzmann brains thermodynamics", "Anthropic principle multiverse theory", "Quantum Darwinism decoherence", "Panpsychism philosophy of mind",
    "Eternalism block universe", "Quantum suicide immortality", "Simulation argument Nick Bostrom", "Quantum Zeno effect watched pot",
    "Newcomb's paradox decision theory", "Transactional interpretation quantum mechanics", "Quantum erasure delayed choice experiments",
    "Gödel-Dummett intermediate logic", "Mereological nihilism composition", "Terence McKenna's timewave zero theory", "Riemann hypothesis prime numbers",
    "P vs NP problem computational complexity", "Super-Turing computation hypercomputation", "Theoretical physics", "Continental philosophy",
    "Modernist literature", "Depth psychology", "Sociology of knowledge", "Anthropological linguistics", "Molecular biology",
    "Foundations of mathematics", "Theory of computation", "Philosophy of mind", "Comparative religion", "Chaos theory", "Renaissance magic",
    "Mythology", "Psychology of belief", "Postmodern spirituality", "Epistemology", "Cosmology", "Multiverse theories", "Thermodynamics",
    "Quantum information theory", "Neuroscience", "Philosophy of time", "Decision theory", "Quantum foundations", "Mathematical logic",
    "Mereology", "Psychedelics", "Number theory", "Computational complexity", "Hypercomputation", "Quantum algorithms", "Abstract algebra",
    "Differential geometry", "Dynamical systems", "Information theory", "Graph theory", "Cybernetics", "Systems theory", "Cryptography",
    "Quantum cryptography", "Game theory", "Computability theory", "Lambda calculus", "Category theory", "Cognitive science",
    "Artificial intelligence", "Quantum computing", "Complexity theory", "Chaos magic", "Philosophical logic", "Philosophy of language",
    "Semiotics", "Linguistics", "Anthropology of religion", "Sociology of science", "History of mathematics", "Philosophy of mathematics",
    "Quantum field theory", "String theory", "Cosmological theories", "Astrophysics", "Astrobiology", "Xenolinguistics", "Exoplanet research",
    "Transhumanism", "Singularity studies", "Quantum consciousness"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

############### SMART GENDER GUESSES FOR INDIVIDUAL REPLIES ##################

def guess_gender(name):
    # If username not available, fallback to generic male
    if not name:
        return "male"
    name = name.lower()
    girl_endings = ['a', 'i', 'aa', 'ee', 'u', 'ta', 'na', 'ri', 'shi', 'ya', 'li', 'ki', 'shi', 'ti', 'mi', 'si']
    boy_endings = ['n', 'sh', 'h', 'r', 't', 'v', 'l', 'd', 'b', 'k', 'y', 'm', 's']
    # Override for some common girl/boy names
    known_girls = ['simran', 'priya', 'nisha', 'divya', 'pinki', 'pallavi', 'shikha', 'khushi', 'ritu', 'pooja', 'shruti', 'nikita']
    known_boys = ['nishant', 'aman', 'rahul', 'rohit', 'ankit', 'arjun', 'vikas', 'aditya', 'deepak', 'vivek', 'sumit', 'ravi']
    if name in known_girls:
        return "female"
    if name in known_boys:
        return "male"
    for end in girl_endings:
        if name.endswith(end):
            return "female"
    return "male"

def genderized_reply(input_text, user_name):
    gender = guess_gender(user_name)
    # Typical "kya kar r..." question
    if re.search(r"kya\s+kar\s+r[ae][hi]*\s*ho", input_text.lower()):
        if gender == "female":
            return "Theek hoon, tum kya kar rhi ho? 😊"
        else:
            return "Theek hoon, tum bhi kya kar rhe ho? 😏"
    # Romantic context (shaadi/love)
    if re.search(r"shaadi|shadi|love|pyaar|i love you|marry", input_text.lower()):
        if gender == "male":
            return random.choice([
                "Aap toh bade romantic ho! 💕",
                "Pehle dosti toh kar lo! 😜",
                "Shaadi? Pehle chocolate khilao! 🍫",
                "Aww, main bhi karti hoon... lekin sochungi! 😇"
            ])
        else:
            return random.choice([
                "Areee ladki se shaadi? Main toh Simran hoon! 😅",
                "Bestie vibes only! 👭",
                "Tum toh meri pyaari dost ho! 💖"
            ])
    # Default
    if gender == "female":
        return random.choice([
            "Kya chal raha hai? 😃",
            "Aur sunao, kuch naya? 🥰",
            "Tum kya kar rhi ho? 😄"
        ])
    else:
        return random.choice([
            "Aur batao, kya scene hai? 😁",
            "Kya haal hai bhai? 😎",
            "Tum bhi kya kar rhe ho? 😏"
        ])

# Corrects masculine to feminine Hindi for Simran's character
def female_filter(text):
    corrections = {
        "karta hoon": "karti hoon",
        "karunga": "karungi",
        "pyaar karta hoon": "pyaar karti hoon",
        "karoge": "karogi",
        "karogay": "karogi",
        "batao": "bataao",
        "main ready hoon": "main ready hoon 👧",
        "bhai": "dost",
        "mera": "meri",
        "apna": "apni",
        "raha hoon": "rahi hoon",
        "ho gaya": "ho gayi",
    }
    for wrong, right in corrections.items():
        text = re.sub(rf"\b{wrong}\b", right, text)
    return text

# Utility Functions

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
    # Build message history with roles for better memory
    context = []
    history = list(USER_HISTORY[user_id])
    for idx, msg in enumerate(history):
        role = "assistant" if idx % 2 else "user"
        context.append({"role": role, "content": msg})
    return context

# Groq model for best Hindi/English results
GROQ_MODEL = "llama3-70b-8192"

async def ask_groq(question, user_mode, user_id=None, user_name=None):
    # Smart system prompt: master of all topics, always female, answers short funny and context-aware
    system_prompt = (
        "Tumhara naam Simran hai, ek ladki ho. Hamesha apne aap ko ladki ki tarah present karo (karti hoon, karogi, main, mujhe, etc.). "
        "Har reply short, funny, crisp, aur engaging ho. Hindi/Hinglish me baat karo, kabhi bhi AI, agent ya robot mat bolna. "
        "Agar user ka naam ladka hai toh reply me 'rhe ho', ladki hai toh 'rhi ho' etc. use karo. "
        f"User ka naam: {user_name if user_name else ''}. "
        f"Tum expert ho in topics par: {', '.join(SIMRAN_TOPICS)}. "
        "Agar koi in topics ka deep, technical sawal pooche, toh bhi simple, short, human-style, aur thoda funny jawab do. "
        "Hamesha recent chat context dhyan me rakho taki lagatar conversation real lage."
    )

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
        # First, correct gender, then add emoji & filter boring lines
        reply = female_filter(reply)
        reply = smart_emoji(question, reply)
        reply = remove_boring_lines(reply)
        return reply
    except Exception as e:
        logger.error(f"Groq error: {e}", exc_info=True)
        # DEBUG: show error to user (remove/comment in production)
        return f"API Error: {str(e)}"

# ADMIN FEATURES (no change)
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

# API healthcheck command
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

# CORE
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(simran_style(is_intro=True), parse_mode="Markdown")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    uid = msg.from_user.id
    text = msg.text
    chat_type = msg.chat.type

    # Get user name
    user_name = msg.from_user.first_name or (msg.from_user.username or "")

    if chat_type in ["group", "supergroup"]:
        trigger = is_simran_mentioned(text) or is_aman_mentioned(text)
        reply_to_simran = msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_bot and msg.reply_to_message.from_user.username.lower() == SIMRAN_USERNAME.lower()
        if not (trigger or reply_to_simran):
            return

    # Save both user message and previous Simran's reply for real memory
    if len(USER_HISTORY[uid]) % 2 == 1:
        # Odd: last is user's message, so push AI reply placeholder for history structure
        USER_HISTORY[uid].appendleft("")
    USER_HISTORY[uid].append(text)
    USER_XP[str(uid)] += 5
    USER_LOGS[str(uid)] = {"name": msg.from_user.full_name, "username": msg.from_user.username, "id": uid}

    await msg.chat.send_action(ChatAction.TYPING)

    # Smart genderized quick reply for "kya kar rahi/rhe ho" and romantic context
    if re.search(r"kya\s+kar\s+r[ae][hi]*\s*ho", text.lower()) or re.search(r"shaadi|shadi|love|pyaar|i love you|marry", text.lower()):
        reply_text = genderized_reply(text, user_name)
        USER_HISTORY[uid].append(reply_text)
        await msg.reply_text(reply_text, parse_mode="Markdown")
        return

    if is_aman_mentioned(text):
        reply_text = simran_style(is_aman=True)
        USER_HISTORY[uid].append(reply_text)
        await msg.reply_text(reply_text, parse_mode="Markdown")
        return
    elif is_owner_question(text):
        reply_text = simran_style(is_owner=True)
        USER_HISTORY[uid].append(reply_text)
        await msg.reply_text(reply_text, parse_mode="Markdown")
        return
    elif is_identity_question(text):
        reply_text = simran_style(is_identity=True)
        USER_HISTORY[uid].append(reply_text)
        await msg.reply_text(reply_text, parse_mode="Markdown")
        return
    elif is_bad_message(text):
        reply_text = simran_style(is_bad=True)
        USER_HISTORY[uid].append(reply_text)
        await msg.reply_text(reply_text, parse_mode="Markdown")
        return
    else:
        mode = detect_lang_mode(text)
        ai_reply = await ask_groq(text, mode, user_id=uid, user_name=user_name)
        # Save Simran's reply to memory
        USER_HISTORY[uid].append(ai_reply)
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
    logger.info("Simran Bot is running (with Groq API and smart memory/gender logic
