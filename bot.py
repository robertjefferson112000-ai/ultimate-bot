import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import re
import hashlib

# ===== CONFIGURATION =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    print("❌ Missing environment variables!")
    print("Please set TELEGRAM_TOKEN and DEEPSEEK_API_KEY")
    exit(1)

# Initialize DeepSeek
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# ===== DATA DIRECTORY =====
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ===== DATA FILES =====
def get_data_path(filename):
    return os.path.join(DATA_DIR, filename)

def load_json(filename):
    path = get_data_path(filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}
    
def save_json(filename, data):
    path = get_data_path(filename)
    with open(path, "w") as f:
        json.dump(data, f)

# ===== LOAD DATA =====
user_data = load_json("user_data.json")
user_history = load_json("user_history.json")
timetable_data = load_json("timetable.json")
user_themes = load_json("user_themes.json")
spaced_repetition = load_json("spaced_repetition.json")

# ===== THEMES =====
THEMES = {
    "default": {"name": "🌞 Default"},
    "dark": {"name": "🌙 Dark Mode"},
    "neon": {"name": "💫 Neon"},
    "retro": {"name": "🕹️ Retro"},
    "medical": {"name": "🏥 Medical"},
    "nature": {"name": "🌿 Nature"}
}

# ===== SOUND EFFECTS =====
SOUND_EFFECTS = {
    "correct": ["🎉", "✨", "🌟", "💪", "🔥", "🎯", "⭐"],
    "wrong": ["😅", "💀", "🤦", "😬", "💥", "😰"],
    "level_up": ["🎊", "🎉", "🌟", "🏆", "👑", "🚀"],
    "perfect": ["🏆", "🌟", "💎", "👑", "🎊"],
    "streak": ["🔥", "⚡", "💪", "🚀", "✨"],
    "time_up": ["⏰", "💀", "😤", "💥", "🚨"],
}

def get_sound(category):
    return random.choice(SOUND_EFFECTS.get(category, ["✨"]))

# ===== MULTIPLAYER EMOJIS =====
MULTIPLAYER_EMOJIS = [
    "🏆", "🥇", "🥈", "🥉", "🎯", "⭐", "🌟", "💎",
    "👑", "🚀", "🔥", "⚡", "💪", "🎮", "🌈", "✨",
    "🎊", "🎉", "💫", "🌙", "☀️", "🌊", "🌺", "🌸"
]

# ===== ROASTS =====
ROASTS = {
    "time_up": [
        "😤 TIME'S UP! Were you napping? 🥱",
        "⏰ BOOO! Even a snail moves faster! 🐌",
        "💀 You just got OUT-TIMED! Try again, slowpoke!",
        "🤦‍♂️ Your brain needs a speed boost! ⚡",
        "🎯 Too slow! The tortoise beat you! 🐢",
        "😅 Did you fall asleep? Wake up!",
        "🚀 Speed check: FAILED! Try harder!",
        "💤 Zzz... Oh, time's up! Move faster!"
    ],
    "wrong": [
        "😅 Oops! Even Einstein got things wrong sometimes!",
        "💀 That was... interesting. Let's review!",
        "🤦 Not quite! But now you'll remember!",
        "😬 Yikes! That's one way to learn!",
        "💥 Wrong! But mistakes make us stronger!",
        "😰 Close! But no cigar! Keep going!",
        "🤔 Not that one! But you're learning!"
    ]
}

# ===== ENCOURAGEMENT =====
ENCOURAGEMENT = [
    "💪 Don't give up! You got this!",
    "🌟 Every mistake is a lesson! Keep going!",
    "🔥 You're getting better! Stay focused!",
    "📚 Review the answer and come back stronger!",
    "⚡ Speed comes with practice! You'll improve!",
    "🎯 Almost there! Keep pushing!",
    "🧠 Your brain is building new connections!",
    "🚀 You're on the right track!",
    "💎 Every expert was once a beginner!"
]

# ===== GAME CONFIG =====
XP_PER_QUESTION = 10
XP_PER_CORRECT = 25
STREAK_BONUS = 15
LEVEL_UP_BASE = 100
DAILY_CHALLENGE_XP_BONUS = 50
MULTIPLAYER_BONUS = 30
# ===== SPACED REPETITION SYSTEM =====
def add_to_spaced_repetition(chat_id: str, question: dict, is_correct: bool):
    if chat_id not in spaced_repetition:
        spaced_repetition[chat_id] = []
    
    if is_correct:
        review_intervals = [1, 3, 7, 14, 30, 60, 120]
        for item in spaced_repetition[chat_id]:
            if item.get('question') == question.get('q'):
                current_idx = item.get('interval_idx', 0)
                new_idx = min(current_idx + 1, len(review_intervals) - 1)
                item['interval_idx'] = new_idx
                item['next_review'] = (datetime.now() + timedelta(days=review_intervals[new_idx])).isoformat()
                item['correct_count'] = item.get('correct_count', 0) + 1
                save_json("spaced_repetition.json", spaced_repetition)
                return
    
    spaced_repetition[chat_id].append({
        'question': question.get('q', ''),
        'options': question.get('options', []),
        'answer': question.get('answer', 0),
        'explanation': question.get('explanation', ''),
        'topic': question.get('topic', 'General'),
        'interval_idx': 0,
        'next_review': (datetime.now() + timedelta(days=1)).isoformat(),
        'correct_count': 0,
        'wrong_count': 1 if not is_correct else 0,
        'last_reviewed': datetime.now().isoformat()
    })
    save_json("spaced_repetition.json", spaced_repetition)

def get_due_questions(chat_id: str, limit: int = 5):
    if chat_id not in spaced_repetition:
        return []
    
    now = datetime.now()
    due = []
    
    for item in spaced_repetition[chat_id]:
        if item.get('next_review'):
            review_date = datetime.fromisoformat(item['next_review'])
            if review_date <= now:
                due.append(item)
    
    due.sort(key=lambda x: x.get('next_review', ''))
    return due[:limit]

