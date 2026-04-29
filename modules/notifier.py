"""Telegram notification module with rate-limiting and retry logic."""

import asyncio
import logging
from datetime import datetime

import config
from db.database import Job

logger = logging.getLogger(__name__)

# Telegram hard-limit: 30 messages/second per bot; we stay well under it
SEND_DELAY = 1.5  # seconds between messages

CATEGORY_EMOJI: dict[str, str] = {
    "software":   "💻",
    "marketing":  "📣",
    "finance":    "💰",
    "design":     "🎨",
    "hr":         "🤝",
    "operations": "⚙️",
    "sales":      "📈",
    "other":      "📋",
}

SOURCE_EMOJI: dict[str, str] = {
    "LinkedIn":    "🔵",
    "Kariyer.net": "🟠",
    "Youthall":    "🟣",
}


class TelegramNotifier:
    """Sends job alerts and status messages to a Telegram chat."""

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self._bot = None

    async def _get_bot(self):
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self.token)
        return self._bot

    async def send_job_alert(self, job: Job) -> bool:
        """Send a single job alert. Returns True on success."""
        message = _format_job_message(job)
        return await self._send(message, disable_web_page_preview=True)

    async def send_batch(self, jobs: list[Job]) -> int:
        """Send alerts for multiple jobs. Returns count of successful sends."""
        if not jobs:
            return 0

        sent = 0
        if len(jobs) > 3:
            header = (
                f"🔍 <b>{len(jobs)} yeni staj ilanı bulundu!</b>\n"
                f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
            )
            await self._send(header)
            await asyncio.sleep(SEND_DELAY)

        for job in jobs:
            ok = await self.send_job_alert(job)
            if ok:
                sent += 1
            await asyncio.sleep(SEND_DELAY)

        return sent

    async def send_health_report(self, stats: dict, source_statuses: dict[str, str]) -> None:
        """Send weekly bot health report."""
        lines = [
            "🤖 <b>HAFTALIK BOT DURUM RAPORU</b>",
            f"📅 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            "",
            "📊 <b>Veritabanı İstatistikleri:</b>",
            f"  • Toplam ilan: <code>{stats.get('total', 0)}</code>",
        ]

        by_source = stats.get("by_source", {})
        for src, count in by_source.items():
            emoji = SOURCE_EMOJI.get(src, "📌")
            lines.append(f"  {emoji} {_h(src)}: <code>{count}</code>")

        lines += ["", "🔍 <b>Kaynak Durumları:</b>"]
        for source, status in source_statuses.items():
            icon = "✅" if status == "OK" else "❌"
            lines.append(f"  {icon} {_h(source)}: {_h(status)}")

        by_cat = stats.get("by_category", {})
        if by_cat:
            lines += ["", "🗂 <b>Kategorilere Göre:</b>"]
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                emoji = CATEGORY_EMOJI.get(cat, "📋")
                lines.append(f"  {emoji} {_h(cat.capitalize())}: <code>{count}</code>")

        await self._send("\n".join(lines))

    async def send_startup_message(self) -> None:
        await self._send(
            "🚀 <b>Staj Botu Başlatıldı</b>\n"
            f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
            "LinkedIn, Kariyer.net ve Youthall izleniyor. "
            "Yeni staj ilanları anında bildirilecek."
        )

    async def send_error_alert(self, source: str, error: str) -> None:
        await self._send(
            f"⚠️ <b>HATA: {_h(source)}</b>\n"
            f"<code>{_h(error[:300])}</code>"
        )

    async def _send(
        self,
        text: str,
        disable_web_page_preview: bool = True,
        retries: int = 3,
    ) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured – skipping message.")
            return False

        bot = await self._get_bot()
        for attempt in range(1, retries + 1):
            try:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=disable_web_page_preview,
                )
                return True
            except Exception as exc:
                err = str(exc)
                logger.warning(
                    "Telegram send attempt %d/%d failed: %s", attempt, retries, err
                )
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)

        logger.error("Failed to send Telegram message after %d attempts.", retries)
        return False


def _format_job_message(job: Job) -> str:
    cat_emoji = CATEGORY_EMOJI.get(job.category, "📋")
    src_emoji = SOURCE_EMOJI.get(job.source, "📌")

    lines = [
        f"🚀 <b>YENİ STAJ İLANI</b> {cat_emoji}",
        "",
        f"🏢 <b>Şirket:</b> {_h(job.company)}",
        f"💼 <b>Pozisyon:</b> {_h(job.title)}",
        f"📍 <b>Konum:</b> {_h(job.location or 'Türkiye')}",
        f"{src_emoji} <b>Kaynak:</b> {_h(job.source)}",
    ]

    if job.posted_date:
        lines.append(f"📅 <b>Tarih:</b> {_h(job.posted_date)}")

    if job.category and job.category != "other":
        lines.append(f"🏷 <b>Kategori:</b> {_h(job.category.capitalize())}")

    if job.url:
        lines.append(f"\n🔗 <a href=\"{job.url}\">Başvur / Apply</a>")

    return "\n".join(lines)


def _h(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
