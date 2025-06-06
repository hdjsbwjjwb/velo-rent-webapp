import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
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

def save_rent_to_gsheet(data, duration_min, total_price, period_str):
    print("save_rent_to_gsheet вызвана")
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
        print("✅ Успешно добавлено в Google Таблицу")
    except Exception as e:
        print("Ошибка при записи в Google Таблицу:")
        traceback.print_exc()
        with open("gspread_error.log", "a") as f:
            f.write(f"{datetime.now()} — Ошибка:\n")
            traceback.print_exc(file=f)

ADMIN_ID = 6425885445  # <-- сюда свой user_id

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
    'Спортивный':  {"hour": 250, "emoji": "🚵", "img": "images/Sport.jpg"},
    'Фэтбайк':     {"hour": 300, "emoji": "🌄", "img": "images/Fat.jpg"},
}

QUANTITY_CHOICES = [1, 2, 3, 4, 5]
user_rent_data = {}
KALININGRAD_TZ = pytz.timezone('Europe/Kaliningrad')

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# -------- Клавиатуры -------- #

def main_menu_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Перезапустить бот"), types.KeyboardButton(text="📞 Поддержка")]
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
            [types.KeyboardButton(text="Посмотреть корзину")],
            [types.KeyboardButton(text="Начать аренду 🚴🚴🚴...")],
            [types.KeyboardButton(text="Перезапустить бот"), types.KeyboardButton(text="📞 Поддержка")]
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
            [types.KeyboardButton(text="🔴 Завершить аренду")],  # Кнопка для завершения аренды
            [types.KeyboardButton(text="⏱ Сколько времени катаюсь?")],  # Кнопка для времени
            [types.KeyboardButton(text="📞 Поддержка")]  # Кнопка для поддержки
        ],
        resize_keyboard=True
    )

def contact_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True
    )

# -------- Inline клавиатуры -------- #

def confirm_rent_inline():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Подтвердить аренду", callback_data="confirm_rent")],
        [types.InlineKeyboardButton(text="↩️ Вернуться к выбору", callback_data="back_to_cart")]
    ])


# -------- Обработчики -------- #

