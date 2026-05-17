import asyncio
import aiohttp
import json
import secrets
import os
from datetime import datetime
from enum import Enum
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# ===== ТОКЕНЫ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_TOKEN = os.environ.get("API_TOKEN")
API_BASE_URL = "https://api.funtime.su"

# Проверка наличия токенов
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не установлен!")
if not API_TOKEN:
    raise ValueError("❌ API_TOKEN не установлен!")

# ===== АДМИН И КАНАЛ =====
ADMIN_ID = 6647553935
REQUIRED_CHANNEL = "@WlecksiFT"
BOT_USERNAME = "WleckEvents_bot"

# ===== РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ =====
PAYMENT_DETAILS = """
💳 <b>Способы оплаты:</b>

1️⃣ <b>Т-Банк</b>
   Номер карты: 2200 7020 5886 3372
   Получатель: Даниил

📌 После оплаты отправь скриншот чека сюда
"""

PREMIUM_PLANS = {
    "30": {"days": 30, "price": 100},
    "60": {"days": 60, "price": 150},
    "90": {"days": 90, "price": 200}
}

# ===== АНАРХИИ ДЛЯ РАЗНЫХ ВЕРСИЙ =====
ANARCHIES_1_16_5 = sorted([
    1001, 1002, 1003, 1004, 1005, 1006,
    2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016,
    3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008,
    5001, 5002, 5003, 5004,
    6001, 6002, 6003
])

def get_anarchies_1_21():
    anars = []
    anars.extend(range(101, 113))
    anars.extend(range(201, 229))
    anars.extend(range(301, 320))
    anars.extend(range(501, 513))
    anars.extend(range(901, 905))
    return sorted(anars)

ANARCHIES_1_21 = get_anarchies_1_21()

