# -*- coding: utf-8 -*-
"""
ADVANCED BOT HOSTING v2.0
Complete Professional Version
- Beautiful UI
- Code validation
- Manual package install
- Powerful admin panel
- All features working
"""

import asyncio
import os
import sys
import shutil
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile

# Import our modules
from config import *
from database import *
from hosting import *
from validators import *
from admin_panel import *

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("AdvancedHost")

# =============================================================================
# BOT INITIALIZATION
# =============================================================================
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize database
init_database()

# =============================================================================
# FSM STATES
# =============================================================================
class ProjectCreate(StatesGroup):
    name = State()
    description = State()

class ProjectSettings(StatesGroup):
    entry_file = State()
    language = State()
    auto_restart = State()

class FileUpload(StatesGroup):
    waiting_file = State()

class FileEdit(StatesGroup):
    edit_line = State()
    insert_line = State()
    delete_line = State()
    find_replace = State()
    rename = State()

class TemplateInstall(StatesGroup):
    project_name = State()

class PackageInstall(StatesGroup):
    package_name = State()

class AdminStates(StatesGroup):
    add_premium_id = State()
    add_premium_days = State()
    remove_premium_id = State()
    add_admin_id = State()
    remove_admin_id = State()
    ban_user_id = State()
    ban_reason = State()
    unban_user_id = State()
    broadcast_target = State()
    broadcast_message = State()
    user_search = State()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_bytes(bytes_num: int) -> str:
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def paginate(items: list, page: int, per_page: int = PAGINATION_PAGE_SIZE):
    """Paginate items"""
    page = max(1, page)
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], page, pages, total

def safe_filename(name: str) -> str:
    """Sanitize filename"""
    name = name.replace("\\", "/").split("/")[-1]
    return "".join(ch for ch in name if ch.isalnum() or ch in "._-()[] ").strip() or "file"

def get_file_type(filename: str) -> str:
    """Get file type from extension"""
    ext = Path(filename).suffix.lower()
    if ext == '.py':
        return 'py'
    elif ext == '.js':
        return 'js'
    elif ext in ['.txt', '.md', '.json', '.yml', '.yaml', '.toml']:
        return 'text'
    else:
        return 'other'

def get_user_limits(user_id: int) -> dict:
    """Get user limits based on role"""
    if user_id == OWNER_ID:
        return {
            'files': OWNER_FILE_LIMIT,
            'projects': OWNER_PROJECT_LIMIT,
            'upload_mb': 1000
        }
    elif is_admin(user_id):
        return {
            'files': ADMIN_FILE_LIMIT,
            'projects': ADMIN_PROJECT_LIMIT,
            'upload_mb': 200
        }
    elif is_premium(user_id):
        return {
            'files': SUBSCRIBED_USER_FILE_LIMIT,
            'projects': SUBSCRIBED_USER_PROJECT_LIMIT,
            'upload_mb': 100
        }
    else:
        return {
            'files': FREE_USER_FILE_LIMIT,
            'projects': FREE_USER_PROJECT_LIMIT,
            'upload_mb': MAX_UPLOAD_MB
        }

# =============================================================================
# KEYBOARD BUILDERS
# =============================================================================

def kb_main(user_id: int) -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    buttons = [
        [
            InlineKeyboardButton(text="🚀 New Project", callback_data="project_create"),
            InlineKeyboardButton(text="📦 My Projects", callback_data="projects")
        ],
        [
            InlineKeyboardButton(text="🛍️ Templates", callback_data="templates"),
            InlineKeyboardButton(text="📤 Upload File", callback_data="upload")
        ],
        [
            InlineKeyboardButton(text="⭐ Favorites", callback_data="favorites"),
            InlineKeyboardButton(text="📊 My Stats", callback_data="my_stats")
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="📢 Updates", url=UPDATE_CHANNEL)
        ]
    ]
    
    if is_admin(user_id):
        buttons.insert(3, [
            InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_back_home() -> InlineKeyboardMarkup:
    """Back to home button"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Home", callback_data="home")]
    ])

def kb_confirm(action_yes: str, action_no: str = "home") -> InlineKeyboardMarkup:
    """Confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=action_yes),
            InlineKeyboardButton(text="❌ No", callback_data=action_no)
        ]
    ])

