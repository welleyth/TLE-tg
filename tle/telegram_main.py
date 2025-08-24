import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
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

    from tle.tg.commands import get_router
    dp.include_router(get_router())

    # Middlewares
    dp.message.middleware(ChatActionMiddleware())

    # ---------------- Register bot commands globally -----------------

    async def set_bot_commands(bot: Bot):
        commands = [
            types.BotCommand(command="ping", description="Health check"),
            types.BotCommand(command="user", description="Codeforces user info"),
            types.BotCommand(command="handle", description="Link or get Codeforces handle"),
            types.BotCommand(command="gimme", description="Recommend a Codeforces problem"),
        ]
        await bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())

    # command handlers are now in tle.tg.commands

    # init Codeforces cache/db etc. similar to Discord bot on_ready
    await cf_common.initialize(False)

    # Start polling
    try:
        await set_bot_commands(bot)

        # Listener: log when bot status changes in supergroups
        @dp.chat_member()
        async def chat_member_update(event: types.ChatMemberUpdated):
            old, new = event.old_chat_member, event.new_chat_member
            if old.status != new.status:
                logging.info("ChatMember update in %s: %s -> %s", event.chat.title, old.status, new.status)

        await dp.start_polling(bot)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
