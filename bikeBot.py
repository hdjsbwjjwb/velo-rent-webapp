import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import FSInputFile
from datetime import datetime, date
import json
import pytz
import os
import re
import csv
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from collections import Counter

from dotenv import load_dotenv
load_dotenv()  # загружает переменные окружения из .env
TOKEN = os.getenv("BOT_TOKEN")  # получаем токен

import gspread
from oauth2client.service_account import ServiceAccountCredentials


import traceback

from aiologger import Logger
import sys
from datetime import date
async def generate_stats_chart(records, filename='stats_chart.png'):
    from collections import Counter
    import matplotlib.pyplot as plt
    import json

    bikes_counter = Counter()
    total_income = 0
    total_minutes = 0

    for row in records:
        cart_json = row.get("cart") or row.get("Велосипеды") or "{}"
        cart = json.loads(cart_json)
        for cat, qty in cart.items():
            bikes_counter[cat] += int(qty)

        sum_str = str(row.get("total_price", 0) or row.get("Сумма", "0")).replace("₽", "").replace(" ", "").strip()
        try:
            total_income += int(sum_str)
        except Exception:
            pass

        total_minutes += int(row.get("minutes", 0) or row.get("Время проката", 0))

    if records:
        avg_minutes = total_minutes // len(records)
    else:
        avg_minutes = 0

    plt.figure(figsize=(12, 6))
    # --- график 1 ---
    plt.subplot(1, 2, 1)
    bars1 = plt.bar(bikes_counter.keys(), bikes_counter.values(), color='skyblue')
    plt.title('Популярность велосипедов')
    plt.ylabel('Количество аренд')
    for bar in bars1:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height, f"{int(height)}", ha='center', va='bottom', fontsize=12, fontweight='bold')

    # --- график 2 ---
    plt.subplot(1, 2, 2)
    bars2 = plt.bar(['Выручка', 'Среднее время аренды (мин)'], [total_income, avg_minutes], color=['lightgreen', 'salmon'])
    plt.title('Выручка и среднее время')
    for bar, value in zip(bars2, [total_income, avg_minutes]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:,}".replace(',', ' '), ha='center', va='bottom', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(filename)
    plt.close()



logger = Logger.with_default_handlers(name='bike_bot', level='INFO')

async def save_rent_to_gsheet(data, duration_min, total_price, period_str):
    #await logger.info("save_rent_to_gsheet вызвана")
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1dXcmUr0Dtx1fylu3DaUdZigFwkjTKnPCkPf9OcuiGOE").sheet1
        
        cart_human = "\n".join([f"{cat} — {qty}" for cat, qty in data.get("cart", {}).items()])
        
        sheet.append_row([
            data.get("user_id"),
            data.get("user_name"),
            data.get("phone"),
            json.dumps(data.get("cart"), ensure_ascii=False),
            cart_human,
            duration_min,
            total_price,
            period_str
        ])
        #await logger.info("✅ Успешно добавлено в Google Таблицу")
    except Exception as e:
        await logger.error(f"Ошибка записи в Google таблицу: {e}")
        traceback.print_exc()
        with open("gspread_error.log", "a") as f:
            f.write(f"{datetime.now()} — Ошибка:\n")
            traceback.print_exc(file=f)

def get_gsheet_records():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1dXcmUr0Dtx1fylu3DaUdZigFwkjTKnPCkPf9OcuiGOE").sheet1
    records = sheet.get_all_records()
    return records

ADMIN_ID = 7666320318 # <-- сюда свой user_id
    
SUPPORT_TEXT = (
    "💬 <b>📞   BalticBike</b>\n\n"
    "Если возникли вопросы:\n"
    "Телефон: <a href='tel:+79992552854'>+7 999 255-28-54</a>\n"
    "Telegram: @realBalticBike\n"
    "E-mail: velo.prokat@internet.ru"
)

PHONE_NUMBER = "+7 906 211-29-40"  # <-- номер для оплаты

bike_categories = {
    'Детский':     {"hour": 150, "emoji": "🧒", "img": "images/Baby.jpg"},
    'Прогулочный': {"hour": 200, "emoji": "🚲", "img": "images/City.jpg"},
    'Скоростной':  {"hour": 250, "emoji": "🚵", "img": "images/Sport.jpg"},
}