def kb_projects_list(projects: list, page: int, pages: int) -> InlineKeyboardMarkup:
    """Projects list keyboard"""
    buttons = []
    
    for pid, name, entry, lang, auto_restart, desc in projects:
        status = "⚙️" if not entry else "✅"
        buttons.append([
            InlineKeyboardButton(text=f"{status} {name[:25]}", callback_data=f"project:{pid}"),
            InlineKeyboardButton(text="⚙️", callback_data=f"settings:{pid}")
        ])
    
    # Pagination
    nav = []
    if pages > 1:
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"projects_page:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"📄 {page}/{pages}", callback_data="noop"))
        if page < pages:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"projects_page:{page+1}"))
        buttons.append(nav)
    
    buttons.append([
        InlineKeyboardButton(text="➕ Create New", callback_data="project_create")
    ])
    buttons.append([
        InlineKeyboardButton(text="🏠 Home", callback_data="home")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_project_menu(pid: int, user_id: int) -> InlineKeyboardMarkup:
    """Project menu keyboard"""
    key = make_key(user_id, pid)
    is_running = key in running_processes and running_processes[key].process.poll() is None
    
    buttons = [
        [
            InlineKeyboardButton(text="📁 Files", callback_data=f"files:{pid}:1"),
            InlineKeyboardButton(text="🎮 Control", callback_data=f"control:{pid}")
        ],
        [
            InlineKeyboardButton(text="📦 Install Deps", callback_data=f"install_deps:{pid}"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data=f"settings:{pid}")
        ]
    ]
    
    if is_running:
        buttons.append([
            InlineKeyboardButton(text="📊 Stats", callback_data=f"stats:{pid}"),
            InlineKeyboardButton(text="📝 Logs", callback_data=f"logs:{pid}")
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton(text="📦 Export ZIP", callback_data=f"export:{pid}"),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete_ask:{pid}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="projects")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_control_panel(pid: int, user_id: int) -> InlineKeyboardMarkup:
    """Control panel keyboard"""
    key = make_key(user_id, pid)
    is_running = key in running_processes and running_processes[key].process.poll() is None
    
    buttons = []
    
    if is_running:
        buttons.append([
            InlineKeyboardButton(text="🛑 Stop", callback_data=f"stop:{pid}"),
            InlineKeyboardButton(text="🔄 Restart", callback_data=f"restart:{pid}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="▶️ Start", callback_data=f"start:{pid}")
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton(text="📝 View Logs", callback_data=f"logs:{pid}"),
            InlineKeyboardButton(text="📊 Statistics", callback_data=f"stats:{pid}")
        ],
        [
            InlineKeyboardButton(text="⬇️ Download Logs", callback_data=f"download_logs:{pid}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_files_list(pid: int, files: list, page: int, pages: int) -> InlineKeyboardMarkup:
    """Files list keyboard"""
    buttons = []
    
    for fname, ftype, fsize, upload_date in files:
        icon = "🐍" if ftype == "py" else "🟨" if ftype == "js" else "📄"
        size_str = format_bytes(fsize)
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {fname[:20]} ({size_str})", callback_data=f"file:{pid}:{fname}"),
            InlineKeyboardButton(text="⭐", callback_data=f"fav:{pid}:{fname}")
        ])
    
    # Pagination
    nav = []
    if pages > 1:
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"files:{pid}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"📄 {page}/{pages}", callback_data="noop"))
        if page < pages:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"files:{pid}:{page+1}"))
        buttons.append(nav)
    
    buttons.extend([
        [
            InlineKeyboardButton(text="📤 Upload File", callback_data=f"upload_to:{pid}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_file_menu(pid: int, fname: str) -> InlineKeyboardMarkup:
    """File menu keyboard"""
    buttons = [
        [
            InlineKeyboardButton(text="👁️ View", callback_data=f"view:{pid}:{fname}"),
            InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit_menu:{pid}:{fname}")
        ],
        [
            InlineKeyboardButton(text="⬇️ Download", callback_data=f"download:{pid}:{fname}"),
            InlineKeyboardButton(text="📝 Rename", callback_data=f"rename_ask:{pid}:{fname}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete_file_ask:{pid}:{fname}")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data=f"files:{pid}:1")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_admin_panel() -> InlineKeyboardMarkup:
    """Admin panel keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users"),
            InlineKeyboardButton(text="📊 Analytics", callback_data="admin_analytics")
        ],
        [
            InlineKeyboardButton(text="🚀 Running Bots", callback_data="admin_running"),
            InlineKeyboardButton(text="📦 All Projects", callback_data="admin_projects")
        ],
        [
            InlineKeyboardButton(text="💎 Manage Premium", callback_data="admin_premium"),
            InlineKeyboardButton(text="👑 Manage Admins", callback_data="admin_admins")
        ],
        [
            InlineKeyboardButton(text="🚫 Ban/Unban", callback_data="admin_ban"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton(text="🏠 Home", callback_data="home")
        ]
    ])

# =============================================================================
# UI TEXT GENERATORS
# =============================================================================

def ui_home_text(user: types.User) -> str:
    """Generate beautiful home screen text"""
    stats = get_user_stats(user.id)
    limits = get_user_limits(user.id)
    
    # Status badge
    if user.id == OWNER_ID:
        badge = "👑 <b>OWNER</b>"
    elif stats['is_admin']:
        badge = "👑 <b>ADMIN</b>"
    elif stats['is_premium']:
        badge = "💎 <b>PREMIUM</b>"
    else:
        badge = "🆓 <b>FREE</b>"
    
    return f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   ✨ <b>ADVANCED BOT HOSTING</b> ✨
┃   <i>Professional Cloud Platform</i>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛

👤 <b>User Profile</b>
├ Name: <b>{user.full_name}</b>
├ ID: <code>{user.id}</code>
├ Status: {badge}
└ Member Since: <code>{stats['join_date'][:10] if stats['join_date'] else 'Unknown'}</code>

📊 <b>Your Statistics</b>
├ 📦 Projects: <b>{stats['project_count']}/{limits['projects']}</b>
├ 📁 Files: <b>{stats['file_count']}/{limits['files']}</b>
└ 💾 Upload Limit: <b>{limits['upload_mb']} MB</b>

⚡ <b>Quick Actions</b>
• Create new project from scratch
• Install ready-made templates
• Upload and manage files
• Monitor running bots

💡 <i>Tip: Use templates for instant deployment!</i>
"""

# =============================================================================
# COMMAND HANDLERS
# =============================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start command"""
    ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    if is_banned(message.from_user.id):
        await message.answer(
            "🚫 <b>Account Banned</b>\n\n"
            "Your account has been banned from using this bot.\n"
            f"Contact admin: {YOUR_USERNAME}",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        ui_home_text(message.from_user),
        reply_markup=kb_main(message.from_user.id),
        parse_mode="HTML"
    )

@dp.message(Command("install"))
async def cmd_install(message: types.Message, command: CommandObject):
    """Install package command"""
    ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    if is_banned(message.from_user.id):
        return
    
    # Get active project
    stats = get_user_stats(message.from_user.id)
    active_pid = stats['active_project_id']
    
    if not active_pid:
        await message.answer(
            "❌ <b>No Active Project</b>\n\n"
            "Please select a project first using /projects",
            parse_mode="HTML"
        )
        return
    
    # Check if package name provided
    if not command.args:
        await message.answer(
            "📦 <b>Manual Package Install</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/install package_name</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/install aiogram</code>\n"
            "• <code>/install requests</code>\n"
            "• <code>/install beautifulsoup4</code>\n\n"
            "💡 This will install the package in your active project's virtual environment.",
            parse_mode="HTML"
        )
        return
    
    package_name = command.args.strip()
    
    status_msg = await message.answer(
        f"⏳ Installing <code>{package_name}</code>...\n\n"
        "This may take a minute...",
        parse_mode="HTML"
    )
    
    # Install package
    success, msg = install_package(message.from_user.id, active_pid, package_name)
    
    if success:
        await status_msg.edit_text(
            f"✅ <b>Installation Complete!</b>\n\n"
            f"{msg}\n\n"
            f"📦 Project ID: <code>{active_pid}</code>",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"❌ <b>Installation Failed</b>\n\n"
            f"{msg}",
            parse_mode="HTML"
        )

@dp.message(Command("userinfo"))
async def cmd_userinfo(message: types.Message, command: CommandObject):
    """User info command"""
    if not is_admin(message.from_user.id):
        return
    
    if not command.args:
        await message.answer(
            "Usage: <code>/userinfo USER_ID</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(command.args)
    except:
        await message.answer("Invalid user ID")
        return
    
    stats = get_user_stats(user_id)
    
    status_badges = []
    if stats['is_admin']:
        status_badges.append("👑 Admin")
    if stats['is_premium']:
        status_badges.append("💎 Premium")
    if stats['is_banned']:
        status_badges.append("🚫 Banned")
    
    status_text = " | ".join(status_badges) if status_badges else "🆓 Regular User"
    
    text = f"""
<b>👤 User Information</b>

🆔 ID: <code>{user_id}</code>
📊 Status: {status_text}

📦 Projects: <b>{stats['project_count']}</b>
📁 Files: <b>{stats['file_count']}</b>
📅 Joined: <code>{stats['join_date'][:16] if stats['join_date'] else 'Unknown'}</code>
🕒 Last Active: <code>{stats['last_active'][:16] if stats['last_active'] else 'Unknown'}</code>
"""
    
    await message.answer(text, parse_mode="HTML")

# =============================================================================
# CALLBACK HANDLERS - HOME & NAVIGATION
# =============================================================================

@dp.callback_query(F.data == "home")
async def cb_home(call: types.CallbackQuery):
    """Home button"""
    ensure_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
    
    await call.message.edit_text(
        ui_home_text(call.from_user),
        reply_markup=kb_main(call.from_user.id),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "noop")
async def cb_noop(call: types.CallbackQuery):
    """No operation"""
    await call.answer()

@dp.callback_query(F.data == "help")
async def cb_help(call: types.CallbackQuery):
    """Help screen"""
    text = """
<b>❓ Help & Guide</b>

<b>🚀 Getting Started:</b>
1. Create a new project or install a template
2. Upload your bot files
3. Install dependencies (requirements.txt)
4. Set entry file in Settings
5. Start your bot!

<b>📦 Projects:</b>
• Create unlimited projects (based on your plan)
• Each project has isolated environment
• Auto-restart on crash (optional)

<b>📤 File Upload:</b>
• Upload .py, .js, and other files
• Automatic syntax validation
• Detects missing dependencies

<b>🛍️ Templates:</b>
• Ready-made bot templates
• One-click installation
• Fully customizable

<b>🎛️ Control Panel:</b>
• Start/Stop/Restart bots
• View real-time logs
• Monitor CPU/RAM usage
• Download logs

<b>📦 Dependencies:</b>
• Use /install command for manual install
• Or create requirements.txt and click Install Deps

<b>⚙️ Settings:</b>
• Set entry file (main.py, bot.py, etc)
• Choose language (Python/Node.js)
• Enable auto-restart

<b>💎 Premium Features:</b>
• More projects and files
• Larger upload limits
• Priority support

<b>Commands:</b>
• /start - Home screen
• /install package_name - Install package
• /userinfo USER_ID - User info (admin only)

Need help? Contact: """ + YOUR_USERNAME
    
    await call.message.edit_text(
        text,
        reply_markup=kb_back_home(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "my_stats")
async def cb_my_stats(call: types.CallbackQuery):
    """User statistics"""
    stats = get_user_stats(call.from_user.id)
    limits = get_user_limits(call.from_user.id)
    all_stats = get_all_stats()
    
    # Count running bots
    running_count = sum(1 for k in running_processes.keys() 
                       if k.startswith(f"{call.from_user.id}:"))
    
    text = f"""
<b>📊 Your Statistics</b>

<b>👤 Account Info:</b>
├ User ID: <code>{call.from_user.id}</code>
├ Status: {'💎 Premium' if stats['is_premium'] else '🆓 Free'}
└ Joined: <code>{stats['join_date'][:10] if stats['join_date'] else 'Unknown'}</code>

<b>📦 Projects & Files:</b>
├ Projects: <b>{stats['project_count']}/{limits['projects']}</b>
├ Files: <b>{stats['file_count']}/{limits['files']}</b>
└ Running Now: <b>{running_count}</b>

<b>🌐 Global Statistics:</b>
├ Total Uploads: <b>{all_stats.get('total_uploads', 0)}</b>
├ Total Runs: <b>{all_stats.get('total_runs', 0)}</b>
├ Total Downloads: <b>{all_stats.get('total_downloads', 0)}</b>
└ Template Installs: <b>{all_stats.get('total_template_installs', 0)}</b>
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_back_home(),
        parse_mode="HTML"
    )
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - PROJECTS
# =============================================================================

@dp.callback_query(F.data == "projects")
async def cb_projects(call: types.CallbackQuery):
    """Projects list"""
    projects = list_projects(call.from_user.id)
    
    if not projects:
        text = """
<b>📦 Your Projects</b>

You don't have any projects yet.

<b>Get Started:</b>
• Create a new project from scratch
• Install a ready-made template
• Upload a ZIP file

💡 Templates are the fastest way to get started!
"""
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Create Project", callback_data="project_create")],
                [InlineKeyboardButton(text="🛍️ Browse Templates", callback_data="templates")],
                [InlineKeyboardButton(text="🏠 Home", callback_data="home")]
            ]),
            parse_mode="HTML"
        )
    else:
        page_items, page, pages, total = paginate(projects, 1)
        
        text = f"""
<b>📦 Your Projects</b>

Total: <b>{total}</b> projects
Page: <b>{page}/{pages}</b>

Select a project to manage:
"""
        
        await call.message.edit_text(
            text,
            reply_markup=kb_projects_list(page_items, page, pages),
            parse_mode="HTML"
        )
    
    await call.answer()

@dp.callback_query(F.data.startswith("projects_page:"))
async def cb_projects_page(call: types.CallbackQuery):
    """Projects pagination"""
    page = int(call.data.split(":")[1])
    projects = list_projects(call.from_user.id)
    page_items, page, pages, total = paginate(projects, page)
    
    text = f"""
<b>📦 Your Projects</b>

Total: <b>{total}</b> projects
Page: <b>{page}/{pages}</b>

Select a project to manage:
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_projects_list(page_items, page, pages),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "project_create")
async def cb_project_create(call: types.CallbackQuery, state: FSMContext):
    """Start project creation"""
    limits = get_user_limits(call.from_user.id)
    stats = get_user_stats(call.from_user.id)
    
    if stats['project_count'] >= limits['projects']:
        await call.answer(
            f"❌ Project limit reached ({limits['projects']})\n"
            "Delete old projects or upgrade to Premium",
            show_alert=True
        )
        return
    
    await state.set_state(ProjectCreate.name)
    await call.message.edit_text(
        "<b>➕ Create New Project</b>\n\n"
        "Send the project name:\n\n"
        "<b>Example:</b>\n"
        "• <code>MyTelegramBot</code>\n"
        "• <code>WebApp_v2</code>\n"
        "• <code>DataScraper</code>\n\n"
        "💡 Use a descriptive name",
        parse_mode="HTML",
        reply_markup=kb_back_home()
    )
    await call.answer()

@dp.message(ProjectCreate.name)
async def fsm_project_name(message: types.Message, state: FSMContext):
    """Handle project name"""
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Name too short. Please send again:")
        return
    
    if len(name) > 50:
        await message.answer("❌ Name too long (max 50 chars). Please send again:")
        return
    
    # Store name and ask for description
    await state.update_data(name=name)
    await state.set_state(ProjectCreate.description)
    
    await message.answer(
        f"<b>Project Name:</b> <code>{name}</code> ✅\n\n"
        "Now send a short description (optional):\n\n"
        "Or send <code>/skip</code> to skip",
        parse_mode="HTML"
    )

@dp.message(ProjectCreate.description)
async def fsm_project_description(message: types.Message, state: FSMContext):
    """Handle project description"""
    description = message.text.strip() if message.text != "/skip" else ""
    
    # Get stored name
    data = await state.get_data()
    name = data['name']
    
    # Create project
    try:
        pid = create_project(message.from_user.id, name, description)
        
        # Create README
        project_root = get_project_root(message.from_user.id, pid)
        readme = project_root / "README.md"
        readme.write_text(
            f"# {name}\n\n"
            f"{description}\n\n"
            "## Getting Started\n\n"
            "1. Upload your files\n"
            "2. Set entry file in Settings\n"
            "3. Install dependencies\n"
            "4. Start your bot!\n",
            encoding='utf-8'
        )
        
        add_file(message.from_user.id, pid, "README.md", "text", readme.stat().st_size)
        
        await state.clear()
        
        await message.answer(
            f"✅ <b>Project Created!</b>\n\n"
            f"📦 Name: <b>{name}</b>\n"
            f"🆔 Project ID: <code>{pid}</code>\n\n"
            f"<b>Next Steps:</b>\n"
            "1. Upload your files\n"
            "2. Configure settings\n"
            "3. Install dependencies\n"
            "4. Start your project!",
            parse_mode="HTML",
            reply_markup=kb_project_menu(pid, message.from_user.id)
        )
    
    except Exception as e:
        await message.answer(
            f"❌ <b>Error:</b>\n{str(e)}\n\n"
            "Project name might already exist.",
            parse_mode="HTML"
        )
        await state.clear()

@dp.callback_query(F.data.startswith("project:"))
async def cb_project_open(call: types.CallbackQuery):
    """Open project menu"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    _, name, entry, lang, auto_restart, desc, created = project
    
    # Get file count
    files = list_files(call.from_user.id, pid)
    file_count = len(files)
    
    # Check if running
    key = make_key(call.from_user.id, pid)
    is_running = key in running_processes and running_processes[key].process.poll() is None
    status = "🟢 Running" if is_running else "🔴 Stopped"
    
    # Get total size
    total_size = sum(f[2] for f in files)
    
    text = f"""
<b>📦 Project: {name}</b>

<b>Status:</b> {status}
<b>Files:</b> {file_count}
<b>Size:</b> {format_bytes(total_size)}
<b>Created:</b> {created[:10] if created else 'Unknown'}

<b>Configuration:</b>
├ Entry: <code>{entry or 'Not set'}</code>
├ Language: <b>{lang.upper() if lang else 'Not set'}</b>
└ Auto-restart: <b>{'ON' if auto_restart else 'OFF'}</b>

{f'<i>{desc}</i>' if desc else ''}
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_project_menu(pid, call.from_user.id),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("delete_ask:"))
async def cb_delete_ask(call: types.CallbackQuery):
    """Ask for delete confirmation"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    name = project[1]
    
    await call.message.edit_text(
        f"<b>⚠️ Delete Project?</b>\n\n"
        f"Project: <b>{name}</b>\n"
        f"ID: <code>{pid}</code>\n\n"
        f"<b>This will delete:</b>\n"
        f"• All files\n"
        f"• All settings\n"
        f"• All logs\n\n"
        f"<b>This action cannot be undone!</b>",
        parse_mode="HTML",
        reply_markup=kb_confirm(f"delete_confirm:{pid}", f"project:{pid}")
    )
    await call.answer()

@dp.callback_query(F.data.startswith("delete_confirm:"))
async def cb_delete_confirm(call: types.CallbackQuery):
    """Confirm project deletion"""
    pid = int(call.data.split(":")[1])
    
    # Stop if running
    key = make_key(call.from_user.id, pid)
    if key in running_processes:
        stop_process(call.from_user.id, pid)
    
    # Delete from filesystem
    project_root = get_project_root(call.from_user.id, pid)
    if project_root.exists():
        shutil.rmtree(project_root, ignore_errors=True)
    
    # Delete from database
    delete_project(call.from_user.id, pid)
    
    await call.message.edit_text(
        "✅ <b>Project Deleted</b>\n\n"
        "The project and all its files have been removed.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 My Projects", callback_data="projects")],
            [InlineKeyboardButton(text="🏠 Home", callback_data="home")]
        ])
    )
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - SETTINGS
# =============================================================================

@dp.callback_query(F.data.startswith("settings:"))
async def cb_settings(call: types.CallbackQuery):
    """Project settings"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    _, name, entry, lang, auto_restart, desc, _ = project
    
    # List available files
    files = list_files(call.from_user.id, pid)
    py_files = [f[0] for f in files if f[1] == 'py']
    js_files = [f[0] for f in files if f[1] == 'js']
    
    text = f"""
<b>⚙️ Project Settings</b>

<b>Project:</b> {name}
<b>ID:</b> <code>{pid}</code>

<b>Current Configuration:</b>
├ Entry File: <code>{entry or 'Not set'}</code>
├ Language: <b>{lang.upper() if lang else 'Not set'}</b>
└ Auto-restart: <b>{'✅ Enabled' if auto_restart else '❌ Disabled'}</b>

<b>Available Files:</b>
"""
    
    if py_files:
        text += f"\n🐍 Python: {', '.join(py_files[:5])}"
    if js_files:
        text += f"\n🟨 JavaScript: {', '.join(js_files[:5])}"
    
    if not py_files and not js_files:
        text += "\n<i>No code files uploaded yet</i>"
    
    text += "\n\n💡 Click a button below to configure:"
    
    buttons = [
        [InlineKeyboardButton(text="📝 Set Entry File", callback_data=f"set_entry:{pid}")],
        [InlineKeyboardButton(text="🔄 Toggle Auto-restart", callback_data=f"toggle_restart:{pid}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")]
    ]
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("set_entry:"))
async def cb_set_entry(call: types.CallbackQuery, state: FSMContext):
    """Set entry file"""
    pid = int(call.data.split(":")[1])
    
    # List code files
    files = list_files(call.from_user.id, pid)
    code_files = [f for f in files if f[1] in ['py', 'js']]
    
    if not code_files:
        await call.answer(
            "❌ No code files found!\nUpload .py or .js files first.",
            show_alert=True
        )
        return
    
    await state.update_data(project_id=pid)
    await state.set_state(ProjectSettings.entry_file)
    
    files_list = "\n".join([f"• <code>{f[0]}</code> ({f[1].upper()})" for f in code_files])
    
    await call.message.edit_text(
        f"<b>📝 Set Entry File</b>\n\n"
        f"<b>Available files:</b>\n{files_list}\n\n"
        f"Send the filename:\n"
        f"Example: <code>main.py</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data=f"settings:{pid}")]
        ])
    )
    await call.answer()

@dp.message(ProjectSettings.entry_file)
async def fsm_set_entry(message: types.Message, state: FSMContext):
    """Handle entry file input"""
    data = await state.get_data()
    pid = data['project_id']
    entry = message.text.strip()
    
    # Check if file exists
    files = list_files(message.from_user.id, pid)
    file_exists = any(f[0] == entry for f in files)
    
    if not file_exists:
        await message.answer(
            f"❌ File <code>{entry}</code> not found.\n"
            "Please send a valid filename:",
            parse_mode="HTML"
        )
        return
    
    # Determine language
    lang = get_file_type(entry)
    if lang not in ['py', 'js']:
        await message.answer(
            "❌ File must be .py or .js\n"
            "Please send again:"
        )
        return
    
    # Update settings
    project = get_project(message.from_user.id, pid)
    auto_restart = project[4] if project else 0
    
    update_project_settings(message.from_user.id, pid, entry, lang, auto_restart)
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Entry File Set!</b>\n\n"
        f"File: <code>{entry}</code>\n"
        f"Language: <b>{lang.upper()}</b>\n\n"
        f"You can now start your project!",
        parse_mode="HTML",
        reply_markup=kb_project_menu(pid, message.from_user.id)
    )

@dp.callback_query(F.data.startswith("toggle_restart:"))
async def cb_toggle_restart(call: types.CallbackQuery):
    """Toggle auto-restart"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    _, name, entry, lang, auto_restart, _, _ = project
    
    # Toggle
    new_value = 0 if auto_restart else 1
    update_project_settings(call.from_user.id, pid, entry, lang, new_value)
    
    await call.answer(
        f"✅ Auto-restart {'enabled' if new_value else 'disabled'}",
        show_alert=True
    )
    
    # Refresh settings page
    await cb_settings(call)

# =============================================================================
# CALLBACK HANDLERS - FILES
# =============================================================================

@dp.callback_query(F.data.startswith("files:"))
async def cb_files(call: types.CallbackQuery):
    """Files list"""
    parts = call.data.split(":")
    pid = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 1
    
    files = list_files(call.from_user.id, pid)
    
    if not files:
        project = get_project(call.from_user.id, pid)
        name = project[1] if project else "Unknown"
        
        await call.message.edit_text(
            f"<b>📁 Files: {name}</b>\n\n"
            f"No files uploaded yet.\n\n"
            f"Click the button below to upload files.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📤 Upload File", callback_data=f"upload_to:{pid}")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")]
            ])
        )
    else:
        page_items, page, pages, total = paginate(files, page)
        
        project = get_project(call.from_user.id, pid)
        name = project[1] if project else "Unknown"
        
        total_size = sum(f[2] for f in files)
        
        text = f"""
<b>📁 Files: {name}</b>

Total: <b>{total}</b> files ({format_bytes(total_size)})
Page: <b>{page}/{pages}</b>

Select a file to manage:
"""
        
        await call.message.edit_text(
            text,
            reply_markup=kb_files_list(pid, page_items, page, pages),
            parse_mode="HTML"
        )
    
    await call.answer()

@dp.callback_query(F.data.startswith("file:"))
async def cb_file_open(call: types.CallbackQuery):
    """Open file menu"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    project_root = get_project_root(call.from_user.id, pid)
    file_path = project_root / fname
    
    if not file_path.exists():
        await call.answer("❌ File not found", show_alert=True)
        return
    
    # Get file info
    size = file_path.stat().st_size
    ftype = get_file_type(fname)
    
    text = f"""
<b>📄 File Details</b>

<b>Name:</b> <code>{fname}</code>
<b>Type:</b> {ftype.upper()}
<b>Size:</b> {format_bytes(size)}

Select an action:
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_file_menu(pid, fname),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("view:"))
async def cb_view_file(call: types.CallbackQuery):
    """View file contents"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    project_root = get_project_root(call.from_user.id, pid)
    file_path = project_root / fname
    
    if not file_path.exists():
        await call.answer("❌ File not found", show_alert=True)
        return
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
        
        # Truncate if too long
        if len(content) > MAX_FILE_VIEW_CHARS:
            content = content[:MAX_FILE_VIEW_CHARS] + "\n\n... (truncated)"
        
        text = f"<b>📄 {fname}</b>\n\n<pre>{content}</pre>"
        
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"file:{pid}:{fname}")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.answer(f"❌ Error reading file: {e}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data.startswith("download:"))
async def cb_download_file(call: types.CallbackQuery):
    """Download file"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    project_root = get_project_root(call.from_user.id, pid)
    file_path = project_root / fname
    
    if not file_path.exists():
        await call.answer("❌ File not found", show_alert=True)
        return
    
    await call.answer("⏳ Preparing download...", show_alert=False)
    
    try:
        # Send file
        await call.message.answer_document(
            FSInputFile(file_path, filename=fname),
            caption=f"📥 <b>{fname}</b>",
            parse_mode="HTML"
        )
        
        stat_increment('total_downloads')
    except Exception as e:
        await call.message.answer(f"❌ Download failed: {e}")
    
    await call.answer()

@dp.callback_query(F.data.startswith("delete_file_ask:"))
async def cb_delete_file_ask(call: types.CallbackQuery):
    """Ask to delete file"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    await call.message.edit_text(
        f"<b>⚠️ Delete File?</b>\n\n"
        f"File: <code>{fname}</code>\n\n"
        f"This action cannot be undone!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes", callback_data=f"delete_file_confirm:{pid}:{fname}"),
                InlineKeyboardButton(text="❌ No", callback_data=f"file:{pid}:{fname}")
            ]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("delete_file_confirm:"))
async def cb_delete_file_confirm(call: types.CallbackQuery):
    """Confirm file deletion"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    project_root = get_project_root(call.from_user.id, pid)
    file_path = project_root / fname
    
    if file_path.exists():
        file_path.unlink()
    
    remove_file(call.from_user.id, pid, fname)
    
    await call.message.edit_text(
        f"✅ <b>File Deleted</b>\n\n"
        f"<code>{fname}</code> has been removed.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📁 Back to Files", callback_data=f"files:{pid}:1")]
        ])
    )
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - UPLOAD
# =============================================================================

@dp.callback_query(F.data == "upload")
async def cb_upload(call: types.CallbackQuery):
    """Upload file (no project selected)"""
    stats = get_user_stats(call.from_user.id)
    active_pid = stats['active_project_id']
    
    if not active_pid:
        projects = list_projects(call.from_user.id)
        if not projects:
            await call.answer(
                "❌ Create a project first!",
                show_alert=True
            )
            return
        
        # Show project selection
        buttons = []
        for pid, name, _, _, _, _ in projects[:10]:
            buttons.append([
                InlineKeyboardButton(text=f"📦 {name}", callback_data=f"upload_to:{pid}")
            ])
        buttons.append([InlineKeyboardButton(text="🏠 Home", callback_data="home")])
        
        await call.message.edit_text(
            "<b>📤 Upload File</b>\n\n"
            "Select a project to upload to:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    else:
        # Upload to active project
        await cb_upload_to(call)
    
    await call.answer()

@dp.callback_query(F.data.startswith("upload_to:"))
async def cb_upload_to(call: types.CallbackQuery, state: FSMContext):
    """Start upload to specific project"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    name = project[1]
    limits = get_user_limits(call.from_user.id)
    
    await state.update_data(project_id=pid)
    await state.set_state(FileUpload.waiting_file)
    
    await call.message.edit_text(
        f"<b>📤 Upload File</b>\n\n"
        f"<b>Project:</b> {name}\n"
        f"<b>Max Size:</b> {limits['upload_mb']} MB\n\n"
        f"<b>Send your file now:</b>\n"
        f"• Python files (.py)\n"
        f"• JavaScript files (.js)\n"
        f"• Configuration files\n"
        f"• ZIP archives\n\n"
        f"💡 Code files will be validated automatically!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data=f"project:{pid}")]
        ])
    )
    await call.answer()

