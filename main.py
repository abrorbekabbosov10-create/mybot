import os
import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- Telegram ID va Token ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8880269827:AAFrLdxPWnz4fEU4GMw8PkY6b_2KUrvF5b8")
ADMIN_ID = 8694110588

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

active_games = {}

class Form(StatesGroup):
    waiting_for_deposit = State()
    waiting_for_add_bal_user = State()
    waiting_for_add_bal_amount = State()
    waiting_for_card = State()
    waiting_for_shop_item_name = State()
    waiting_for_shop_item_price = State()
    waiting_for_channel = State()

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
    cursor.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY AUTOINCREMENT, card_number TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS shop_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
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

# --- Majburiy Obuna ---
async def check_subscription(user_id: int):
    channel = db_query("SELECT value FROM settings WHERE key = 'channel'", fetchone=True)
    if not channel or not channel[0]:
        return True
    
    channel_username = channel[0].replace("@", "")
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        return True

def sub_keyboard(channel_username):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{channel_username.replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
        ]
    )

def get_rank(wins, balance):
    if wins >= 100 and balance >= 30000:
        return "👑 X-O Qiroli"
    elif wins >= 100 and balance < 30000:
        return "💎 Olmos Afsona"
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
def main_keyboard(user_id: int):
    kb = [
        [KeyboardButton(text="🤖 Bot bilan o'ynash"), KeyboardButton(text="👥 Do'st bilan o'ynash")],
        [KeyboardButton(text="👤 Profil & Statistika"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="👥 Taklif qilish"), KeyboardButton(text="💳 Hisob to'ldirish")],
        [KeyboardButton(text="🛍 AEXCoin ishlatish")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta qo'shish", callback_data="admin_add_card")],
            [InlineKeyboardButton(text="💰 Balans boshqarish", callback_data="admin_change_bal")],
            [InlineKeyboardButton(text="🛍 Xizmat qo'shish", callback_data="admin_add_shop")],
            [InlineKeyboardButton(text="🗑 Xizmat o'chirish", callback_data="admin_delete_shop")],
            [InlineKeyboardButton(text="📢 Majburiy obuna kanali", callback_data="admin_set_channel")]
        ]
    )

