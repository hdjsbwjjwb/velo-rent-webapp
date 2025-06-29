from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from dotenv import load_dotenv
import os

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')  # Новый токен
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Удаление всех сообщений бота в чате
@dp.message_handler()
async def handle_message(message: types.Message):
    try:
        # Если сообщение от бота, удаляем
        if message.from_user.is_bot:
            await message.delete()
            print(f"Удалено сообщение с ID {message.message_id}")
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")

# Запуск бота
if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