@dp.message(FileUpload.waiting_file, F.document)
async def handle_file_upload(message: types.Message, state: FSMContext):
    """Handle uploaded file"""
    data = await state.get_data()
    pid = data['project_id']
    
    doc = message.document
    limits = get_user_limits(message.from_user.id)
    
    # Check size
    if doc.file_size > limits['upload_mb'] * 1024 * 1024:
        await message.answer(
            f"❌ File too large!\n"
            f"Max: {limits['upload_mb']} MB\n"
            f"Your file: {format_bytes(doc.file_size)}"
        )
        return
    
    # Check file limit
    file_count = count_user_files(message.from_user.id)
    if file_count >= limits['files']:
        await message.answer(
            f"❌ File limit reached ({limits['files']})\n"
            "Delete old files or upgrade to Premium"
        )
        return
    
    fname = safe_filename(doc.file_name)
    project_root = get_project_root(message.from_user.id, pid)
    file_path = project_root / fname
    
    # Download file
    status_msg = await message.answer("⏳ Uploading...")
    
    try:
        await bot.download(doc, file_path)
        
        # Validate if code file
        ftype = get_file_type(fname)
        
        if ftype in ['py', 'js']:
            await status_msg.edit_text("🔍 Validating code...")
            
            is_valid, validation_msg = validate_file_on_upload(file_path, ftype)
            
            if not is_valid:
                # File has errors
                await status_msg.delete()
                await message.answer(
                    validation_msg,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🗑️ Delete File", callback_data=f"delete_file_confirm:{pid}:{fname}")],
                        [InlineKeyboardButton(text="📁 Keep Anyway", callback_data=f"files:{pid}:1")]
                    ])
                )
            else:
                # File is valid
                await status_msg.edit_text(
                    validation_msg,
                    parse_mode="HTML",
                    reply_markup=kb_file_menu(pid, fname)
                )
        else:
            # Non-code file
            await status_msg.edit_text(
                f"✅ <b>Upload Complete!</b>\n\n"
                f"File: <code>{fname}</code>\n"
                f"Size: {format_bytes(doc.file_size)}",
                parse_mode="HTML",
                reply_markup=kb_file_menu(pid, fname)
            )
        
        # Add to database
        add_file(message.from_user.id, pid, fname, ftype, doc.file_size)
        stat_increment('total_uploads')
        
        await state.clear()
    
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload failed: {e}")
        if file_path.exists():
            file_path.unlink()
        await state.clear()