# ===== ФАЙЛЫ ДЛЯ ХРАНЕНИЯ =====
USERS_FILE = "users.json"
REFERRALS_FILE = "referrals.json"
TOTAL_REFERRALS_FILE = "total_referrals.json"
CONTEST_FILE = "contest.json"
PLAYERS_FILE = "players.json"
PREMIUM_FILE = "premium.json"
USER_SETTINGS_FILE = "user_settings.json"

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_referrals():
    try:
        with open(REFERRALS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_referrals(refs):
    with open(REFERRALS_FILE, 'w') as f:
        json.dump(refs, f, indent=2)

def load_total_referrals():
    try:
        with open(TOTAL_REFERRALS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_total_referrals(total):
    with open(TOTAL_REFERRALS_FILE, 'w') as f:
        json.dump(total, f, indent=2)

def load_contest():
    try:
        with open(CONTEST_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"active": False, "end_time": None, "start_time": None, "top": []}

def save_contest(contest):
    with open(CONTEST_FILE, 'w') as f:
        json.dump(contest, f, indent=2)

def load_players():
    try:
        with open(PLAYERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_players(players):
    with open(PLAYERS_FILE, 'w') as f:
        json.dump(players, f, indent=2)

def load_premium():
    try:
        with open(PREMIUM_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_premium(premium):
    with open(PREMIUM_FILE, 'w') as f:
        json.dump(premium, f, indent=2)

def load_user_settings():
    try:
        with open(USER_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_user_settings(settings):
    with open(USER_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_user_version(user_id: str) -> str:
    settings = load_user_settings()
    return settings.get(user_id, {}).get("version", "1.16.5")

def get_anarchies_by_version(version: str):
    if version == "1.21":
        return ANARCHIES_1_21
    return ANARCHIES_1_16_5

def check_premium(user_id: int) -> bool:
    premium = load_premium()
    user_premium = premium.get(str(user_id))
    if user_premium:
        if user_premium.get("expires") > datetime.now().timestamp():
            return True
        del premium[str(user_id)]
        save_premium(premium)
    return False

def get_premium_expiry(user_id: int) -> str:
    premium = load_premium()
    user_premium = premium.get(str(user_id))
    if user_premium:
        expires = datetime.fromtimestamp(user_premium["expires"])
        return expires.strftime("%d.%m.%Y")
    return "Нет"

def activate_premium(user_id: int, days: int = 30):
    premium = load_premium()
    user_id_str = str(user_id)
    current_time = datetime.now().timestamp()
    if user_id_str in premium:
        new_expiry = max(premium[user_id_str]["expires"], current_time) + (days * 24 * 60 * 60)
    else:
        new_expiry = current_time + (days * 24 * 60 * 60)
    premium[user_id_str] = {
        "activated": current_time,
        "expires": new_expiry,
        "days": days
    }
    save_premium(premium)

def add_referral(referrer_id: str, new_user_id: str):
    refs = load_referrals()
    if referrer_id not in refs:
        refs[referrer_id] = []
    if new_user_id not in refs[referrer_id]:
        refs[referrer_id].append(new_user_id)
        save_referrals(refs)
    
    total = load_total_referrals()
    if referrer_id not in total:
        total[referrer_id] = []
    if new_user_id not in total[referrer_id]:
        total[referrer_id].append(new_user_id)
        save_total_referrals(total)

def get_total_referrals_count(user_id: str) -> int:
    total = load_total_referrals()
    return len(total.get(str(user_id), []))

def get_contest_referrals_count(user_id: str) -> int:
    refs = load_referrals()
    return len(refs.get(str(user_id), []))

def get_main_keyboard(version: str = "1.16.5"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Текущие ивенты"), KeyboardButton(text="⏰ Ближайшие ивенты")],
            [KeyboardButton(text="⛏ Шахты"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="📞 Помощь"), KeyboardButton(text="💎 Премиум")],
            [KeyboardButton(text="🔄 Изменить версию")]
        ],
        resize_keyboard=True
    )

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ===== Flask для keep-alive =====
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

def run_web():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_web).start()

# ===== ПРОВЕРКА ПОДПИСКИ =====
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def generate_referral_code(user_id: int) -> str:
    return f"ref_{user_id}_{secrets.token_hex(4)}"

def register_user(user_id: int, username: str = None, referrer_id: str = None):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        return False
    users[user_id_str] = {
        "user_id": user_id,
        "username": username,
        "joined": datetime.now().isoformat(),
        "referral_code": generate_referral_code(user_id),
        "premium": False
    }
    save_users(users)
    if referrer_id and referrer_id != user_id_str and referrer_id in users:
        add_referral(referrer_id, user_id_str)
    return True

def format_username(username, user_id):
    if username:
        return f"@{username}"
    return f"[ID: {user_id}]"

def get_rarity_emoji(rarity: str) -> str:
    if "Легендарный" in rarity:
        return "💎"
    if "Элитный" in rarity:
        return "👑"
    if "Богатый" in rarity:
        return "💰"
    if "Солидный" in rarity:
        return "⭐"
    return "📦"

def get_event_info(event_id: str):
    events = {
        "myst_beacon": {"name": "Маяк убийца", "emoji": "🩸"},
        "beacon": {"name": "Маяк убийца", "emoji": "🩸"},
        "epstein": {"name": "Остров пепешнейна", "emoji": "🏝️"},
        "vote": {"name": "Идет голосование..", "emoji": "📊"},
        "vulkan": {"name": "Вулкан", "emoji": "🌋"},
        "hell_fight": {"name": "Адская резня", "emoji": "👹"},
        "hellm": {"name": "Адская резня", "emoji": "👹"},
        "death_chest": {"name": "Сундук смерти", "emoji": "💀"},
        "deathchest": {"name": "Сундук смерти", "emoji": "💀"},
        "meteor": {"name": "Метеоритный дождь", "emoji": "☄️"},
        "shakhty": {"name": "Шахты", "emoji": "⛏️"},
        "geyser": {"name": "Гейзер", "emoji": "🐳"}
    }
    for key, info in events.items():
        if key in event_id.lower():
            return info
    return {"name": "Системный ивент", "emoji": "📌"}

def is_known_event(event_id: str) -> bool:
    known_ids = ["vulkan", "death_chest", "deathchest", "vote", "myst_beacon", "beacon", "hell_fight", "hellm", "meteor", "shakhty", "epstein", "geyser"]
    for kid in known_ids:
        if kid in event_id.lower():
            return True
    return False

def format_event_status(event_id: str, time_left: int, phase: str) -> str:
    minutes = time_left // 60
    seconds = time_left % 60
    time_str = f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"
    
    if phase == "RUNNING" or time_left == 0:
        if "death_chest" in event_id.lower() or "deathchest" in event_id.lower():
            return f"🟢 ДО ЗАКРЫТИЯ: {time_str}"
        if "vulkan" in event_id.lower():
            return f"🌋 ДО ЗАВЕРШЕНИЯ: {time_str}"
        if "meteor" in event_id.lower():
            return f"☄️ ДО КОНЦА: {time_str}"
        if "hell_fight" in event_id.lower() or "hellm" in event_id.lower():
            return f"👹 ДО КОНЦА: {time_str}"
        if "myst_beacon" in event_id.lower() or "beacon" in event_id.lower():
            return f"🔮 ДО ДЕАКТИВАЦИИ: {time_str}"
        if "geyser" in event_id.lower():
            return f"🐳 ДО ЗАВЕРШЕНИЯ: {time_str}"
        return f"🔥 ДО КОНЦА: {time_str}"
    
    if "death_chest" in event_id.lower() or "deathchest" in event_id.lower():
        return f"💀 ДО ОТКРЫТИЯ: {time_str}"
    if "vulkan" in event_id.lower():
        return f"🌋 ДО ИЗВЕРЖЕНИЯ: {time_str}"
    if "meteor" in event_id.lower():
        return f"☄️ ДО ПАДЕНИЯ: {time_str}"
    if "hell_fight" in event_id.lower() or "hellm" in event_id.lower():
        return f"👹 ДО АДСКОЙ РЕЗНИ: {time_str}"
    if "myst_beacon" in event_id.lower() or "beacon" in event_id.lower():
        return f"🔮 ДО АКТИВАЦИИ: {time_str}"
    if "geyser" in event_id.lower():
        return f"🐳 ДО АКТИВАЦИИ: {time_str}"
    return f"⏳ ДО ПОЯВЛЕНИЯ: {time_str}"

class SortType(Enum):
    BY_ANARCHY = "по анархии"
    BY_STATUS = "по статусу"
    BY_LOOT = "по луту"

def get_loot_level(loot: str) -> int:
    levels = {"Легендарный": 5, "Элитный": 4, "Богатый": 3, "Солидный": 2, "Обычный": 1}
    return levels.get(loot, 0)

def apply_sorting(events, sort_type: SortType):
    if sort_type == SortType.BY_ANARCHY:
        return sorted(events, key=lambda x: x.get('server', 0))
    if sort_type == SortType.BY_STATUS:
        return sorted(events, key=lambda x: x.get("time-seconds-left", 0))
    if sort_type == SortType.BY_LOOT:
        return sorted(events, key=lambda x: get_loot_level(x.get('loot', 'Обычный')), reverse=True)
    return events

def apply_filters(events, event_filters, loot_filters):
    result = []
    for e in events:
        event_name = get_event_info(e.get('id', ''))["name"]
        loot = e.get('loot', 'Обычный')
        if event_filters and event_name not in event_filters:
            continue
        if loot_filters and loot not in loot_filters:
            continue
        result.append(e)
    return result

async def fetch_events_for_anarchy(anarchy: int):
    url = f"{API_BASE_URL}/method/events-info"
    params = {"event-type": "all", "server-type": f"anarchy{anarchy}"}
    headers = {"Authorization-Token": API_TOKEN}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", [])
                return []
    except:
        return []

async def get_all_events(version: str = "1.16.5"):
    all_events = []
    for anarchy in get_anarchies_by_version(version):
        events_data = await fetch_events_for_anarchy(anarchy)
        if events_data:
            for item in events_data:
                if "events" in item:
                    for event in item["events"]:
                        event["server"] = anarchy
                        all_events.append(event)
    return all_events

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    if not await check_subscription(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПОДПИСАТЬСЯ", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
        ])
        await message.answer(
            "🔒 <b>ДОСТУП ОГРАНИЧЕН</b>\n\n"
            f"Для использования бота подпишись на канал:\n{REQUIRED_CHANNEL}",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = args[1].split("_")[1]
        except:
            pass
    register_user(user_id, username, referrer_id)
    version = get_user_version(str(user_id))
    await message.answer(
        "🎮 <b>FunTime Bot</b>\n\nИспользуй кнопки меню:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(version)
    )

@dp.callback_query(lambda c: c.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.edit_text("✅ Подписка подтверждена! Напиши /start")
        await cmd_start(callback.message)
    else:
        await callback.answer("❌ Вы не подписаны!", show_alert=True)

@dp.message(Command("events"))
async def cmd_events(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на канал")
        return
    user_id = str(message.from_user.id)
    version = get_user_version(user_id)
    settings = load_user_settings()
    user_settings = settings.get(user_id, {"sort": None, "event_filters": [], "loot_filters": []})
    
    msg = await message.answer(f"🔍 Поиск известных ивентов (версия {version})...")
    all_events = await get_all_events(version)
    known = [e for e in all_events if is_known_event(e.get('id', ''))]
    known = apply_filters(known, user_settings.get("event_filters", []), user_settings.get("loot_filters", []))
    
    if not known:
        await msg.edit_text(f"📅 Известных ивентов нет (версия {version})")
        return
    
    unique_events = {}
    for e in known:
        event_name = get_event_info(e.get('id', ''))["name"]
        server = e.get('server')
        key = f"{event_name}_{server}"
        if key not in unique_events:
            unique_events[key] = e
    
    known = list(unique_events.values())
    
    if user_settings.get("sort"):
        try:
            sort_type = SortType(user_settings["sort"])
            known = apply_sorting(known, sort_type)
        except:
            known.sort(key=lambda x: x.get('server', 0))
    else:
        known.sort(key=lambda x: x.get('server', 0))
    
    text = f"🎉 <b>ИЗВЕСТНЫЕ ИВЕНТЫ (версия {version})</b>\n"
    if user_settings.get("event_filters"):
        text += f"📌 Фильтр: {', '.join(user_settings['event_filters'])}\n"
    if user_settings.get("loot_filters"):
        text += f"💎 Лут: {', '.join(user_settings['loot_filters'])}\n"
    if user_settings.get("sort"):
        text += f"📊 Сортировка: {user_settings['sort']}\n"
    text += f"📊 Показано: {len(known)}\n\n"
    
    for e in known[:50]:
        info = get_event_info(e.get('id', ''))
        server = e.get('server', '?')
        time_left = e.get("time-seconds-left", 0)
        loot = e.get('loot', 'Обычный')
        phase = e.get("phase", "")
        rarity_emoji = get_rarity_emoji(loot)
        status = format_event_status(e.get('id', ''), time_left, phase)
        
        text += f"╔═ {info['emoji']} {info['name']}\n"
        text += f"║ » {status}\n"
        if loot and loot != "Обычный":
            text += f"║ » Редкость: {rarity_emoji} {loot}\n"
        text += f"╚═ ⚔️ Анархия #{server}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Сортировка", callback_data="open_sort")],
        [InlineKeyboardButton(text="🔍 Фильтры", callback_data="open_filters")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")]
    ])
    await msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("near"))
async def cmd_near(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на канал")
        return
    user_id = str(message.from_user.id)
    version = get_user_version(user_id)
    
    msg = await message.answer(f"🔍 Поиск неизвестных ивентов (версия {version})...")
    all_events = await get_all_events(version)
    unknown = [e for e in all_events if not is_known_event(e.get('id', ''))]
    
    unique_unknown = {}
    for e in unknown:
        server = e.get('server')
        key = f"system_{server}"
        if key not in unique_unknown:
            unique_unknown[key] = e
    
    unknown = list(unique_unknown.values())
    unknown.sort(key=lambda x: x.get('time-seconds-left', 0))
    
    if not unknown:
        await msg.edit_text(f"📅 Неизвестных ивентов нет (версия {version})")
        return
    
    text = f"⏰ <b>НЕИЗВЕСТНЫЕ ИВЕНТЫ (версия {version})</b>\n\n"
    for e in unknown[:30]:
        server = e.get('server', '?')
        time_left = e.get("time-seconds-left", 0)
        phase = e.get("phase", "")
        status = format_event_status(e.get('id', ''), time_left, phase)
        text += f"╔═ 📌 Системный ивент\n"
        text += f"║ » {status}\n"
        text += f"╚═ ⚔️ Анархия #{server}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_near")]
    ])
    await msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("mines"))
