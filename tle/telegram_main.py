import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import CommandStart, Command
from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.client.session.aiohttp import AiohttpSession

from tle import constants
from tle.util import codeforces_common as cf_common, font_downloader


async def setup():
    # Create necessary directories and configure logging similar to discord version
    for path in constants.ALL_DIRS:
        os.makedirs(path, exist_ok=True)

    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(constants.LOG_FILE_PATH),
        ],
    )

    # download fonts for matplotlib
    font_downloader.maybe_download()


async def ping_handler(message: types.Message):
    await message.answer("Pong!")


async def main():
    await setup()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        logging.error("BOT_TOKEN env variable required")
        return

    # aiogram 3 requires a session object if we set timeout limits etc.
    session = AiohttpSession()
    bot = Bot(token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.message.middleware(ChatActionMiddleware())

    # --- Register handlers ---
    dp.message.register(ping_handler, Command("ping"))

    # /user <handle> – basic Codeforces user info

    async def user_info_handler(message: types.Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) == 1:
            await message.answer("Usage: /user <handle>")
            return
        handle = parts[1].strip()
        try:
            (user,) = await cf_common.cf.user.info(handles=[handle])  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            from tle.util.telegram_common import embed_alert, safe_send

            await safe_send(message, embed_alert(f"Error: {e}"))
            return

        from tle.util.telegram_common import embed_success

        desc = f"<a href='{user.url}'>{user.handle}</a>\nRating: {user.rating if user.rating else 'Unrated'}"
        await message.answer(embed_success(desc), disable_web_page_preview=True)

    dp.message.register(user_info_handler, Command("user"))

    # init Codeforces cache/db etc. similar to Discord bot on_ready
    await cf_common.initialize(False)

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