QUANTITY_CHOICES = [1, 2, 3, 4, 5]
user_rent_data = {}
KALININGRAD_TZ = pytz.timezone('Europe/Kaliningrad')

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Список точек маршрута (например, 9 точек с информацией о месте)
places_info = {
    1: "Место 1: Описание места 1",
    2: "Место 2: Описание места 2",
    3: "Место 3: Описание места 3",
    4: "Место 4: Описание места 4",
    5: "Место 5: Описание места 5",
    6: "Место 6: Описание места 6",
    7: "Место 7: Описание места 7",
    8: "Место 8: Описание места 8",
    9: "Место 9: Описание места 9",
}

async def set_user_commands(bot):
    commands = [
        types.BotCommand(command="support", description="Поддержка"),
        types.BotCommand(command="active", description="Активные аренды")
        # оставляем только команды для обычных пользователей
    ]
    await bot.set_my_commands(commands, scope=types.BotCommandScopeDefault())

async def set_admin_commands(bot, admin_id):
    commands = [
        types.BotCommand(command="start", description="Запустить бота"),
        types.BotCommand(command="help", description="Справка"),
        types.BotCommand(command="stats", description="Статистика"),
        types.BotCommand(command="report", description="Отчёт за сегодня"),
        types.BotCommand(command="active", description="Активные аренды"),
        # другие админ-команды если есть
    ]
    scope = types.BotCommandScopeChat(chat_id=admin_id)
    await bot.set_my_commands(commands, scope=scope)

# -------- Клавиатуры -------- #

def main_menu_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[ 
            [types.KeyboardButton(text="📞 Поддержка")]
            # Убираем кнопки "Перезапустить бота", "📞 Поддержка" остаётся
        ],
        resize_keyboard=True
    )

def categories_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=f"{bike_categories[cat]['emoji']} {cat} ({bike_categories[cat]['hour']}₽/ч)"
                )
            ] for cat in bike_categories.keys()
        ] +
        [
            [types.KeyboardButton(text="🟢 НАЧАТЬ АРЕНДУ 🟢")],
            [types.KeyboardButton(text="Посмотреть корзину")]
        ],
        resize_keyboard=True
    )

def cart_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Очистить корзину")],
            [types.KeyboardButton(text="Назад к выбору категории")]
        ],
        resize_keyboard=True
    )



# Клавиатура во время аренды
def during_rent_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🗺 Что посмотреть?")],
            [types.KeyboardButton(text="📞 Поддержка")],  # Кнопка для поддержки
            [types.KeyboardButton(text="⏱ Сколько времени катаюсь?")],  # Кнопка для времени
            [types.KeyboardButton(text="🔴 Завершить аренду")],  # Кнопка для завершения аренды
        ],
        resize_keyboard=True
    )

def contact_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="✅ Я соглашаюсь с правилами ✅", request_contact=True)]],
        resize_keyboard=True
    )

# -------- Inline клавиатуры -------- #

def create_places_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)  # 3 кнопки в ряду
    for i in range(1, 10):  # Создаем 9 кнопок
        keyboard.add(InlineKeyboardButton(f"Место {i}", callback_data=f"place_{i}"))
    return keyboard

# -------- Обработчики -------- #

@dp.message(F.text == "/start")
async def greet(message: types.Message):
    user_id = message.from_user.id

    try:
        # Отправляем фото всем пользователям
        photo = FSInputFile("welcome.png")  # Убедись, что путь правильный
        await message.answer_photo(
            photo,
            caption=(
                "<b>Добро пожаловать в сервис велопроката BalticBike!</b>\n\n"
                "🌊 Прокатитесь по Балтийской косе и побережью на стильных велосипедах!\n"
            )
        )
    except Exception as e:
        # Если произошла ошибка с отправкой фото, отправляем текст
        print(f"Ошибка при отправке фото: {e}")
        await message.answer(
            "<b>Добро пожаловать в сервис велопроката BalticBike!</b>\n\n"
            "🌊 Прокатитесь по Балтийской косе и побережью на стильных велосипедах!\n"
        )

    # После фото показываем выбор категорий
    user_rent_data[user_id] = {
        "cart": {},
        "start_time": None,
        "awaiting_quantity": False,
        "last_category": None,
        "is_renting": False,
        "phone": None,
        "asked_phone": False,
    }

    keyboard = categories_keyboard()
    await message.answer("Выберите категорию велосипеда для аренды:", reply_markup=keyboard)