async def cmd_mines(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("❌ Подпишись на канал")
        return
    user_id = str(message.from_user.id)
    version = get_user_version(user_id)
    anarchies = get_anarchies_by_version(version)
    
    text = f"⛏ <b>ШАХТЫ НА АНАРХИЯХ (версия {version})</b>\n\n"
    for a in anarchies[:20]:
        if version == "1.21":
            if a in [301, 302, 303, 304, 305]:
                emoji, name = "💎", "Легендарная"
            elif a in [201, 202, 203, 204, 205]:
                emoji, name = "💰", "Мифическая"
            else:
                emoji, name = "💵", "Обычная"
        else:
            if a in [3002, 2008, 2007, 1002]:
                emoji, name = "💎", "Легендарная"
            elif a in [3001, 2015, 2013, 2010, 2005, 2003]:
                emoji, name = "💰", "Мифическая"
            else:
                emoji, name = "💵", "Обычная"
        text += f"╔═ {emoji} {name}\n╚═ ⚔️ Анархия #{a}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("my_refs"))
async def cmd_my_refs(message: types.Message):
    user_id = str(message.from_user.id)
    total_count = get_total_referrals_count(user_id)
    contest_count = get_contest_referrals_count(user_id)
    await message.answer(
        f"📊 <b>Мои рефералы</b>\n\n"
        f"📌 Всего приглашено: <b>{total_count}</b>\n"
        f"🎯 За текущий конкурс: <b>{contest_count}</b>\n\n"
        f"💡 Чтобы пригласить друга, отправь ему свою реферальную ссылку из /profile",
        parse_mode="HTML"
    )

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)
    if user_id not in users:
        await message.answer("❌ Напиши /start")
        return
    user = users[user_id]
    total_count = get_total_referrals_count(user_id)
    version = get_user_version(user_id)
    
    if total_count >= 10:
        level = "👑 Легендарный"
    elif total_count >= 5:
        level = "💎 Премиум"
    elif total_count >= 1:
        level = "⭐ Продвинутый"
    else:
        level = "🟢 Обычный"
    username_display = format_username(user.get("username"), user_id)
    text = f"👤 <b>ПРОФИЛЬ</b>\n\n"
    text += f"Ник: {username_display}\n"
    text += f"Уровень: {level}\n"
    text += f"Приглашено (всего): {total_count}\n"
    text += f"Premium: {'✅' if check_premium(int(user_id)) else '❌'}\n"
    text += f"Версия: {version}\n\n"
    text += f"🔗 Твоя реферальная ссылка:\n"
    text += f"<code>https://t.me/{BOT_USERNAME}?start={user['referral_code']}</code>"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("premium"))
