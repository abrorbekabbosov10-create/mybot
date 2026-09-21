import os
import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- Muhit o'zgaruvchilari ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# O'yinlar xotirasi
active_games = {}

class Form(StatesGroup):
    waiting_for_deposit = State()
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()
    waiting_for_add_bal_user = State()
    waiting_for_add_bal_amount = State()

# --- Ma'lumotlar bazasi ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            referrer_id INTEGER DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_url TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return result

# --- Darajalarni hisoblash ---
def get_rank(wins, balance):
    if wins >= 100 and balance >= 30000:
        return "👑 X-O Qiroli"
    elif wins >= 100 and balance < 30000:
        return "💎 Olmos Afsona (30.000 AEXCoin yetmadi)"
    elif wins >= 50:
        return "💎 Olmos Afsona"
    elif wins >= 30:
        return "🥇 Oltin Chempion"
    elif wins >= 15:
        return "🥈 Kumush Master"
    elif wins >= 5:
        return "🥉 Bronza Usta"
    else:
        return "🌱 Yangi o'yinchi"

# --- Klaviaturalar ---
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Bot bilan o'ynash"), KeyboardButton(text="👥 Do'st bilan o'ynash")],
            [KeyboardButton(text="👤 Profil & Statistika"), KeyboardButton(text="🏆 Reyting")],
            [KeyboardButton(text="👥 Taklif qilish"), KeyboardButton(text="💳 Hisob to'ldirish")],
            [KeyboardButton(text="⚙️ Admin Panel")]
        ],
        resize_keyboard=True
    )

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💰 Balans boshqarish (AEXCoin)", callback_data="admin_change_bal")],
            [InlineKeyboardButton(text="📢 Obuna kanali qo'shish", callback_data="admin_add_channel")],
            [InlineKeyboardButton(text="🗑 Kanallarni tozalash", callback_data="admin_clear_channels")]
        ]
    )

# --- Obuna tekshiruvi ---
async def check_sub(user_id: int) -> bool:
    channels = db_query("SELECT channel_id, channel_url FROM channels", fetchall=True)
    if not channels:
        return True
    unsubscribed = []
    for ch_id, ch_url in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append((ch_id, ch_url))
        except Exception:
            unsubscribed.append((ch_id, ch_url))
    if unsubscribed:
        btns = [[InlineKeyboardButton(text="Kanalga o'tish", url=url)] for _, url in unsubscribed]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")])
        await bot.send_message(user_id, "⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        return False
    return True

# --- Start Handler ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    init_db()
    u_id = message.from_user.id
    u_name = message.from_user.username or message.from_user.first_name
    
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() and int(args[1]) != u_id else None
    
    user = db_query("SELECT * FROM users WHERE user_id = ?", (u_id,), fetchone=True)
    if not user:
        db_query("INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)", (u_id, u_name, ref_id), commit=True)
        if ref_id:
            db_query("UPDATE users SET balance = balance + 500 WHERE user_id = ?", (ref_id,), commit=True)
            try:
                await bot.send_message(ref_id, "🎉 Do'stingiz kirdi! +500 AEXCoin bonus berildi.")
            except: pass

    if await check_sub(u_id):
        await message.answer(f"Xush kelibsiz, {message.from_user.first_name}!", reply_markup=main_keyboard())

@dp.callback_query(F.data == "check_subscription")
async def check_sub_call(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Obuna tasdiqlandi!", reply_markup=main_keyboard())

# --- Profil va Statistika ---
@dp.message(F.text == "👤 Profil & Statistika")
async def profile_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    u = db_query("SELECT balance, wins, losses, draws FROM users WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    balance, wins, losses, draws = u[0], u[1], u[2], u[3]
    total_games = wins + losses + draws
    rank = get_rank(wins, balance)
    
    text = (
        f"👤 **Sizning profilingiz:**\n\n"
        f"🎖 **Daraja:** {rank}\n"
        f"💰 **Balans:** {balance} AEXCoin\n\n"
        f"📊 **Statistika:**\n"
        f"🎮 Jami o'yinlar: {total_games}\n"
        f"🥇 G'alabalar: {wins}\n"
        f"❌ Mag'lubiyatlar: {losses}\n"
        f"🤝 Duranglar: {draws}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 Taklif qilish")
async def invite_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    me = await bot.get_me()
    await message.answer(f"👥 Do'stlarni taklif qiling va 500 AEXCoin oling:\nhttps://t.me/{me.username}?start={message.from_user.id}")

@dp.message(F.text == "🏆 Reyting")
async def top_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    top = db_query("SELECT username, wins, balance FROM users ORDER BY wins DESC LIMIT 10", fetchall=True)
    text = "🏆 **Eng kuchli o'yinchilar:**\n\n"
    for idx, (name, wins, balance) in enumerate(top, 1):
        text += f"{idx}. @{name} — {wins} ta g'alaba ({get_rank(wins, balance)})\n"
    await message.answer(text, parse_mode="Markdown")

# --- O'YIN MANTIQI (X-O) ---
def get_xo_board(game_id):
    b = active_games[game_id]['board']
    kb = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            row.append(InlineKeyboardButton(text=b[i] if b[i] != " " else " ", callback_data=f"xo_{game_id}_{i}"))
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

def check_win(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for x, y, z in wins:
        if b[x] == b[y] == b[z] and b[x] != " ":
            return b[x]
    if " " not in b: return "Draw"
    return None

# --- Bot Bilan O'ynash ---
@dp.message(F.text == "🤖 Bot bilan o'ynash")
async def vs_bot_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    g_id = f"bot_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': 'X',
        'player_x': message.from_user.id,
        'vs_bot': True
    }
    await message.answer("🤖 Botga qarshi o'yin boshlandi! Siz: ❌\nNavbatingiz:", reply_markup=get_xo_board(g_id))

# --- Do'st Bilan O'ynash ---
@dp.message(F.text == "👥 Do'st bilan o'ynash")
async def vs_p_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    g_id = f"pvp_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': 'X',
        'player_x': message.from_user.id,
        'player_o': None,
        'vs_bot': False
    }
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Qo'shilish", callback_data=f"join_{g_id}")]])
    await message.answer("🎮 Yangi o'yin yaratildi! Raqib tugmani bosishini kuting:", reply_markup=kb)

@dp.callback_query(F.data.startswith("join_"))
async def join_game(call: types.CallbackQuery):
    g_id = call.data.replace("join_", "")
    if g_id not in active_games: return await call.answer("O'yin yakunlangan!", show_alert=True)
    g = active_games[g_id]
    if g['player_x'] == call.from_user.id: return await call.answer("O'zingizga qarshi o'ynay olmaysiz!", show_alert=True)
    g['player_o'] = call.from_user.id
    await call.message.edit_text("🎮 O'yin boshlandi!\n❌ - Siz\n⭕ - Raqib\nNavbat: ❌", reply_markup=get_xo_board(g_id))

@dp.callback_query(F.data.startswith("xo_"))
async def xo_click(call: types.CallbackQuery):
    _, g_id, idx = call.data.split("_")
    idx = int(idx)
    if g_id not in active_games: return await call.answer("O'yin yakunlangan!", show_alert=True)
    
    g = active_games[g_id]
    u_id = call.from_user.id
    
    if g['vs_bot']:
        if u_id != g['player_x']: return
    else:
        exp = g['player_x'] if g['turn'] == 'X' else g['player_o']
        if u_id != exp: return await call.answer("Hozir sizning navbatingiz emas!", show_alert=True)
        
    if g['board'][idx] != " ": return await call.answer("Katak band!", show_alert=True)
    
    g['board'][idx] = g['turn']
    res = check_win(g['board'])
    
    if res:
        await finish_game(call.message, g_id, res)
        return

    if g['vs_bot']:
        g['turn'] = 'O'
        empty_spots = [i for i, val in enumerate(g['board']) if val == " "]
        if empty_spots:
            bot_move = random.choice(empty_spots)
            g['board'][bot_move] = 'O'
            res_b = check_win(g['board'])
            if res_b:
                await finish_game(call.message, g_id, res_b)
                return
        g['turn'] = 'X'
        await call.message.edit_text("Sizning navbatingiz: ❌", reply_markup=get_xo_board(g_id))
    else:
        g['turn'] = 'O' if g['turn'] == 'X' else 'X'
        await call.message.edit_text(f"Navbat: {g['turn']}", reply_markup=get_xo_board(g_id))

async def finish_game(msg, g_id, winner):
    g = active_games[g_id]
    px = g['player_x']
    po = g.get('player_o')
    
    if winner == "Draw":
        txt = "🤝 Durang yakunlandi!"
        db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (po,), commit=True)
    elif winner == 'X':
        txt = "🎉 ❌ G'alaba qozondi!"
        db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (po,), commit=True)
    else:
        txt = "🎉 ⭕ G'alaba qozondi!"
        db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (po,), commit=True)
        
    await msg.edit_text(txt, reply_markup=get_xo_board(g_id))
    del active_games[g_id]