# Continue in next part...

# =============================================================================
# CALLBACK HANDLERS - CONTROL PANEL
# =============================================================================

@dp.callback_query(F.data.startswith("control:"))
async def cb_control(call: types.CallbackQuery):
    """Control panel"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    _, name, entry, lang, auto_restart, _, _ = project
    
    # Check status
    key = make_key(call.from_user.id, pid)
    is_running = key in running_processes and running_processes[key].process.poll() is None
    
    if is_running:
        stats = get_process_stats(call.from_user.id, pid)
        if stats:
            status_text = f"""
<b>Status:</b> {stats['status']}
<b>PID:</b> <code>{stats['pid']}</code>
<b>CPU:</b> {stats['cpu']}
<b>Memory:</b> {stats['memory']}
<b>Uptime:</b> {stats['uptime']}
<b>Restarts:</b> {stats['restarts']}
"""
        else:
            status_text = "<b>Status:</b> 🟢 Running"
    else:
        status_text = "<b>Status:</b> 🔴 Stopped"
    
    text = f"""
<b>🎮 Control Panel</b>

<b>Project:</b> {name}
<b>ID:</b> <code>{pid}</code>

{status_text}

<b>Configuration:</b>
├ Entry: <code>{entry or 'Not set'}</code>
├ Language: <b>{lang.upper() if lang else 'Not set'}</b>
└ Auto-restart: <b>{'ON' if auto_restart else 'OFF'}</b>
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_control_panel(pid, call.from_user.id),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("start:"))
async def cb_start_bot(call: types.CallbackQuery):
    """Start bot"""
    pid = int(call.data.split(":")[1])
    
    await call.answer("⏳ Starting...", show_alert=False)
    
    success, msg = start_process(call.from_user.id, pid)
    
    if success:
        await call.message.edit_text(
            msg,
            parse_mode="HTML",
            reply_markup=kb_control_panel(pid, call.from_user.id)
        )
    else:
        await call.message.answer(msg, parse_mode="HTML")
        await cb_control(call)

