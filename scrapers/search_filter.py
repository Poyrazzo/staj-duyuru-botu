"""Filters for broad web-search results before they become Job objects."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

CURRENT_YEAR = datetime.utcnow().year

SOCIAL_OR_CONTENT_DOMAINS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "youtube.com", "medium.com", "substack.com",
)

NEWS_DOMAINS = (
    "aa.com.tr", "hurriyet.com.tr", "milliyet.com.tr", "sabah.com.tr",
    "sozcu.com.tr", "haberturk.com", "ntv.com.tr", "cnnturk.com",
    "dunya.com", "ekonomim.com", "bloomberght.com", "webrazzi.com",
    "donanimhaber.com", "shiftdelete.net",
)

BLOCKED_DOMAINS = (
    "gooverseas.com", "localjobs.com",
)

JOB_URL_HINTS = (
    "/job", "/jobs", "/career", "/careers", "/kariyer", "/ilan",
    "/is-ilan", "/basvuru", "/başvuru", "/apply", "/position",
    "/positions", "/opening", "/openings", "/staj", "/intern",
)

JOB_HOST_HINTS = (
    "greenhouse.io", "lever.co", "workdayjobs.com", "smartrecruiters.com",
    "taleo.net", "successfactors", "kariyer.net", "youthall.com",
    "toptalent.co", "secretcv.com", "linkedin.com/jobs",
)

APPLICATION_SIGNALS = (
    "başvur", "basvur", "apply", "application", "ilan", "iş ilan",
    "is ilan", "job", "jobs", "career", "careers", "kariyer",
    "position", "positions", "opening", "openings", "hiring",
    "recruiting", "son başvuru", "son basvuru", "deadline",
    "requirements", "qualifications", "aranan nitelikler",
)

STRONG_APPLICATION_SIGNALS = (
    "başvuru", "basvuru", "başvurular", "basvurular", "apply",
    "application", "son başvuru", "son basvuru", "deadline",
)

PERSONAL_UPDATE_PATTERNS = (
    r"\bi('?m| am)?\s+(happy|excited|glad|proud)\s+to\s+(share|announce)\b",
    r"\bstarted\s+(my|a|an|as)\s+.*\bintern",
    r"\bbegan\s+(my|a|an)\s+.*\bintern",
    r"\bjoined\s+.*\s+as\s+.*\bintern",
    r"\bnew\s+position\s+as\s+.*\bintern",
    r"\binternship\s+experience\b",
    r"\bcompleted\s+(my|a|an)?\s*.*\binternship\b",
    r"\bstaja\s+başlad",
    r"\bstaj(a|ı|i|im)?\s+başlad",
    r"\bstaj\s+deneyim",
    r"\bstajımı\s+tamamlad",
)

GUIDE_OR_ARTICLE_PATTERNS = (
    r"\bnedir\b",
    r"\bnasil\s+olunur\b",
    r"\bnasil\s+basvurulur\b",
    r"\bmaasi\b",
    r"\bne\s+kadar\b",
    r"\bsik\s+sorulan\s+sorular\b",
    r"\bkariyerine\s+dair\b",
    r"\bkacirmak\s+istemezsin\b",
    r"\bbilgisayar\s+muhendisligi\b",
    r"\begitim[-\s]ogretim\s+yili\b",
    r"\bstaj\s+i\s+ve\s+staj\s+ii\b",
)

DIRECTORY_TITLE_PATTERNS = (
    r"\bis\s+ilanlari\b",
    r"\bis\s+firsatlari\b",
    r"\bstaj\s+ilanlari\b",
    r"\bstajyer\s+arayan\s+firmalar\b",
    r"\binternships\s+in\s+turkey\b",
)

NON_TURKEY_LOCATION_HINTS = (
    "hudson", "nashua", "new hampshire", "massachusetts", "new york",
    "california", "texas", "florida", "london", "germany", "deutschland",
    "dubai", "egypt", "poland", "netherlands",
)

TURKEY_SIGNALS = (
    "turkey", "turkiye", "remote", "istanbul", "ankara", "izmir",
    "kocaeli", "bursa", "eskisehir", "turk", ".tr/",
)


def is_actionable_search_result(title: str, url: str, snippet: str) -> bool:
    """Return True only for search results that look like application pages."""
    title = (title or "").strip()
    url = (url or "").strip()
    snippet = (snippet or "").strip()
    if not title or not url:
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.lower()
    text = f" {title} {snippet} {url} ".lower()
    normalized_text = _normalize_text(text)
    normalized_title = _normalize_text(title)

    if _is_blocked_domain(domain):
        return False
    if _is_stale(normalized_text):
        return False
    if _is_personal_update(normalized_text):
        return False
    if _is_guide_or_article(normalized_title):
        return False
    if _is_directory_title(normalized_title):
        return False
    if _looks_outside_turkey(normalized_text):
        return False
    if _is_blocked_social_result(domain, path):
        return False

    has_job_url = _contains_any(url.lower(), JOB_URL_HINTS) or _contains_any(
        f"{domain}{path}", JOB_HOST_HINTS
    )
    has_application_signal = _contains_any(text, APPLICATION_SIGNALS)
    has_strong_signal = _contains_any(text, STRONG_APPLICATION_SIGNALS)

    if _is_news_domain(domain):
        return has_strong_signal and not _is_personal_update(text)

    return has_job_url or has_application_signal


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(needle) in normalized for needle in needles)


def _is_stale(text: str) -> bool:
    years = [int(match) for match in re.findall(r"\b20\d{2}\b", text)]
    return bool(years) and max(years) < CURRENT_YEAR


def _is_personal_update(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in PERSONAL_UPDATE_PATTERNS)


def _is_guide_or_article(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in GUIDE_OR_ARTICLE_PATTERNS)


def _is_directory_title(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in DIRECTORY_TITLE_PATTERNS)


def _looks_outside_turkey(text: str) -> bool:
    return _contains_any(text, NON_TURKEY_LOCATION_HINTS) and not _contains_any(text, TURKEY_SIGNALS)


def _is_blocked_domain(domain: str) -> bool:
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS)


def _is_blocked_social_result(domain: str, path: str) -> bool:
    if "linkedin.com" in domain:
        return not (path.startswith("/jobs/") or "/jobs/view" in path)
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in SOCIAL_OR_CONTENT_DOMAINS)


def _is_news_domain(domain: str) -> bool:
    return any(domain == news or domain.endswith(f".{news}") for news in NEWS_DOMAINS)


_TURKISH_TRANSLATION = str.maketrans({
    "ı": "i", "İ": "i",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ş": "s", "Ş": "s",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
})


def _normalize_text(text: str) -> str:
    text = str(text).translate(_TURKISH_TRANSLATION).lower()
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
