import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from bot_handlers import register_handlers

logging.basicConfig(level=logging.INFO)


async def web_health_check(request):
    return web.Response(text="Альоу Кицюня! Бот працює, все чітко. 🤙")


async def main():
    app = web.Application()
    app.router.add_get('/', web_health_check)

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    register_handlers(dp)

    async def start_bot_polling(app_instance):
        await dp.start_polling(bot)

    app.on_startup.append(start_bot_polling)

    port = int(os.environ.get('PORT', 10000))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logging.info(f"Сервер запущено на порті {port}. Бот починає роботу.")

    await asyncio.Event().wait()


if __name__ == '__main__':
    if not BOT_TOKEN:
        logging.critical("Не знайдено токен бота. Перевір змінні середовища.")
    else:
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            logging.info("Бот зупинений.")