@dp.callback_query(F.data.startswith("stop:"))
async def cb_stop_bot(call: types.CallbackQuery):
    """Stop bot"""
    pid = int(call.data.split(":")[1])
    
    await call.answer("⏳ Stopping...", show_alert=False)
    
    success, msg = stop_process(call.from_user.id, pid)
    
    await call.answer(msg, show_alert=True)
    await cb_control(call)

@dp.callback_query(F.data.startswith("restart:"))
async def cb_restart_bot(call: types.CallbackQuery):
    """Restart bot"""
    pid = int(call.data.split(":")[1])
    
    await call.answer("⏳ Restarting...", show_alert=False)
    
    success, msg = restart_process(call.from_user.id, pid)
    
    if success:
        await call.answer("✅ Restarted successfully", show_alert=True)
    else:
        await call.answer(f"❌ {msg}", show_alert=True)
    
    await cb_control(call)

@dp.callback_query(F.data.startswith("stats:"))
async def cb_stats(call: types.CallbackQuery):
    """Show detailed statistics"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    _, name, entry, lang, auto_restart, _, created = project
    
    # Get stats
    key = make_key(call.from_user.id, pid)
    is_running = key in running_processes and running_processes[key].process.poll() is None
    
    text = f"""
<b>📊 Project Statistics</b>

<b>Project:</b> {name}
<b>ID:</b> <code>{pid}</code>
<b>Created:</b> {created[:16] if created else 'Unknown'}

"""
    
    if is_running:
        stats = get_process_stats(call.from_user.id, pid)
        if stats:
            text += f"""
<b>Runtime Status:</b>
├ Status: {stats['status']}
├ PID: <code>{stats['pid']}</code>
├ CPU Usage: <b>{stats['cpu']}</b>
├ Memory: <b>{stats['memory']}</b>
├ Uptime: <b>{stats['uptime']}</b>
└ Restarts: <b>{stats['restarts']}</b>
"""
    else:
        text += "<b>Status:</b> 🔴 Not running"
    
    # File statistics
    files = list_files(call.from_user.id, pid)
    total_size = sum(f[2] for f in files)
    py_count = sum(1 for f in files if f[1] == 'py')
    js_count = sum(1 for f in files if f[1] == 'js')
    
    text += f"""

<b>File Statistics:</b>
├ Total Files: <b>{len(files)}</b>
├ Python Files: <b>{py_count}</b>
├ JavaScript Files: <b>{js_count}</b>
└ Total Size: <b>{format_bytes(total_size)}</b>
"""
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"stats:{pid}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"control:{pid}")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("logs:"))
async def cb_logs(call: types.CallbackQuery):
    """Show logs"""
    pid = int(call.data.split(":")[1])
    
    logs = read_logs(call.from_user.id, pid, lines=50)
    
    if len(logs) > 3500:
        logs = logs[-3500:]
    
    await call.message.edit_text(
        f"<b>📝 Logs (last 50 lines)</b>\n\n<pre>{logs}</pre>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"logs:{pid}")],
            [InlineKeyboardButton(text="⬇️ Download", callback_data=f"download_logs:{pid}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"control:{pid}")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("download_logs:"))
async def cb_download_logs(call: types.CallbackQuery):
    """Download log file"""
    pid = int(call.data.split(":")[1])
    
    log_path = get_log_path(call.from_user.id, pid)
    
    if not log_path.exists():
        await call.answer("❌ No logs available", show_alert=True)
        return
    
    await call.answer("⏳ Preparing logs...", show_alert=False)
    
    try:
        await call.message.answer_document(
            FSInputFile(log_path, filename=f"project_{pid}_logs.txt"),
            caption=f"📝 <b>Logs for Project {pid}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await call.message.answer(f"❌ Download failed: {e}")
    
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - DEPENDENCIES
# =============================================================================

@dp.callback_query(F.data.startswith("install_deps:"))
async def cb_install_deps(call: types.CallbackQuery):
    """Install dependencies from requirements.txt"""
    pid = int(call.data.split(":")[1])
    
    project_root = get_project_root(call.from_user.id, pid)
    req_file = project_root / "requirements.txt"
    
    if not req_file.exists():
        await call.message.edit_text(
            "<b>📦 Install Dependencies</b>\n\n"
            "❌ <code>requirements.txt</code> not found.\n\n"
            "<b>How to add:</b>\n"
            "1. Create a file named <code>requirements.txt</code>\n"
            "2. List your dependencies (one per line)\n"
            "3. Upload it to this project\n"
            "4. Come back and click Install\n\n"
            "<b>Example requirements.txt:</b>\n"
            "<pre>aiogram>=3.4.1\n"
            "requests>=2.31.0\n"
            "beautifulsoup4>=4.12.0</pre>\n\n"
            "💡 Or use: <code>/install package_name</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")]
            ])
        )
        await call.answer()
        return
    
    # Read requirements
    try:
        requirements = req_file.read_text(encoding='utf-8')
        package_count = len([line for line in requirements.split('\n') if line.strip() and not line.startswith('#')])
    except:
        package_count = 0
    
    await call.message.edit_text(
        f"<b>📦 Install Dependencies</b>\n\n"
        f"Found <code>requirements.txt</code>\n"
        f"Packages to install: <b>{package_count}</b>\n\n"
        f"<b>This will:</b>\n"
        f"• Create virtual environment (if needed)\n"
        f"• Install all packages\n"
        f"• May take 2-5 minutes\n\n"
        f"Proceed?",
        parse_mode="HTML",
        reply_markup=kb_confirm(f"install_deps_confirm:{pid}", f"project:{pid}")
    )
    await call.answer()

@dp.callback_query(F.data.startswith("install_deps_confirm:"))
async def cb_install_deps_confirm(call: types.CallbackQuery):
    """Confirm and install dependencies"""
    pid = int(call.data.split(":")[1])
    
    status_msg = await call.message.edit_text(
        "⏳ <b>Installing Dependencies...</b>\n\n"
        "This may take several minutes.\n"
        "Please wait...",
        parse_mode="HTML"
    )
    
    # Install
    success, msg = install_requirements(call.from_user.id, pid)
    
    if success:
        await status_msg.edit_text(
            "✅ <b>Dependencies Installed!</b>\n\n"
            "All packages have been installed successfully.\n\n"
            "You can now start your project!",
            parse_mode="HTML",
            reply_markup=kb_project_menu(pid, call.from_user.id)
        )
    else:
        await status_msg.edit_text(
            f"❌ <b>Installation Failed</b>\n\n{msg}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data=f"install_deps:{pid}")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"project:{pid}")]
            ])
        )
    
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - TEMPLATES
# =============================================================================

@dp.callback_query(F.data == "templates")
async def cb_templates(call: types.CallbackQuery):
    """Templates marketplace"""
    categories = TEMPLATE_CATEGORIES
    
    text = """
