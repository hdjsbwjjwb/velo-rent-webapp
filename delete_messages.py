from aiogram import Bot, Dispatcher, types
import os

# Загружаем токен бота
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler()
async def handle_message(message: types.Message):
    # Если сообщение нарушает правила, удаляем его
    if "Тройничок" in message.text.lower():  # Например, ищем слово "порно"
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
