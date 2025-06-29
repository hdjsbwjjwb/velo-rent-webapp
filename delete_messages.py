from aiogram import Bot, types
from aiogram import Application
from dotenv import load_dotenv
import os

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')  # Новый токен

# Создаем приложение (замена Dispatcher на Application)
application = Application.builder().token(TOKEN).build()

@application.message_handler()
async def handle_message(message: types.Message):
    # Если сообщение нарушает правила, удаляем его
    if "порно" in message.text.lower():  # Например, ищем слово "порно"
        try:
            # Удаляем сообщение
            await message.delete()
            # Отправляем ответ пользователю, что сообщение удалено
            await message.answer("Это сообщение нарушает правила и было удалено.")
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

# Запуск бота
if __name__ == "__main__":
    # Запускаем приложение
    application.run_polling()