<b>🛍️ Template Marketplace</b>

Choose a category to browse ready-made templates:

<b>Available Categories:</b>
"""
    
    for cat in categories:
        count = sum(1 for t in TEMPLATES.values() if t['category'] == cat)
        text += f"\n• <b>{cat}</b> ({count} templates)"
    
    text += "\n\n💡 Templates are pre-configured projects ready to use!"
    
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"tpl_cat:{cat}")
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Home", callback_data="home")])
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("tpl_cat:"))
async def cb_template_category(call: types.CallbackQuery):
    """Show templates in category"""
    category = call.data.split(":", 1)[1]
    
    # Get templates in this category
    templates = [(tid, t) for tid, t in TEMPLATES.items() if t['category'] == category]
    
    text = f"""
<b>🛍️ Templates: {category}</b>

Total: <b>{len(templates)}</b> templates

Select a template to preview:
"""
    
    buttons = []
    for tid, t in templates:
        difficulty_icon = "🟢" if t['difficulty'] == 'Easy' else "🟡" if t['difficulty'] == 'Medium' else "🔴"
        buttons.append([
            InlineKeyboardButton(
                text=f"{difficulty_icon} {t['title']}", 
                callback_data=f"tpl_view:{tid}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="templates")])
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("tpl_view:"))
async def cb_template_view(call: types.CallbackQuery):
    """View template details"""
    tid = call.data.split(":")[1]
    
    if tid not in TEMPLATES:
        await call.answer("❌ Template not found", show_alert=True)
        return
    
    t = TEMPLATES[tid]
    
    # List files
    files_list = "\n".join([f"• <code>{fname}</code>" for fname in t['files'].keys()])
    
    text = f"""
<b>🧩 Template Preview</b>

<b>{t['title']}</b>

<b>Category:</b> {t['category']}
<b>Difficulty:</b> {t['difficulty']}
<b>Language:</b> {t['lang'].upper()}
<b>Entry File:</b> <code>{t['entry']}</code>
<b>Auto-restart:</b> {'✅ Enabled' if t['auto_restart'] else '❌ Disabled'}

<b>Description:</b>
<i>{t['description']}</i>

<b>Included Files:</b>
{files_list}