async def cmd_premium(message: types.Message):
    user_id = message.from_user.id
    if check_premium(user_id):
        await message.answer(f"💎 <b>У вас есть Premium</b>\n\n📅 Действует до: {get_premium_expiry(user_id)}", parse_mode="HTML")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 30 дней — 100₽", callback_data="premium_30")],
            [InlineKeyboardButton(text="💎 60 дней — 150₽", callback_data="premium_60")],
            [InlineKeyboardButton(text="💎 90 дней — 200₽", callback_data="premium_90")]
        ])
        await message.answer(
            f"💎 <b>ПРЕМИУМ ДОСТУП</b>\n\n"
            f"💰 Выбери тариф:\n\n"
            f"{PAYMENT_DETAILS}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

@dp.message(Command("version"))
async def cmd_version(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 1.16.5", callback_data="set_version_1.16.5")],
        [InlineKeyboardButton(text="🎮 1.21", callback_data="set_version_1.21")]
    ])
    await message.answer(
        "🔄 <b>ВЫБОР ВЕРСИИ</b>\n\n"
        "Выбери версию Minecraft для отображения ивентов и шахт:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("set_version_"))
async def set_version(callback: types.CallbackQuery):
    version = callback.data.replace("set_version_", "")
    user_id = str(callback.from_user.id)
    
    settings = load_user_settings()
    if user_id not in settings:
        settings[user_id] = {}
    settings[user_id]["version"] = version
    save_user_settings(settings)
    
    await callback.message.edit_text(
        f"🔄 <b>ВЕРСИЯ ИЗМЕНЕНА</b>\n\n"
        f"Текущая версия: <b>{version}</b>\n\n"
        f"Теперь ивенты и шахты будут отображаться для этой версии.",
        parse_mode="HTML"
    )
    await callback.answer(f"✅ Версия изменена на {version}")

@dp.callback_query(lambda c: c.data.startswith("premium_"))
async def premium_plan_callback(callback: types.CallbackQuery):
    days = int(callback.data.split("_")[1])
    price = PREMIUM_PLANS[str(days)]["price"]
    await callback.message.answer(
        f"💎 <b>ОПЛАТА PREMIUM</b>\n\n"
        f"📅 Период: {days} дней\n"
        f"💰 Сумма: {price} руб\n\n"
        f"{PAYMENT_DETAILS}\n\n"
        f"📌 После оплаты отправь скриншот чека с подписью «чек {days}»"
    )
    await callback.answer()

@dp.message(lambda message: message.photo and message.caption and "чек" in message.caption.lower())
async def forward_receipt(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"📸 Чек от {format_username(message.from_user.username, message.from_user.id)}\n💰 Сумма: {message.caption}")
    await message.answer("✅ Чек отправлен администратору! Ожидайте активации Premium.")

@dp.message(Command("activate_premium"))
async def cmd_activate_premium(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет прав")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ /activate_premium <user_id> <дни>\nПример: /activate_premium 123456789 30")
        return
    try:
        user_id = int(args[1])
        days = int(args[2])
        activate_premium(user_id, days)
        await bot.send_message(user_id, f"💎 <b>Premium активирован!</b>\n\n📅 Действует {days} дней", parse_mode="HTML")
        await message.answer(f"✅ Premium активирован для {user_id} на {days} дней")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("support"))
async def cmd_support(message: types.Message):
    await message.answer("📞 Связь с поддержкой: @wlecksi")

async def main():
    print("🤖 Бот запущен!")
    print(f"📡 Версия 1.16.5: {len(ANARCHIES_1_16_5)} анархий")
    print(f"📡 Версия 1.21: {len(ANARCHIES_1_21)} анархий")
    print(f"👑 Админ: {ADMIN_ID}")
    print(f"📢 Канал: {REQUIRED_CHANNEL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
