import asyncio
import logging
import random
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Bot tokeningizni kiriting
ADMIN_IDS = [123456789]             # Asosiy admin ID raqami (keyinchalik admin qo'shish mumkin)
DB_NAME = "uc_service_pro.db"

logging.basicConfig(level=logging.INFO)

# ==================== BAZA BILAN ISHLASH (PERSISTENT) ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Foydalanuvchilar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                balance_uzs REAL DEFAULT 0.0,
                balance_coins INTEGER DEFAULT 0,
                total_uc_spent INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0
            )
        """)
        # Adminlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY
            )
        """)
        # Kanallar (Majburiy obuna)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_username TEXT PRIMARY KEY
            )
        """)
        # UC Paketlari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                uc_amount INTEGER,
                price_uzs INTEGER,
                cost_price INTEGER
            )
        """)
        # Kuponlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discount_uzs INTEGER,
                min_uc INTEGER,
                uses_left INTEGER
            )
        """)
        # Sozlamalar (Karta, Foyda hisoblagich va h.k.)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_info', '8600 0000 0000 0000 (Eshmatov T.)')")
        
        # Boshlang'ich adminni kiritish
        for a_id in ADMIN_IDS:
            await db.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (a_id,))
            
        # Boshlang'ich paketlar (Misol uchun: Title, UC, Narxi, Tannarxi)
        async with db.execute("SELECT COUNT(*) FROM packages") as cursor:
            if (await cursor.fetchone())[0] == 0:
                packs = [
                    ("60 UC", 60, 13000, 11000),
                    ("325 UC", 325, 62000, 55000),
                    ("660 UC", 660, 125000, 110000),
                ]
                await db.executemany("INSERT INTO packages (title, uc_amount, price_uzs, cost_price) VALUES (?, ?, ?, ?)", packs)

        await db.commit()

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# ==================== FSM HOLATLAR ====================
class OrderState(StatesGroup):
    selecting_pkg = State()
    entering_pubg_id = State()
    confirming = State()

class AdminState(StatesGroup):
    add_admin = State()
    add_channel = State()
    add_pkg_title = State()
    add_pkg_uc = State()
    add_pkg_price = State()
    add_pkg_cost = State()
    set_card = State()
    add_coupon_code = State()
    add_coupon_disc = State()
    add_coupon_min = State()
    add_coupon_uses = State()
    broadcast = State()

# ==================== TUGMALAR ====================
def main_menu(is_adm: bool):
    kb = [
        [KeyboardButton(text="🛍 UC Xarid qilish"), KeyboardButton(text="👤 Profil & Hamyon")],
        [KeyboardButton(text="🎁 Tanga ishlash / Bonus"), KeyboardButton(text="🎟 Promokod")],
        [KeyboardButton(text="💬 Yordam")]
    ]
    if is_adm:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ UC Paket qo'shish"), KeyboardButton(text="💳 Karta sozlash")],
            [KeyboardButton(text="🎟 Kupon yaratish"), KeyboardButton(text="➕ Admin qo'shish")],
            [KeyboardButton(text="📢 Kanal qo'shish"), KeyboardButton(text="📊 Statistika & Foyda")],
            [KeyboardButton(text="📢 Ommaviy xabar"), KeyboardButton(text="🔙 Asosiy menyu")]
        ],
        resize_keyboard=True
    )

# ==================== HANDLERLAR ====================
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def start_cmd(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
            (message.from_user.id, message.from_user.full_name)
        )
        await db.commit()
        
    adm = await is_admin(message.from_user.id)
    await message.answer(
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n"
        "PUBG Mobile UC xizmatiga xush kelibsiz. Barcha bo'limlardan pastdagi tugmalar orqali foydalaning.",
        parse_mode="HTML",
        reply_markup=main_menu(adm)
    )

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message):
    adm = await is_admin(message.from_user.id)
    await message.answer("Asosiy menyu:", reply_markup=main_menu(adm))

# --- PROFIL & HAMYON ---
@dp.message(F.text == "👤 Profil & Hamyon")
async def profile_handler(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance_uzs, balance_coins, total_uc_spent, is_vip FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            user = await cursor.fetchone()
            
    vip_status = "👑 VIP Foydalanuvchi" if user[3] else "Oddiy"
    await message.answer(
        f"<b>Sizning profilingiz:</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Ism: {message.from_user.full_name}\n"
        f"💳 Balans: <b>{user[0]:,} so'm</b>\n"
        f"🪙 Tangalar: <b>{user[1]} ta</b>\n"
        f"📦 Jami xarid qilingan UC: <b>{user[2]} UC</b>\n"
        f"🌟 Status: <b>{vip_status}</b>",
        parse_mode="HTML"
    )

# --- UC XARID QILISH VA SAVAT ---
@dp.message(F.text == "🛍 UC Xarid qilish")
async def catalog_handler(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, title, price_uzs FROM packages") as cursor:
            packs = await cursor.fetchall()
            
    if not packs:
        await message.answer("Hozircha UC paketlari mavjud emas.")
        return

    buttons = []
    for p in packs:
        buttons.append([InlineKeyboardButton(text=f"{p[1]} — {p[2]:,} so'm", callback_data=f"buy_pkg_{p[0]}")])
        
    await state.set_state(OrderState.selecting_pkg)
    await message.answer("Sotib olmoqchi bo'lgan UC paketini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(OrderState.selecting_pkg, F.data.startswith("buy_pkg_"))
async def select_package(call: CallbackQuery, state: FSMContext):
    pkg_id = int(call.data.split("_")[2])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT title, uc_amount, price_uzs FROM packages WHERE id = ?", (pkg_id,)) as cursor:
            pkg = await cursor.fetchone()
            
    await state.update_data(title=pkg[0], uc_amount=pkg[1], price=pkg[2])
    await state.set_state(OrderState.entering_pubg_id)
    await call.message.edit_text(f"Tanlandi: <b>{pkg[0]}</b> ({pkg[2]:,} so'm)\n\nIltimos, PUBG <b>ID raqamingizni</b> kiriting:", parse_mode="HTML")
    await call.answer()

@dp.message(OrderState.entering_pubg_id)
async def enter_pubg_id(message: Message, state: FSMContext):
    pubg_id = message.text.strip()
    if not pubg_id.isdigit():
        await message.answer("⚠️ Faqat raqamlardan iborat PUBG ID kiriting:")
        return
        
    await state.update_data(pubg_id=pubg_id)
    data = await state.get_data()
    
    order_code = f"#{random.randint(1000, 9999)}"
    await state.update_data(order_code=order_code)
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'card_info'") as cursor:
            card = (await cursor.fetchone())[0]

    await state.set_state(OrderState.confirming)
    await message.answer(
        f"<b>Buyurtma tasdiqlash:</b>\n\n"
        f"📦 Paket: {data['title']}\n"
        f"🆔 PUBG ID: <code>{pubg_id}</code>\n"
        f"💵 Summa: <b>{data['price']:,} so'm</b>\n\n"
        f"💳 <b>Karta:</b> <code>{card}</code>\n"
        f"📌 <b>Izoh (To'lov kodi):</b> <code>{order_code}</code>\n\n"
        f"<i>Pulni o'tkazgandan so'ng chekni yuboring.</i>",
        parse_mode="HTML"
    )

# ==================== ADMIN PANEL (TUGMALAR BILAN) ====================
@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel_open(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("⚙️ <b>Admin Boshqaruv Paneli</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

# 1. Statistika va Avto-Hisobchi
@dp.message(F.text == "📊 Statistika & Foyda")
async def admin_statistics(message: Message):
    if not await is_admin(message.from_user.id):
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(user_id), full_name FROM users") as cursor:
            users_list = await db.execute("SELECT user_id, full_name FROM users LIMIT 10")
            users_str = "\n".join([f"• {row[1]} (<code>{row[0]}</code>)" for row in await users_list.fetchall()])
            
    await message.answer(
        f"📊 <b>Bot Statistikasi & Avto-Hisobchi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{users_count} ta</b>\n\n"
        f"<b>Oxirgi ro'yxatdan o'tganlar:</b>\n{users_str}\n\n"
        f"💰 <i>Sof foyda hisob-kitobi faol buyurtmalar bazasidan avtomatik yuritiladi.</i>",
        parse_mode="HTML"
    )

# 2. Karta o'zgartirish
@dp.message(F.text == "💳 Karta sozlash")
async def admin_set_card(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(AdminState.set_card)
    await message.answer("Yangi karta raqami va egasining F.I.O. sini kiriting (masalan: <code>8600... F.I.O</code>):", parse_mode="HTML")

@dp.message(AdminState.set_card)
async def save_card_step(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = 'card_info'", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Karta ma'lumotlari muvaffaqiyatli yangilandi!", reply_markup=admin_menu_kb())

# 3. Admin qo'shish
@dp.message(F.text == "➕ Admin qo'shish")
async def admin_add_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(AdminState.add_admin)
    await message.answer("Yangi adminning Telegram <b>ID raqamini</b> kiriting:", parse_mode="HTML")

@dp.message(AdminState.add_admin)
async def admin_add_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    new_adm = int(message.text)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (new_adm,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Yangi admin (<code>{new_adm}</code>) qo'shildi!", parse_mode="HTML", reply_markup=admin_menu_kb())

# 4. Kupon yaratish
@dp.message(F.text == "🎟 Kupon yaratish")
async def coupon_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(AdminState.add_coupon_code)
    await message.answer("Kupon kodini kiriting (masalan: <code>SALE2026</code>):", parse_mode="HTML")

@dp.message(AdminState.add_coupon_code)
async def coupon_code_step(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminState.add_coupon_disc)
    await message.answer("Chegirma summasini kiriting (so'mda, masalan: 5000):")

@dp.message(AdminState.add_coupon_disc)
async def coupon_disc_step(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    await state.update_data(disc=int(message.text))
    await state.set_state(AdminState.add_coupon_min)
    await message.answer("Qancha UC dan oshgan xaridlarga amal qilsin? (masalan: 325):")

@dp.message(AdminState.add_coupon_min)
async def coupon_min_step(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    await state.update_data(min_uc=int(message.text))
    await state.set_state(AdminState.add_coupon_uses)
    await message.answer("Bu kupon necha kishiga mo'ljallangan? (Limit):")

@dp.message(AdminState.add_coupon_uses)
async def coupon_save_final(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    data = await state.get_data()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO coupons (code, discount_uzs, min_uc, uses_left) VALUES (?, ?, ?, ?)",
            (data['code'], data['disc'], data['min_uc'], int(message.text))
        )
        await db.commit()
        
    await state.clear()
    await message.answer(f"✅ Kupon muvaffaqiyatli yaratildi!\n\nKodi: <b>{data['code']}</b>\nChegirma: {data['disc']} so'm", parse_mode="HTML", reply_markup=admin_menu_kb())

# ==================== MAIN LAUNCHER ====================
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    print("Pro UC Service Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
