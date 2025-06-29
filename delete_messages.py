from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import os

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')  # Новый токен
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler()
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
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