<b>What happens when you install:</b>
• New project is created
• All files are added
• Settings are configured
• Ready to customize!
"""
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Install This Template", callback_data=f"tpl_install:{tid}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"tpl_cat:{t['category']}")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("tpl_install:"))
async def cb_template_install(call: types.CallbackQuery, state: FSMContext):
    """Start template installation"""
    tid = call.data.split(":")[1]
    
    if tid not in TEMPLATES:
        await call.answer("❌ Template not found", show_alert=True)
        return
    
    # Check project limit
    limits = get_user_limits(call.from_user.id)
    stats = get_user_stats(call.from_user.id)
    
    if stats['project_count'] >= limits['projects']:
        await call.answer(
            f"❌ Project limit reached ({limits['projects']})\n"
            "Delete old projects or upgrade",
            show_alert=True
        )
        return
    
    t = TEMPLATES[tid]
    
    await state.update_data(template_id=tid)
    await state.set_state(TemplateInstall.project_name)
    
    await call.message.edit_text(
        f"<b>✅ Install Template</b>\n\n"
        f"<b>Template:</b> {t['title']}\n"
        f"<b>Files:</b> {len(t['files'])}\n\n"
        f"Send a name for your new project:\n\n"
        f"<b>Example:</b>\n"
        f"• <code>MyBot</code>\n"
        f"• <code>WebApp_v1</code>",
        parse_mode="HTML",
        reply_markup=kb_back_home()
    )
    await call.answer()

@dp.message(TemplateInstall.project_name)
async def fsm_template_install(message: types.Message, state: FSMContext):
    """Handle template installation"""
    data = await state.get_data()
    tid = data['template_id']
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Name too short. Please send again:")
        return
    
    t = TEMPLATES[tid]
    
    status_msg = await message.answer("⏳ Installing template...")
    
    try:
        # Create project
        pid = create_project(message.from_user.id, name, t['description'])
        project_root = get_project_root(message.from_user.id, pid)
        
        # Create all files
        for fname, content in t['files'].items():
            file_path = project_root / fname
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            
            ftype = get_file_type(fname)
            fsize = file_path.stat().st_size
            add_file(message.from_user.id, pid, fname, ftype, fsize)
        
        # Update project settings
        update_project_settings(
            message.from_user.id, 
            pid, 
            t['entry'], 
            t['lang'], 
            t['auto_restart']
        )
        
        stat_increment('total_template_installs')
        
        await status_msg.edit_text(
            f"✅ <b>Template Installed!</b>\n\n"
            f"<b>Project:</b> {name}\n"
            f"<b>ID:</b> <code>{pid}</code>\n"
            f"<b>Files:</b> {len(t['files'])}\n\n"
            f"<b>Next Steps:</b>\n"
            f"1. Review and customize files\n"
            f"2. Install dependencies (if needed)\n"
            f"3. Start your bot!\n\n"
            f"💡 Check <code>{t['entry']}</code> and update your TOKEN!",
            parse_mode="HTML",
            reply_markup=kb_project_menu(pid, message.from_user.id)
        )
        
        await state.clear()
    
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Installation Failed</b>\n\n{str(e)}",
            parse_mode="HTML"
        )
        await state.clear()

# =============================================================================
# CALLBACK HANDLERS - EXPORT
# =============================================================================

@dp.callback_query(F.data.startswith("export:"))
async def cb_export(call: types.CallbackQuery):
    """Export project as ZIP"""
    pid = int(call.data.split(":")[1])
    
    project = get_project(call.from_user.id, pid)
    if not project:
        await call.answer("❌ Project not found", show_alert=True)
        return
    
    name = project[1]
    
    await call.answer("⏳ Creating ZIP archive...", show_alert=False)
    
    project_root = get_project_root(call.from_user.id, pid)
    zip_path = LOGS_DIR / f"export_{call.from_user.id}_{pid}.zip"
    
    try:
        # Create ZIP
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in project_root.rglob('*'):
                if file.is_file():
                    # Skip venv and logs
                    if '.venv' in file.parts or '__pycache__' in file.parts:
                        continue
                    
                    arcname = file.relative_to(project_root)
                    zipf.write(file, arcname)
        
        # Send ZIP
        await call.message.answer_document(
            FSInputFile(zip_path, filename=f"{name}.zip"),
            caption=f"📦 <b>Project Export</b>\n\n<b>{name}</b>",
            parse_mode="HTML"
        )
        
        # Clean up
        zip_path.unlink()
        
    except Exception as e:
        await call.message.answer(f"❌ Export failed: {e}")
    
    await call.answer()

# =============================================================================
# CALLBACK HANDLERS - FAVORITES
# =============================================================================

@dp.callback_query(F.data.startswith("fav:"))
async def cb_toggle_favorite(call: types.CallbackQuery):
    """Toggle favorite"""
    parts = call.data.split(":", 2)
    pid = int(parts[1])
    fname = parts[2]
    
    conn = db_connect()
    c = conn.cursor()
    
    # Check if exists
    c.execute(
        "SELECT 1 FROM favorites WHERE user_id=? AND project_id=? AND file_name=?",
        (call.from_user.id, pid, fname)
    )
    
    if c.fetchone():
        # Remove
        c.execute(
            "DELETE FROM favorites WHERE user_id=? AND project_id=? AND file_name=?",
            (call.from_user.id, pid, fname)
        )
        msg = "Removed from favorites"
    else:
        # Add
        c.execute(
            "INSERT INTO favorites(user_id, project_id, file_name) VALUES(?, ?, ?)",
            (call.from_user.id, pid, fname)
        )
        msg = "Added to favorites"
    
    conn.commit()
    conn.close()
    
    await call.answer(f"⭐ {msg}", show_alert=False)

@dp.callback_query(F.data == "favorites")
async def cb_favorites(call: types.CallbackQuery):
    """Show favorites"""
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
        SELECT f.project_id, f.file_name, p.name
        FROM favorites f
        JOIN projects p ON f.project_id = p.project_id AND f.user_id = p.user_id
        WHERE f.user_id = ?
        ORDER BY f.project_id DESC
        LIMIT 30
    """, (call.from_user.id,))
    favorites = c.fetchall()
    conn.close()
    
    if not favorites:
        await call.message.edit_text(
            "<b>⭐ Favorites</b>\n\n"
            "No favorites yet.\n\n"
            "Add files to favorites by clicking the ⭐ button!",
            parse_mode="HTML",
            reply_markup=kb_back_home()
        )
        await call.answer()
        return
    
    text = f"<b>⭐ Your Favorites</b>\n\nTotal: <b>{len(favorites)}</b>\n\n"
    
    buttons = []
    for pid, fname, pname in favorites:
        buttons.append([
            InlineKeyboardButton(
                text=f"📄 {fname[:20]} ({pname[:15]})",
                callback_data=f"file:{pid}:{fname}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="🏠 Home", callback_data="home")])
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()

# Continue with Admin Panel in next part...

# =============================================================================
# ADMIN PANEL - MAIN
# =============================================================================

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery):
    """Admin panel main menu"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    analytics = get_bot_analytics()
    
    text = f"""
<b>👑 Admin Panel</b>

<b>📊 Bot Statistics:</b>
├ Total Users: <b>{analytics['total_users']}</b>
├ Active (24h): <b>{analytics['active_24h']}</b>
├ Premium Users: <b>{analytics['premium_users']}</b>
├ Banned Users: <b>{analytics['banned_users']}</b>
└ Admins: <b>{analytics['admins']}</b>

<b>📦 Content:</b>
├ Total Projects: <b>{analytics['total_projects']}</b>
├ Total Files: <b>{analytics['total_files']}</b>
└ Running Bots: <b>{len(get_all_running())}</b>

<b>📈 Activity:</b>
├ Total Uploads: <b>{analytics['stats'].get('total_uploads', 0)}</b>
├ Total Runs: <b>{analytics['stats'].get('total_runs', 0)}</b>
├ Total Downloads: <b>{analytics['stats'].get('total_downloads', 0)}</b>
└ Template Installs: <b>{analytics['stats'].get('total_template_installs', 0)}</b>
"""
    
    await call.message.edit_text(
        text,
        reply_markup=kb_admin_panel(),
        parse_mode="HTML"
    )
    await call.answer()

# =============================================================================
# ADMIN PANEL - USERS
# =============================================================================

@dp.callback_query(F.data == "admin_users")
async def cb_admin_users(call: types.CallbackQuery):
    """View users list"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    users = get_user_list(limit=20)
    
    text = f"<b>👥 Users (Last 20)</b>\n\n"
    
    for uid, username, full_name, join_date, last_active in users:
        status = []
        if is_admin(uid):
            status.append("👑")
        if is_premium(uid):
            status.append("💎")
        if is_banned(uid):
            status.append("🚫")
        
        status_str = " ".join(status) if status else ""
        
        text += f"• <code>{uid}</code> {status_str}\n"
        text += f"  {full_name or 'Unknown'}\n"
        text += f"  @{username or 'none'}\n\n"
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "admin_search")
async def cb_admin_search(call: types.CallbackQuery, state: FSMContext):
    """Search user"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.user_search)
    
    await call.message.edit_text(
        "<b>🔍 Search User</b>\n\n"
        "Send user ID, username, or name:\n\n"
        "<b>Examples:</b>\n"
        "• <code>123456789</code>\n"
        "• <code>@username</code>\n"
        "• <code>John</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.user_search)
async def fsm_admin_search(message: types.Message, state: FSMContext):
    """Handle user search"""
    query = message.text.strip().replace("@", "")
    
    users = search_user(query)
    
    if not users:
        await message.answer(
            "❌ No users found.",
            reply_markup=kb_admin_panel()
        )
        await state.clear()
        return
    
    text = f"<b>🔍 Search Results</b>\n\nFound: <b>{len(users)}</b> users\n\n"
    
    for uid, username, full_name, join_date, last_active in users:
        stats = get_user_stats(uid)
        
        status = []
        if stats['is_admin']:
            status.append("👑 Admin")
        if stats['is_premium']:
            status.append("💎 Premium")
        if stats['is_banned']:
            status.append("🚫 Banned")
        
        status_str = " | ".join(status) if status else "Regular"
        
        text += f"<b>{full_name or 'Unknown'}</b>\n"
        text += f"├ ID: <code>{uid}</code>\n"
        text += f"├ Username: @{username or 'none'}\n"
        text += f"├ Status: {status_str}\n"
        text += f"├ Projects: {stats['project_count']}\n"
        text += f"└ Files: {stats['file_count']}\n\n"
    
    await message.answer(
        text,
        reply_markup=kb_admin_panel(),
        parse_mode="HTML"
    )
    await state.clear()

# =============================================================================
# ADMIN PANEL - ANALYTICS
# =============================================================================

@dp.callback_query(F.data == "admin_analytics")
async def cb_admin_analytics(call: types.CallbackQuery):
    """Detailed analytics"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    analytics = get_bot_analytics()
    
    # Calculate percentages
    premium_pct = (analytics['premium_users'] / analytics['total_users'] * 100) if analytics['total_users'] > 0 else 0
    active_pct = (analytics['active_24h'] / analytics['total_users'] * 100) if analytics['total_users'] > 0 else 0
    
    text = f"""
<b>📊 Detailed Analytics</b>

<b>👥 Users:</b>
├ Total: <b>{analytics['total_users']}</b>
├ Active (24h): <b>{analytics['active_24h']}</b> ({active_pct:.1f}%)
├ Premium: <b>{analytics['premium_users']}</b> ({premium_pct:.1f}%)
├ Banned: <b>{analytics['banned_users']}</b>
└ Admins: <b>{analytics['admins']}</b>

<b>📦 Content:</b>
├ Projects: <b>{analytics['total_projects']}</b>
├ Files: <b>{analytics['total_files']}</b>
└ Running: <b>{len(get_all_running())}</b>

<b>📈 Activity Stats:</b>
├ Uploads: <b>{analytics['stats'].get('total_uploads', 0)}</b>
├ Downloads: <b>{analytics['stats'].get('total_downloads', 0)}</b>
├ Bot Runs: <b>{analytics['stats'].get('total_runs', 0)}</b>
├ Restarts: <b>{analytics['stats'].get('total_restarts', 0)}</b>
└ Template Installs: <b>{analytics['stats'].get('total_template_installs', 0)}</b>

<b>Averages:</b>
├ Projects per User: <b>{analytics['total_projects'] / analytics['total_users']:.1f}</b>
└ Files per User: <b>{analytics['total_files'] / analytics['total_users']:.1f}</b>
"""
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_analytics")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

# =============================================================================
# ADMIN PANEL - RUNNING BOTS
# =============================================================================

@dp.callback_query(F.data == "admin_running")
async def cb_admin_running(call: types.CallbackQuery):
    """View running bots"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    running = get_all_running()
    
    if not running:
        await call.message.edit_text(
            "<b>🚀 Running Bots</b>\n\n"
            "No bots are currently running.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")]
            ])
        )
        await call.answer()
        return
    
    text = f"<b>🚀 Running Bots</b>\n\nTotal: <b>{len(running)}</b>\n\n"
    
    buttons = []
    for proc in running[:15]:
        text += f"• User <code>{proc['user_id']}</code> | Project <code>{proc['project_id']}</code>\n"
        text += f"  PID: <code>{proc['pid']}</code> | Uptime: {proc['uptime']}\n\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"🛑 Stop {proc['user_id']}:{proc['project_id']}",
                callback_data=f"admin_stop:{proc['user_id']}:{proc['project_id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")])
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("admin_stop:"))
async def cb_admin_stop(call: types.CallbackQuery):
    """Admin stop bot"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    parts = call.data.split(":")
    user_id = int(parts[1])
    project_id = int(parts[2])
    
    success, msg = stop_process(user_id, project_id)
    
    await call.answer(msg, show_alert=True)
    
    # Refresh list
    await cb_admin_running(call)

# =============================================================================
# ADMIN PANEL - PREMIUM MANAGEMENT
# =============================================================================

@dp.callback_query(F.data == "admin_premium")
async def cb_admin_premium(call: types.CallbackQuery):
    """Premium management"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    premium_users = list_premium()
    
    text = f"<b>💎 Premium Management</b>\n\n"
    text += f"Total Premium Users: <b>{len(premium_users)}</b>\n\n"
    
    if premium_users:
        text += "<b>Active Premium:</b>\n"
        for uid, expiry in premium_users[:10]:
            text += f"• <code>{uid}</code> - Expires: {expiry[:10]}\n"
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Premium", callback_data="admin_add_premium")],
            [InlineKeyboardButton(text="➖ Remove Premium", callback_data="admin_remove_premium")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "admin_add_premium")
async def cb_admin_add_premium(call: types.CallbackQuery, state: FSMContext):
    """Add premium"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.add_premium_id)
    
    await call.message.edit_text(
        "<b>➕ Add Premium</b>\n\n"
        "Send the user ID:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_premium")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.add_premium_id)