# --- Start Handler ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    u_id = message.from_user.id
    u_name = message.from_user.username or message.from_user.first_name
    
    if not await check_subscription(u_id):
        channel = db_query("SELECT value FROM settings WHERE key = 'channel'", fetchone=True)[0]
        return await message.answer("⚠️ Botdan foydalanish uchun kanalimizga obuna bo'ling:", reply_markup=sub_keyboard(channel))

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

    await message.answer(f"Xush kelibsiz, {message.from_user.first_name}!", reply_markup=main_keyboard(u_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.answer("✅ Obuna tasdiqlandi!")
        await call.message.delete()
        await call.message.answer("Xush kelibsiz! Menyunidan foydalanishingiz mumkin.", reply_markup=main_keyboard(call.from_user.id))
    else:
        await call.answer("❌ Hali kanalga obuna bo'lmadingiz!", show_alert=True)

# --- Profil va Statistika ---
@dp.message(F.text == "👤 Profil & Statistika")
async def profile_handler(message: types.Message, state: FSMContext):
    await state.clear()
    if not await check_subscription(message.from_user.id):
        channel = db_query("SELECT value FROM settings WHERE key = 'channel'", fetchone=True)[0]
        return await message.answer("⚠️ Botdan foydalanish uchun kanalimizga obuna bo'ling:", reply_markup=sub_keyboard(channel))

    u = db_query("SELECT balance, wins, losses, draws FROM users WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    balance, wins, losses, draws = u[0] if u else 0.0, u[1] if u else 0, u[2] if u else 0, u[3] if u else 0
    total_games = wins + losses + draws
    
    text = (
        f"👤 **Sizning profilingiz:**\n\n"
        f"🎖 **Daraja:** {get_rank(wins, balance)}\n"
        f"💰 **Balans:** {balance:,.0f} AEXCoin\n\n"
        f"📊 **Statistika:**\n"
        f"🎮 Jami o'yinlar: {total_games}\n"
        f"🥇 G'alabalar: {wins}\n"
        f"❌ Mag'lubiyatlar: {losses}\n"
        f"🤝 Duranglar: {draws}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 Taklif qilish")
async def invite_handler(message: types.Message, state: FSMContext):
    await state.clear()
    me = await bot.get_me()
    await message.answer(f"👥 Do'stlarni taklif qiling va 500 AEXCoin oling:\nhttps://t.me/{me.username}?start={message.from_user.id}")

@dp.message(F.text == "🏆 Reyting")
async def top_handler(message: types.Message, state: FSMContext):
    await state.clear()
    top = db_query("SELECT username, wins, balance FROM users ORDER BY wins DESC LIMIT 10", fetchall=True)
    text = "🏆 **Eng kuchli o'yinchilar:**\n\n"
    if top:
        for idx, (name, wins, balance) in enumerate(top, 1):
            text += f"{idx}. @{name} — {wins} g'alaba ({get_rank(wins, balance)})\n"
    else:
        text += "Hozircha o'yinchilar yo'q."
    await message.answer(text, parse_mode="Markdown")

# --- HISOB TO'LDIRISH BO'LIMI (STARS VA PUL TANLOVI) ---
@dp.message(F.text == "💳 Hisob to'ldirish")
async def deposit_menu(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Telegram Stars orqali", callback_data="dep_stars_menu")],
            [InlineKeyboardButton(text="💳 So'm (Karta) orqali", callback_data="dep_card_menu")]
        ]
    )
    await message.answer("To'lov usulini tanlang:", reply_markup=kb)

# 1. Telegram Stars Orqali To'lov
@dp.callback_query(F.data == "dep_stars_menu")
async def dep_stars_menu_handler(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 1 Star (150 AEXCoin)", callback_data="buy_stars_1")],
            [InlineKeyboardButton(text="⭐ 5 Stars (750 AEXCoin)", callback_data="buy_stars_5")],
            [InlineKeyboardButton(text="⭐ 10 Stars (1 500 AEXCoin)", callback_data="buy_stars_10")],
            [InlineKeyboardButton(text="⭐ 50 Stars (7 500 AEXCoin)", callback_data="buy_stars_50")],
            [InlineKeyboardButton(text="⭐ 100 Stars (15 000 AEXCoin)", callback_data="buy_stars_100")]
        ]
    )
    await call.message.edit_text("⭐ **Telegram Stars orqali hisob to'ldirish:**\n\nKurs: **1 Star = 150 AEXCoin**\n\nPaketni tanlang:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars_invoice(call: types.CallbackQuery):
    stars_count = int(call.data.replace("buy_stars_", ""))
    aex_amount = stars_count * 150
    
    prices = [LabeledPrice(label=f"{aex_amount} AEXCoin", amount=stars_count)]
    
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"{aex_amount:,.0f} AEXCoin sotib olish",
        description=f"{stars_count} Telegram Stars evaziga {aex_amount:,.0f} AEXCoin balansingizga qo'shiladi.",
        payload=f"stars_deposit_{stars_count}_{aex_amount}",
        provider_token="",  # Telegram Stars uchun tokenni bo'sh qoldiriladi
        currency="XTR",
        prices=prices
    )
    await call.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("stars_deposit_"):
        parts = payload.split("_")
        aex_amount = float(parts[3])
        u_id = message.from_user.id
        
        db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (aex_amount, u_id), commit=True)
        await message.answer(f"🎉 **To'lov muvaffaqiyatli amalga oshirildi!**\nHisobingizga **{aex_amount:,.0f} AEXCoin** qo'shildi.", parse_mode="Markdown")

# 2. So'm (Karta) Orqali To'lov
@dp.callback_query(F.data == "dep_card_menu")
async def dep_card_menu_handler(call: types.CallbackQuery, state: FSMContext):
    cards = db_query("SELECT card_number FROM cards", fetchall=True)
    if not cards:
        return await call.answer("Hozircha to'lov kartalari kiritilmagan.", show_alert=True)
        
    card_text = "\n".join([f"💳 `{c[0]}`" for c in cards])
    await state.set_state(Form.waiting_for_deposit)
    await call.message.edit_text(
        f"💵 **Kurs:** 1 So'm = 1 AEXCoin\n\n"
        f"To'lov uchun kartalar:\n{card_text}\n\n"
        f"Qancha **so'm** o'tkazganingizni yozib yuboring (Bot avtomatik AEXCoin hisoblaydi):",
        parse_mode="Markdown"
    )

@dp.message(Form.waiting_for_deposit)
async def proc_dep(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): 
        return await msg.answer("Faqat raqam kiriting!")
    
    amount = int(msg.text)
    await state.clear()
    await msg.answer(f"✅ So'rov yuborildi!\nKiritilgan summa: {amount:,.0f} so'm\nHisobingizga qo'shiladi: **{amount:,.0f} AEXCoin**", parse_mode="Markdown")
    try:
        await bot.send_message(ADMIN_ID, f"💳 **Hisob to'ldirish so'rovi:**\nFoydalanuvchi: @{msg.from_user.username} (ID: `{msg.from_user.id}`)\nSumma: {amount:,.0f} so'm ({amount:,.0f} AEXCoin)", parse_mode="Markdown")
    except: pass

