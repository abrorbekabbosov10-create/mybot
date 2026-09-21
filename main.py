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

# --- Telegram ID va Token ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8880269827:AAFrLdxPWnz4fEU4GMw8PkY6b_2KUrvF5b8")
ADMIN_ID = 8694110588

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Faol o'yinlar xotirasi
active_games = {}

class Form(StatesGroup):
    waiting_for_deposit = State()
    waiting_for_add_bal_user = State()
    waiting_for_add_bal_amount = State()
    waiting_for_card = State()
    waiting_for_shop_item_name = State()
    waiting_for_shop_item_price = State()

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
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL
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
            [KeyboardButton(text="🛍 AEXCoin ishlatish")]
        ],
        resize_keyboard=True
    )

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta qo'shish", callback_data="admin_add_card")],
            [InlineKeyboardButton(text="💰 Balans boshqarish (AEXCoin)", callback_data="admin_change_bal")],
            [InlineKeyboardButton(text="🛍 Xizmat qo'shish", callback_data="admin_add_shop")],
            [InlineKeyboardButton(text="🗑 Xizmat o'chirish", callback_data="admin_delete_shop")]
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

# --- AEXCoin ishlatish (Do'kon) ---
@dp.message(F.text == "🛍 AEXCoin ishlatish")
async def shop_user_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    items = db_query("SELECT id, name, price FROM shop_items", fetchall=True)
    if not items:
        return await message.answer("🛍 Hozircha AEXCoin evaziga xarid qilish uchun maxsus xizmatlar mavjud emas.")
    
    text = "🛍 **AEXCoin xizmatlar do'koni:**\n\n"
    kb = []
    for item_id, name, price in items:
        text += f"🔹 **{name}** — {price} AEXCoin\n"
        kb.append([InlineKeyboardButton(text=f"Sotib olish: {name}", callback_data=f"buy_shop_{item_id}")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_shop_"))
async def buy_shop_item(call: types.CallbackQuery):
    item_id = int(call.data.replace("buy_shop_", ""))
    item = db_query("SELECT name, price FROM shop_items WHERE id = ?", (item_id,), fetchone=True)
    if not item:
        return await call.answer("Xizmat topilmadi!", show_alert=True)
    
    u = db_query("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,), fetchone=True)
    user_bal = u[0]
    name, price = item[0], item[1]
    
    if user_bal < price:
        return await call.answer(f"Mablag' yetarli emas! Sizda {user_bal} AEXCoin bor.", show_alert=True)
    
    # Balansdan ayirish
    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, call.from_user.id), commit=True)
    await call.answer("So'rov yuborildi!", show_alert=True)
    await call.message.answer(f"✅ `{name}` uchun {price} AEXCoin to'landi! So'rov adminga yetkazildi.", parse_mode="Markdown")
    
    # Adminga xabar
    try:
        await bot.send_message(ADMIN_ID, f"🛍 **Yangi buyurtma!**\nFoydalanuvchi: @{call.from_user.username} (ID: `{call.from_user.id}`)\nXizmat: {name}\nNarxi: {price} AEXCoin", parse_mode="Markdown")
    except: pass

# --- O'YIN MANTIQI (X-O) ---
def get_xo_board(game_id):
    b = active_games[game_id]['board']
    kb = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            symbol = b[i] if b[i] != " " else "➖"
            row.append(InlineKeyboardButton(text=symbol, callback_data=f"xo_{game_id}_{i}"))
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

def check_win(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for x, y, z in wins:
        if b[x] == b[y] == b[z] and b[x] != " ":
            return b[x]
    if " " not in b: return "Draw"
    return None

@dp.message(F.text == "🤖 Bot bilan o'ynash")
async def vs_bot_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    g_id = f"bot_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': '❌',
        'player_x': message.from_user.id,
        'vs_bot': True
    }
    await message.answer("🤖 Botga qarshi o'yin boshlandi! Siz: ❌\nNavbatingiz:", reply_markup=get_xo_board(g_id))

@dp.message(F.text == "👥 Do'st bilan o'ynash")
async def vs_p_handler(message: types.Message):
    if not await check_sub(message.from_user.id): return
    g_id = f"pvp_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': '❌',
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
    await call.message.edit_text("🎮 O'yin boshlandi!\n❌ - Yaratuvchi\n⭕ - Qo'shilgan raqib\nNavbat: ❌", reply_markup=get_xo_board(g_id))

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
        exp = g['player_x'] if g['turn'] == '❌' else g['player_o']
        if u_id != exp: return await call.answer("Hozir sizning navbatingiz emas!", show_alert=True)
        
    if g['board'][idx] != " ": return await call.answer("Katak band!", show_alert=True)
    
    g['board'][idx] = g['turn']
    res = check_win(g['board'])
    
    if res:
        await finish_game(call.message, g_id, res)
        return

    if g['vs_bot']:
        empty_spots = [i for i, val in enumerate(g['board']) if val == " "]
        if empty_spots:
            bot_move = random.choice(empty_spots)
            g['board'][bot_move] = '⭕'
            res_b = check_win(g['board'])
            if res_b:
                await finish_game(call.message, g_id, res_b)
                return
        await call.message.edit_text("Sizning navbatingiz: ❌", reply_markup=get_xo_board(g_id))
    else:
        g['turn'] = '⭕' if g['turn'] == '❌' else '❌'
        await call.message.edit_text(f"Navbat: {g['turn']}", reply_markup=get_xo_board(g_id))

async def finish_game(msg, g_id, winner):
    g = active_games[g_id]
    px = g['player_x']
    po = g.get('player_o')
    
    if winner == "Draw":
        txt = "🤝 Durang yakunlandi!"
        db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (po,), commit=True)
    elif winner == '❌':
        txt = "🎉 ❌ G'alaba qozondi!"
        db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (po,), commit=True)
    else:
        txt = "🎉 ⭕ G'alaba qozondi!"
        db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (px,), commit=True)
        if po: db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (po,), commit=True)
        
    await msg.edit_text(txt, reply_markup=get_xo_board(g_id))
    del active_games[g_id]

