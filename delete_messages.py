from aiogram import Bot, types
from aiogram import Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import executor
from dotenv import load_dotenv
import os

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')  # Новый токен

# Инициализируем объект бота
bot = Bot(token=TOKEN)

# Инициализируем объект Application (Dispatcher больше не используется напрямую)
from aiogram import Application
application = Application.builder().token(TOKEN).build()

# Обработчик сообщений
@application.message_handler()
async def handle_message(message: types.Message):
    # Если сообщение нарушает правила, удаляем его
    if "порно" in message.text.lower():  # Например, ищем слово "порно"
        try:
            # Удаляем сообщение
            await message.delete()
            # Отправляем ответ пользователю, что сообщение удалено
            await message.answer("Это сообщение нарушает правила и было удалено.", reply_markup=None)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

# Запуск бота
if __name__ == "__main__":
    # Запуск приложения
    application.run_polling()