# --- AEXCoin Ishlatish (Do'kon) ---
@dp.message(F.text == "🛍 AEXCoin ishlatish")
async def shop_user_handler(message: types.Message, state: FSMContext):
    await state.clear()
    items = db_query("SELECT id, name, price FROM shop_items", fetchall=True)
    if not items:
        return await message.answer("🛍 Hozircha xizmatlar yo'q.")
    
    text = "🛍 **AEXCoin xizmatlar do'koni:**\n\n"
    kb = []
    for item_id, name, price in items:
        text += f"🔹 **{name}** — {price:,.0f} AEXCoin\n"
        kb.append([InlineKeyboardButton(text=f"Sotib olish: {name}", callback_data=f"buy_shop_{item_id}")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_shop_"))
async def buy_shop_item(call: types.CallbackQuery):
    item_id = int(call.data.replace("buy_shop_", ""))
    item = db_query("SELECT name, price FROM shop_items WHERE id = ?", (item_id,), fetchone=True)
    if not item: return await call.answer("Xizmat topilmadi!", show_alert=True)
    
    u = db_query("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,), fetchone=True)
    user_bal = u[0] if u else 0.0
    name, price = item[0], item[1]
    
    if user_bal < price:
        return await call.answer(f"Mablag' yetarli emas! Sizda {user_bal:,.0f} AEXCoin bor.", show_alert=True)
    
    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, call.from_user.id), commit=True)
    await call.answer("So'rov yuborildi!", show_alert=True)
    await call.message.answer(f"✅ `{name}` xarid qilindi! So'rov adminga yetkazildi.", parse_mode="Markdown")
    try:
        await bot.send_message(ADMIN_ID, f"🛍 **Yangi buyurtma!**\nFoydalanuvchi: @{call.from_user.username} (ID: `{call.from_user.id}`)\nXizmat: {name}", parse_mode="Markdown")
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
async def vs_bot_handler(message: types.Message, state: FSMContext):
    await state.clear()
    g_id = f"bot_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {'board': [" "] * 9, 'turn': '❌', 'player_x': message.from_user.id, 'vs_bot': True}
    await message.answer("🤖 Botga qarshi o'yin boshlandi!\nSiz: ❌\nNavbatingiz:", reply_markup=get_xo_board(g_id))

@dp.message(F.text == "👥 Do'st bilan o'ynash")
async def vs_p_handler(message: types.Message, state: FSMContext):
    await state.clear()
    g_id = f"pvp_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    active_games[g_id] = {'board': [" "] * 9, 'turn': '❌', 'player_x': message.from_user.id, 'player_o': None, 'vs_bot': False}
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Qo'shilish", callback_data=f"join_{g_id}")]])
    await message.answer("🎮 Yangi o'yin yaratildi! Raqib tugmani bosishini kuting:", reply_markup=kb)

@dp.callback_query(F.data.startswith("join_"))
async def join_game(call: types.CallbackQuery):
    g_id = call.data.replace("join_", "")
    if g_id not in active_games: return await call.answer("O'yin yakunlangan!", show_alert=True)
    g = active_games[g_id]
    if g['player_x'] == call.from_user.id: return await call.answer("O'zingizga qarshi o'ynay olmaysiz!", show_alert=True)
    g['player_o'] = call.from_user.id
    await call.answer("O'yinga qo'shildingiz!")
    await call.message.edit_text("🎮 O'yin boshlandi!\n❌ - Yaratuvchi | ⭕ - Raqib\nNavbat: ❌", reply_markup=get_xo_board(g_id))

@dp.callback_query(F.data.startswith("xo_"))
async def xo_click(call: types.CallbackQuery):
    parts = call.data.split("_")
    g_id = f"{parts[1]}_{parts[2]}_{parts[3]}"
    idx = int(parts[4])
    
    if g_id not in active_games: return await call.answer("O'yin yakunlangan!", show_alert=True)
    g = active_games[g_id]
    u_id = call.from_user.id
    
    if g['vs_bot'] and u_id != g['player_x']: return await call.answer("Bu sizning o'yiningiz emas!", show_alert=True)
    if not g['vs_bot']:
        exp = g['player_x'] if g['turn'] == '❌' else g['player_o']
        if u_id != exp: return await call.answer("Hozir sizning navbatingiz emas!", show_alert=True)
        
    if g['board'][idx] != " ": return await call.answer("Katak band!", show_alert=True)
    
    await call.answer()
    g['board'][idx] = g['turn']
    res = check_win(g['board'])
    
    if res: return await finish_game(call.message, g_id, res)

    if g['vs_bot']:
        empty_spots = [i for i, val in enumerate(g['board']) if val == " "]
        if empty_spots:
            g['board'][random.choice(empty_spots)] = '⭕'
            res_b = check_win(g['board'])
            if res_b: return await finish_game(call.message, g_id, res_b)
        await call.message.edit_text("Sizning navbatingiz: ❌", reply_markup=get_xo_board(g_id))
    else:
        g['turn'] = '⭕' if g['turn'] == '❌' else '❌'
        await call.message.edit_text(f"Navbat: {g['turn']}", reply_markup=get_xo_board(g_id))

async def finish_game(msg, g_id, winner):
    g = active_games[g_id]
    px, po = g['player_x'], g.get('player_o')
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

# --- ADMIN PANEL ---
@dp.message(F.text == "⚙️ Admin Panel")
async def adm_cmd_button(msg: types.Message, state: FSMContext):
    await state.clear()
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("⚙️ **Admin paneli:**", reply_markup=admin_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_add_card")
async def admin_add_card_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_card)
    await call.message.answer("Yangi karta raqami va egalari ismini kiriting:")

@dp.message(Form.waiting_for_card)
async def process_add_card(msg: types.Message, state: FSMContext):
    db_query("INSERT INTO cards (card_number) VALUES (?)", (msg.text,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Yangi karta qo'shildi:\n`{msg.text}`", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_change_bal")
async def admin_change_bal_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_add_bal_user)
    await call.message.answer("Foydalanuvchining **Telegram ID** raqamini kiriting:")

@dp.message(Form.waiting_for_add_bal_user)
async def process_bal_user(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("ID faqat raqam bo'ladi!")
    await state.update_data(target_user_id=int(msg.text))
    await state.set_state(Form.waiting_for_add_bal_amount)
    await msg.answer("Qancha **AEXCoin** qo'shmoqchisiz?:")

@dp.message(Form.waiting_for_add_bal_amount)
async def process_bal_amount(msg: types.Message, state: FSMContext):
    try: amount = float(msg.text)
    except: return await msg.answer("Noto'g'ri summa!")
    data = await state.get_data()
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, data['target_user_id']), commit=True)
    await state.clear()
    await msg.answer(f"✅ Balans o'zgartirildi.")

@dp.callback_query(F.data == "admin_add_shop")
async def admin_add_shop_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_shop_item_name)
    await call.message.answer("Xizmat nomini kiriting:")