# --- To'lov ---
@dp.message(F.text == "💳 Hisob to'ldirish")
async def dep_cmd(msg: types.Message, state: FSMContext):
    cards = db_query("SELECT card_number FROM cards", fetchall=True)
    if not cards:
        return await msg.answer("Hozircha to'lov kartalari biriktirilmagan. Keyinroq urinib ko'ring!")
        
    card_text = "\n".join([f"💳 `{c[0]}`" for c in cards])
    await state.set_state(Form.waiting_for_deposit)
    await msg.answer(
        f"To'lov qilish uchun quyidagi kartalarga pul o'tkazing:\n\n{card_text}\n\n"
        f"To'lagan summangiz va AEXCoin miqdorini kiriting:",
        parse_mode="Markdown"
    )

@dp.message(Form.waiting_for_deposit)
async def proc_dep(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("Faqat raqam kiriting!")
    await state.clear()
    await msg.answer("So'rov adminga yuborildi. Tekshiruvdan so'ng hisobingizga qo'shiladi.")
    try:
        await bot.send_message(ADMIN_ID, f"💳 **Hisob to'ldirish so'rovi:**\nFoydalanuvchi: @{msg.from_user.username} (ID: `{msg.from_user.id}`)\nMiqdor: {msg.text}", parse_mode="Markdown")
    except: pass

# --- Faqat Admin Kiradigan Panel (/admin) ---
@dp.message(Command("admin"))
async def adm_cmd(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("⚙️ Admin paneli:", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "admin_add_card")
async def admin_add_card_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_card)
    await call.message.answer("Yangi karta raqami va egalari ismini kiriting:")

@dp.message(Form.waiting_for_card)
async def process_add_card(msg: types.Message, state: FSMContext):
    db_query("INSERT INTO cards (card_number) VALUES (?)", (msg.text,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Yangi karta muvaffaqiyatli qo'shildi:\n`{msg.text}`", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_change_bal")
async def admin_change_bal_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_add_bal_user)
    await call.message.answer("Balansini o'zgartirmoqchi bo'lgan foydalanuvchining **Telegram ID** raqamini kiriting:")

@dp.message(Form.waiting_for_add_bal_user)
async def process_bal_user(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("ID faqat raqamlardan iborat bo'ladi!")
    await state.update_data(target_user_id=int(msg.text))
    await state.set_state(Form.waiting_for_add_bal_amount)
    await msg.answer("Qancha **AEXCoin** qo'shmoqchisiz?:")

@dp.message(Form.waiting_for_add_bal_amount)
async def process_bal_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text)
    except ValueError:
        return await msg.answer("Noto'g'ri summa kiritildi!")
        
    data = await state.get_data()
    target_id = data['target_user_id']
    
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id), commit=True)
    await state.clear()
    await msg.answer(f"✅ ID `{target_id}` balansiga {amount} AEXCoin o'zgartirildi.")

# --- Admin Xizmatlar Qo'shish ---
@dp.callback_query(F.data == "admin_add_shop")
async def admin_add_shop_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_shop_item_name)
    await call.message.answer("Xizmat nomini kiriting (Masalan: `Telegram Premium 1 oy`):")

@dp.message(Form.waiting_for_shop_item_name)
async def process_shop_name(msg: types.Message, state: FSMContext):
    await state.update_data(shop_name=msg.text)
    await state.set_state(Form.waiting_for_shop_item_price)
    await msg.answer("Ushbu xizmat necha AEXCoin bo'lsin?:")

@dp.message(Form.waiting_for_shop_item_price)
async def process_shop_price(msg: types.Message, state: FSMContext):
    try:
        price = float(msg.text)
    except ValueError:
        return await msg.answer("Narxni faqat raqamlarda kiriting!")
    
    data = await state.get_data()
    db_query("INSERT INTO shop_items (name, price) VALUES (?, ?)", (data['shop_name'], price), commit=True)
    await state.clear()
    await msg.answer(f"✅ Yangi xizmat qo'shildi: **{data['shop_name']}** — {price} AEXCoin", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_delete_shop")
async def admin_del_shop(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    items = db_query("SELECT id, name FROM shop_items", fetchall=True)
    if not items:
        return await call.answer("O'chirish uchun xizmatlar mavjud emas!", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_item_{item_id}")] for item_id, name in items]
    await call.message.answer("O'chirmoqchi bo'lgan xizmatni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_item_"))
async def process_del_item(call: types.CallbackQuery):
    item_id = int(call.data.replace("del_item_", ""))
    db_query("DELETE FROM shop_items WHERE id = ?", (item_id,), commit=True)
    await call.answer("Xizmat o'chirildi!", show_alert=True)
    await call.message.delete()

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
