import asyncio
import logging
import sqlite3
import random
import string
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = "8535443974:AAEeleptCF1PgSKPkzXDMSoyvlC-lnFmF-s"

# Каналы для подписки (без @)
CHANNELS = [
    "-1003694969896",
    "-1003646046099",
]

# Стоимость активации в звёздах
ACTIVATION_COST = 1

# Эмодзи для викторины
QUIZ_EMOJIS = [
    "😀", "😎", "🥳", "😍", "🤩", "😇", "🤠", "🥸", "😈", "👻",
    "👽", "🤖", "🎃", "😺", "🐶", "🦊", "🦁", "🐸", "🐵", "🐔"
]

# ==================== БАЗА ДАННЫХ ====================

class Database:
    def __init__(self, db_name: str = "bot_database.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registration_date TEXT,
                stars INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                referral_active INTEGER DEFAULT 0,
                referred_by INTEGER,
                total_purchases INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                quiz_passed INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                purpose TEXT,
                date TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, first_name: str, referred_by: Optional[int] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.close()
            return False
        
        registration_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, registration_date, referred_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, registration_date, referred_by))
        
        if referred_by:
            cursor.execute('''
                UPDATE users 
                SET referrals_count = referrals_count + 1,
                    points = points + 1
                WHERE user_id = ? AND referral_active = 1
            ''', (referred_by,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_user(self, user_id: int) -> Optional[dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "registration_date": row[3],
                "stars": row[4],
                "points": row[5],
                "referrals_count": row[6],
                "referral_active": row[7],
                "referred_by": row[8],
                "total_purchases": row[9],
                "total_spent": row[10],
                "quiz_passed": row[11]
            }
        return None
    
    def set_quiz_passed(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET quiz_passed = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def activate_referral(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET referral_active = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def add_payment(self, user_id: int, amount: int, purpose: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute('''
            INSERT INTO payments (user_id, amount, purpose, date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, purpose, date))
        cursor.execute('''
            UPDATE users SET stars = stars + ?, total_spent = total_spent + ?
            WHERE user_id = ?
        ''', (amount, amount, user_id))
        conn.commit()
        conn.close()

db = Database()

# ==================== КЛАВИАТУРЫ ====================

def get_quiz_keyboard(emojis: list, correct_index: int) -> InlineKeyboardMarkup:
    buttons = []
    for i, emoji in enumerate(emojis):
        buttons.append(InlineKeyboardButton(
            text=emoji,
            callback_data=f"quiz_{i}_{correct_index}"
        ))
    
    keyboard = []
    for i in range(0, len(buttons), 5):
        keyboard.append(buttons[i:i+5])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for i, channel in enumerate(CHANNELS):
        buttons.append([InlineKeyboardButton(
            text=f"📢 Канал {i+1}",
            url=f"https://t.me/{channel}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="✅ Проверить подписку",
        callback_data="check_subscription"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🎁 Получить Подарок", callback_data="get_gift")],
        [InlineKeyboardButton(text="🎰 Ежемесячная лотерея", callback_data="lottery")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="referral_link")],
        [InlineKeyboardButton(text="🏆 Топ дня", callback_data="top_day")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_gift_keyboard(referral_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    if not referral_active:
        buttons.append([InlineKeyboardButton(
            text="⭐️ Активировать за 1 звезду",
            callback_data="activate_referral"
        )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Вернуться в главное меню",
        callback_data="main_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="main_menu")]
    ])

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def check_subscription(bot: Bot, user_id: int) -> bool:
    if not CHANNELS:
        return True
    
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            continue
    return True

async def show_main_menu(message: Message):
    await message.answer(
        "🏠 Главное меню\n\nВыбери действие:",
        reply_markup=get_main_menu_keyboard()
    )

async def show_main_menu_edit(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Главное меню\n\nВыбери действие:",
        reply_markup=get_main_menu_keyboard()
    )

# ==================== РОУТЕР И ХЕНДЛЕРЫ ====================

router = Router()

# --- Команда /start ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Пользователь"
    
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        try:
            referred_by = int(args[1])
            if referred_by == user_id:
                referred_by = None
        except ValueError:
            pass
    
    db.add_user(user_id, username, first_name, referred_by)
    user = db.get_user(user_id)
    
    if user and user["quiz_passed"]:
        await show_main_menu(message)
        return
    
    correct_emoji = random.choice(QUIZ_EMOJIS)
    shuffled = QUIZ_EMOJIS.copy()
    random.shuffle(shuffled)
    correct_index = shuffled.index(correct_emoji)
    
    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"🎯 Пройди небольшую викторину!\n\n"
        f"Найди этот смайл: {correct_emoji}",
        reply_markup=get_quiz_keyboard(shuffled, correct_index)
    )

# --- Викторина ---
@router.callback_query(F.data.startswith("quiz_"))
async def handle_quiz_answer(callback: CallbackQuery):
    parts = callback.data.split("_")
    selected = int(parts[1])
    correct = int(parts[2])
    
    if selected == correct:
        db.set_quiz_passed(callback.from_user.id)
        
        if CHANNELS:
            await callback.message.edit_text(
                "✅ Правильно!\n\n"
                "📢 Для продолжения подпишись на наши каналы:",
                reply_markup=get_subscribe_keyboard()
            )
        else:
            await show_main_menu_edit(callback)
    else:
        await callback.answer("❌ Неправильно! Попробуй ещё раз.", show_alert=True)

# --- Проверка подписки ---
@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: CallbackQuery, bot: Bot):
    if await check_subscription(bot, callback.from_user.id):
        await show_main_menu_edit(callback)
    else:
        await callback.answer("❌ Ты не подписался на все каналы!", show_alert=True)

# --- Главное меню ---
@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    await show_main_menu_edit(callback)

# --- Лотерея ---
@router.callback_query(F.data == "lottery")
async def lottery_handler(callback: CallbackQuery):
    await callback.answer(
        "🎰 Нет активных лотерей\n\nСледите за обновлениями!",
        show_alert=True
    )

# --- Профиль ---
@router.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Перезапустите бота /start", show_alert=True)
        return
    
    status = "✅" if user["referral_active"] else "❌"
    
    text = f"""👤 Мой профиль

📝 Информация:
👤 Имя: {user['first_name']}
📅 Регистрация: {user['registration_date']}
⭐️ Звезд: {user['stars']}

💰 Реферальная система:
👥 Приглашено: {user['referrals_count']}
💰 Баллов: {user['points']}
🔗 Статус: {status}

🎁 Покупки:
🛍️ Всего: {user['total_purchases']}
💸 Потрачено: {user['total_spent']}"""

    await callback.message.edit_text(text, reply_markup=get_back_keyboard())

# --- Получить подарок ---
@router.callback_query(F.data == "get_gift")
async def get_gift_handler(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Перезапустите бота /start", show_alert=True)
        return
    
    bot_info = await callback.bot.get_me()
    
    if user["referral_active"]:
        link_text = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    else:
        link_text = "❌ Реф ссылка не активирована"
    
    text = f"""🎁 Подарки уже ждут тебя!

Приглашай друзей и зарабатывай баллы, которые можно обменять на подарки:

🐻 Мишка — 5 баллов
💝 Сердце — 5 баллов 

⚡️ Активируй свою реферальную ссылку всего за 1 ⭐️ и начинай
зарабатывать уже сейчас!

🔗 Твоя ссылка: {link_text}"""

    if not user["referral_active"]:
        text += """

Для активации необходимо оплатить 1 звезду

Что дает активация:
• 🔗 Персональная реф ссылка
• 🎁 Доступ к магазину подарков
• 👥 Начисление баллов за друзей"""

    await callback.message.edit_text(
        text,
        reply_markup=get_gift_keyboard(user["referral_active"])
    )

# --- Реферальная ссылка ---
@router.callback_query(F.data == "referral_link")
async def referral_link_handler(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Перезапустите бота /start", show_alert=True)
        return
    
    if user["referral_active"]:
        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
        
        await callback.message.edit_text(
            f"🔗 Твоя реферальная ссылка:\n\n{ref_link}\n\n"
            f"👥 Приглашено: {user['referrals_count']}\n"
            f"💰 Баллов: {user['points']}",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.message.edit_text(
            "❌ Реферальная ссылка не активирована!\n\n"
            "Активируй её в разделе «🎁 Получить Подарок» всего за 1 ⭐️",
            reply_markup=get_back_keyboard()
        )

# --- Топ дня ---
@router.callback_query(F.data == "top_day")
async def top_day_handler(callback: CallbackQuery):
    top_list = []
    for i in range(1, 6):
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        stars = '*' * random.randint(3, 7)
        referrals = random.randint(5, 50)
        top_list.append(f"{i}. {letters}{stars} — {referrals} рефералов")
    
    text = "🏆 Топ дня по рефералам:\n\n" + "\n".join(top_list)
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())

# --- Активация реферальной ссылки (оплата) ---
@router.callback_query(F.data == "activate_referral")
async def activate_referral_handler(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user and user["referral_active"]:
        await callback.answer("✅ Реферальная ссылка уже активирована!", show_alert=True)
        return
    
    await callback.message.answer_invoice(
        title="Активация реферальной ссылки",
        description="Активация персональной реферальной ссылки для получения баллов за приглашённых друзей",
        payload="activate_referral",
        currency="XTR",
        prices=[LabeledPrice(label="Активация", amount=ACTIVATION_COST)]
    )
    await callback.answer()

# --- Предпроверка платежа ---
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# --- Успешный платёж ---
@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount
    
    if payload == "activate_referral":
        db.activate_referral(user_id)
        db.add_payment(user_id, amount, "referral_activation")
        
        bot_info = await message.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        await message.answer(
            f"✅ Реферальная ссылка успешно активирована!\n\n"
            f"🔗 Твоя ссылка:\n{ref_link}\n\n"
            f"Приглашай друзей и получай баллы!"
        )
        
        await message.answer(
            "🏠 Главное меню",
            reply_markup=get_main_menu_keyboard()
        )

# ==================== ЗАПУСК БОТА ====================

async def main():
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