# --- Admin va Balans boshqaruvi ---
@dp.message(F.text == "💳 Hisob to'ldirish")
async def dep_cmd(msg: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_for_deposit)
    await msg.answer("To'ldirmoqchi bo'lgan AEXCoin miqdorini kiriting:")

@dp.message(Form.waiting_for_deposit)
async def proc_dep(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("Faqat raqam kiriting!")
    db_query("INSERT INTO deposit_requests (user_id, amount) VALUES (?, ?)", (msg.from_user.id, float(msg.text)), commit=True)
    await state.clear()
    await msg.answer("So'rov adminga yuborildi.")

@dp.message(F.text == "⚙️ Admin Panel")
async def adm_cmd(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("Admin paneli:", reply_markup=admin_keyboard())

# --- Admin AEXCoin Balans O'zgartirish ---
@dp.callback_query(F.data == "admin_change_bal")
async def admin_change_bal_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_for_add_bal_user)
    await call.message.answer("Balansini o'zgartirmoqchi bo'lgan foydalanuvchining **Telegram ID** raqamini kiriting:")

@dp.message(Form.waiting_for_add_bal_user)
async def process_bal_user(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("ID faqat raqamlardan iborat bo'ladi!")
    await state.update_data(target_user_id=int(msg.text))
    await state.set_state(Form.waiting_for_add_bal_amount)
    await msg.answer("Qancha **AEXCoin** qo'shmoqchisiz? (Ayrish uchun manfiy raqam kiriting, masalan: `-500`):")

@dp.message(Form.waiting_for_add_bal_amount)
async def process_bal_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text)
    except ValueError:
        return await msg.answer("Noto'g'ri summa kiritildi!")
        
    data = await state.get_data()
    target_id = data['target_user_id']
    
    user = db_query("SELECT user_id FROM users WHERE user_id = ?", (target_id,), fetchone=True)
    if not user:
        await state.clear()
        return await msg.answer("Bunday foydalanuvchi bazadan topilmadi!")
        
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id), commit=True)
    await state.clear()
    await msg.answer(f"✅ ID `{target_id}` foydalanuvchi balansiga {amount} AEXCoin muvaffaqiyatli o'zgartirildi.")
    try:
        await bot.send_message(target_id, f"💳 Admin tomonidan balansingizga {amount} AEXCoin o'zgartirildi.")
    except: pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
