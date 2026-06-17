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