@dp.message(F.text == "/active")
async def active_rents(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    active = []
    now = datetime.now(KALININGRAD_TZ)

    for uid, data in user_rent_data.items():
        if data.get("is_renting"):
            start_time = data.get("start_time")
            if start_time:
                if isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(start_time)
                    except Exception:
                        start_time = now
                duration = now - start_time
                minutes = int(duration.total_seconds() // 60)
                start_str = start_time.strftime("%H:%M")
            else:
                minutes = "-"
                start_str = "-"
            user_name = data.get("user_name") or "-"
            phone = data.get("phone") or "-"
            cart = data.get("cart", {})
            if cart:
                bikes = "\n".join([f"{cat}: {qty}" for cat, qty in cart.items()])
            else:
                bikes = "-"
            active.append([
                user_name,
                phone,
                bikes,
                start_str,
                minutes
            ])

    if not active:
        await message.answer("Нет активных аренд.")
        return

    # --- PIL рендер таблицы ---
    headers = ["Имя", "Телефон", "Велосипеды", "Старт", "Время"]

    font_path = "shobhika_regular.otf"  # путь до TTF-файла шрифта
    try:
        font = ImageFont.truetype(font_path, 28)
        font_bold = ImageFont.truetype(font_path, 32)
    except:
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    row_height = 56
    col_widths = [180, 260, 370, 120, 170]  # подгони под свой вкус

    # Считаем высоту таблицы (учитывая переносы строк в столбце "Велосипеды")
    total_height = row_height * (len(active) + 1)
    for row in active:
        bike_lines = row[2].count('\n')
        if bike_lines:
            total_height += bike_lines * 30  # 30px на каждую доп. строку велосипеда

    total_width = sum(col_widths) + 20

    img = Image.new('RGB', (total_width, total_height + 30), color='#fff')
    draw = ImageDraw.Draw(img)

    # Рисуем шапку
    x = 10
    y = 10
    for i, h in enumerate(headers):
        draw.rectangle([x, y, x+col_widths[i], y+row_height], fill="#ffe066", outline="#bdbdbd", width=2)
        draw.text((x+10, y+10), h, font=font_bold, fill="#222")
        x += col_widths[i]
    y += row_height

    # Рисуем строки
    for idx, row in enumerate(active):
        x = 10
        bike_lines = row[2].split('\n')
        bike_lines_count = len(bike_lines)
        bike_cell_height = row_height + (bike_lines_count-1)*30
        for i, val in enumerate(row):
            # Цвет полосатый
            fill = "#f9f9f9" if idx % 2 == 0 else "#eafaf1"
            draw.rectangle([x, y, x+col_widths[i], y+bike_cell_height], fill=fill, outline="#bdbdbd", width=2)
            # Велосипеды — многострочный текст
            if i == 2:
                for line_idx, line in enumerate(bike_lines):
                    draw.text((x+10, y+10+line_idx*30), line, font=font, fill="#222")
            else:
                draw.text((x+10, y+10), str(val), font=font, fill="#222")
            x += col_widths[i]
        y += bike_cell_height

    img_path = "active_rents_pil.png"
    img.save(img_path)

    await message.answer_photo(FSInputFile(img_path), caption="🚴‍♂️ Текущие активные аренды")

@dp.message(F.text == "/help")
async def help_cmd(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id != ADMIN_ID:
        # Если пользователь не админ, не показываем полное меню и инструкцию
        await message.answer(
            "<b>ℹ️ Краткая инструкция по боту BalticBike:</b>\n"
            "• <b>/start</b> — начать сначала\n"
            "• <b>📞 Поддержка</b> — связаться с нами\n"
        )
    else:
        # Для админа показываем полное меню и инструкцию
        await message.answer(
            "<b>ℹ️ Краткая инструкция по боту BalticBike:</b>\n"
            "• <b>/start</b> — начать сначала\n"
            "• <b>/help</b> — справка\n"
            "• <b>/myid</b> — узнать свой ID\n"
            "• <b>📞 Поддержка</b> — связаться с нами\n"
        )
        
@dp.message(F.text == "Перезапустить бот")
async def restart_bot(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)
    if data and data.get("is_renting"):
        await message.answer("❗ Нельзя перезапустить бот во время активной аренды. Сначала завершите аренду!")
        return
    user_rent_data[user_id] = {
        "cart": {},
        "start_time": None,
        "awaiting_quantity": False,
        "last_category": None,
        "is_renting": False,
        "phone": None,
        "asked_phone": False,
    }
    keyboard = categories_keyboard()
    await message.answer(
        "Бот успешно перезапущен!\n\nВыберите категорию велосипеда для аренды:",
        reply_markup=keyboard
    )

@dp.message(F.text == "/report")
async def admin_report(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    def get_period(row):
        return row.get("period") or row.get("Период") or ""

    IGNORE_PHONES = ["7993734285"]  # твой игнор-лист

    today = date.today().isoformat()  # '2025-06-09'
    records = get_gsheet_records()

    # Для отладки выводим today и все периоды
    #await logger.info(f"TODAY: {today}")
    for row in records:
        period = get_period(row)
        included = today in period
        #await logger.info(f"PERIOD: {period}")
        #await logger.info(f"INCLUDED: {included}")

    today_rents = [
        row for row in records
        if today in get_period(row) and str(row.get("phone") or row.get("Телефон") or "") not in IGNORE_PHONES
    ]

    if not today_rents:
        await message.answer("Сегодня прокатов не было.")
        return
    #await logger.info("TODAY_RENTS:\n" + "\n".join(str(r) for r in today_rents))

    await generate_stats_chart(today_rents, filename='daily_stats.png')
    await message.answer_photo(
        FSInputFile('daily_stats.png'),
        caption=f"📊 Отчёт за сегодня ({today})"
    )


@dp.message(F.text == "📞 Поддержка")
async def support(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)

    if data and data.get("is_renting"):
        await message.answer(
            SUPPORT_TEXT,
            reply_markup=during_rent_keyboard()
        )
    else:
        # Показываем категории (основное меню)
        await message.answer(
            SUPPORT_TEXT,
            reply_markup=categories_keyboard()
        )

@dp.message(F.text == "⏱ Сколько времени катаюсь?")
async def time_spent(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)

    if data and data.get("is_renting"):
        # Рассчитываем время, которое прошло с начала аренды
        start_time = data["start_time"]
        end_time = datetime.now(KALININGRAD_TZ)
        duration = end_time - start_time
        minutes = int(duration.total_seconds() // 60)

        # Если прошло меньше часа, показываем в минутах
        if minutes < 60:
            time_str = f"{minutes} мин"
        else:
            hours = minutes // 60
            minutes_left = minutes % 60
            time_str = f"{hours} ч {minutes_left} мин"

        await message.answer(
            f"⏱ Вы катаетесь уже {time_str}.",
            reply_markup=during_rent_keyboard()
        )
    else:
        await message.answer(
            "Ошибка! Вы не начали аренду или аренда уже завершена.",
            reply_markup=main_menu_keyboard()
        )

@dp.message(F.text == "Арендовать велосипед")
async def start_rent_button(message: types.Message):
    user_id = message.from_user.id
    user_rent_data[user_id] = {
        "cart": {},
        "start_time": None,
        "awaiting_quantity": False,
        "last_category": None,
        "is_renting": False,
        "phone": None,
        "asked_phone": False,
    }
    keyboard = categories_keyboard()
    await message.answer("Выберите категорию велосипеда для добавления в корзину:", reply_markup=keyboard)

@dp.message(lambda m: any(m.text and m.text.startswith(bike_categories[cat]['emoji']) for cat in bike_categories))
async def select_category(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_rent_data:
        await start_rent_button(message)
        return
    data = user_rent_data[user_id]
    if data["is_renting"]:
        await message.answer("Аренда уже запущена! Завершите аренду или перезапустите бот.", reply_markup=during_rent_keyboard())
        return

    cat_name = None
    for cat, info in bike_categories.items():
        pattern = f"^{re.escape(info['emoji'])} {cat}"
        if re.match(pattern, message.text):
            cat_name = cat
            break
    if not cat_name:
        await message.answer("Не удалось распознать категорию, попробуйте снова.")
        return

    data["awaiting_quantity"] = True
    data["last_category"] = cat_name

    qty_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=str(qty)) for qty in QUANTITY_CHOICES],
            [types.KeyboardButton(text="Назад к выбору категории")]
        ],
        resize_keyboard=True
    )
    # Показываем фото, если файл есть
    img_path = bike_categories[cat_name]["img"]
    if os.path.exists(img_path):
        await message.answer_photo(
            FSInputFile(img_path),
            caption=f"Вы выбрали: {bike_categories[cat_name]['emoji']} <b>{cat_name}</b>\nЦена: {bike_categories[cat_name]['hour']}₽/час\n\nСколько добавить в корзину?",
            reply_markup=qty_keyboard
        )
    else:
        await message.answer(
            f"Вы выбрали: {bike_categories[cat_name]['emoji']} <b>{cat_name}</b>\nЦена: {bike_categories[cat_name]['hour']}₽/час\n\nСколько добавить в корзину?",
            reply_markup=qty_keyboard
        )

@dp.message(F.text == "Назад к выбору категории")
async def back_to_category(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_rent_data:
        user_rent_data[user_id]["awaiting_quantity"] = False
        user_rent_data[user_id]["last_category"] = None
    keyboard = categories_keyboard()
    await message.answer("Выберите категорию велосипеда для добавления:", reply_markup=keyboard)

@dp.message(lambda m: m.from_user.id in user_rent_data and user_rent_data[m.from_user.id]["awaiting_quantity"])
async def select_quantity(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data[user_id]
    if message.text == "Назад к выбору категории":
        await back_to_category(message)
        return
    try:
        qty = int(message.text)
        if qty not in QUANTITY_CHOICES:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, выберите количество только из кнопок ниже!")
        return
    cat = data["last_category"]
    data["cart"][cat] = data["cart"].get(cat, 0) + qty
    data["awaiting_quantity"] = False
    data["last_category"] = None
    keyboard = categories_keyboard()
    await message.answer(
        f"Добавлено {qty} |{cat}| велосипед(а).\n\n"
        "Добавьте ещё и нажмите <b>«Начать аренду»</b>.",
        reply_markup=keyboard
    )

@dp.message(F.text == "Посмотреть корзину")
async def view_cart(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)
    if not data or not data["cart"]:
        await message.answer("Ваша корзина пуста! Добавьте велосипеды для аренды.", reply_markup=categories_keyboard())
        return
    cart_str = "\n".join([
        f"{bike_categories[cat]['emoji']} <b>{cat}</b>: {cnt} шт. ({bike_categories[cat]['hour']}₽/ч)"
        for cat, cnt in data["cart"].items()
    ])
    total_hour_price = sum([bike_categories[cat]['hour'] * cnt for cat, cnt in data["cart"].items()])
    await message.answer(
        f"В вашей корзине:\n{cart_str}\n━━━━━━━━━━━━━━━━━━━━\n<b>Общая стоимость за 1 час: {total_hour_price}₽</b>",
        reply_markup=cart_keyboard()
    )

@dp.message(F.text == "Очистить корзину")
async def clear_cart(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_rent_data:
        user_rent_data[user_id]["cart"] = {}
        user_rent_data[user_id]["is_renting"] = False
        user_rent_data[user_id]["start_time"] = None
    keyboard = categories_keyboard()
    await message.answer("Корзина очищена! Можете выбрать велосипеды снова.", reply_markup=keyboard)


@dp.message(F.text == "🟢 НАЧАТЬ АРЕНДУ 🟢")
async def start_rent_preview(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)

    if not data or not data["cart"]:
        await message.answer("Сначала выберите хотя бы один велосипед.")
        return

    cart_str = "\n".join([
        f"{bike_categories[cat]['emoji']} <b>{cat}</b>: {cnt} шт. ({bike_categories[cat]['hour']}₽/ч)"
        for cat, cnt in data["cart"].items()
    ])
    total_hour_price = sum([bike_categories[cat]['hour'] * cnt for cat, cnt in data["cart"].items()])

    await message.answer(
        "Прежде чем поехать, проверьте велосипед и убедитесь, что всё работает:\n"
        "- Тормоза и шины.\n"
        "- Сиденье под ваш рост.\n\n"
        "<b><u>Теперь соблюдайте эти простые правила безопасности:</u></b>\n"
        "- <b>Будьте внимательны!</b> Следите за дорогой.\n"
        "- <b>Не гоните!</b> Наслаждайтесь поездкой.\n"
        "- <b>Осторожно на подъёмах и спусках.</b> Дороги могут быть неровными.\n"
        "- <b>Берегите велосипед.</b> Возвращайте его в хорошем состоянии.\n\n"
    )

    await message.answer(
        f"Вы выбрали:\n{cart_str}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>💸 Стоимость за 1 час: {total_hour_price} руб.</b>\n\n"
        "Для оформления аренды нажмите на кнопку ниже 👇",
        reply_markup=contact_keyboard()
    )
    data["asked_phone"] = True


@dp.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: types.CallbackQuery):
    # Убираем только кнопки "Подтвердить аренду" и "Вернуться к выбору"
    await callback.message.edit_reply_markup(reply_markup=None)

    # Показываем корзину снова
    user_id = callback.from_user.id
    data = user_rent_data.get(user_id)

    if not data or not data["cart"]:
        await callback.message.answer("Ваша корзина пуста! Добавьте велосипеды для аренды.", reply_markup=categories_keyboard())
        return

    cart_str = "\n".join([f"{bike_categories[cat]['emoji']} <b>{cat}</b>: {cnt} шт. ({bike_categories[cat]['hour']}₽/ч)" for cat, cnt in data["cart"].items()])
    total_hour_price = sum([bike_categories[cat]['hour'] * cnt for cat, cnt in data["cart"].items()])

    await callback.message.answer(
        f"В вашей корзине:\n{cart_str}\n━━━━━━━━━━━━━━━━━━━━\n<b>Общая стоимость за 1 час: {total_hour_price}₽</b>",
        reply_markup=cart_keyboard()  # Возвращаем клавиатуру корзины
    )

@dp.message(lambda m: m.contact is not None)
async def handle_contact(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)

    if not data:
        await message.answer("Пожалуйста, начните оформление аренды сначала через /start.")
        return

    phone = message.contact.phone_number
    data["phone"] = phone
    data["asked_phone"] = False

    await message.answer("Спасибо! Ваш номер сохранён. Оформляем аренду…")
    try:
        await start_rent_real(message)
    except Exception as e:
        #await logger.info(f"Ошибка при записи в Google Таблицу: {e}")
        await message.answer(f"Ошибка при запуске аренды: {e}")
        #await logger.info("Ошибка при запуске аренды:", e)

async def start_rent_real(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data[user_id]
    data["start_time"] = datetime.now(KALININGRAD_TZ)
    data["is_renting"] = True
    keyboard = during_rent_keyboard()
    #await logger.info(f"Аренда началась: {message.from_user.full_name}, id: {user_id}, телефон: {data.get('phone')}")

    cart_str = "\n".join([
    f"• <b>{cat}</b> — <b>{qty}</b> шт. <i>({bike_categories[cat]['hour']}₽/ч)</i>"
    for cat, qty in data["cart"].items()
    ])
    total_hour_price = sum([bike_categories[cat]['hour'] * qty for cat, qty in data["cart"].items()])

    # --- КРАСИВОЕ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ ---
    await message.answer(
        f"<b>Аренда началась!</b>\n"
        f"<b>Время старта:</b> <u>{data['start_time'].strftime('%H:%M')}</u>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Вы взяли:</b>\n{cart_str}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"💸 <b>Стоимость за 1 час:</b> <u>{total_hour_price} руб.</u>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Желаем вам приятной поездке 😊",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    # --- Уведомление админу ---
    try:
        await bot.send_message(
            ADMIN_ID,
            f"НАЧАЛАСЬ АРЕНДА!\n"
            f"User: {message.from_user.full_name}\n"
            f"Телефон: {data['phone'] if data['phone'] else 'Не указан'}\n"
            f"id: {message.from_user.id}\n"
            f"Время: {data['start_time'].strftime('%H:%M')}\n"
            f"Корзина:\n{cart_str}"
        )
    except Exception as e:
        
        pass
        #await logger.info(f"Не удалось отправить уведомление админу (начало): {e}")

@dp.message(F.text == "🗺 Что посмотреть?")
async def interesting_places(message: types.Message):
    # Отправляем карту (сначала отправляем картинку с маршрутом)
    photo_path = "images/route_map.jpg"  # Убедитесь, что путь к изображению верный
    photo = FSInputFile(photo_path)

    # Отправляем изображение карты
    sent_message = await message.answer_photo(
        photo,
        caption="Вот ваш маршрут с интересными местами. Нажмите на кнопку, чтобы узнать больше!",
        reply_markup=create_places_keyboard()  # Клавиатура с кнопками для мест
    )

    # Сохраняем id сообщения для дальнейшего редактирования
    user_rent_data[message.from_user.id] = {"message_id": sent_message.message_id}
    
@dp.message(F.text == "🔴 Завершить аренду")
async def finish_rent(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)
    if not data or not data["is_renting"]:
        await message.answer("Вы ещё не начали аренду. Для старта — выберите велосипеды и начните аренду.")
        return

    end_time = datetime.now(KALININGRAD_TZ)
    start_time = data["start_time"]
    duration = end_time - start_time
    total_minutes = duration.total_seconds() / 60

    # Округляем к ближайшим 15 минутам (с логикой приближения)
    block = 15
    pay_minutes = int(round(total_minutes / block) * block)
    if pay_minutes == 0:
        pay_minutes = 15

    # Время в удобном формате
    if int(total_minutes) >= 60:
        hours_part = int(total_minutes) // 60
        minutes_part = int(total_minutes) % 60
        ride_time = f"{hours_part} ч {minutes_part} мин"
    else:
        ride_time = f"{int(total_minutes)} мин"

    total_price = 0
    cart_lines = []

    for cat, qty in data["cart"].items():
        hour_price = bike_categories[cat]["hour"]
        block_price = hour_price / 60 * pay_minutes
        cat_price = int(block_price * qty)
        cart_lines.append(
            f"• <b>{cat}</b>: <b>{qty}</b> шт. (<i>{hour_price}₽/ч</i>)"
        )
        total_price += cat_price

    cart_str = "\n".join(cart_lines)

    await message.answer(
        f"<b>Аренда завершена!</b>\n"
        f"<b>Время в пути:</b> <u>{ride_time}</u>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Вы брали:</b>\n{cart_str}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Итого к оплате:</b> <u>{total_price} руб.</u>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<i>Спасибо за поездку! Хорошего дня 😊</i>",
        parse_mode="HTML"
    )

    # --- Уведомление админу ---
    try:
        await bot.send_message(
            ADMIN_ID,
            f"ЗАВЕРШЕНА АРЕНДА!\n"
            f"User: {message.from_user.full_name}\n"
            f"Телефон: {data['phone'] if data.get('phone') else 'Не указан'}\n"
            f"id: {message.from_user.id}\n"
            f"Время: {start_time.strftime('%H:%M')} — {end_time.strftime('%H:%M')} ({ride_time})\n"
            f"Корзина: {data['cart']}\n"
            f"Стоимость: {total_price} руб."
        )
    except Exception as e:
        await logger.error(f"Ошибка отправки уведомления админу при завершении аренды: {e}")

    # --- Сохраняем в Google Sheets ---
    period_str = f"{date.today().isoformat()} {start_time.strftime('%H:%M')} — {end_time.strftime('%H:%M')}"
    await save_rent_to_gsheet({
        "user_id": message.from_user.id,
        "user_name": message.from_user.full_name,
        "phone": data.get("phone"),
        "cart": data.get("cart"),
    }, pay_minutes, total_price, period_str)

    # --- Сброс данных аренды ---
    user_rent_data[user_id] = {
        "cart": {},
        "start_time": None,
        "awaiting_quantity": False,
        "last_category": None,
        "is_renting": False,
        "phone": data.get("phone"),
        "asked_phone": False,
    }

    keyboard = categories_keyboard()
    await message.answer(
        "Аренда завершена! Можете выбрать велосипеды для новой аренды:",
        reply_markup=keyboard
    )

@dp.message(F.text == "/stats")
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    IGNORE_PHONES = ["79937342853"]  # Сюда можно добавить ещё номера через запятую

    records = get_gsheet_records()
    bikes_counter = Counter()
    total_income = 0
    total_minutes = 0
    total_rents = 0  # Считаем только валидные

    for row in records:
        phone = str(row.get("phone") or row.get("Телефон") or "")
        if phone in IGNORE_PHONES:
            continue  # Пропускаем запись

        cart_json = row.get("cart") or row.get("Велосипеды") or "{}"
        try:
            cart = json.loads(cart_json)
        except Exception:
            cart = {}
        for cat, qty in cart.items():
            bikes_counter[cat] += int(qty)
        try:
            total_income += int(str(row.get("total_price") or row.get("Сумма", "0")).replace("₽", "").replace(" ", ""))
            total_minutes += int(row.get("minutes") or row.get("Время проката") or 0)
        except Exception:
            pass

        total_rents += 1

    total_bikes = sum(bikes_counter.values())
    most_popular = bikes_counter.most_common(1)
    popular_bike = most_popular[0][0] if most_popular else "Нет данных"
    avg_minutes = total_minutes // total_rents if total_rents else 0

    await message.answer(
        f"📊 <b>Статистика проката</b>\n"
        f"Всего завершённых прокатов: <b>{total_rents}</b>\n"
        f"Всего велосипедов взято: <b>{total_bikes}</b>\n"
        f"Самый популярный велик: <b>{popular_bike}</b>\n"
        f"Общая выручка: <b>{total_income} руб.</b>\n"
        f"Среднее время аренды: <b>{avg_minutes} мин</b>"
    )

@dp.message(F.text == "/refresh_commands")
async def refresh_commands(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await set_user_commands(bot)
    for admin_id in ADMIN_ID:
        await set_admin_commands(bot, admin_id)
    await message.answer("Команды обновлены.")

# Обработчик нажатия на кнопку "Место X"
@dp.callback_query(lambda c: c.data.startswith("place_"))
async def handle_place(callback: types.CallbackQuery):
    place_id = int(callback.data.split("_")[1])  # Получаем id места
    place_description = places_info.get(place_id, "Информация о месте недоступна.")

    # Получаем сообщение, которое отправили ранее
    user_id = callback.from_user.id
    message_id = user_rent_data.get(user_id, {}).get("message_id")

    if message_id:
        # Заменяем текст в том же сообщении
        await callback.message.edit_text(
            place_description,  # Описание выбранного места
            reply_markup=create_places_keyboard()  # Клавиатура с кнопками
        )
    else:
        # Если сообщение не найдено (по какой-то причине), отправляем новое
        await callback.message.answer(
            place_description,
            reply_markup=create_places_keyboard()
        )

    # Подтверждаем, что кнопка была нажата
    await callback.answer()

# --- Показываем время аренды, если аренда активна --- #
@dp.message(lambda m: m.from_user.id in user_rent_data and user_rent_data[m.from_user.id].get("is_renting"))
async def status_time_active(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data.get(user_id)
    if data and data.get("is_renting"):
        duration = datetime.now(KALININGRAD_TZ) - data["start_time"]
        minutes = int(duration.total_seconds() // 60)
        await message.answer(
            f"⏱ Сейчас ваша аренда продолжается уже {minutes} мин.\n"
            "Нажмите 'Завершить аренду', когда закончите кататься.",
            reply_markup=during_rent_keyboard()
        )

# --- Общий обработчик на случайный текст --- #
@dp.message()
async def fallback(message: types.Message):
    await logger.warning(f"Неизвестное сообщение от {message.from_user.full_name} (id: {message.from_user.id}): {message.text}")
    await message.answer(
        "Пожалуйста, пользуйтесь кнопками ниже 👇\n"
        "Так оформление пройдёт быстрее и без ошибок!"
    )

# -------- Запуск -------- #
async def send_daily_report():
    from datetime import date
    from collections import Counter
    import json

    records = get_gsheet_records()
    today = date.today().isoformat()
    today_rents = [row for row in records if today in row.get("period", "")]

    if not today_rents:
        await bot.send_message(ADMIN_ID, "Сегодня прокатов не было.")
        return

    bikes_counter = Counter()
    total_income = 0
    total_minutes = 0
    total_bikes = 0

    for row in today_rents:
        try:
            cart = json.loads(row["cart"])
        except Exception:
            cart = {}
        for cat, qty in cart.items():
            bikes_counter[cat] += int(qty)
            total_bikes += int(qty)
        total_income += int(row.get("total_price", 0))
        total_minutes += int(row.get("minutes", 0))

    most_popular = bikes_counter.most_common(1)
    popular_bike = most_popular[0][0] if most_popular else "Нет данных"
    avg_minutes = total_minutes // len(today_rents) if today_rents else 0

    text = (
        f"📅 <b>Отчёт за {today}</b>\n"
        f"Прокатов: <b>{len(today_rents)}</b>\n"
        f"Всего велосипедов выдали: <b>{total_bikes}</b>\n"
        f"Самый популярный велик: <b>{popular_bike}</b>\n"
        f"Выручка за день: <b>{total_income} руб.</b>\n"
        f"Среднее время аренды: <b>{avg_minutes} мин</b>"
    )
    await bot.send_message(ADMIN_ID, text)


async def main():
    await set_user_commands(bot)
    await set_admin_commands(bot, ADMIN_ID)
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