@dp.message(F.text == "/start")
async def greet(message: types.Message):
    try:
        photo = FSInputFile("welcome.png")
        await message.answer_photo(
            photo,
            caption=(
                "<b>Добро пожаловать в сервис велопроката BalticBike!</b>\n\n"
                "🌊 Прокатитесь по Балтийской косе и побережью на стильных велосипедах!\n"
            )
        )
    except Exception:
        await message.answer(
            "<b>Добро пожаловать в сервис велопроката BalticBike!</b>\n\n"
            "🌊 Прокатитесь по Балтийской косе и побережью на стильных велосипедах!\n"
        )
    # Сразу выводим выбор категорий!
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
    headers = ["Имя", "Телефон", "Велосипеды", "Старт", "Длится (мин)"]

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
    await message.answer(
        "<b>ℹ️ Краткая инструкция по боту BalticBike:</b>\n"
        "• <b>/start</b> — начать сначала\n"
        "• <b>/help</b> — справка\n"
        "• <b>/myid</b> — узнать свой ID\n"
        "• <b>/stats</b> — статистика (только для админа)\n"
        "• <b>Арендовать велосипед</b> — начать оформление\n"
        "• <b>📞 Поддержка</b> — связаться с нами\n"
        "• Всё остальное — используйте кнопки ниже!"
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
    await send_daily_report()
    await message.answer("Отчёт отправлен.")

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


@dp.message(F.text == "Начать аренду 🚴🚴🚴...")
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
        "- <b>Не перегружайте велосипед.</b> Удобство важнее.\n"
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
        print(f"Ошибка при записи в Google Таблицу: {e}")
        await message.answer(f"Ошибка при запуске аренды: {e}")
        print("Ошибка при запуске аренды:", e)
async def start_rent_real(message: types.Message):
    user_id = message.from_user.id
    data = user_rent_data[user_id]
    data["start_time"] = datetime.now(KALININGRAD_TZ)
    data["is_renting"] = True
    keyboard = during_rent_keyboard()
    cart_str = "\n".join([
        f"{bike_categories[cat]['emoji']} <b>{cat}</b>: {cnt} шт. ({bike_categories[cat]['hour']}₽/ч)"
        for cat, cnt in data["cart"].items()
    ])

    total_hour_price = sum([bike_categories[cat]['hour'] * qty for cat, qty in data["cart"].items()])

    try:
        await bot.send_message(
            ADMIN_ID,
            f"НАЧАЛАСЬ АРЕНДА!\n"
            f"User: {message.from_user.full_name}\n"
            f"Телефон: {data['phone'] if data['phone'] else 'Не указан'}\n"
            f"id: {message.from_user.id}\n"
            f"Время: {datetime.now(KALININGRAD_TZ).strftime('%H:%M')}\n"
            f"Корзина:\n{cart_str}"
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление админу (начало): {e}")

    await message.answer(
        f"Вы арендовали:\n{cart_str}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>💸 Стоимость всех велосипедов за 1 час: {total_hour_price} руб.</b>\n\n"
        "Когда закончите кататься — нажмите 'Завершить аренду'.",
        reply_markup=keyboard
    )

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
    minutes = int(duration.total_seconds() // 60)

    # Новая логика округления
    remainder = minutes % 15
    if remainder < 8:
        rounded_minutes = (minutes // 15) * 15
    else:
        rounded_minutes = ((minutes // 15) + 1) * 15
    if rounded_minutes == 0:
        rounded_minutes = 15  # Любая поездка (даже 1 минута) считается как 15 минут

    start_str = start_time.strftime("%H:%M")
    end_str = end_time.strftime("%H:%M")
    hours_part = rounded_minutes // 60
    minutes_part = rounded_minutes % 60
    if hours_part > 0:
        ride_time = f"{hours_part} ч {minutes_part} мин"
    else:
        ride_time = f"{minutes_part} мин"
    period_str = f"{date.today().isoformat()} {start_str} — {end_str}"

    total_price = 0
    lines = []
    for cat, qty in data["cart"].items():
        hour_price = bike_categories[cat]["hour"]
        emoji = bike_categories[cat]['emoji']
        minute_price = hour_price / 60
        price = int(minute_price * rounded_minutes)
        line = f"{emoji} <b>{cat}</b>: {qty} шт. × {rounded_minutes} мин × {minute_price:.2f}₽ = {price * qty}₽"
        lines.append(line)
        total_price += price * qty

    # Уведомляем админа
    try:
        await bot.send_message(
            ADMIN_ID,
            f"ЗАВЕРШЕНА АРЕНДА!\n"
            f"User: {message.from_user.full_name}\n"
            f"Телефон: {data['phone'] if data.get('phone') else 'Не указан'}\n"
            f"id: {message.from_user.id}\n"
            f"Время: {start_str} — {end_str} ({ride_time})\n"
            f"Корзина: {data['cart']}\n"
            f"Стоимость: {total_price} руб."
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление админу (конец): {e}")

    # --- Вот ТУТ главный правильный вызов:
    save_rent_to_gsheet({
        "user_id": message.from_user.id,
        "user_name": message.from_user.full_name,
        "phone": data.get("phone"),
        "cart": data.get("cart"),
    }, rounded_minutes, total_price, period_str)
    # ---

    # Сбросить данные аренды, но оставить телефон (чтобы не спрашивать при следующей аренде)
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
        f"⏰ <b>Вы катались {ride_time} на:</b>\n"
        + "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━"
        f"\n<b>🐝 Общая стоимость: <u>{total_price} руб.</u></b>\n\n"
        "<b>💸 Оплата аренды по СБП</b>\n"
        "Переведите сумму на карту:\n"
        "\n<b>💳 <a href='tel:+79062112940'><code>+7 906 211-29-40</code></a></b>\n"
        "\n<b>👤 Виталий А.Г.</b> <i>Сбербанк</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Нажмите на номер, чтобы скопировать или позвонить</i>\n"
        "<i>После оплаты покажите чек сотруднику или отправьте его в аккаунт поддержки.</i>\n\n"
        "<b>🚴 Хотите взять велосипед снова?</b> Просто выберите категорию ниже 👇",
        reply_markup=keyboard,
        disable_web_page_preview=True  # чтобы ссылка выглядела аккуратно
    )

@dp.message(F.text == "/stats")
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    try:
        with open("rents.csv", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
    except FileNotFoundError:
        await message.answer("Пока нет данных о прокатах.")
        return

    total_rents = len(reader)
    bikes_counter = Counter()
    total_income = 0
    total_minutes = 0

    for row in reader:
        try:
            cart = json.loads(row["cart"])
        except Exception:
            cart = {}
        for cat, qty in cart.items():
            bikes_counter[cat] += int(qty)
        total_income += int(row.get("total_price", 0))
        total_minutes += int(row.get("minutes", 0))

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
    await message.answer(
        "Пожалуйста, пользуйтесь кнопками ниже 👇\n"
        "Так оформление пройдёт быстрее и без ошибок!"
    )

# -------- Запуск -------- #
async def send_daily_report():
    try:
        with open("rents.csv", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
    except FileNotFoundError:
        await bot.send_message(ADMIN_ID, "За сегодня нет данных о прокатах.")
        return

    today = date.today().isoformat()
    today_rents = [row for row in reader if today in row["period"]]

    if not today_rents:
        await bot.send_message(ADMIN_ID, "Сегодня прокатов не было.")
        return

    bikes_counter = Counter()
    total_income = 0
    total_minutes = 0
    total_bikes = 0

    for row in today_rents:
        cart = json.loads(row["cart"])
        for cat, qty in cart.items():
            bikes_counter[cat] += int(qty)
            total_bikes += int(qty)
        total_income += int(row["total_price"])
        total_minutes += int(row["minutes"])

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
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
