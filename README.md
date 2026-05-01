# 🤖 Staj Duyuru Botu

**LinkedIn, Kariyer.net ve Youthall'u her 3 saatte bir otomatik olarak tarayan, yeni staj ilanlarını anında Telegram'a bildiren bot.**
---

Her yeni staj ilanı için Telegram'a şöyle bir mesaj gelir:

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

---

## ⚙️ Nasıl Çalışır?

1. Her 3 saatte bir LinkedIn, Kariyer.net ve Youthall'u tarar
2. "Staj", "Intern", "Genç Yetenek" gibi anahtar kelimelerle filtreler
3. "Senior", "Manager" gibi alakasız ilanları eler
4. Aynı ilanı iki kez göndermez (SHA-256 ile tekilleştirme)
5. Her yeni ilan için anında Telegram bildirimi gönderir
6. Haftada bir sağlık raporu yayınlar

---

## 🚀 Kurulum (Adım Adım)

### Gereksinimler
- Python 3.11 veya üstü
- Linux / macOS / Windows (WSL)
- Telegram hesabı

---

### 1. Projeyi İndir

```bash
git clone https://github.com/Poyrazzo/staj-duyuru-botu.git
cd staj-duyuru-botu
```

---

### 2. Telegram Bot Token Al

1. Telegram'da **@BotFather**'a mesaj at
2. `/newbot` yaz ve gönder
3. Bota bir isim ver (örn: `Staj Duyuru Botu`)
4. Kullanıcı adı ver (örn: `stajduyurum_bot` — `bot` ile bitmeli)
5. BotFather sana şöyle bir token gönderir:
   ```
   5823901234:AAFx9kLmN2pQrStUvWxYz1234567890abc
   ```
6. Bu tokeni kopyala

---

### 3. Telegram Chat ID Al

1. Telegram'da **@userinfobot**'a mesaj at
2. `/start` yaz
3. Sana şunu gönderir: `Id: 123456789`
4. Bu numarayı kopyala

---

### 4. `.env` Dosyasını Oluştur

```bash
cp .env.example .env
nano .env
```

Şu iki satırı kendi bilgilerinle doldur:

```
TELEGRAM_BOT_TOKEN=buraya_token_yaz
TELEGRAM_CHAT_ID=buraya_chat_id_yaz
```

Kaydet: `Ctrl+O` → Enter → `Ctrl+X`

---

### 5. Kurulumu Tamamla

```bash
bash setup.sh
```

Bu komut şunları yapar:
- Python sanal ortamı oluşturur
- Tüm bağımlılıkları yükler
- Playwright (Chromium tarayıcısı) indirir

---

### 6. Botu Çalıştır

**Tek seferlik test:**
```bash
source .venv/bin/activate
python main.py
```

**Sürekli çalıştır (her 3 saatte bir):**
```bash
python main.py --loop
```

**Sağlık raporu gönder:**
```bash
python main.py --health
```

---

## ☁️ GitHub Actions ile Ücretsiz 7/24 Çalıştırma

Bilgisayarını kapatsan bile bot çalışmaya devam etsin istiyorsan:

### 1. Repoyu Fork'la veya Klonla

```bash
git clone https://github.com/Poyrazzo/staj-duyuru-botu.git
```

### 2. GitHub Secrets Ekle

GitHub reposunda:
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Şu iki secret'ı ekle:

| İsim | Değer |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | BotFather'dan aldığın token |
| `TELEGRAM_CHAT_ID` | userinfobot'tan aldığın ID |

### 3. Actions'ı Etkinleştir

Repo sayfasında **Actions** sekmesine git → **"I understand my workflows, go ahead and enable them"** butonuna bas.

Artık bot her 3 saatte bir otomatik çalışır, Telegram'a bildirim gönderir.

---

## 🔧 Ayarlar (`.env`)

| Değişken | Varsayılan | Açıklama |
|----------|-----------|---------|
| `TELEGRAM_BOT_TOKEN` | — | BotFather token |
| `TELEGRAM_CHAT_ID` | — | Bildirim gönderilecek chat |
| `RUN_INTERVAL_MINUTES` | `180` | Çalışma aralığı (dakika) |
| `MAX_JOBS_PER_SOURCE` | `50` | Kaynak başına max ilan |
| `LOOKBACK_DAYS` | `1` | Kaç günlük ilan çekilsin |
| `HEADLESS` | `true` | `false` yaparak tarayıcıyı görsel aç |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

---

## 📁 Proje Yapısı

```
staj-duyuru-botu/
├── main.py                    # Ana orkestratör
├── config.py                  # Merkezi yapılandırma
├── requirements.txt
├── setup.sh                   # Kurulum scripti
├── .env.example               # Ortam değişkenleri şablonu
├── db/
│   └── database.py            # SQLite veritabanı katmanı
├── scrapers/
│   ├── linkedin_scraper.py    # LinkedIn (JobSpy)
│   ├── kariyer_scraper.py     # Kariyer.net (Playwright)
│   └── youthall_scraper.py    # Youthall (Playwright)
├── modules/
│   ├── data_cleaner.py        # Filtre ve kategori
│   ├── notifier.py            # Telegram bildirimleri
│   └── health_check.py        # Haftalık sağlık raporu
└── .github/workflows/
    └── scrape.yml             # GitHub Actions (ücretsiz)
```

---

## 🏷️ Desteklenen Kategoriler

Bot ilanları otomatik olarak kategorilere ayırır:

| Emoji | Kategori | Anahtar Kelimeler |
|-------|----------|------------------|
| 💻 | Yazılım | software, developer, backend, frontend, data, AI |
| 📣 | Pazarlama | marketing, dijital, sosyal medya, SEO |
| 💰 | Finans | finans, muhasebe, yatırım, audit |
| 🎨 | Tasarım | tasarım, UI, UX, grafik |
| 🤝 | İK | insan kaynakları, recruitment, işe alım |
| ⚙️ | Operasyon | lojistik, supply chain, tedarik |
| 📈 | Satış | satış, business development |

---

## ❓ Sık Sorulan Sorular

**S: Bot ücretsiz mi çalışır?**
E: Evet. GitHub Actions ayda 2000 dakika ücretsiz sağlar. 3 saatlik çalışma yaklaşık 240 dakika/ay kullanır.

**S: Aynı ilan iki kez gelir mi?**
H: Hayır. Her ilan SHA-256 hash ile kayıt altına alınır, bir daha gönderilmez.

**S: Yeni site eklenebilir mi?**
E: Evet. Her site için yaklaşık 50–80 satır Python kodu yeterli.

**S: Bot ne zaman çalışır?**
H: GitHub Actions ile Türkiye saati 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00 ve 21:00'de.

---

## 📄 Lisans

MIT License — dilediğin gibi kullanabilirsin.
