from __future__ import annotations

import logging
from typing import List

from aiogram import Router, types, Bot
from aiogram.enums import ParseMode
from aiogram.filters.command import Command

from tle.util import codeforces_common as cf_common, events
from tle.util.telegram_common import embed_success, embed_alert, hyperlink

logger = logging.getLogger(__name__)

router = Router()


# ---- Command to enable/disable auto standings ----


auto_chats_key = "tg_auto_standings_chats"  # key in misc storage; fallback to user_db methods


@router.message(Command("standings"))
async def standings_cmd(message: types.Message):
    if not message.chat.type.endswith("group"):
        await message.answer(embed_alert("This command must be used in a group."))
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) == 1:
        await message.answer("Usage: /standings here|off")
        return
    sub = parts[1].lower()
    chat_id = message.chat.id
    if sub == "here":
        cf_common.user_db.set_rankup_channel(chat_id, chat_id)  # chat_id as both guild and channel analogue
        await message.answer(embed_success("Standings digest enabled for this chat."))
    elif sub == "off":
        cf_common.user_db.clear_rankup_channel(chat_id)
        await message.answer(embed_success("Standings digest disabled."))
    else:
        await message.answer("Unknown option. Use here/off.")


# ---- Listener for rating changes ----


def register_listener(bot: Bot):
    """Attach rating update listener to event system sending digests via *bot*."""

    @events.listener_spec(
        name="TelegramStandingsDigest",
        event_cls=events.RatingChangesUpdate,
        with_lock=True,
    )
    async def _on_rating_changes(event):
        contest, changes = event.contest, event.rating_changes
        change_by_handle = {c.handle: c for c in changes}

        # chats configured
        chat_ids = cf_common.user_db.get_all_rankup_channels()  # returns list[(chat_id, channel)] in original; adapt
        chat_ids = [cid for cid in chat_ids if cid == cid[0]] if isinstance(chat_ids, list) else []
        # fallback: if user_db not adapted, use all chats with handles
        if not chat_ids:
            chat_ids = [chat for chat, _ in cf_common.user_db.get_all_chats()]

        for chat_id in chat_ids:
            user_id_handle_pairs = cf_common.user_db.get_handles_for_guild(chat_id)
            member_changes = [change_by_handle[h] for _, h in user_id_handle_pairs if h in change_by_handle]
            if not member_changes:
                continue
            member_changes.sort(key=lambda c: c.newRating - c.oldRating, reverse=True)
            lines = []
            for ch in member_changes[:15]:
                delta = ch.newRating - ch.oldRating
                lines.append(
                    f"{hyperlink(ch.handle, cf_common.PROFILE_BASE_URL + ch.handle)}: {ch.oldRating} → {ch.newRating} (Δ{delta:+})"
                )
            text = (
                f"<b>{contest.name}</b> rating updates for this chat:\n" + "\n".join(lines)
            )
            try:
                await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except Exception as e:
                logger.warning("Failed to send standings to %s: %s", chat_id, e)

    # register
    cf_common.event_sys.add_listener(_on_rating_changes)


def get_router() -> Router:
    return router