# ===== GENERATE QUESTIONS =====
async def generate_questions(topic: str, num_questions: int = 10, difficulty: str = "medium", 
                            question_type: str = "multiple_choice", subject_field: str = "medical"):
    
    type_prompts = {
        "multiple_choice": "Generate {num} multiple-choice questions with 4 options each.",
        "true_false": "Generate {num} true/false questions that test DEEP UNDERSTANDING.",
        "short_answer": "Generate {num} short answer questions. Make answers concise (1-5 words).",
        "mixed": "Generate {num} questions in MIXED format: some MC, some TF, some SA."
    }
    
    prompt = f"""Generate {num_questions} {question_type.replace('_', ' ')} questions about "{topic}".
    
    Difficulty: {difficulty}
    
    {type_prompts.get(question_type, type_prompts['multiple_choice'])}
    
    IMPORTANT: Include DETAILED explanation for each question.
    
    FORMAT EXACTLY like this:
    
    Q1: [Question text]
    A) [Option 1]
    B) [Option 2]
    C) [Option 3]
    D) [Option 4]
    Answer: [Letter OR True/False OR short answer]
    Explanation: [Detailed explanation]
    Type: [MC/TF/SA]
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are an expert educator. Create accurate educational questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=3000
    )
    
    return response.choices[0].message.content

def parse_questions(text: str, question_type: str = "multiple_choice"):
    questions = []
    parts = re.split(r'Q\d+:', text)
    
    for part in parts[1:]:
        lines = part.strip().split('\n')
        if len(lines) < 3:
            continue
        
        question_text = lines[0].strip()
        options = []
        answer = None
        explanation = ""
        q_type = question_type
        
        for line in lines:
            if line.strip().startswith('Type:'):
                type_text = line.replace('Type:', '').strip().lower()
                if 'tf' in type_text or 'true' in type_text:
                    q_type = "true_false"
                elif 'sa' in type_text or 'short' in type_text:
                    q_type = "short_answer"
                else:
                    q_type = "multiple_choice"
        
        if q_type == "true_false":
            options = ["✅ True", "❌ False"]
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('Answer:'):
                    ans_text = line.replace('Answer:', '').strip().lower()
                    answer = 0 if 'true' in ans_text else 1
                elif line.startswith('Explanation:'):
                    explanation = line.replace('Explanation:', '').strip()
        
        elif q_type == "short_answer":
            options = ["✏️ Type your answer"]
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('Answer:'):
                    answer = line.replace('Answer:', '').strip()
                elif line.startswith('Explanation:'):
                    explanation = line.replace('Explanation:', '').strip()
        
        else:
            for line in lines[1:]:
                line = line.strip()
                if line.startswith(('A)', 'B)', 'C)', 'D)')):
                    options.append(line[2:].strip())
                elif line.startswith('Answer:'):
                    answer_letter = line.replace('Answer:', '').strip().upper()
                    if answer_letter in 'ABCD':
                        answer = ord(answer_letter) - 65
                elif line.startswith('Explanation:'):
                    explanation = line.replace('Explanation:', '').strip()
        
        if question_text and answer is not None:
            questions.append({
                'q': question_text,
                'options': options if options else ["✅ True", "❌ False"],
                'answer': answer,
                'explanation': explanation,
                'type': q_type
            })
    
    return questions

# ===== USER FUNCTIONS =====
def get_level(xp):
    return (xp // LEVEL_UP_BASE) + 1

def get_next_level_xp(xp):
    return ((xp // LEVEL_UP_BASE) + 1) * LEVEL_UP_BASE

def get_rank(level):
    if level >= 50: return "👑 LEGEND"
    if level >= 30: return "💎 MASTER"
    if level >= 20: return "⭐ EXPERT"
    if level >= 10: return "🔥 PRO"
    if level >= 5: return "⚡ ADVANCED"
    if level >= 2: return "📚 LEARNER"
    return "🌱 NOVICE"

def get_accuracy(user):
    correct = user.get('total_correct', 0)
    wrong = user.get('total_wrong', 0)
    total = correct + wrong
    if total == 0:
        return 0
    return (correct / total) * 100
                              # ===== START COMMAND =====
user_sessions = {}
multiplayer_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or "User"
    
    if chat_id not in user_data:
        user_data[chat_id] = {
            "username": username,
            "xp": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "total_quizzes": 0,
            "best_streak": 0,
            "current_streak": 0,
            "games_played": 0,
            "perfect_scores": 0,
            "wrong_questions": [],
            "joined_date": datetime.now().isoformat()
        }
        save_json("user_data.json", user_data)
    
    user = user_data[chat_id]
    level = get_level(user["xp"])
    rank = get_rank(level)
    next_xp = get_next_level_xp(user["xp"])
    progress = (user["xp"] % LEVEL_UP_BASE) / LEVEL_UP_BASE * 100
    accuracy = get_accuracy(user)
    
    due_count = len(get_due_questions(chat_id))
    
    keyboard = [
        [InlineKeyboardButton("🎯 Quick Quiz (5 min)", callback_data="mode_quick")],
        [InlineKeyboardButton("⚡ Speed Round (30s)", callback_data="mode_speed")],
        [InlineKeyboardButton("🏆 Marathon (15 min)", callback_data="mode_marathon")],
        [InlineKeyboardButton("📝 Exam Simulation", callback_data="mode_exam")],
        [InlineKeyboardButton("🧠 Spaced Repetition", callback_data="mode_sr")],
        [InlineKeyboardButton("🎯 Daily Challenge", callback_data="view_daily")],
        [InlineKeyboardButton("🤝 Multiplayer", callback_data="view_multiplayer")],
        [InlineKeyboardButton("📅 Upload Timetable", callback_data="upload_timetable")],
        [InlineKeyboardButton("🎨 Change Theme", callback_data="change_theme")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
        [InlineKeyboardButton("🏅 Leaderboard", callback_data="leaderboard")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎮 *BRAIN TRAINER PRO* 🎮\n\n"
        f"👤 {username}\n"
        f"{rank} *Level {level}*\n"
        f"⭐ XP: {user['xp']} / {next_xp}\n"
        f"📊 Progress: [{'█' * int(progress/10)}{'░' * (10 - int(progress/10))}] {progress:.0f}%\n"
        f"🎯 Accuracy: {accuracy:.1f}%\n\n"
        f"📈 *Stats*\n"
        f"✅ Correct: {user['total_correct']}\n"
        f"❌ Wrong: {user['total_wrong']}\n"
        f"🔥 Best Streak: {user['best_streak']}\n"
        f"🎯 Perfect Scores: {user['perfect_scores']}\n"
        f"📚 Quizzes: {user['total_quizzes']}\n"
        f"🧠 Due for Review: {due_count}\n\n"
        f"*Choose your mode:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ===== MODE SELECTION =====
async def mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace("mode_", "")
    
    if mode == "sr":
        await spaced_repetition_review(update, context)
        return
    
    if mode == "exam":
        await ask_topic(update, context, exam_mode=True)
        return
    
    time_map = {
        "quick": 300,
        "speed": 30,
        "marathon": 900
    }
    
    await ask_topic(update, context, duration=time_map.get(mode, 300), exam_mode=False)

async def ask_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, duration=300, exam_mode=False):
    query = update.callback_query
    await query.answer()
    
    context.user_data['quiz_mode'] = {
        'duration': duration,
        'exam_mode': exam_mode
    }
    
    keyboard = [
        [InlineKeyboardButton("💉 Cardiovascular", callback_data="topic_cardiovascular")],
        [InlineKeyboardButton("🫁 Respiratory", callback_data="topic_respiratory")],
        [InlineKeyboardButton("🧠 Neurology", callback_data="topic_neurology")],
        [InlineKeyboardButton("💊 Pharmacology", callback_data="topic_pharmacology")],
        [InlineKeyboardButton("🧬 Anatomy", callback_data="topic_anatomy")],
        [InlineKeyboardButton("🎲 Random", callback_data="topic_random")],
        [InlineKeyboardButton("✏️ Custom Topic", callback_data="topic_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 *Select a topic*\n\n"
        f"⏱️ Time: {duration//60}m {duration%60}s\n"
        f"📝 Mode: {'📝 EXAM' if exam_mode else '🎯 Practice'}\n\n"
        f"*ANY SUBJECT WELCOME!*\n\n"
        f"Choose your subject:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    topic_data = query.data.replace("topic_", "")
    
    mode = context.user_data.get('quiz_mode', {'duration': 300, 'exam_mode': False})
    duration = mode.get('duration', 300)
    exam_mode = mode.get('exam_mode', False)
    
    if topic_data == "custom":
        await query.edit_message_text(
            "✏️ *Type your topic*\n\n"
            "Send me ANY topic you want to study!\n"
            "Examples:\n"
            "• Cardiology\n"
            "• World War 2\n"
            "• Python Programming\n"
            "• ANYTHING!",
            parse_mode="Markdown"
        )
        context.user_data['awaiting_topic'] = True
        return
    
    topic_map = {
        "cardiovascular": "Cardiovascular Physiology",
        "respiratory": "Respiratory System",
        "neurology": "Neurology",
        "pharmacology": "Pharmacology",
        "anatomy": "Human Anatomy",
        "random": "Random Topic"
    }
    
    topic = topic_map.get(topic_data, "General Knowledge")
    
    if topic_data == "random":
        topics = ["Cardiovascular Physiology", "Respiratory System", "Neurology", 
                  "Pharmacology", "Anatomy", "Biochemistry", "Immunology",
                  "Pathology", "Microbiology", "Genetics"]
        topic = random.choice(topics)
    
    keyboard = [
        [InlineKeyboardButton("📝 Multiple Choice", callback_data=f"qtype_mc_{topic}")],
        [InlineKeyboardButton("✅ True/False (Deep)", callback_data=f"qtype_tf_{topic}")],
        [InlineKeyboardButton("✏️ Short Answer", callback_data=f"qtype_sa_{topic}")],
        [InlineKeyboardButton("🎯 MIXED (All Types!)", callback_data=f"qtype_mixed_{topic}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 *Topic: {topic}*\n\n"
        f"*Choose Question Format:*\n"
        f"• Multiple Choice - 4 options\n"
        f"• True/False - Deep understanding test\n"
        f"• Short Answer - Concise answers\n"
        f"• MIXED - All types combined! 🎯",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split('_')
    q_type = parts[1]
    topic = '_'.join(parts[2:])
    
    context.user_data['question_type'] = q_type
    
    mode = context.user_data.get('quiz_mode', {'duration': 300, 'exam_mode': False})
    duration = mode.get('duration', 300)
    exam_mode = mode.get('exam_mode', False)
    
    await start_quiz_from_topic(update, context, topic, duration, exam_mode, q_type)
                              # ===== START QUIZ =====
async def start_quiz_from_topic(update, context, topic, duration, exam_mode=False, q_type="multiple_choice"):
    chat_id = update.effective_chat.id
    
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        status_msg = await query.edit_message_text(
            f"🤔 *Generating {topic} questions...*\n"
            f"📝 Format: {q_type.upper()}\n"
            f"⏱️ Time: {duration}s\n\n"
            f"_⚡ Powering up brain cells..._",
            parse_mode="Markdown"
        )
    else:
        status_msg = await update.message.reply_text(
            f"🤔 *Generating {topic} questions...*\n"
            f"⏱️ Time: {duration}s\n\n"
            f"_⚡ Powering up brain cells..._",
            parse_mode="Markdown"
        )
    
    try:
        if duration <= 30:
            num_q = 5
        elif duration <= 300:
            num_q = 8
        else:
            num_q = 15
        
        difficulty = context.user_data.get('difficulty', 'medium')
        bonus_xp = context.user_data.get('bonus_xp', 0)
        
        ai_response = await generate_questions(topic, num_questions=num_q, difficulty=difficulty,
                                               question_type=q_type)
        questions = parse_questions(ai_response, q_type)
        
        if len(questions) < 3:
            await status_msg.edit_text("❌ Not enough questions generated. Try a different topic.")
            return
        
        end_time = datetime.now() + timedelta(seconds=duration)
        user_sessions[chat_id] = {
            "end_time": end_time,
            "score": 0,
            "answered": 0,
            "total": len(questions),
            "questions": questions,
            "current_q": 0,
            "start_time": datetime.now(),
            "topic": topic,
            "streak": 0,
            "xp_earned": 0,
            "exam_mode": exam_mode,
            "wrong_answers": [],
            "answers": [],
            "bonus_xp": bonus_xp,
            "question_type": q_type
        }
        
        await status_msg.delete()
        await send_question(chat_id, context, 0)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}\n\nPlease try again!")

async def send_question(chat_id, context: ContextTypes.DEFAULT_TYPE, q_index: int):
    session = user_sessions.get(chat_id)
    if not session or q_index >= session["total"]:
        await end_quiz(chat_id, context)
        return
    
    question = session["questions"][q_index]
    remaining = session["end_time"] - datetime.now()
    total_seconds = max(0, remaining.seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    
    progress = q_index / session["total"]
    bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))
    
    streak_emoji = ""
    if session.get("streak", 0) >= 3:
        streak_emoji = "🔥"
    
    keyboard = []
    q_type = session.get("question_type", "multiple_choice")
    
    actual_type = question.get('type', q_type)
    
    if actual_type == "true_false":
        keyboard = [
            [InlineKeyboardButton("✅ True", callback_data="ans_0")],
            [InlineKeyboardButton("❌ False", callback_data="ans_1")]
        ]
    elif actual_type == "short_answer":
        keyboard = [
            [InlineKeyboardButton("✏️ Type Answer", callback_data="short_answer")]
        ]
    else:
        for i, opt in enumerate(question.get('options', [])):
            keyboard.append([InlineKeyboardButton(
                f"{chr(65+i)}. {opt}",
                callback_data=f"ans_{i}"
            )])
    
    if not session.get('exam_mode', False):
        keyboard.append([
            [InlineKeyboardButton("⏭️ Drop", callback_data="drop_ask")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    timer_emoji = "🟢" if total_seconds > 30 else "🟡" if total_seconds > 10 else "🔴"
    mode_text = "📝 EXAM MODE" if session.get('exam_mode', False) else "🎯 Practice Mode"
    
    type_emoji = {"multiple_choice": "📝", "true_false": "✅", "short_answer": "✏️"}.get(actual_type, "📝")
    
    await context.bot.send_message(
        chat_id,
        f"📚 *{session['topic']}*\n"
        f"{mode_text}\n"
        f"{type_emoji} Type: {actual_type.upper()}\n"
        f"❓ *Q{q_index+1}/{session['total']}*\n"
        f"`{bar}`\n\n"
        f"*{question['q']}*\n\n"
        f"{timer_emoji} ⏱️ `{minutes:02d}:{seconds:02d}`\n"
        f"✅ Score: {session['score']}  |  🔥 Streak: {session.get('streak', 0)}{streak_emoji}\n"
        f"⚡ XP: +{XP_PER_QUESTION} base",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if chat_id not in user_sessions:
        await query.edit_message_text("⏰ Session expired! Use /start to begin again.")
        return
    
    session = user_sessions[chat_id]
    
    if datetime.now() > session["end_time"]:
        await time_up(chat_id, context)
        return
    
    data = query.data
    
    if data == "short_answer":
        await query.edit_message_text(
            "✏️ *Type your answer*\n\n"
            "Send your answer as text.",
            parse_mode="Markdown"
        )
        context.user_data['awaiting_short_answer'] = True
        return
    
    if data == "drop_ask":
        keyboard = [
            [InlineKeyboardButton("✅ YES, drop it!", callback_data="drop_yes")],
            [InlineKeyboardButton("❌ NO, keep going!", callback_data="drop_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🤔 *Drop this question?*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return
    
    if data == "drop_yes":
        await query.edit_message_text("⏭️ *Dropping question...*")
        await asyncio.sleep(1.5)
        await query.message.delete()
        session["current_q"] += 1
        if session["current_q"] < session["total"]:
            await send_question(chat_id, context, session["current_q"])
        else:
            await end_quiz(chat_id, context)
        return
    
    if data == "drop_no":
        await query.edit_message_text("💪 *Great! Let's keep going!*")
        await asyncio.sleep(1)
        await query.message.delete()
        await send_question(chat_id, context, session["current_q"])
        return
    
    if data.startswith("ans_"):
        selected = int(data.split("_")[1])
        current_q = session["current_q"]
        question = session["questions"][current_q]
        correct = question["answer"]
        is_correct = (selected == correct)
        
        add_to_spaced_repetition(str(chat_id), question, is_correct)
        
        session["answers"].append({
            "question": question['q'],
            "selected": selected,
            "correct": correct,
            "is_correct": is_correct,
            "options": question.get('options', []),
            "explanation": question.get('explanation', '')
        })
        
        if session.get('exam_mode', False):
            if is_correct:
                session["score"] += 1
                session["streak"] = session.get("streak", 0) + 1
            else:
                session["streak"] = 0
                session["wrong_answers"].append(current_q)
            
            await query.edit_message_text(
                f"📝 *Answer recorded* ({session['answered']+1}/{session['total']})\n"
                f"✅ Correct: {session['score']}",
                parse_mode="Markdown"
            )
            
            session["answered"] += 1
            session["current_q"] += 1
            
            await asyncio.sleep(1.5)
            await query.message.delete()
            
            if session["current_q"] < session["total"]:
                await send_question(chat_id, context, session["current_q"])
            else:
                await end_quiz(chat_id, context)
            return
        
        chat_id_str = str(chat_id)
        user = user_data.get(chat_id_str, {"xp": 0, "total_correct": 0, "total_wrong": 0})
        
        if is_correct:
            sound_effect = get_sound("correct")
            xp_gain = XP_PER_CORRECT
            session["streak"] = session.get("streak", 0) + 1
            session["score"] += 1
            user["total_correct"] = user.get("total_correct", 0) + 1
            
            if session["streak"] >= 3:
                xp_gain += STREAK_BONUS
                streak_msg = f"\n🔥 *Streak Bonus!* +{STREAK_BONUS} XP"
            else:
                streak_msg = ""
            
            if session.get("bonus_xp", 0) > 0:
                xp_gain += session["bonus_xp"]
                streak_msg += f"\n🎯 *Bonus!* +{session['bonus_xp']} XP"
                session["bonus_xp"] = 0
            
            session["xp_earned"] = session.get("xp_earned", 0) + xp_gain
            user["xp"] = user.get("xp", 0) + xp_gain
            
            if session["streak"] > user.get("best_streak", 0):
                user["best_streak"] = session["streak"]
            
            feedback = (
                f"{sound_effect} *CORRECT!* 🎉\n"
                f"✨ +{xp_gain} XP{streak_msg}\n"
                f"🔥 Streak: {session['streak']}\n\n"
                f"📖 *Explanation:*\n{question.get('explanation', 'Great job!')}"
            )
        else:
            sound_effect = get_sound("wrong")
            if question.get('type') == "short_answer":
                correct_text = question['answer']
            else:
                correct_text = question['options'][correct] if question.get('options') else "N/A"
            session["streak"] = 0
            user["total_wrong"] = user.get("total_wrong", 0) + 1
            session["wrong_answers"].append(current_q)
            
            feedback = (
                f"{sound_effect} *WRONG!*\n"
                f"✅ Correct answer: *{correct_text}*\n\n"
                f"📖 *Explanation:*\n{question.get('explanation', 'Review this topic.')}\n\n"
                f"💡 *Better way to understand:*\n"
                f"• Break down the concept\n"
                f"• Create a mnemonic\n"
                f"• Practice similar questions\n\n"
                f"{random.choice(ENCOURAGEMENT)}"
            )
        
        user_data[chat_id_str] = user
        save_json("user_data.json", user_data)
        
        await query.edit_message_text(feedback, parse_mode="Markdown")
        
        session["answered"] += 1
        session["current_q"] += 1
        
        await asyncio.sleep(3)
        await query.message.delete()
        
        if session["current_q"] < session["total"]:
            keyboard = [
                [InlineKeyboardButton("✅ YES, drop it!", callback_data="drop_yes")],
                [InlineKeyboardButton("❌ NO, show it!", callback_data="drop_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id,
                f"⏭️ *Ready for next question?*",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await end_quiz(chat_id, context)
          async def handle_short_answer_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_short_answer'):
        return
    
    chat_id = update.effective_chat.id
    user_answer = update.message.text
    
    if chat_id not in user_sessions:
        await update.message.reply_text("⏰ Session expired!")
        return
    
    session = user_sessions[chat_id]
    current_q = session["current_q"]
    question = session["questions"][current_q]
    
    is_correct = user_answer.lower().strip() == question['answer'].lower().strip()
    
    chat_id_str = str(chat_id)
    user = user_data.get(chat_id_str, {"xp": 0, "total_correct": 0, "total_wrong": 0})
    
    if is_correct:
        xp_gain = XP_PER_CORRECT
        session["score"] += 1
        user["total_correct"] = user.get("total_correct", 0) + 1
        session["xp_earned"] = session.get("xp_earned", 0) + xp_gain
        user["xp"] = user.get("xp", 0) + xp_gain
        feedback = f"✅ *CORRECT!* 🎉\n✨ +{xp_gain} XP"
    else:
        user["total_wrong"] = user.get("total_wrong", 0) + 1
        feedback = (
            f"❌ *WRONG!*\n"
            f"✅ Correct answer: *{question['answer']}*\n\n"
            f"📖 *Explanation:*\n{question.get('explanation', 'Review this.')}"
        )
    
    user_data[chat_id_str] = user
    save_json("user_data.json", user_data)
    
    await update.message.reply_text(feedback, parse_mode="Markdown")
    
    context.user_data['awaiting_short_answer'] = False
    session["answered"] += 1
    session["current_q"] += 1
    
    await asyncio.sleep(2)
    
    if session["current_q"] < session["total"]:
        await send_question(chat_id, context, session["current_q"])
    else:
        await end_quiz(chat_id, context)

async def time_up(chat_id, context: ContextTypes.DEFAULT_TYPE):
    session = user_sessions.pop(chat_id, None)
    if not session:
        return
    
    sound = get_sound("time_up")
    roast = random.choice(ROASTS["time_up"])
    
    answered = session.get("answered", 0)
    total = session.get("total", 0)
    score = session.get("score", 0)
    
    await context.bot.send_message(
        chat_id,
        f"{sound} *TIME'S UP!*\n\n"
        f"{roast}\n\n"
        f"📊 You answered {answered}/{total} questions\n"
        f"✅ Score: {score}\n"
        f"📈 Accuracy: {(score/answered*100 if answered > 0 else 0):.1f}%\n\n"
        f"💪 Practice makes perfect! Try again!",
        parse_mode="Markdown"
    )
    
    await show_quiz_results(chat_id, context, session)

async def end_quiz(chat_id, context: ContextTypes.DEFAULT_TYPE):
    session = user_sessions.pop(chat_id, None)
    if not session:
        return
    
    await show_quiz_results(chat_id, context, session)

async def show_quiz_results(chat_id, context: ContextTypes.DEFAULT_TYPE, session):
    score = session.get("score", 0)
    total = session.get("total", 0)
    elapsed = (datetime.now() - session.get("start_time", datetime.now())).seconds
    xp_earned = session.get("xp_earned", 0)
    streak = session.get("streak", 0)
    wrong_answers = session.get("wrong_answers", [])
    
    percentage = (score / total) * 100 if total > 0 else 0
    
    if score == total and total > 0:
        sound = get_sound("perfect")
        perfect_bonus = 50
        perfect_msg = f"\n🌟 *PERFECT SCORE!* +{perfect_bonus} XP 🌟"
        user_data[str(chat_id)]["perfect_scores"] = user_data[str(chat_id)].get("perfect_scores", 0) + 1
    else:
        sound = get_sound("game_over")
        perfect_bonus = 0
        perfect_msg = ""
    
    avg_time = elapsed / total if total > 0 else 0
    if avg_time < 3:
        speed_bonus = 30
        speed_msg = f"\n⚡ *Speed Demon!* +{speed_bonus} XP"
    elif avg_time < 5:
        speed_bonus = 15
        speed_msg = f"\n💨 *Quick Thinker!* +{speed_bonus} XP"
    else:
        speed_bonus = 0
        speed_msg = ""
    
    total_xp = xp_earned + perfect_bonus + speed_bonus
    chat_id_str = str(chat_id)
    user_data[chat_id_str]["xp"] = user_data[chat_id_str].get("xp", 0) + perfect_bonus + speed_bonus
    user_data[chat_id_str]["total_quizzes"] = user_data[chat_id_str].get("total_quizzes", 0) + 1
    user_data[chat_id_str]["games_played"] = user_data[chat_id_str].get("games_played", 0) + 1
    
    history_entry = {
        "topic": session.get("topic", ""),
        "score": score,
        "total": total,
        "percentage": percentage,
        "time": elapsed,
        "xp_earned": total_xp,
        "date": datetime.now().isoformat(),
        "mode": "Exam" if session.get("exam_mode") else "Practice",
        "wrong_questions": wrong_answers,
        "question_type": session.get("question_type", "multiple_choice")
    }
    
    if chat_id_str not in user_history:
        user_history[chat_id_str] = []
    user_history[chat_id_str].append(history_entry)
    
    save_json("user_data.json", user_data)
    save_json("user_history.json", user_history)
    
    if percentage >= 90:
        grade = "🏆 *S+ RANK* - ABSOLUTE LEGEND!"
    elif percentage >= 80:
        grade = "⭐ *A RANK* - Excellent!"
    elif percentage >= 70:
        grade = "👍 *B RANK* - Good job!"
    elif percentage >= 60:
        grade = "📚 *C RANK* - Keep practicing!"
    else:
        grade = "💪 *D RANK* - Review and try again!"
    
    new_level = get_level(user_data[chat_id_str]["xp"])
    level_up_msg = f"\n🎉 *LEVEL UP!* You're now Level {new_level}! 🎉" if new_level > get_level(user_data[chat_id_str]["xp"] - total_xp) else ""
    
    results_msg = (
        f"{sound} *QUIZ COMPLETE!*\n\n"
        f"📚 Topic: *{session.get('topic', 'Unknown')}*\n"
        f"📝 Type: {session.get('question_type', 'multiple_choice').upper()}\n"
        f"{grade}\n\n"
        f"📊 Score: *{score}/{total}*\n"
        f"📈 Accuracy: *{percentage:.1f}%*\n"
        f"⏱️ Time: *{elapsed//60}m {elapsed%60}s*\n"
        f"🔥 Streak: {streak}\n\n"
        f"✨ *XP EARNED*\n"
        f"Base: +{xp_earned} XP\n"
        f"{perfect_msg}{speed_msg}\n"
        f"⭐ *TOTAL: +{total_xp} XP*\n"
        f"{level_up_msg}"
    )
    
    due_count = len(get_due_questions(chat_id_str))
    if due_count > 0:
        results_msg += f"\n\n🧠 You have {due_count} questions due for review!\nUse /spaced_review to practice them!"
    
    if wrong_answers and not session.get("exam_mode"):
        results_msg += f"\n\n📚 *Questions to review:* {len(wrong_answers)}"
    
    await context.bot.send_message(chat_id, results_msg, parse_mode="Markdown")

# ===== SPACED REPETITION REVIEW =====
async def spaced_repetition_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    due_questions = get_due_questions(chat_id, limit=10)
    
    if not due_questions:
        await update.message.reply_text(
            "🧠 *Spaced Repetition*\n\n"
            "No questions due for review! 🎉\n\n"
            "Keep practicing and I'll remind you when to review!",
            parse_mode="Markdown"
        )
        return
    
    context.user_data['sr_session'] = due_questions
    context.user_data['sr_index'] = 0
    context.user_data['sr_score'] = 0
    
    await send_sr_question(update, context)

async def send_sr_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    due_questions = context.user_data.get('sr_session', [])
    index = context.user_data.get('sr_index', 0)
    
    if index >= len(due_questions):
        score = context.user_data.get('sr_score', 0)
        total = len(due_questions)
        await update.message.reply_text(
            f"🧠 *Spaced Repetition Complete!*\n\n"
            f"📊 Score: {score}/{total}\n"
            f"✅ Accuracy: {(score/total*100 if total > 0 else 0):.1f}%\n\n"
            f"Great job! Your brain is getting stronger! 💪",
            parse_mode="Markdown"
        )
        return
    
    question = due_questions[index]
    
    keyboard = []
    for i, opt in enumerate(question.get('options', [])):
        keyboard.append([InlineKeyboardButton(
            f"{chr(65+i)}. {opt}",
            callback_data=f"sr_ans_{i}"
        )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🧠 *Spaced Repetition* ({index+1}/{len(due_questions)})\n\n"
        f"*{question.get('question', '')}*\n\n"
        f"Topic: {question.get('topic', 'General')}\n"
        f"📊 Correct: {question.get('correct_count', 0)} | Wrong: {question.get('wrong_count', 0)}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_sr_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    data = query.data
    if not data.startswith("sr_ans_"):
        return
    
    selected = int(data.split("_")[2])
    index = context.user_data.get('sr_index', 0)
    due_questions = context.user_data.get('sr_session', [])
    
    if index >= len(due_questions):
        return
    
    question = due_questions[index]
    correct = question.get('answer', 0)
    is_correct = (selected == correct)
    
    if is_correct:
        context.user_data['sr_score'] = context.user_data.get('sr_score', 0) + 1
        await query.edit_message_text(
            f"✅ *Correct!* 🎉\n\n"
            f"Explanation: {question.get('explanation', 'Great job!')}",
            parse_mode="Markdown"
        )
    else:
        correct_text = question.get('options', [])[correct] if question.get('options') else "N/A"
        await query.edit_message_text(
            f"❌ *Wrong!*\n\n"
            f"Correct answer: *{correct_text}*\n\n"
            f"Explanation: {question.get('explanation', 'Review this topic.')}",
            parse_mode="Markdown"
        )
    
    if chat_id in spaced_repetition:
        for item in spaced_repetition[chat_id]:
            if item.get('question') == question.get('question'):
                if is_correct:
                    item['correct_count'] = item.get('correct_count', 0) + 1
                else:
                    item['wrong_count'] = item.get('wrong_count', 0) + 1
                    item['interval_idx'] = 0
                item['last_reviewed'] = datetime.now().isoformat()
                review_intervals = [1, 3, 7, 14, 30, 60, 120]
                idx = min(item.get('interval_idx', 0) + (1 if is_correct else -1), len(review_intervals) - 1)
                idx = max(0, idx)
                item['interval_idx'] = idx
                item['next_review'] = (datetime.now() + timedelta(days=review_intervals[idx])).isoformat()
                save_json("spaced_repetition.json", spaced_repetition)
                break
    
    await asyncio.sleep(3)
    context.user_data['sr_index'] = index + 1
    await send_sr_question(update, context)
# ===== STATS =====
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    user = user_data.get(chat_id, {})
    level = get_level(user.get("xp", 0))
    rank = get_rank(level)
    next_xp = get_next_level_xp(user.get("xp", 0))
    accuracy = get_accuracy(user)
    
    due_count = len(get_due_questions(chat_id))
    
    stats_text = (
        f"📊 *YOUR STATS*\n\n"
        f"{rank} *Level {level}*\n"
        f"⭐ XP: {user.get('xp', 0)} / {next_xp}\n\n"
        f"✅ Correct: {user.get('total_correct', 0)}\n"
        f"❌ Wrong: {user.get('total_wrong', 0)}\n"
        f"📈 Accuracy: {accuracy:.1f}%\n"
        f"🔥 Best Streak: {user.get('best_streak', 0)}\n"
        f"🎯 Perfect Scores: {user.get('perfect_scores', 0)}\n"
        f"🎮 Games Played: {user.get('games_played', 0)}\n"
        f"📚 Total Quizzes: {user.get('total_quizzes', 0)}\n"
        f"🧠 Due for Review: {due_count}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== LEADERBOARD =====
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sorted_users = sorted(user_data.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
    
    leaderboard = "🏅 *LEADERBOARD* 🏅\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, data) in enumerate(sorted_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        level = get_level(data.get("xp", 0))
        rank = get_rank(level)
        username = data.get('username', 'Anonymous')
        leaderboard += f"{medal} {username} - {rank} (Lvl {level}) - {data.get('xp', 0)} XP\n"
        leaderboard += f"   📊 Accuracy: {get_accuracy(data):.1f}%\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(leaderboard, parse_mode="Markdown", reply_markup=reply_markup)

# ===== DAILY CHALLENGE =====
async def view_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await daily_challenge(update, context)

async def daily_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if chat_id in timetable_data:
        timetable = timetable_data[chat_id]["content"]
        topics = []
        for line in timetable.split('\n'):
            if ':' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    topics.append(parts[1].strip())
        
        if topics:
            topic = random.choice(topics)
        else:
            topic = "Medical Physiology"
    else:
        topics = ["Cardiovascular Physiology", "Respiratory System", "Neurology",
                  "Pharmacology", "Anatomy", "Biochemistry"]
        topic = random.choice(topics)
    
    await update.message.reply_text(
        f"🎯 *DAILY CHALLENGE*\n\n"
        f"📚 Topic: *{topic}*\n"
        f"🏆 Bonus XP: +{DAILY_CHALLENGE_XP_BONUS} XP\n\n"
        f"Ready?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Start", callback_data=f"daily_{topic}")]
        ])
    )

async def start_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    topic = query.data.replace("daily_", "")
    
    context.user_data['bonus_xp'] = DAILY_CHALLENGE_XP_BONUS
    context.user_data['quiz_mode'] = {
        'duration': 300,
        'exam_mode': False
    }
    
    keyboard = [
        [InlineKeyboardButton("📝 Multiple Choice", callback_data=f"qtype_mc_{topic}")],
        [InlineKeyboardButton("✅ True/False (Deep)", callback_data=f"qtype_tf_{topic}")],
        [InlineKeyboardButton("✏️ Short Answer", callback_data=f"qtype_sa_{topic}")],
        [InlineKeyboardButton("🎯 MIXED", callback_data=f"qtype_mixed_{topic}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📚 *Topic: {topic}*\n\n"
        f"Choose question format:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ===== TIMETABLE =====
async def upload_timetable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 *Upload Your Timetable*\n\n"
        "Type your timetable like this:\n\n"
        "Monday: Cardiology 9AM-12PM\n"
        "Tuesday: Respiratory 9AM-12PM\n"
        "Wednesday: Neurology 9AM-12PM\n\n"
        "I'll generate daily challenges from it!",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_timetable'] = True

async def handle_timetable_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_timetable'):
        return
    
    chat_id = str(update.effective_chat.id)
    text = update.message.text
    
    timetable_data[chat_id] = {
        "content": text,
        "upload_date": datetime.now().isoformat()
    }
    save_json("timetable.json", timetable_data)
    
    context.user_data['awaiting_timetable'] = False
    
    await update.message.reply_text(
        "✅ *Timetable Saved!*\n\n"
        f"Use /daily to get today's topics!",
        parse_mode="Markdown"
    )

# ===== THEME =====
async def change_theme_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for theme_key, theme_data in THEMES.items():
        keyboard.append([InlineKeyboardButton(
            theme_data['name'],
            callback_data=f"theme_{theme_key}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎨 *Choose Your Theme*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def set_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    theme_name = query.data.replace("theme_", "")
    
    if theme_name in THEMES:
        user_themes[chat_id] = theme_name
        save_json("user_themes.json", user_themes)
        
        await query.edit_message_text(
            f"✅ *Theme Changed!*\n\n"
            f"Now using: {THEMES[theme_name]['name']}",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("❌ Invalid theme!")

# ===== BACK TO MENU =====
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    class FakeMessage:
        def __init__(self, chat_id):
            self.chat_id = chat_id
        async def reply_text(self, *args, **kwargs):
            pass
    
    fake_update = type('obj', (object,), {
        'effective_chat': type('obj', (object,), {'id': query.message.chat_id}),
        'effective_user': type('obj', (object,), {'username': None}),
        'message': FakeMessage(query.message.chat_id),
        'callback_query': query
    })()
    
    await start(fake_update, context)

# ===== HELP =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *BRAIN TRAINER PRO - COMPLETE HELP*\n\n"
        "*🎯 Game Modes:*\n"
        "• Quick Quiz - 5 min practice\n"
        "• Speed Round - 30 seconds!\n"
        "• Marathon - 15 min deep learning\n"
        "• Exam Simulation - NO peeking!\n"
        "• Spaced Repetition - Anki-like review\n"
        "• Daily Challenge - From timetable\n"
        "• Multiplayer - Race against friends!\n\n"
        "*📝 Question Formats:*\n"
        "• Multiple Choice - 4 options\n"
        "• True/False - Deep understanding test\n"
        "• Short Answer - Concise answers\n"
        "• MIXED - All types combined! 🎯\n"
        "• COMBINED - Merge different player choices!\n\n"
        "*🤝 Multiplayer Features:*\n"
        "• Each player picks their format!\n"
        "• Different formats = COMBINED mode! 🔥\n"
        "• One EMOJI per correct answer! 🏆\n"
        "• Live leaderboard after EVERY answer\n"
        "• Both must agree to drop questions\n\n"
        "*Commands:*\n"
        "/start - Main menu\n"
        "/help - This help\n"
        "/cancel - Cancel\n"
        "/quiz [topic] - Quick quiz\n"
        "/join [code] - Join multiplayer\n"
        "/start_match - Start multiplayer\n"
        "/timetable - Upload schedule\n"
        "/daily - Today's challenge\n"
        "/spaced_review - Spaced repetition\n\n"
        "*🧠 Spaced Repetition:*\n"
        "Like Anki! Reviews at optimal intervals\n"
        "1, 3, 7, 14, 30, 60, 120 days! 💪",
        parse_mode="Markdown"
      # ===== CANCEL =====
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
        await update.message.reply_text("❌ Quiz cancelled.")
    else:
        await update.message.reply_text("No active quiz.")

# ===== QUICK QUIZ =====
async def handle_quick_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "🎯 *Quick Quiz*\n\n"
            "Usage: `/quiz [topic] [difficulty] [seconds]`\n\n"
            "Examples:\n"
            "• `/quiz Cardiology hard 30`\n"
            "• `/quiz Python easy`\n"
            "• `/quiz History`\n\n"
            "*Then choose your question format!*",
            parse_mode="Markdown"
        )
        return
    
    topic_parts = []
    difficulty = "medium"
    time_seconds = 300
    
    for arg in args:
        if arg.lower() in ['easy', 'medium', 'hard', 'expert']:
            difficulty = arg.lower()
        elif arg.isdigit():
            time_seconds = int(arg)
        else:
            topic_parts.append(arg)
    
    topic = " ".join(topic_parts) if topic_parts else "General Knowledge"
    
    context.user_data['difficulty'] = difficulty
    context.user_data['quiz_mode'] = {
        'duration': time_seconds,
        'exam_mode': False
    }
    
    keyboard = [
        [InlineKeyboardButton("📝 Multiple Choice", callback_data=f"qtype_mc_{topic}")],
        [InlineKeyboardButton("✅ True/False (Deep)", callback_data=f"qtype_tf_{topic}")],
        [InlineKeyboardButton("✏️ Short Answer", callback_data=f"qtype_sa_{topic}")],
        [InlineKeyboardButton("🎯 MIXED", callback_data=f"qtype_mixed_{topic}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📚 *Topic: {topic}*\n\n"
        f"Choose question format:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def spaced_review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await spaced_repetition_review(update, context)

# ===== MULTIPLAYER =====
async def start_multiplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    keyboard = [
        [InlineKeyboardButton("🎮 Create Room", callback_data="mp_create")],
        [InlineKeyboardButton("🔍 Join Room", callback_data="mp_join")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤝 *MULTIPLAYER MODE*\n\n"
        "Race against friends!\n\n"
        "🔥 *Combined Mode!*\n"
        "• Each player picks their format\n"
        "• Different formats = COMBINED! 🎯\n\n"
        "Rules:\n"
        "• Each correct answer = Random EMOJI! 🏆\n"
        "• Live leaderboard after EVERY answer\n"
        "• Both must agree to drop questions",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def multiplayer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    if query.data == "mp_create":
        room_code = hashlib.md5(str(chat_id + datetime.now().timestamp()).encode()).hexdigest()[:6].upper()
        
        keyboard = [
            [InlineKeyboardButton("📝 Multiple Choice", callback_data=f"mp_type_mc_{room_code}")],
            [InlineKeyboardButton("✅ True/False (Deep)", callback_data=f"mp_type_tf_{room_code}")],
            [InlineKeyboardButton("✏️ Short Answer", callback_data=f"mp_type_sa_{room_code}")],
            [InlineKeyboardButton("🎯 MIXED (All Types!)", callback_data=f"mp_type_mixed_{room_code}")],
            [InlineKeyboardButton("🤝 COMBINED Mode", callback_data=f"mp_type_combined_{room_code}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎮 *Create Room*\n\n"
            f"🔑 Room Code: `{room_code}`\n\n"
            f"*Choose Question Format:*\n"
            f"• Mixed = All types in one quiz\n"
            f"• Combined = Merge different player choices!",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return
    
    if query.data.startswith("mp_type_"):
        parts = query.data.split("_")
        q_type = parts[2]
        room_code = parts[3]
        
        if room_code not in multiplayer_sessions:
            multiplayer_sessions[room_code] = {
                "host": chat_id,
                "players": [chat_id],
                "status": "waiting",
                "questions": [],
                "scores": {},
                "emojis": {},
                "current_q": 0,
                "started": False,
                "question_types": {},
                "drop_votes": {},
                "answered": {},
                "total": 10,
                "combined_mode": q_type == "combined"
            }
        
        multiplayer_sessions[room_code]["question_types"][chat_id] = q_type
        
        await query.edit_message_text(
            f"🎮 *Room Created!*\n\n"
            f"🔑 Room Code: `{room_code}`\n"
            f"📝 Your Format: {q_type.upper()}\n\n"
            f"Share this code with friends!\n"
            f"Use: `/join {room_code}`\n\n"
            f"*If opponent picks different format:*\n"
            f"🤝 COMBINED Mode - We merge both! 🎯\n\n"
            f"When everyone is ready, use `/start_match`",
            parse_mode="Markdown"
        )
        return
    
    if query.data == "mp_join":
        await query.edit_message_text(
            "🔍 *Join Multiplayer*\n\n"
            "Send the room code:\n"
            "Example: `/join ABC123`\n\n"
            "*You'll be asked to choose your format!*",
            parse_mode="Markdown"
        )
        context.user_data['awaiting_room_code'] = True

async def join_multiplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Usage: `/join ROOM_CODE`\n"
            "Example: `/join ABC123`",
            parse_mode="Markdown"
        )
        return
    
    room_code = args[0].upper()
    
    if room_code not in multiplayer_sessions:
        await update.message.reply_text("❌ Room not found! Check the code.")
        return
    
    room = multiplayer_sessions[room_code]
    if room["status"] == "started":
        await update.message.reply_text("❌ Game already started!")
        return
    
    if chat_id in room["players"]:
        await update.message.reply_text("✅ You're already in the room!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Multiple Choice", callback_data=f"mp_join_mc_{room_code}")],
        [InlineKeyboardButton("✅ True/False (Deep)", callback_data=f"mp_join_tf_{room_code}")],
        [InlineKeyboardButton("✏️ Short Answer", callback_data=f"mp_join_sa_{room_code}")],
        [InlineKeyboardButton("🎯 MIXED", callback_data=f"mp_join_mixed_{room_code}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔑 *Joining Room: {room_code}*\n\n"
        f"*Choose your question format:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def mp_join_format_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    data = query.data
    parts = data.split('_')
    q_type = parts[2]
    room_code = parts[3]
    
    room = multiplayer_sessions.get(room_code)
    if not room:
        await query.edit_message_text("❌ Room expired!")
        return
    
    room["players"].append(chat_id)
    room["question_types"][chat_id] = q_type
    
    await query.edit_message_text(
        f"✅ *Joined Room!*\n\n"
        f"🔑 Room: {room_code}\n"
        f"📝 Your Format: {q_type.upper()}\n"
        f"👥 Players: {len(room['players'])}\n\n"
        f"*Combined Mode Active!* 🔥\n"
        f"Different formats will be MERGED!",
        parse_mode="Markdown"
    )
    
    host_id = int(room["host"])
    await context.bot.send_message(
        host_id,
        f"🎮 New player joined!\n"
        f"📝 Format: {q_type.upper()}\n"
        f"👥 Total players: {len(room['players'])}\n"
        f"Use `/start_match` to begin!"
    )

async def start_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    room_code = None
    for code, room in multiplayer_sessions.items():
        if room["host"] == chat_id and room["status"] == "waiting":
            room_code = code
            break
    
    if not room_code:
        await update.message.reply_text("❌ You don't have a waiting room!")
        return
    
    room = multiplayer_sessions[room_code]
    
    if len(room["players"]) < 2:
        await update.message.reply_text("❌ Need at least 2 players to start!")
        return
    
    await update.message.reply_text("🤔 Generating questions for multiplayer...")
    
    topic = random.choice(["Cardiovascular Physiology", "Respiratory System", "Neurology", 
                          "Pharmacology", "Anatomy", "Biochemistry"])
    
    player_types = room.get("question_types", {})
    unique_types = list(set(player_types.values()))
    
    if len(unique_types) > 1 or "combined" in unique_types:
        final_type = "mixed"
        await update.message.reply_text(
            f"🎯 *COMBINED MODE ACTIVATED!*\n\n"
            f"Players chose different formats!\n"
            f"📝 Merging: {', '.join(unique_types)}\n\n"
            f"🔥 Mixed questions incoming!",
            parse_mode="Markdown"
        )
    else:
        final_type = unique_types[0] if unique_types else "multiple_choice"
    
    ai_response = await generate_questions(topic, num_questions=10, difficulty="medium", 
                                           question_type=final_type)
    questions = parse_questions(ai_response, final_type)
    
    if len(questions) < 5:
        await update.message.reply_text("❌ Not enough questions. Try again!")
        return
    
    room["questions"] = questions
    room["status"] = "started"
    room["total"] = len(questions)
    room["scores"] = {player: 0 for player in room["players"]}
    room["emojis"] = {player: [] for player in room["players"]}
    room["drop_votes"] = {}
    room["answered"] = {}
    
    for player_id in room["players"]:
        try:
            await context.bot.send_message(
                int(player_id),
                f"🎮 *MATCH STARTED!*\n\n"
                f"🔑 Room: {room_code}\n"
                f"📚 Topic: {topic}\n"
                f"📝 Format: {final_type.upper()}\n"
                f"📝 {len(questions)} questions\n\n"
                f"🏆 Collect EMOJIS for correct answers!\n"
                f"📊 Live leaderboard after EVERY answer!\n"
                f"🔥 GOOD LUCK!",
                parse_mode="Markdown"
            )
        except:
            pass
    
    await send_multiplayer_question(room_code, context, 0)

async def send_multiplayer_question(room_code: str, context: ContextTypes.DEFAULT_TYPE, q_index: int):
    room = multiplayer_sessions.get(room_code)
    if not room or q_index >= room["total"]:
        await end_multiplayer(room_code, context)
        return
    
    question = room["questions"][q_index]
    room["answered"] = {}
    room["drop_votes"] = {}
    
    keyboard = []
    q_type = question.get('type', 'multiple_choice')
    
    if q_type == "true_false":
        keyboard.append([InlineKeyboardButton("✅ True", callback_data=f"mp_{room_code}_{q_index}_0")])
        keyboard.append([InlineKeyboardButton("❌ False", callback_data=f"mp_{room_code}_{q_index}_1")])
    elif q_type == "short_answer":
        keyboard.append([InlineKeyboardButton("✏️ Type Answer", callback_data=f"mp_short_{room_code}_{q_index}")])
    else:
        for i, opt in enumerate(question.get('options', [])):
            keyboard.append([InlineKeyboardButton(
                f"{chr(65+i)}. {opt}",
                callback_data=f"mp_{room_code}_{q_index}_{i}"
            )])
    
    keyboard.append([InlineKeyboardButton("⏭️ Drop (Both must agree)", callback_data=f"mp_{room_code}_{q_index}_drop")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    type_emoji = {"multiple_choice": "📝", "true_false": "✅", "short_answer": "✏️"}.get(q_type, "📝")
    
    for player_id in room["players"]:
        try:
            await context.bot.send_message(
                int(player_id),
                f"🎮 *Multiplayer - Q{q_index+1}/{room['total']}*\n"
                f"{type_emoji} Type: {q_type.upper()}\n\n"
                f"*{question['q']}*\n\n"
                f"🏆 Correct = Random Emoji!\n"
                f"📊 Leaderboard updates after each answer!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except:
            pass

async def handle_multiplayer_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    
    data = query.data
    parts = data.split('_')
    
    if len(parts) < 3:
        return
    
    room_code = parts[1]
    q_index = int(parts[2])
    
    room = multiplayer_sessions.get(room_code)
    if not room:
        await query.edit_message_text("❌ Room expired!")
        return
    
    if len(parts) > 3 and parts[3] == "drop":
        room["drop_votes"][chat_id] = True
        
        if len(room["drop_votes"]) >= len(room["players"]):
            await query.edit_message_text("⏭️ *All players agree! Dropping...*", parse_mode="Markdown")
            
            question = room["questions"][q_index]
            if question.get('type') == "short_answer":
                correct_text = question['answer']
            else:
                correct_text = question['options'][question['answer']] if question.get('options') else "N/A"
            
            await context.bot.send_message(
                int(chat_id),
                f"📖 *Answer: {correct_text}*\n\n{question.get('explanation', '')}",
                parse_mode="Markdown"
            )
            
            await asyncio.sleep(1.5)
            room["current_q"] += 1
            await send_multiplayer_question(room_code, context, room["current_q"])
            return
        else:
            remaining = len(room["players"]) - len(room["drop_votes"])
            await query.edit_message_text(
                f"⏳ *Waiting for opponent...*\n"
                f"Need {remaining} more vote(s)",
                parse_mode="Markdown"
            )
            return
    
    if parts[0] == "mp" and len(parts) > 3 and parts[3] != "drop":
        selected = int(parts[3])
        
        if chat_id in room.get("answered", {}):
            await query.edit_message_text("⏰ Already answered!")
            return
        
        question = room["questions"][q_index]
        correct = question["answer"]
        
        if question.get('type') == "short_answer":
            await query.edit_message_text(
                "✏️ *Type your answer*\n\n"
                f"Send your answer as text.",
                parse_mode="Markdown"
            )
            context.user_data['mp_answer'] = {
                'room_code': room_code,
                'q_index': q_index
            }
            return
        
        is_correct = (selected == correct)
        
        if is_correct:
            emoji = random.choice(MULTIPLAYER_EMOJIS)
            room["emojis"][chat_id].append(emoji)
            room["scores"][chat_id] = room["scores"].get(chat_id, 0) + 1
            room["answered"][chat_id] = True
            
            feedback = f"✅ *Correct!* 🎉\n🏆 You earned: {emoji}"
        else:
            room["answered"][chat_id] = False
            if question.get('type') == "short_answer":
                correct_text = question['answer']
            else:
                correct_text = question['options'][correct] if question.get('options') else "N/A"
            feedback = f"❌ *Wrong!*\n✅ Correct: {correct_text}"
        
        await query.edit_message_text(feedback, parse_mode="Markdown")
        
        # Show live leaderboard
        leaderboard = await show_live_leaderboard(room_code, context, chat_id)
        if leaderboard:
            await context.bot.send_message(
                int(chat_id),
                leaderboard,
                parse_mode="Markdown"
            )
        
        if len(room["answered"]) >= len(room["players"]):
            await asyncio.sleep(2)
            room["current_q"] += 1
            await send_multiplayer_question(room_code, context, room["current_q"])
        else:
            await context.bot.send_message(
                int(chat_id),
                f"⏳ Waiting for opponent to answer...",
                parse_mode="Markdown"
            )

async def handle_mp_short_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'mp_answer' not in context.user_data:
        return
    
    chat_id = str(update.effective_chat.id)
    answer_data = context.user_data['mp_answer']
    room_code = answer_data['room_code']
    q_index = answer_data['q_index']
    user_answer = update.message.text
    
    room = multiplayer_sessions.get(room_code)
    if not room:
        await update.message.reply_text("❌ Room expired!")
        return
    
    question = room["questions"][q_index]
    
    is_correct = user_answer.lower().strip() == question['answer'].lower().strip()
    
    if is_correct:
        emoji = random.choice(MULTIPLAYER_EMOJIS)
        room["emojis"][chat_id].append(emoji)
        room["scores"][chat_id] = room["scores"].get(chat_id, 0) + 1
        room["answered"][chat_id] = True
        
        feedback = f"✅ *Correct!* 🎉\n🏆 You earned: {emoji}"
    else:
        room["answered"][chat_id] = False
        feedback = f"❌ *Wrong!*\n✅ Correct answer: {question['answer']}\n\n{question.get('explanation', '')}"
    
    await update.message.reply_text(feedback, parse_mode="Markdown")
    
    leaderboard = await show_live_leaderboard(room_code, context, chat_id)
    if leaderboard:
        await context.bot.send_message(
            int(chat_id),
            leaderboard,
            parse_mode="Markdown"
        )
    
    context.user_data.pop('mp_answer', None)
    
    if len(room["answered"]) >= len(room["players"]):
        await asyncio.sleep(2)
        room["current_q"] += 1
        await send_multiplayer_question(room_code, context, room["current_q"])

async def end_multiplayer(room_code: str, context: ContextTypes.DEFAULT_TYPE):
    room = multiplayer_sessions.pop(room_code, None)
    if not room:
        return
    
    sorted_players = sorted(room["players"], key=lambda x: room["scores"].get(x, 0), reverse=True)
    
    results = "🏆 *MULTIPLAYER FINAL RESULTS* 🏆\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, player_id in enumerate(sorted_players[:3]):
        medal = medals[i] if i < 3 else f"{i+1}."
        score = room["scores"].get(player_id, 0)
        emoji_list = ' '.join(room["emojis"].get(player_id, []))
        results += f"{medal} Player {player_id[:6]}: {score} correct\n"
        results += f"   Emojis: {emoji_list}\n\n"
    
    winner_id = sorted_players[0]
    chat_id_str = str(winner_id)
    user_data[chat_id_str]["xp"] = user_data[chat_id_str].get("xp", 0) + MULTIPLAYER_BONUS
    save_json("user_data.json", user_data)
    
    results += f"🎉 Winner gets +{MULTIPLAYER_BONUS} XP bonus!"
    
    for player_id in room["players"]:
        try:
            await context.bot.send_message(
                int(player_id),
   
)
