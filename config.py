# -*- coding: utf-8 -*-
"""
Configuration file for Advanced Bot Hosting
"""

import os
from pathlib import Path

# =============================================================================
# BOT CONFIGURATION (Use environment variables for Render)
# =============================================================================
TOKEN = os.getenv("BOT_TOKEN", "8472500254:AAFYstP3ifectlNp2QJFXbkSoUzZPyD8k_s")
OWNER_ID = int(os.getenv("OWNER_ID", "7857957075"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "7857957075"))
YOUR_USERNAME = os.getenv("YOUR_USERNAME", "@mrseller_00")
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "https://t.me/gadgetpremiumzone")

# =============================================================================
# USER LIMITS
# =============================================================================
FREE_USER_FILE_LIMIT = int(os.getenv("FREE_USER_FILE_LIMIT", "5"))
FREE_USER_PROJECT_LIMIT = int(os.getenv("FREE_USER_PROJECT_LIMIT", "2"))
SUBSCRIBED_USER_FILE_LIMIT = int(os.getenv("SUBSCRIBED_USER_FILE_LIMIT", "20"))
SUBSCRIBED_USER_PROJECT_LIMIT = int(os.getenv("SUBSCRIBED_USER_PROJECT_LIMIT", "10"))
ADMIN_FILE_LIMIT = int(os.getenv("ADMIN_FILE_LIMIT", "100"))
ADMIN_PROJECT_LIMIT = int(os.getenv("ADMIN_PROJECT_LIMIT", "50"))
OWNER_FILE_LIMIT = 10**9
OWNER_PROJECT_LIMIT = 10**9

# =============================================================================
# UPLOAD & DISPLAY SETTINGS
# =============================================================================
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_FILE_VIEW_CHARS = 4000
LOG_TAIL_LINES = 80
PAGINATION_PAGE_SIZE = 7

# =============================================================================
# HOSTING SETTINGS
# =============================================================================
AUTO_RESTART_CHECK_INTERVAL = 3
AUTO_RESTART_BACKOFF_SEC = 3
WEB_SERVER_PORT = int(os.getenv("PORT", "5000"))  # Render uses PORT env var

# =============================================================================
# PATHS (Render compatible - use /tmp for writable storage)
# =============================================================================
BASE_DIR = Path(__file__).parent.absolute()

# Use /tmp for data on Render (ephemeral but writable)
if os.getenv("RENDER"):
    DATA_DIR = Path("/tmp/bot_data")
    USERS_DIR = Path("/tmp/user_projects")
    LOGS_DIR = Path("/tmp/logs")
else:
    DATA_DIR = BASE_DIR / "bot_data"
    USERS_DIR = BASE_DIR / "user_projects"
    LOGS_DIR = BASE_DIR / "logs"

DB_PATH = DATA_DIR / "hosting.db"

# Create directories
DATA_DIR.mkdir(exist_ok=True, parents=True)
USERS_DIR.mkdir(exist_ok=True, parents=True)
LOGS_DIR.mkdir(exist_ok=True, parents=True)

# =============================================================================
# TEMPLATES (keep same as before)
# =============================================================================
TEMPLATES = {
    "telegram_echo": {
        "title": "🤖 Telegram Echo Bot",
        "category": "Telegram Bots",
        "difficulty": "Easy",
        "description": "Simple echo bot that repeats messages",
        "entry": "main.py",
        "lang": "py",
        "auto_restart": 1,
        "files": {
            "main.py": """# Telegram Echo Bot
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Hello!</b>\\n\\n"
        "I'm an echo bot. Send me any text and I'll repeat it!",
        parse_mode="HTML"
    )

@dp.message(F.text)
async def echo_handler(message: types.Message):
    await message.answer(message.text)

async def main():
    print("🚀 Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
""",
            "requirements.txt": "aiogram>=3.4.1\n",
            "README.md": "# Echo Bot\\n\\nSimple Telegram bot that echoes messages.\\n"
        }
    },
    
    "telegram_menu": {
        "title": "📱 Telegram Menu Bot",
        "category": "Telegram Bots",
        "difficulty": "Medium",
        "description": "Bot with inline keyboard menu and FSM",
        "entry": "main.py",
        "lang": "py",
        "auto_restart": 1,
        "files": {
            "main.py": """# Telegram Menu Bot with FSM
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    name = State()
    age = State()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ About", callback_data="about")],
        [InlineKeyboardButton(text="📝 Register", callback_data="register")],
        [InlineKeyboardButton(text="❓ Help", callback_data="help")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "🎉 <b>Welcome to Menu Bot!</b>\\n\\n"
        "Choose an option from the menu:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "about")
async def about_callback(call: types.CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>About This Bot</b>\\n\\n"
        "This is a demo menu bot with FSM support.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "register")
async def register_callback(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.name)
    await call.message.edit_text("📝 Please send your name:")
    await call.answer()

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.age)
    await message.answer("📅 Now send your age:")

@dp.message(Form.age)
async def process_age(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await message.answer(
        f"✅ <b>Registration Complete!</b>\\n\\n"
        f"Name: {data['name']}\\n"
        f"Age: {message.text}",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "help")
async def help_callback(call: types.CallbackQuery):
    await call.message.edit_text(
        "❓ <b>Help</b>\\n\\n"
        "Use /start to open the menu.\\n"
        "Click buttons to navigate.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await call.answer()

async def main():
    print("🚀 Menu bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
""",
            "requirements.txt": "aiogram>=3.4.1\n",
            "README.md": "# Menu Bot\\n\\nTelegram bot with inline menus and FSM.\\n"
        }
    },
}

TEMPLATE_CATEGORIES = sorted(set(t["category"] for t in TEMPLATES.values()))