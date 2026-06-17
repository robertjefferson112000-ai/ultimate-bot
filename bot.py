import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== CONFIGURATION =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    print("❌ Missing TELEGRAM_TOKEN!")
    exit(1)

# ===== SIMPLE START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ BOT IS WORKING!\n\n"
        "Your bot is alive and responding!\n"
        "Now we can slowly add features."
    )

# ===== SIMPLE HELP COMMAND =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Available commands:*\n"
        "/start - Test the bot\n"
        "/help - Show this message\n"
        "/ping - Check if bot is alive",
        parse_mode="Markdown"
    )

# ===== SIMPLE PING COMMAND =====
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 PONG! Bot is alive!")

# ===== MAIN =====
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    
    print("✅ SIMPLE BOT IS RUNNING!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
