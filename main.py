import os
import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, 
    LabeledPrice, PreCheckoutQuery,
    SwitchInlineQueryChosenChat
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN", "8880269827:AAFrLdxPWnz4fEU4GMw8PkY6b_2KUrvF5b8")
ADMIN_ID = 8694110588

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Faol o'yinlarni saqlash
active_games = {}

class Form(StatesGroup):
    waiting_for_deposit = State()
    waiting_for_add_bal_user = State()
    waiting_for_add_bal_amount = State()
    waiting_for_card = State()
    waiting_for_shop_item_name = State()
    waiting_for_shop_item_price = State()
    waiting_for_channel = State()

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

async def check_subscription(user_id: int):
    channel = db_query("SELECT value FROM settings WHERE key = 'channel'", fetchone=True)
    if not channel or not channel[0]:
        return True
    
    channel_username = channel[0].replace("@", "")
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
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

def admin_reply_keyboard():
    channel = db_query("SELECT value FROM settings WHERE key = 'channel'", fetchone=True)
    ch_status = f" ({channel[0]})" if channel and channel[0] else " (O'chirilgan)"
    
    kb = [
        [KeyboardButton(text="💳 Karta qo'shish"), KeyboardButton(text="💰 Balans boshqarish")],
        [KeyboardButton(text="🛍 Xizmat qo'shish"), KeyboardButton(text="🗑 Xizmat o'chirish")],
        [KeyboardButton(text=f"📢 Kanal ulash{ch_status}"), KeyboardButton(text="❌ Obunani o'chirish")],
        [KeyboardButton(text="⬅️ Bosh menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

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
            except Exception: pass

    await message.answer(f"Xush kelibsiz, {message.from_user.first_name}!", reply_markup=main_keyboard(u_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.answer("✅ Obuna tasdiqlandi!")
        await call.message.delete()
        await call.message.answer("Xush kelibsiz! Menyunidan foydalanishingiz mumkin.", reply_markup=main_keyboard(call.from_user.id))
    else:
        await call.answer("❌ Hali kanalga obuna bo'lmadingiz!", show_alert=True)

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
        provider_token="",
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
    except Exception: pass

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
    except Exception: pass

# --- O'YIN MANTIQI (X-O) ---
def get_xo_board(game_id, disabled=False):
    b = active_games.get(game_id, {}).get('board', [" "] * 9)
    kb = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            symbol = b[i] if b[i] != " " else "➖"
            cb = "noop" if disabled else f"xo_{game_id}_{i}"
            row.append(InlineKeyboardButton(text=symbol, callback_data=cb))
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)

def check_win(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for x, y, z in wins:
        if b[x] == b[y] == b[z] and b[x] != " ":
            return b[x]
    if " " not in b: return "Draw"
    return None

async def disable_user_old_games(user_id):
    to_del = []
    for g_id, g in active_games.items():
        if g['player_x'] == user_id or g.get('player_o') == user_id:
            to_del.append(g_id)
            if 'msg_obj' in g and g['msg_obj']:
                try:
                    await g['msg_obj'].edit_text("⚠️ **Ushbu o'yin eskirgan yoki bekor qilingan.**", reply_markup=get_xo_board(g_id, disabled=True))
                except Exception: pass
    for g_id in to_del:
        if g_id in active_games:
            del active_games[g_id]

@dp.callback_query(F.data == "noop")
async def noop_handler(call: types.CallbackQuery):
    await call.answer("O'yin yakunlangan!", show_alert=True)

@dp.message(F.text == "🤖 Bot bilan o'ynash")
async def vs_bot_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await disable_user_old_games(message.from_user.id)
    
    g_id = f"bot_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    msg = await message.answer("🤖 **Botga qarshi o'yin boshlandi!**\n\nSiz: ❌ (X-lar)\nBot: ⭕ (O-lar)\n\n👉 **Sizning navbatingiz (❌):**", parse_mode="Markdown")
    
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': '❌',
        'player_x': message.from_user.id,
        'player_x_name': message.from_user.first_name,
        'vs_bot': True,
        'msg_obj': msg
    }
    await msg.edit_reply_markup(reply_markup=get_xo_board(g_id))

@dp.message(F.text == "👥 Do'st bilan o'ynash")
async def vs_p_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await disable_user_old_games(message.from_user.id)
    
    g_id = f"pvp_{message.from_user.id}_{int(asyncio.get_event_loop().time())}"
    
    active_games[g_id] = {
        'board': [" "] * 9,
        'turn': '❌',
        'player_x': message.from_user.id,
        'player_x_name': message.from_user.first_name,
        'player_o': None,
        'player_o_name': None,
        'vs_bot': False,
        'msg_obj': None
    }
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Do'stga chaqiruv yuborish", switch_inline_query=f"play_{g_id}")],
        [InlineKeyboardButton(text="🎮 O'zim shu yerda kutaman (Sinov)", callback_data=f"join_{g_id}")]
    ])
    
    msg = await message.answer(
        f"🎮 **Yangi o'yin taklifi yaratildi!**\n\n"
        f"Pastdagi **'📩 Do'stga chaqiruv yuborish'** tugmasini bosing va o'ynamoqchi bo'lgan do'stingizni tanlang!",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    active_games[g_id]['msg_obj'] = msg

@dp.inline_query(F.query.startswith("play_"))
async def inline_game_invite(inline_query: types.InlineQuery):
    g_id = inline_query.query.replace("play_", "")
    if g_id not in active_games:
        return
        
    g = active_games[g_id]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 O'yinga qo'shilish", callback_data=f"join_{g_id}")]
    ])
    
    results = [
        types.InlineQueryResultArticle(
            id=g_id,
            title="🎮 Tic-Tac-Toe (X-O) O'yini!",
            description=f"{g['player_x_name']} sizni o'yinga taklif qilmoqda. Qo'shilish uchun bosing!",
            input_message_content=types.InputTextMessageContent(
                message_text=f"🎮 **{g['player_x_name']} bilan X-O O'yini!**\n\n❌ **Yaratuvchi:** {g['player_x_name']}\n⭕ **Raqib:** Kutilmoqda...\n\nO'yinga qo'shilish uchun tugmani bosing:",
                parse_mode="Markdown"
            ),
            reply_markup=kb
        )
    ]
    await inline_query.answer(results, cache_time=1)

@dp.callback_query(F.data.startswith("join_"))
async def join_game(call: types.CallbackQuery):
    g_id = call.data.replace("join_", "")
    if g_id not in active_games: 
        return await call.answer("Bu o'yin bekor qilingan yoki eskirgan!", show_alert=True)
        
    g = active_games[g_id]
    
    if g['player_o'] is not None:
        return await call.answer("O'yinga raqib allqachon qo'shilgan!", show_alert=True)
    
    if g['player_x'] == call.from_user.id and "inline_message_id" in call:
        return await call.answer("O'zingizga qarshi o'yna olmaysiz!", show_alert=True)
    
    g['player_o'] = call.from_user.id
    g['player_o_name'] = call.from_user.first_name
    
    await call.answer("O'yinga muvaffaqiyatli qo'shildingiz!")
    
    text = (
        f"🎮 **O'yin Boshlandi!**\n\n"
        f"❌ {g['player_x_name']}\n"
        f"⭕ {g['player_o_name']}\n\n"
        f"👉 **Navbat:** ❌ {g['player_x_name']}"
    )
    
    reply_markup = get_xo_board(g_id)
    
    if call.inline_message_id:
        g['inline_message_id'] = call.inline_message_id
        await bot.edit_message_text(inline_message_id=call.inline_message_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await call.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        g['msg_obj'] = call.message

@dp.callback_query(F.data.startswith("xo_"))
async def xo_click(call: types.CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 5: return
    g_id = f"{parts[1]}_{parts[2]}_{parts[3]}"
    idx = int(parts[4])
    
    if g_id not in active_games: 
        await call.answer("Bu o'yin eskirgan yoki tugagan!", show_alert=True)
        return
        
    g = active_games[g_id]
    u_id = call.from_user.id
    
    if g['vs_bot']:
        if u_id != g['player_x']: 
            return await call.answer("Bu sizning o'yiningiz emas!", show_alert=True)
    else:
        if g['player_o'] is None:
            return await call.answer("Raqib hali qo'shilmadi!", show_alert=True)
            
        exp_player = g['player_x'] if g['turn'] == '❌' else g['player_o']
        if u_id != exp_player: 
            return await call.answer("Hozir sizning navbatingiz emas!", show_alert=True)
        
    if g['board'][idx] != " ": 
        return await call.answer("Bu katak allaqachon band!", show_alert=True)
    
    await call.answer()
    
    # Yurish
    g['board'][idx] = g['turn']
    res = check_win(g['board'])
    
    if res: 
        return await finish_game(g_id, res)

    # Botga qarshi
    if g['vs_bot']:
        empty_spots = [i for i, val in enumerate(g['board']) if val == " "]
        if empty_spots:
            g['board'][random.choice(empty_spots)] = '⭕'
            res_b = check_win(g['board'])
            if res_b: 
                return await finish_game(g_id, res_b)
                
        await g['msg_obj'].edit_text(
            f"🤖 **Bot bilan o'yin!**\n\n"
            f"Siz: ❌\nBot: ⭕\n\n"
            f"👉 **Sizning navbatingiz (❌):**",
            reply_markup=get_xo_board(g_id),
            parse_mode="Markdown"
        )
    else:
        # PvP (Do'st bilan)
        g['turn'] = '⭕' if g['turn'] == '❌' else '❌'
        curr_name = g['player_x_name'] if g['turn'] == '❌' else g['player_o_name']
        text = (
            f"🎮 **O'yin ketmoqda!**\n\n"
            f"❌ {g['player_x_name']}\n"
            f"⭕ {g['player_o_name']}\n\n"
            f"👉 **Navbat:** {g['turn']} {curr_name}"
        )
        reply_markup = get_xo_board(g_id)
        
        if 'inline_message_id' in g:
            await bot.edit_message_text(inline_message_id=g['inline_message_id'], text=text, reply_markup=reply_markup, parse_mode="Markdown")
        elif g.get('msg_obj'):
            await g['msg_obj'].edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def finish_game(g_id, winner):
    g = active_games.get(g_id, {})
    px, po = g.get('player_x'), g.get('player_o')
    px_name = g.get('player_x_name', 'O\'yinchi')
    po_name = g.get('player_o_name', 'Bot' if g.get('vs_bot') else 'O\'yinchi')
    
    if winner == "Draw":
        txt = f"🤝 **O'yin Durang bilan yakunlandi!**\n\nHech kim ochko olmadi."
        if px: db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (px,), commit=True)
        if po and not g.get('vs_bot'): db_query("UPDATE users SET draws = draws + 1 WHERE user_id = ?", (po,), commit=True)
    elif winner == '❌':
        txt = f"🎉 **G'alaba!** ❌ `{px_name}` o'yinda yutdi!\n\n❌ **Yutdi:** {px_name} (+1 g'alaba)\n⭕ **Yutqazdi:** {po_name}"
        if px: db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (px,), commit=True)
        if po and not g.get('vs_bot'): db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (po,), commit=True)
    else:
        txt = f"🎉 **G'alaba!** ⭕ `{po_name}` o'yinda yutdi!\n\n⭕ **Yutdi:** {po_name} (+1 g'alaba)\n❌ **Yutqazdi:** {px_name}"
        if px: db_query("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (px,), commit=True)
        if po and not g.get('vs_bot'): db_query("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (po,), commit=True)
        
    reply_markup = get_xo_board(g_id, disabled=True)
    
    try:
        if 'inline_message_id' in g:
            await bot.edit_message_text(inline_message_id=g['inline_message_id'], text=txt, reply_markup=reply_markup, parse_mode="Markdown")
        elif g.get('msg_obj'):
            await g['msg_obj'].edit_text(txt, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception: pass

    if g_id in active_games:
        del active_games[g_id]

# --- ADMIN PANEL ---
@dp.message(F.text == "⚙️ Admin Panel")
async def adm_cmd_button(msg: types.Message, state: FSMContext):
    await state.clear()
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("⚙️ **Admin Paneliga xush kelibsiz:**\nBoshqaruv tugmasini tanlang:", reply_markup=admin_reply_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "⬅️ Bosh menyu")
async def back_to_main(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Bosh menyudasiz:", reply_markup=main_keyboard(msg.from_user.id))

@dp.message(F.text == "💳 Karta qo'shish")
async def admin_add_card_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_card)
    await msg.answer("Yangi karta raqami va egalari ismini kiriting:")

@dp.message(Form.waiting_for_card)
async def process_add_card(msg: types.Message, state: FSMContext):
    db_query("INSERT INTO cards (card_number) VALUES (?)", (msg.text,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Yangi karta qo'shildi:\n`{msg.text}`", parse_mode="Markdown", reply_markup=admin_reply_keyboard())

@dp.message(F.text == "💰 Balans boshqarish")
async def admin_change_bal_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_add_bal_user)
    await msg.answer("Foydalanuvchining **Telegram ID** raqamini kiriting:")

@dp.message(Form.waiting_for_add_bal_user)
async def process_bal_user(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("ID faqat raqam bo'ladi!")
    await state.update_data(target_user_id=int(msg.text))
    await state.set_state(Form.waiting_for_add_bal_amount)
    await msg.answer("Qancha **AEXCoin** qo'shmoqchisiz?:")

@dp.message(Form.waiting_for_add_bal_amount)
async def process_bal_amount(msg: types.Message, state: FSMContext):
    try: amount = float(msg.text)
    except Exception: return await msg.answer("Noto'g'ri summa!")
    data = await state.get_data()
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, data['target_user_id']), commit=True)
    await state.clear()
    await msg.answer("✅ Balans o'zgartirildi.", reply_markup=admin_reply_keyboard())

@dp.message(F.text == "🛍 Xizmat qo'shish")
async def admin_add_shop_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_shop_item_name)
    await msg.answer("Xizmat nomini kiriting:")

@dp.message(Form.waiting_for_shop_item_name)
async def process_shop_name(msg: types.Message, state: FSMContext):
    await state.update_data(shop_name=msg.text)
    await state.set_state(Form.waiting_for_shop_item_price)
    await msg.answer("Narxini kiriting (AEXCoin):")

@dp.message(Form.waiting_for_shop_item_price)
async def process_shop_price(msg: types.Message, state: FSMContext):
    try: price = float(msg.text)
    except Exception: return await msg.answer("Faqat raqam kiriting!")
    data = await state.get_data()
    db_query("INSERT INTO shop_items (name, price) VALUES (?, ?)", (data['shop_name'], price), commit=True)
    await state.clear()
    await msg.answer("✅ Xizmat qo'shildi.", reply_markup=admin_reply_keyboard())

@dp.message(F.text == "🗑 Xizmat o'chirish")
async def admin_del_shop(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    items = db_query("SELECT id, name FROM shop_items", fetchall=True)
    if not items: return await msg.answer("Xizmatlar yo'q!")
    kb = [[InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_item_{item_id}")] for item_id, name in items]
    await msg.answer("O'chiriladigan xizmatni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_item_"))
async def process_del_item(call: types.CallbackQuery):
    db_query("DELETE FROM shop_items WHERE id = ?", (int(call.data.replace("del_item_", "")),), commit=True)
    await call.answer("O'chirildi!", show_alert=True)
    await call.message.delete()

@dp.message(F.text.startswith("📢 Kanal ulash"))
async def admin_set_channel_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(Form.waiting_for_channel)
    await msg.answer("Kanal username'ini kiriting (Masalan: `@my_channel`):")

@dp.message(Form.waiting_for_channel)
async def process_set_channel(msg: types.Message, state: FSMContext):
    ch = msg.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel', ?)", (ch,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Majburiy obuna kanali o'rnatildi: {ch}", reply_markup=admin_reply_keyboard())

@dp.message(F.text == "❌ Obunani o'chirish")
async def admin_remove_channel_handler(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    db_query("DELETE FROM settings WHERE key = 'channel'", commit=True)
    await msg.answer("✅ Majburiy obuna kanali o'chirib tashlandi!", reply_markup=admin_reply_keyboard())

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
