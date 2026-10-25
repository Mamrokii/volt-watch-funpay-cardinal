"""
VOLT Watch — сторож лотов FunPay (бесплатный плагин VOLT).

- Каждые 15 минут сверяет активные лоты на профиле с прошлой проверкой.
- Если лот пропал (снят модерацией, деактивирован после продажи, удалён) или появился новый —
  присылает уведомление в Telegram.
- Команда /lots: сколько активных лотов в каждом разделе.

Больше плагинов VOLT: https://t.me/VOLT_PLUGINS
"""

from __future__ import annotations

import html
import logging
import threading
import time
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

NAME = "VOLT Watch"
VERSION = "1.0.0"
DESCRIPTION = "Уведомляет, если лот пропал с профиля. Команда /lots. Бесплатно от VOLT: t.me/VOLT_PLUGINS"
CREDITS = "VOLT Plugins · t.me/VOLT_PLUGINS"
UUID = "c4f8a2d6-1e3b-4a7c-8d59-b0e2f6c3a184"
SETTINGS_PAGE = False

CHECK_INTERVAL = 15 * 60
MAX_ITEMS_IN_ALERT = 15

logger = logging.getLogger(f"FPC.{NAME}")
LOGGER_PREFIX = f"[{NAME}]"
_known: dict[int | str, tuple[str, str]] = {}
_first_check_done = False
_lock = threading.Lock()


def get_active_lots(cardinal: Cardinal) -> dict[int | str, tuple[str, str]]:
    """{id лота: (название, раздел)} для всех активных лотов на профиле."""
    profile = cardinal.account.get_user(cardinal.account.id)
    return {lot.id: ((lot.description or "").strip(), lot.subcategory.fullname if lot.subcategory else "")
            for lot in profile.get_lots()}


def check(cardinal: Cardinal) -> tuple[list, list]:
    """Возвращает (пропавшие, новые) с прошлой проверки. Первая проверка только запоминает лоты."""
    global _known, _first_check_done
    with _lock:
        current = get_active_lots(cardinal)
        if not _first_check_done:
            _known, _first_check_done = current, True
            logger.info(f"{LOGGER_PREFIX} Слежу за {len(current)} лотами.")
            return [], []
        gone = [(lid, *_known[lid]) for lid in _known if lid not in current]
        new = [(lid, *current[lid]) for lid in current if lid not in _known]
        _known = current
        return gone, new


def build_alert(gone: list, new: list) -> str:
    lines = []
    if gone:
        lines += [f"⚠️ <b>VOLT Watch: пропали лоты ({len(gone)})</b>", ""]
        for lid, title, category in gone[:MAX_ITEMS_IN_ALERT]:
            lines.append(f"• {html.escape(title[:70])}\n  {html.escape(category)} · ID {lid}")
        if len(gone) > MAX_ITEMS_IN_ALERT:
            lines.append(f"...и ещё {len(gone) - MAX_ITEMS_IN_ALERT}")
        lines += ["", "Проверь: лот мог снять модератор или он деактивировался после продажи."]
    if new:
        if lines:
            lines.append("")
        lines.append(f"🆕 Новых активных лотов: {len(new)}")
    return "\n".join(lines)


def watch_loop(cardinal: Cardinal):
    while True:
        try:
            gone, new = check(cardinal)
            if gone or new:
                logger.info(f"{LOGGER_PREFIX} Пропало: {len(gone)}, новых: {len(new)}")
                if cardinal.telegram:
                    cardinal.telegram.send_notification(build_alert(gone, new))
        except Exception as e:
            logger.error(f"{LOGGER_PREFIX} Ошибка проверки лотов: {e}")
            logger.debug("TRACEBACK", exc_info=True)
        time.sleep(CHECK_INTERVAL)


def start_watch(cardinal: Cardinal):
    threading.Thread(target=watch_loop, args=(cardinal,), daemon=True).start()


def init_telegram(cardinal: Cardinal):
    if not cardinal.telegram:
        return
    tg = cardinal.telegram

    def lots_cmd(message):
        try:
            lots = get_active_lots(cardinal)
            by_category = Counter(category for _, category in lots.values())
            lines = [f"📦 <b>Активных лотов: {len(lots)}</b>", ""]
            lines += [f"• {html.escape(cat or 'Без раздела')}: {n}" for cat, n in by_category.most_common()]
            lines += ["", "⚡ Больше плагинов: t.me/VOLT_PLUGINS"]
            tg.bot.send_message(message.chat.id, "\n".join(lines), disable_web_page_preview=True)
        except Exception as e:
            tg.bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

    cardinal.add_telegram_commands(UUID, [("lots", "сводка активных лотов", True)])
    tg.msg_handler(lots_cmd, commands=["lots"])


BIND_TO_PRE_INIT = [init_telegram]
BIND_TO_POST_INIT = [start_watch]
BIND_TO_DELETE = None
