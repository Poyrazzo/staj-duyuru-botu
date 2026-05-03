"""Telegram notification module — rich HTML format with all detail fields."""

import asyncio
import logging
from datetime import datetime
from collections.abc import Callable

import config
from db.database import Job

logger = logging.getLogger(__name__)

SEND_DELAY = 1.5

CATEGORY_EMOJI: dict[str, str] = {
    "software":    "💻",
    "marketing":   "📣",
    "finance":     "💰",
    "design":      "🎨",
    "hr":          "🤝",
    "operations":  "⚙️",
    "sales":       "📈",
    "legal":       "⚖️",
    "engineering": "🔧",
    "other":       "📋",
}

SOURCE_EMOJI: dict[str, str] = {
    "LinkedIn":      "🔵",
    "Kariyer.net":   "🟠",
    "Youthall":      "🟣",
    "Toptalent":     "🟡",
    "Vizyoner Genç": "🟤",
    "Kariyer Kapısı":"🟢",
}


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = config.TELEGRAM_BOT_TOKEN if token is None else token
        self.chat_id = config.TELEGRAM_CHAT_ID if chat_id is None else chat_id
        self._bot = None

    async def _get_bot(self):
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self.token)
        return self._bot

    async def send_job_alert(self, job: Job) -> bool:
        return await self._send(_format_job_message(job), disable_web_page_preview=True)

    async def send_batch(self, jobs: list[Job]) -> int:
        return len(await self.send_job_batch(jobs))

    async def send_job_batch(
        self,
        jobs: list[Job],
        on_sent: Callable[[str], None] | None = None,
    ) -> list[str]:
        if not jobs:
            return []
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured – skipping batch.")
            return []
        sent_job_ids: list[str] = []
        if len(jobs) > 3:
            await self._send(
                f"🔍 <b>{len(jobs)} yeni staj ilanı bulundu!</b>\n"
                f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
            )
            await asyncio.sleep(SEND_DELAY)
        for job in jobs:
            if await self.send_job_alert(job):
                sent_job_ids.append(job.job_id)
                if on_sent:
                    on_sent(job.job_id)
            await asyncio.sleep(SEND_DELAY)
        return sent_job_ids

    async def send_health_report(self, stats: dict, source_statuses: dict[str, str]) -> None:
        lines = [
            "🤖 <b>HAFTALIK BOT DURUM RAPORU</b>",
            f"📅 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            "",
            "📊 <b>Veritabanı:</b>",
            f"  • Toplam ilan: <code>{stats.get('total', 0)}</code>",
        ]
        for src, count in stats.get("by_source", {}).items():
            emoji = SOURCE_EMOJI.get(src, "📌")
            lines.append(f"  {emoji} {_h(src)}: <code>{count}</code>")
        lines += ["", "🔍 <b>Kaynak Durumları:</b>"]
        for source, status in source_statuses.items():
            icon = "✅" if status == "OK" else "❌"
            lines.append(f"  {icon} {_h(source)}: {_h(status)}")
        by_cat = stats.get("by_category", {})
        if by_cat:
            lines += ["", "🗂 <b>Kategoriler:</b>"]
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                emoji = CATEGORY_EMOJI.get(cat, "📋")
                lines.append(f"  {emoji} {_h(cat.capitalize())}: <code>{count}</code>")
        await self._send("\n".join(lines))

    async def send_startup_message(self) -> None:
        import config as _cfg
        await self._send(
            "🚀 <b>Staj Botu Başlatıldı</b>\n"
            f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
            "LinkedIn, Kariyer.net, Youthall, Toptalent, Vizyoner Genç, "
            f"Kariyer Kapısı, SecretCV, Yenibiriş, Co-Matching, İSO Staj\n"
            f"ve <b>{len(_cfg.COMPANY_CONFIGS)} şirket kariyer sayfası</b> izleniyor.\n"
            "Yeni staj ilanları anında bildirilecek. ✅"
        )

    async def send_error_alert(self, source: str, error: str) -> None:
        await self._send(
            f"⚠️ <b>HATA: {_h(source)}</b>\n<code>{_h(error[:300])}</code>"
        )

    async def _send(self, text: str, disable_web_page_preview: bool = True, retries: int = 3) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured – skipping.")
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
                logger.warning("Telegram attempt %d/%d: %s", attempt, retries, exc)
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
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
        lines.append(f"📅 <b>İlan Tarihi:</b> {_h(job.posted_date)}")

    if job.deadline:
        lines.append(f"⏰ <b>Son Başvuru:</b> <b>{_h(job.deadline)}</b>")

    if job.start_date:
        lines.append(f"🗓 <b>Başvuru Başlangıç:</b> {_h(job.start_date)}")

    if job.category and job.category != "other":
        lines.append(f"🏷 <b>Kategori:</b> {_h(job.category.capitalize())}")

    if job.requirements:
        # Show only first 200 chars of requirements
        req_preview = job.requirements[:200].strip()
        if len(job.requirements) > 200:
            req_preview += "…"
        lines.append(f"\n📋 <b>Aranan Nitelikler:</b>\n<i>{_h(req_preview)}</i>")

    if job.url:
        lines.append(f"\n🔗 <a href=\"{job.url}\">Başvur / Apply</a>")

    return "\n".join(lines)


def _h(text: str) -> str:
    """HTML-escape for Telegram parse_mode='HTML'."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
