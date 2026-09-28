from datetime import datetime, date
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, Integer, Float, DateTime, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Telegram ID
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    pubg_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pubg_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    total_bought_uc: Mapped[int] = mapped_column(Integer, default=0)
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="user", uselist=False)
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")

class Wallet(Base):
    __tablename__ = "wallets"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    balance_uzs: Mapped[float] = mapped_column(Float, default=0.0) # So'm balansi
    balance_coins: Mapped[int] = mapped_column(Integer, default=0) # Tanga balansi

    user: Mapped["User"] = relationship("User", back_populates="wallet")

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_code: Mapped[str] = mapped_column(String(16), unique=True, index=True) # Unikal kod (#7492)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    
    uc_amount: Mapped[int] = mapped_column(Integer) # Qancha UC
    price_uzs: Mapped[float] = mapped_column(Float) # Asosiy narx
    paid_from_wallet: Mapped[float] = mapped_column(Float, default=0.0)
    paid_from_coins: Mapped[int] = mapped_column(Integer, default=0)
    final_payable_uzs: Mapped[float] = mapped_column(Float) # Kartaga o'tkazishi kerak bo'lgan summa
    
    pubg_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: MappedAjoyib! PUBG Mobile UC savdosi uchun `aiogram 3.x` kutubxonasiga asoslangan, xavfsiz va qulay bot strukturasi hamda kodini tuzib chiqamiz.

Botda buyurtma berish jarayoni **FSM (State)** orqali boshqariladi: paket tanlanadi $\rightarrow$ PUBG ID kiritiladi $\rightarrow$ buyurtma tasdiqlanib adminga yuboriladi.

### Rejalashtirilgan bot kodi (`main.py`)

```python
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # BotFather'dan olingan token
ADMIN_ID = 123456789  # O'zingizning Telegram ID ingiz

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# UC Paketlari va narxlari
UC_PACKAGES = {
    "uc_60": {"title": "⚡️ 60 UC", "price": 14000},
    "uc_325": {"title": "⚡️ 325 + 25 UC", "price": 68000},
    "uc_660": {"title": "⚡️ 660 + 60 UC", "price": 135000},
    "uc_1800": {"title": "⚡️ 1800 + 300 UC", "price": 360000},
}


# FSM Holatlari
class OrderUC(StatesGroup):
    selecting_package = State()
    entering_pubg_id = State()
    confirming_order = State()


# Keyboards
def get_main_menu():
    kb = [
        [
            KeyboardButton(text="🛒 UC Xarid Qilish"),
            KeyboardButton(text="👤 Profil"),
        ],
        [
            KeyboardButton(text="💬 Qo'llab-quvvatlash"),
            KeyboardButton(text="ℹ️ Qoidalar"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_packages_keyboard():
    buttons = []
    for key, item in UC_PACKAGES.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{item['title']} - {item['price']:,} so'm",
                    callback_data=f"pkg_{key}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash va To'lash", callback_data="confirm_pay"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="cancel_order"
                )
            ],
        ]
    )


# Handlers
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        f"Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
        "Ushbu bot orqali PUBG Mobile o'yini uchun hamyonbop va tezkor UC xarid qilishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=get_main_menu(),
    )


@dp.message(F.text == "🛒 UC Xarid Qilish")
async def start_uc_order(message: types.Message, state: FSMContext):
    await state.set_state(OrderUC.selecting_package)
    await message.answer(
        "Kerakli UC paketini tanlang:", reply_markup=get_packages_keyboard()
    )


@dp.callback_query(
    OrderUC.selecting_package, F.data.startswith("pkg_")
)
async def package_selected(callback: types.CallbackQuery, state: FSMContext):
    pkg_key = callback.data.replace("pkg_", "")
    selected_pkg = UC_PACKAGES.get(pkg_key)

    await state.update_data(package=selected_pkg)
    await state.set_state(OrderUC.entering_pubg_id)

    await callback.message.edit_text(
        f"Siz tanladingiz: <b>{selected_pkg['title']}</b>\nNarxi: <b>{selected_pkg['price']:,} so'm</b>\n\n"
        "Iltimos, PUBG Mobile <b>ID raqamingizni (Player ID)</b> kiriting:",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(OrderUC.entering_pubg_id)
async def pubg_id_entered(message: types.Message, state: FSMContext):
    pubg_id = message.text.strip()

    if not pubg_id.isdigit() or len(pubg_id) < 8:
        await message.answer(
            "⚠️ Noto'g me'yoriy PUBG ID! Iltimos, faqat raqamlardan iborat to'g'ri ID kiriting:"
        )
        return

    data = await state.get_data()
    pkg = data["package"]
    await state.update_data(pubg_id=pubg_id)
    await state.set_state(OrderUC.confirming_order)

    await message.answer(
        "<b>Buyurtma tafsilotlari:</b>\n\n"
        f"📦 Paket: {pkg['title']}\n"
        f"🆔 PUBG ID: <code>{pubg_id}</code>\n"
        f"💰 To'lov summasi: <b>{pkg['price']:,} so'm</b>\n\n"
        "Buyurtmani tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard(),
    )


@dp.callback_query(OrderUC.confirming_order, F.data == "confirm_pay")
async def order_confirmed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pkg = data["package"]
    pubg_id = data["pubg_id"]
    user = callback.from_user

    # Adminga xabar yuborish
    admin_text = (
        "📥 <b>Yangi Buyurtma!</b>\n\n"
        f"👤 Xaridor: {user.full_name} (@{user.username or 'yoq'})\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"🎯 PUBG ID: <code>{pubg_id}</code>\n"
        f"📦 Paket: {pkg['title']}\n"
        f"💵 Summa: {pkg['price']:,} so'm"
    )

    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")

    # Xaridorga to'lov rekvizitlarini berish
    await callback.message.edit_text(
        "✅ Buyurtmangiz qabul qilindi!\n\n"
        "<b>To'lov uchun karta:</b> <code>8600 0000 0000 0000</code> (Eshmatov T.)\n"
        f"<b>Summa:</b> {pkg['price']:,} so'm\n\n"
        "To'lovni amalga oshirgach, chekni admin/qo'llab-quvvatlash bo'limiga yuboring.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "cancel_order")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.answer()


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
