from telethon import TelegramClient
from dotenv import load_dotenv
import os

# Загружаем переменные из .env
load_dotenv()

# Получаем данные из .env
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')  # Используем chat_id из .env

# Подключаемся к Telegram через Telethon
client = TelegramClient('session_name', api_id, api_hash)

async def delete_all_messages():
    await client.start(bot_token=bot_token)

    # Получаем последние 100 сообщений
    messages = await client.get_messages(chat_id, limit=100)

    # Удаляем сообщения
    for message in messages:
        try:
            await client.delete_messages(chat_id, message.id)
            print(f"Удалено сообщение с ID {message.id}")
        except Exception as e:
            print(f"Не удалось удалить сообщение с ID {message.id}: {e}")

# Запускаем клиента
with client:
    client.loop.run_until_complete(delete_all_messages())