async def fsm_add_premium_id(message: types.Message, state: FSMContext):
    """Get user ID for premium"""
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Invalid user ID. Please send again:")
        return
    
    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.add_premium_days)
    
    await message.answer(
        f"<b>User ID:</b> <code>{user_id}</code> ✅\n\n"
        "Now send number of days:\n\n"
        "<b>Examples:</b>\n"
        "• <code>30</code> (1 month)\n"
        "• <code>365</code> (1 year)\n"
        "• <code>9999</code> (lifetime)",
        parse_mode="HTML"
    )

@dp.message(AdminStates.add_premium_days)
async def fsm_add_premium_days(message: types.Message, state: FSMContext):
    """Get days and add premium"""
    try:
        days = int(message.text.strip())
    except:
        await message.answer("❌ Invalid number. Please send again:")
        return
    
    data = await state.get_data()
    user_id = data['user_id']
    
    success = add_premium(user_id, days, message.from_user.id)
    
    if success:
        await message.answer(
            f"✅ <b>Premium Added!</b>\n\n"
            f"User: <code>{user_id}</code>\n"
            f"Duration: <b>{days}</b> days",
            parse_mode="HTML",
            reply_markup=kb_admin_panel()
        )
    else:
        await message.answer(
            "❌ Failed to add premium",
            reply_markup=kb_admin_panel()
        )
    
    await state.clear()

@dp.callback_query(F.data == "admin_remove_premium")
async def cb_admin_remove_premium(call: types.CallbackQuery, state: FSMContext):
    """Remove premium"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.remove_premium_id)
    
    await call.message.edit_text(
        "<b>➖ Remove Premium</b>\n\n"
        "Send the user ID:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_premium")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.remove_premium_id)
async def fsm_remove_premium(message: types.Message, state: FSMContext):
    """Remove premium"""
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Invalid user ID")
        await state.clear()
        return
    
    success = remove_premium(user_id)
    
    if success:
        await message.answer(
            f"✅ Premium removed from <code>{user_id}</code>",
            parse_mode="HTML",
            reply_markup=kb_admin_panel()
        )
    else:
        await message.answer(
            "❌ Failed to remove premium",
            reply_markup=kb_admin_panel()
        )
    
    await state.clear()

# =============================================================================
# ADMIN PANEL - BAN MANAGEMENT
# =============================================================================

@dp.callback_query(F.data == "admin_ban")
async def cb_admin_ban_menu(call: types.CallbackQuery):
    """Ban management menu"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    banned = list_banned()
    
    text = f"<b>🚫 Ban Management</b>\n\n"
    text += f"Total Banned: <b>{len(banned)}</b>\n\n"
    
    if banned:
        text += "<b>Banned Users:</b>\n"
        for uid, banned_date, reason in banned[:10]:
            text += f"• <code>{uid}</code>\n"
            text += f"  Reason: <i>{reason or 'No reason'}</i>\n\n"
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban_user")],
            [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban_user")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "admin_ban_user")
async def cb_admin_ban_user(call: types.CallbackQuery, state: FSMContext):
    """Ban user"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.ban_user_id)
    
    await call.message.edit_text(
        "<b>🚫 Ban User</b>\n\n"
        "Send the user ID to ban:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_ban")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.ban_user_id)
async def fsm_ban_user_id(message: types.Message, state: FSMContext):
    """Get user ID to ban"""
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Invalid user ID. Please send again:")
        return
    
    # Prevent banning admins
    if is_admin(user_id):
        await message.answer(
            "❌ Cannot ban admin users!",
            reply_markup=kb_admin_panel()
        )
        await state.clear()
        return
    
    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.ban_reason)
    
    await message.answer(
        f"<b>User ID:</b> <code>{user_id}</code> ✅\n\n"
        "Send ban reason:",
        parse_mode="HTML"
    )

@dp.message(AdminStates.ban_reason)
async def fsm_ban_reason(message: types.Message, state: FSMContext):
    """Ban user with reason"""
    reason = message.text.strip()
    data = await state.get_data()
    user_id = data['user_id']
    
    success = ban_user(user_id, reason, message.from_user.id)
    
    if success:
        await message.answer(
            f"✅ <b>User Banned</b>\n\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Reason: <i>{reason}</i>",
            parse_mode="HTML",
            reply_markup=kb_admin_panel()
        )
    else:
        await message.answer(
            "❌ Failed to ban user",
            reply_markup=kb_admin_panel()
        )
    
    await state.clear()

@dp.callback_query(F.data == "admin_unban_user")
async def cb_admin_unban_user(call: types.CallbackQuery, state: FSMContext):
    """Unban user"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.unban_user_id)
    
    await call.message.edit_text(
        "<b>✅ Unban User</b>\n\n"
        "Send the user ID to unban:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_ban")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.unban_user_id)
async def fsm_unban_user(message: types.Message, state: FSMContext):
    """Unban user"""
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Invalid user ID")
        await state.clear()
        return
    
    success = unban_user(user_id)
    
    if success:
        await message.answer(
            f"✅ User <code>{user_id}</code> has been unbanned",
            parse_mode="HTML",
            reply_markup=kb_admin_panel()
        )
    else:
        await message.answer(
            "❌ Failed to unban user",
            reply_markup=kb_admin_panel()
        )
    
    await state.clear()

# =============================================================================
# ADMIN PANEL - BROADCAST
# =============================================================================

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: types.CallbackQuery, state: FSMContext):
    """Broadcast message"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ Admin only!", show_alert=True)
        return
    
    await state.set_state(AdminStates.broadcast_target)
    
    await call.message.edit_text(
        "<b>📢 Broadcast Message</b>\n\n"
        "Choose target audience:\n\n"
        "• <code>all</code> - All users\n"
        "• <code>premium</code> - Premium users only\n"
        "• <code>active</code> - Active users (24h)",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]
        ])
    )
    await call.answer()

@dp.message(AdminStates.broadcast_target)
async def fsm_broadcast_target(message: types.Message, state: FSMContext):
    """Get broadcast target"""
    target = message.text.strip().lower()
    
    if target not in ['all', 'premium', 'active']:
        await message.answer(
            "❌ Invalid target. Send: all, premium, or active"
        )
        return
    
    await state.update_data(target=target)
    await state.set_state(AdminStates.broadcast_message)
    
    target_name = {
        'all': 'All Users',
        'premium': 'Premium Users',
        'active': 'Active Users (24h)'
    }[target]
    
    await message.answer(
        f"<b>Target:</b> {target_name} ✅\n\n"
        "Now send your message:\n\n"
        "💡 You can use HTML formatting",
        parse_mode="HTML"
    )

@dp.message(AdminStates.broadcast_message)
async def fsm_broadcast_message(message: types.Message, state: FSMContext):
    """Send broadcast"""
    msg_text = message.text or message.caption
    
    if not msg_text:
        await message.answer("❌ Message cannot be empty")
        return
    
    data = await state.get_data()
    target = data['target']
    
    status_msg = await message.answer("⏳ Broadcasting...")
    
    success_count, fail_count = await broadcast_message(bot, msg_text, target)
    
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"Target: <b>{target}</b>\n"
        f"✅ Success: <b>{success_count}</b>\n"
        f"❌ Failed: <b>{fail_count}</b>",
        parse_mode="HTML",
        reply_markup=kb_admin_panel()
    )
    
    await state.clear()

# =============================================================================
# WEB SERVER (KEEP-ALIVE)
# =============================================================================

async def webserver():
    """Simple web server to keep service alive"""
    
    async def health_check(request):
        return web.Response(text="Bot is running! ✅")
    
    async def stats(request):
        analytics = get_bot_analytics()
        return web.json_response({
            'status': 'ok',
            'users': analytics['total_users'],
            'projects': analytics['total_projects'],
            'running_bots': len(get_all_running())
        })
    
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/stats', stats)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
    await site.start()
    
    logger.info(f"🌐 Web server started on port {WEB_SERVER_PORT}")

# =============================================================================
# MAIN FUNCTION
# =============================================================================
async def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 ADVANCED BOT HOSTING v2.0")
    
    # Detect Render environment
    if os.getenv("RENDER"):
        logger.info("🌐 Running on Render.com")
        logger.info("⚠️ Note: Storage is ephemeral on Render")
    
    logger.info("=" * 60)
    
    # ... rest of the code stays same

async def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 ADVANCED BOT HOSTING v2.0")
    logger.info("=" * 60)
    
    # Start web server
    asyncio.create_task(webserver())
    logger.info("✅ Web server started")
    
    # Start auto-restart monitor
    asyncio.create_task(auto_restart_monitor())
    logger.info("✅ Auto-restart monitor started")
    
    # Log bot info
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"✅ Bot ID: {me.id}")
    logger.info(f"✅ Database: {DB_PATH}")
    logger.info(f"✅ Users directory: {USERS_DIR}")
    logger.info("=" * 60)
    logger.info("📡 Polling started...")
    
    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Cleanup on exit
        logger.info("\n⚠️ Stopping bot...")
        
        # Stop all running processes
        for key in list(running_processes.keys()):
            stop_process(*map(int, key.split(":")))
        
        await bot.session.close()
        logger.info("✅ Bot stopped gracefully")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n✅ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)