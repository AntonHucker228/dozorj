import asyncio
import logging
import sqlite3
import random
import string
import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types, F, Router

from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = "8553213516:AAE71Ddi650C-LEBUwvHKzYTgaZAnsLK12I"

# Каналы для подписки
CHANNELS = [
    {"name": "Telegram contests", "url": "https://t.me/NFT_news_dzr", "id": "@NFT_news_dzr"},
    {"name": "Конкурсы / розыгрыши", "url": "https://t.me/channelstarstg", "id": "@channelstarstg"}
]

# Подарки в магазине
GIFTS = {
    "bear": {"name": "Мишка", "emoji": "🐻", "cost": 5},
    "heart": {"name": "Сердце", "emoji": "💝", "cost": 5},
    "rose": {"name": "Роза", "emoji": "🌹", "cost": 9},
    "cake": {"name": "Торт", "emoji": "🎂", "cost": 16},
    "diamond": {"name": "Алмаз", "emoji": "💎", "cost": 25},
    "random_nft": {"name": "Рандом NFT", "emoji": "🎁", "cost": 100},
}

# Стоимость лотереи в звёздах
LOTTERY_COST = 30
GIFT_COST = 10

# Призы лотереи с шансами (в процентах)
LOTTERY_PRIZES = [
    {"name": "15⭐️", "chance": 35, "type": "stars", "amount": 15},
    {"name": "25⭐️", "chance": 30, "type": "stars", "amount": 25},
    {"name": "50⭐️", "chance": 25, "type": "stars", "amount": 50},
    {"name": "100⭐️", "chance": 20, "type": "stars", "amount": 100},
    {"name": "NFT🎁", "chance": 10, "type": "nft", "amount": 0},
]

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
                quiz_passed INTEGER DEFAULT 0,
                subscription_passed INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lottery_wins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prize TEXT,
                date TEXT,
                claimed INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gift_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                gift_name TEXT,
                cost INTEGER,
                date TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bought_gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        gift_name TEXT,
        purchase_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE -- Ссылаемся на user_id в таблице users
    )''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, first_name: str, referred_by: Optional[int] = None) -> bool:
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
                "quiz_passed": row[11],
                "subscription_passed": row[12] if len(row) > 12 else 0
            }
        return None
    
    def set_quiz_passed(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET quiz_passed = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def set_subscription_passed(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET subscription_passed = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def activate_referral(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET referral_active = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def credit_referral_bonus(self, referrer_id: int) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT referral_active, points FROM users WHERE user_id = ?", (referrer_id,))
        row = cursor.fetchone()
        
        if not row or row[0] != 1:
            conn.close()
            return None
        
        cursor.execute('''
            UPDATE users 
            SET referrals_count = referrals_count + 1,
                points = points + 1
            WHERE user_id = ?
        ''', (referrer_id,))
        
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (referrer_id,))
        new_points = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        return new_points
    
    def add_lottery_win(self, user_id: int, prize: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute('''
            INSERT INTO lottery_wins (user_id, prize, date)
            VALUES (?, ?, ?)
        ''', (user_id, prize, date))
        conn.commit()
        conn.close()
    
    def update_spent(self, user_id: int, amount: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET total_spent = total_spent + ?, total_purchases = total_purchases + 1
            WHERE user_id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()

    # --- Методы для работы с подарками ---

    def add_gift_purchase(self, user_id: int, gift_name: str):
        """Добавляет новую запись о покупке подарка."""
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Правильное использование datetime
        conn = self.get_connection()
        if conn is None:
            print("Failed to get connection for adding gift purchase.")
            return

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bought_gifts (user_id, gift_name, purchase_date)
                VALUES (?, ?, ?)
            """, (user_id, gift_name, current_datetime))
            conn.commit()
            print(f"Gift purchase recorded: UserID={user_id}, Gift='{gift_name}'")
        except sqlite3.Error as e:
            print(f"Error recording gift purchase for user {user_id}: {e}")
            conn.rollback()
        finally:
            conn.close()

    # --- Синхронный метод для извлечения всех покупок ---
    def get_all_gift_purchases(self):
            conn = self.get_connection()
            if conn is None:
                print("Failed to get connection for getting gift purchases.")
                return []

            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT 
                    bg.gift_name, 
                    u.username, -- Используем username вместо user_name
                    u.full_name, 
                    bg.user_id  -- Добавим user_id
                FROM bought_gifts bg
                JOIN users u ON bg.user_id = u.user_id -- Ссылаемся на user_id в users
                ORDER BY bg.id DESC -- Сортируем по ID самой покупки
            """)
            
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                purchases = [dict(zip(columns, row)) for row in rows]
                return purchases
            except sqlite3.Error as e:
                print(f"Error fetching gift purchases: {e}")
            # Здесь может быть ошибка, если 'users' не имеет столбца 'username'
            # или если FOREIGN KEY неверный.
                return []
            finally:
                conn.close()




    def spend_points(self, user_id: int, amount: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row or row[0] < amount:
            conn.close()
            return False
        
        cursor.execute('''
            UPDATE users SET points = points - ?, total_purchases = total_purchases + 1
            WHERE user_id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    
    def add_gift_order(self, user_id: int, gift_name: str, cost: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute('''
            INSERT INTO gift_orders (user_id, gift_name, cost, date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, gift_name, cost, date))
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
    for channel in CHANNELS:
        buttons.append([InlineKeyboardButton(
            text=f"📢 {channel['name']}",
            url=channel['url']
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
        [InlineKeyboardButton(text="🏆 Топ дня", callback_data="top_day")],
        [InlineKeyboardButton(text="🧸/💝 за 10⭐", callback_data="for_10")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_gift_keyboard(referral_active: bool, user_points: int) -> InlineKeyboardMarkup:
    buttons = []
    
    if referral_active:
        for gift_id, gift in GIFTS.items():
            status = "✅" if user_points >= gift["cost"] else "❌"
            buttons.append([InlineKeyboardButton(
                text=f"{gift['emoji']} {gift['name']} — {gift['cost']} баллов {status}",
                callback_data=f"buy_gift_{gift_id}"
            )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🆓 Активировать бесплатно",
            callback_data="activate_referral"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="🔙 Вернуться в главное меню",
        callback_data="main_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_activate_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for channel in CHANNELS:
        buttons.append([InlineKeyboardButton(
            text=f"📢 {channel['name']}",
            url=channel['url']
        )])
    
    buttons.append([InlineKeyboardButton(
        text="✅ Проверить и активировать",
        callback_data="check_and_activate"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="get_gift"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_lottery_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"💫 Оплатить {LOTTERY_COST}⭐️", callback_data="pay_lottery")],
        [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_gift_keyboard(gift_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить покупку", callback_data=f"confirm_gift_{gift_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="get_gift")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="main_menu")]
    ])

def choise_gift() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мишка🧸", callback_data="bear_gift")],
        [InlineKeyboardButton(text="Сердце💝", callback_data="heart_gift")],
        [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="main_menu")]
    ])

def app_to_pay() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к оплате", callback_data="start_to_pay")]
        [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="main_menu")]
    ])

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def check_subscription(bot: Bot, user_id: int) -> bool:
    if not CHANNELS:
        return True
    
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel['id'], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.error(f"Ошибка проверки подписки на {channel['id']}: {e}")
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

def spin_lottery() -> Optional[dict]:
    if random.randint(1, 100) <= 30:
        return None
    
    roll = random.randint(1, 100)
    cumulative = 0
    
    for prize in LOTTERY_PRIZES:
        cumulative += prize["chance"]
        if roll <= cumulative:
            return prize
    
    return None



async def notify_referrer(bot: Bot, referrer_id: int, new_user_name: str, new_points: int):
    try:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={referrer_id}"
        
        text = f"""🎉 Новый реферал активирован!

👤 Пользователь: {new_user_name}

✅ Статус: Прошёл капчу и подписку

💎 Начислено: 1 балл
💰 Всего баллов: {new_points}

🎁 Подарки уже ждут тебя!

Приглашай друзей и зарабатывай баллы, которые можно обменять на подарки:

🐻 Мишка — 5 баллов
💝 Сердце — 5 баллов
🌹 Роза — 9 баллов
🎂 Торт — 16 баллов
💎 Алмаз — 25 баллов
🎁 Рандом NFT — 100 баллов

💰 Твой баланс: {new_points} баллов

🔗 Твоя ссылка: {ref_link}

👇 Продолжай приглашать друзей!"""

        await bot.send_message(
            chat_id=referrer_id,
            text=text,
            reply_markup=get_gift_keyboard(True, new_points)
        )
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления рефереру {referrer_id}: {e}")

# ==================== РОУТЕР И ХЕНДЛЕРЫ ====================

router = Router()

user_referrers = {}
# _ _ _ Покупка подарка _ _ _
@router.callback_query(F.data == "for_10")
async def gifts_for_10(callback_query: CallbackQuery):

    await callback_query.message.edit_text("Здесь вы можете приобрести подарки\n 🧸/💝'\nВсего за 10 звезд⭐\n\nВыберите подарок, а затем проведите оплату!", reply_markup=choise_gift())
    

@router.callback_query(F.data == "bear_gift")
async def pay_gifts_handler(callback_query: CallbackQuery):
    await callback_query.message.answer_invoice(
        title="⭐ Оплата подарка",
        description=f"Оплати 10⭐ и подарок скоро прилетит на акк!",
        payload="gift_pay_bear",
        currency="XTR",
        
        prices=[LabeledPrice(label="Подарок 🧸", amount=GIFT_COST)]
    )
    await callback_query.answer()

@router.callback_query(F.data == "heart_gift")
async def pay_gifts_handler(callback_query: CallbackQuery):
    await callback_query.message.answer_invoice(
        title="⭐ Оплата подарка",
        description=f"Оплати 10⭐ и подарок скоро прилетит на акк!",
        payload="gift_pay_heart",
        currency="XTR",
        
        prices=[LabeledPrice(label="Подарок 💝", amount=GIFT_COST)]
    )
    await callback_query.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment) # Или напрямую с диспетчером
async def successful_payment(message: types.Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    gift_name = None
    
    if payload == "gift_pay_bear":
        gift_name = "Мишка 🧸"
    elif payload == "gift_pay_heart": # Используем elif для второго условия
        gift_name = "Сердце 💝"

    if gift_name:
        # Вызываем синхронный метод
        db.add_gift_purchase(user_id, gift_name) 
        await message.answer(f"✅ Оплата прошла успешно! Ваш подарок '{gift_name}' скоро будет отправлен.\nОжидайте!")
    else:
        # Если payload не совпал ни с одним из известных
        await message.answer("Произошла ошибка при обработке вашего платежа. Неизвестный тип подарка.")


# --- Обработчик для команды /get_gift_info ---
# @router.message(Command("get_gift_info")) # Если используешь роутеры
@router.message(Command("get_gift_info")) # Напрямую с диспетчером
async def get_gift_table(message: types.Message):
    user_id = message.from_user.id # ID пользователя, который запросил информацию

    # Проверяем, имеет ли пользователь права просматривать список покупок.
    # Например, только администраторы. Если нет, то лучше выйти.
    # В этом примере я предположу, что любой может запросить, но в реальном боте надо добавить проверку!
    
    purchases = db.get_all_gift_purchases()

    if not purchases:
        await message.answer("Пока никто не покупал подарки.")
        return

    response_text = "🎁 Список покупок подарков:\n\n"
    for purchase in purchases:
        gift_name = purchase.get('gift_name', 'Неизвестный подарок')
        user_name = purchase.get('user_name', 'Нет юзернейма')
        full_name = purchase.get('full_name', 'Нет полного имени')
        purchase_date = purchase.get('purchase_date', 'Нет даты')

        # Формируем ссылку на аккаунт пользователя, если ID известен
        user_account_link = f"tg://user?id={purchase.get('user_id')}" if purchase.get('user_id') else "Без ID"

        response_text += (
            f"<b>Подарок:</b> {gift_name}\n"
            f"<b>Купил:</b> <a href='{user_account_link}'>{user_name}</a> ({full_name})\n"
            f"<b>Дата:</b> {purchase_date}\n"
            f"--------------------\n"
        )
        
        # Ограничение длины сообщения, если список покупок очень большой
        if len(response_text) > 4000: # Максимум Telegram ~4096 символов
            await message.answer(response_text)
            response_text = "" # Сбрасываем текст для следующей порции
            
    if response_text: # Отправляем оставшийся текст, если он есть
        await message.answer(response_text)






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
    
    if referred_by:
        user_referrers[user_id] = referred_by
    
    db.add_user(user_id, username, first_name, referred_by)
    user = db.get_user(user_id)
    
    if user and user["quiz_passed"] and user.get("subscription_passed", 0):
        await show_main_menu(message)
        return
    
    if user and user["quiz_passed"]:
        if CHANNELS:
            await message.answer(
                "📢 Для продолжения подпишись на наши каналы:",
                reply_markup=get_subscribe_keyboard()
            )
        else:
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
            await process_referral_bonus(callback.bot, callback.from_user.id, callback.from_user.first_name)
            db.set_subscription_passed(callback.from_user.id)
            await show_main_menu_edit(callback)
    else:
        await callback.answer("❌ Неправильно! Попробуй ещё раз.", show_alert=True)

async def process_referral_bonus(bot: Bot, user_id: int, user_name: str):
    if user_id in user_referrers:
        referrer_id = user_referrers[user_id]
        new_points = db.credit_referral_bonus(referrer_id)
        
        if new_points is not None:
            await notify_referrer(bot, referrer_id, user_name, new_points)
        
        del user_referrers[user_id]

# --- Проверка подписки ---
@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: CallbackQuery, bot: Bot):
    if await check_subscription(bot, callback.from_user.id):
        await process_referral_bonus(bot, callback.from_user.id, callback.from_user.first_name)
        db.set_subscription_passed(callback.from_user.id)
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
    text = f"""🎰 Испытай свою удачу!

Попытай свою удачу за {LOTTERY_COST} звёзд!⭐️
➖➖➖➖➖➖➖➖➖
15⭐️ (35%)
25⭐️ (30%)
50⭐️ (25%)
100⭐️ (20%)
NFT🎁 (10%)
➖➖➖➖➖➖➖➖➖

💫 Крути и выигрывай!"""

    await callback.message.edit_text(
        text,
        reply_markup=get_lottery_keyboard()
    )

# --- Оплата лотереи ---
@router.callback_query(F.data == "pay_lottery")
async def pay_lottery_handler(callback: CallbackQuery):
    await callback.message.answer_invoice(
        title="🎰 Лотерея",
        description=f"Попытай удачу и выиграй до 100⭐️ или NFT!",
        payload="lottery_spin",
        currency="XTR",
        prices=[LabeledPrice(label="Лотерея", amount=LOTTERY_COST)]
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
    
    if payload == "lottery_spin":
        db.update_spent(user_id, amount)
        
        prize = spin_lottery()
        
        if prize:
            db.add_lottery_win(user_id, prize["name"])
            
            await message.answer(
                f"🍀 Удача!\n\n"
                f"🎉 Поздравляем! Вы выиграли: {prize['name']}\n\n"
                f"⏳ Дождитесь администрацию для получения приза!\n"
                f"📩 Мы свяжемся с вами в ближайшее время.",
                reply_markup=get_back_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удача!\n\n"
                "😔 К сожалению, в этот раз не повезло...\n"
                "🍀 Попробуй ещё раз!",
                reply_markup=get_lottery_keyboard()
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
💸 Потрачено: {user['total_spent']}⭐️"""

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
        
        text = f"""🎁 Подарки уже ждут тебя!

Приглашай друзей и зарабатывай баллы, которые можно обменять на подарки:

🐻 Мишка — 5 баллов
💝 Сердце — 5 баллов
🌹 Роза — 9 баллов
🎂 Торт — 16 баллов
💎 Алмаз — 25 баллов
🎁 Рандом NFT — 100 баллов

💰 Твой баланс: {user['points']} баллов

🔗 Твоя ссылка: {link_text}

👇 Выбери подарок для покупки:"""
    else:
        link_text = "❌ Реф ссылка не активирована"
        
        text = f"""🎁 Подарки уже ждут тебя!

Приглашай друзей и зарабатывай баллы, которые можно обменять на подарки:

🐻 Мишка — 5 баллов
💝 Сердце — 5 баллов
🌹 Роза — 9 баллов
🎂 Торт — 16 баллов
💎 Алмаз — 25 баллов
🎁 Рандом NFT — 100 баллов

🆓 Активируй свою реферальную ссылку БЕСПЛАТНО и начинай
зарабатывать уже сейчас!

🔗 Твоя ссылка: {link_text}

Для активации необходимо подписаться на каналы

Что дает активация:
• 🔗 Персональная реф ссылка
• 🎁 Доступ к магазину подарков
• 👥 Начисление баллов за друзей"""

    await callback.message.edit_text(
        text,
        reply_markup=get_gift_keyboard(user["referral_active"], user["points"])
    )

# --- Покупка подарка ---
@router.callback_query(F.data.startswith("buy_gift_"))
async def buy_gift_handler(callback: CallbackQuery):
    gift_id = callback.data.replace("buy_gift_", "")
    
    if gift_id not in GIFTS:
        await callback.answer("❌ Подарок не найден!", show_alert=True)
        return
    
    user = db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Перезапустите бота /start", show_alert=True)
        return
    
    if not user["referral_active"]:
        await callback.answer("❌ Сначала активируй реферальную ссылку!", show_alert=True)
        return
    
    gift = GIFTS[gift_id]
    
    if user["points"] < gift["cost"]:
        await callback.answer(
            f"❌ Недостаточно баллов!\n\n"
            f"Нужно: {gift['cost']} баллов\n"
            f"У тебя: {user['points']} баллов",
            show_alert=True
        )
        return
    
    text = f"""🛒 Подтверждение покупки

Вы хотите приобрести:
{gift['emoji']} {gift['name']}

💰 Стоимость: {gift['cost']} баллов
💳 Ваш баланс: {user['points']} баллов
📊 После покупки: {user['points'] - gift['cost']} баллов

Подтвердить покупку?"""

    await callback.message.edit_text(
        text,
        reply_markup=get_confirm_gift_keyboard(gift_id)
    )

# --- Подтверждение покупки подарка ---
@router.callback_query(F.data.startswith("confirm_gift_"))
async def confirm_gift_handler(callback: CallbackQuery):
    gift_id = callback.data.replace("confirm_gift_", "")
    
    if gift_id not in GIFTS:
        await callback.answer("❌ Подарок не найден!", show_alert=True)
        return
    
    user = db.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка! Перезапустите бота /start", show_alert=True)
        return
    
    gift = GIFTS[gift_id]
    
    if db.spend_points(callback.from_user.id, gift["cost"]):
        db.add_gift_order(callback.from_user.id, gift["name"], gift["cost"])
        
        await callback.message.edit_text(
            f"✅ Заявка на подарок принята!\n\n"
            f"🎁 Подарок: {gift['emoji']} {gift['name']}\n"
            f"💰 Списано: {gift['cost']} баллов\n\n"
            f"⏳ Ваша заявка рассматривается администрацией.\n"
            f"📩 Мы свяжемся с вами в ближайшее время!\n\n"
            f"Спасибо за покупку! 🎉",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.answer(
            f"❌ Недостаточно баллов!\n\n"
            f"Нужно: {gift['cost']} баллов",
            show_alert=True
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
            "Активируй её в разделе «🎁 Получить Подарок» бесплатно!",
            reply_markup=get_back_keyboard()
        )


# Функция для получения топа пользователей по рефералам
def get_top_referrals():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, referrals_count 
        FROM users 
        ORDER BY referrals_count DESC 
        LIMIT 6
    ''')
    top_list = cursor.fetchall()
    conn.close()
    return top_list

# Функция для получения количества пользователей, прошедших проверку подписки
def get_subscription_count():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) 
        FROM users 
        WHERE subscription_passed = 1
    ''')
    count = cursor.fetchone()[0]
    conn.close()
    return count

@router.callback_query(F.data == "top_day")
async def top_day_handler(callback: CallbackQuery):
    top_list = get_top_referrals()
    text = "🏆 Топ дня по рефералам (24 часа):\n\n"
    for i, (user_id, username, referrals) in enumerate(top_list, start=1):
        text += f"{i}. {username} — {referrals} рефералов\n"
    
    # Добавляем количество пользователей, прошедших проверку подписки
    subscription_count = get_subscription_count()
    text += f"\nВсего пользователей: {subscription_count}"
    text += "\n\n🎁 Приз сегодня: 💍"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


import asyncio
from datetime import datetime, timedelta

# Функция для сброса топа
async def reset_top():
    # Здесь можно добавить логику для сброса данных в базе данных
    # Например, обновить поле referrals_count для всех пользователей до 0
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET referrals_count = 0")
    conn.commit()
    conn.close()
    print("Топ сброшен в", datetime.now())

# Функция для планирования сброса топа каждые 24 часа
async def schedule_reset_top():
    while True:
        # Ждем до следующего дня в полночь
        next_midnight = datetime.combine(datetime.now().date() + timedelta(days=1), datetime.min.time())
        await asyncio.sleep((next_midnight - datetime.now()).total_seconds())
        await reset_top()



# --- Активация реферальной ссылки (бесплатно) ---
@router.callback_query(F.data == "activate_referral")
async def activate_referral_handler(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user and user["referral_active"]:
        await callback.answer("✅ Реферальная ссылка уже активирована!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🆓 Бесплатная активация реферальной ссылки!\n\n"
        "📢 Для активации подпишись на все каналы ниже:",
        reply_markup=get_activate_keyboard()
    )

# --- Проверка подписки и активация ---
@router.callback_query(F.data == "check_and_activate")
async def check_and_activate_handler(callback: CallbackQuery, bot: Bot):
    user = db.get_user(callback.from_user.id)
    
    if user and user["referral_active"]:
        await callback.answer("✅ Реферальная ссылка уже активирована!", show_alert=True)
        return
    
    if await check_subscription(bot, callback.from_user.id):
        db.activate_referral(callback.from_user.id)
        
        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
        
        await callback.message.edit_text(
            f"✅ Реферальная ссылка успешно активирована!\n\n"
            f"🔗 Твоя ссылка:\n{ref_link}\n\n"
            f"Приглашай друзей и получай баллы!",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.answer(
            "❌ Ты не подписался на все каналы!\n\nПодпишись и попробуй снова.",
            show_alert=True
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

    asyncio.run(schedule_reset_top())

if __name__ == "__main__":

    asyncio.run(main())