@dp.message(Form.waiting_for_shop_item_name)
async def process_shop_name(msg: types.Message, state: FSMContext):
    await state.update_data(shop_name=msg.text)
    await state.set_state(Form.waiting_for_shop_item_price)
    await msg.answer("Narxini kiriting (AEXCoin):")

@dp.message(Form.waiting_for_shop_item_price)
async def process_shop_price(msg: types.Message, state: FSMContext):
    try: price = float(msg.text)
    except: return await msg.answer("Faqat raqam kiriting!")
    data = await state.get_data()
    db_query("INSERT INTO shop_items (name, price) VALUES (?, ?)", (data['shop_name'], price), commit=True)
    await state.clear()
    await msg.answer("✅ Xizmat qo'shildi.")

@dp.callback_query(F.data == "admin_delete_shop")
async def admin_del_shop(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    items = db_query("SELECT id, name FROM shop_items", fetchall=True)
    if not items: return await call.answer("Xizmatlar yo'q!", show_alert=True)
    kb = [[InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_item_{item_id}")] for item_id, name in items]
    await call.message.answer("O'chiriladigan xizmatni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_item_"))
async def process_del_item(call: types.CallbackQuery):
    db_query("DELETE FROM shop_items WHERE id = ?", (int(call.data.replace("del_item_", "")),), commit=True)
    await call.answer("O'chirildi!", show_alert=True)
    await call.message.delete()

@dp.callback_query(F.data == "admin_set_channel")
async def admin_set_channel_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_channel)
    await call.message.answer("Kanal username'ini kiriting (Masalan: `@my_channel`):")

@dp.message(Form.waiting_for_channel)
async def process_set_channel(msg: types.Message, state: FSMContext):
    ch = msg.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel', ?)", (ch,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Majburiy obuna kanali o'rnatildi: {ch}")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
