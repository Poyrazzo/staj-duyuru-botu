# 🤖 Staj Duyuru Botu

Türkiye'deki staj ilanlarını **LinkedIn**, **Kariyer.net** ve **Youthall**'dan 7/24 izleyip Telegram'a anlık bildirim gönderen otomasyon botu.

---

## Özellikler

| Özellik | Detay |
|---|---|
| **3 Kaynak** | LinkedIn (JobSpy), Kariyer.net (Playwright), Youthall (Playwright + API intercept) |
| **Stealth Tarayıcı** | `playwright-stealth` ile Cloudflare & bot algılama bypass |
| **Anlık Bildirim** | Her yeni ilan için Telegram mesajı |
| **Akıllı Dedup** | Aynı ilan farklı sitede görünse bile tek bildirim |
| **Rol Kategorisi** | Yazılım / Pazarlama / Finans / Tasarım / İK vb. otomatik etiket |
| **SQLite Kalıcılık** | Hangi ilanların bildirildiği takip edilir |
| **Haftalık Rapor** | Bot sağlık durumu ve istatistik özeti |
| **Cron & GitHub Actions** | Sıfır maliyetle zamanlanmış çalışma |

---

## Hızlı Başlangıç

```bash
# 1. Depoyu klonla
git clone <repo-url> staj-bot && cd staj-bot

# 2. Kurulum (venv + bağımlılıklar + Playwright)
bash setup.sh

# 3. Telegram bilgilerini gir
nano .env
#   TELEGRAM_BOT_TOKEN=xxxx:yyyy
#   TELEGRAM_CHAT_ID=123456789

# 4. Tek seferlik test çalıştır
source .venv/bin/activate
python main.py

# 5. Sürekli çalıştır (her 30 dk)
python main.py --loop
```

---

## Telegram Bot Kurulumu

1. Telegram'da `@BotFather`'a mesaj at → `/newbot` → token al
2. `@userinfobot`'a mesaj at → chat ID'ni öğren
3. `.env` dosyasına yaz

---

## Kullanım

```
python main.py              # Bir kez çalıştır
python main.py --loop       # Her 30 dk'da bir çalıştır (config ile ayarlanır)
python main.py --health     # Zorla sağlık raporu gönder
```

---

## Proje Yapısı

```
.
├── main.py                 # Ana orkestratör
├── config.py               # Merkezi yapılandırma
├── requirements.txt
├── setup.sh                # Kurulum scripti
├── .env.example            # Ortam değişkenleri şablonu
├── db/
│   └── database.py         # SQLite kalıcılık katmanı
├── scrapers/
│   ├── base_scraper.py
│   ├── linkedin_scraper.py  # JobSpy ile LinkedIn
│   ├── kariyer_scraper.py   # Playwright ile Kariyer.net
│   └── youthall_scraper.py  # Playwright ile Youthall
├── modules/
│   ├── data_cleaner.py      # Filtre, dedup, kategorileme
│   ├── notifier.py          # Telegram bildirimleri
│   ├── health_check.py      # Haftalık sağlık raporu
│   └── logger_setup.py      # Renkli log yapılandırması
├── cron/
│   ├── install_cron.sh      # Cron job kur
│   └── remove_cron.sh       # Cron job kaldır
└── .github/workflows/
    └── scrape.yml           # GitHub Actions (ücretsiz hosting)
```

---

## GitHub Actions ile Ücretsiz Çalıştırma

1. Repoyu GitHub'a push la
2. `Settings → Secrets → Actions` kısmına ekle:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. `.github/workflows/scrape.yml` otomatik devreye girer (her 30 dk)

---

## Yapılandırma (`.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | BotFather'dan alınan token |
| `TELEGRAM_CHAT_ID` | — | Bildirim gönderilecek chat ID |
| `RUN_INTERVAL_MINUTES` | `30` | Döngü aralığı (dakika) |
| `MAX_JOBS_PER_SOURCE` | `50` | Kaynak başına max ilan |
| `LOOKBACK_DAYS` | `1` | Kaç günlük ilan çekilsin |
| `HEADLESS` | `true` | `false` yaparak tarayıcıyı görsel aç |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

---

## Telegram Bildirim Formatı

```
🚀 YENİ STAJ İLANI 💻

🏢 Şirket: Trendyol
💼 Pozisyon: Software Engineering Intern
📍 Konum: İstanbul, Türkiye
🔵 Kaynak: LinkedIn
📅 Tarih: 2025-05-15
🏷 Kategori: Software

🔗 Başvur / Apply
```
