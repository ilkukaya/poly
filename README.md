# 🐺 Wolf of Polymarket — Paper Trading System

**$30 → Growth Machine | Tamamen Ücretsiz Altyapı**

---

## 🚀 5 Dakikada Kurulum (Adım Adım)

### Adım 1: GitHub Repo Oluştur

1. https://github.com/new adresine git
2. Repository name: `polymarket-paper-trader`
3. **Public** seç (ücretsiz sınırsız Actions dakikası için)
4. "Add a README" tikini KOYMA
5. **Create repository** butonuna bas

### Adım 2: Dosyaları Yükle

Repo sayfasında "uploading an existing file" linkine tıkla, veya terminalden:

```bash
git clone https://github.com/SENIN-USERNAME/polymarket-paper-trader.git
cd polymarket-paper-trader

# Bu paketin tüm dosyalarını buraya kopyala
# Yapı şöyle olmalı:
#
# polymarket-paper-trader/
# ├── .github/
# │   └── workflows/
# │       └── polymarket_scanner.yml
# ├── polymarket_trader/
# │   ├── config.py
# │   ├── api.py
# │   ├── strategies.py
# │   ├── portfolio.py
# │   ├── scanner.py
# │   ├── dashboard_export.py
# │   ├── portfolio.json      (mevcut paper trade state)
# │   ├── trade_log.json
# │   └── scan_log.json
# ├── logs/                    (boş klasör - .gitkeep koy)
# ├── index.html               (dashboard)
# └── README.md

mkdir -p logs
touch logs/.gitkeep

git add .
git commit -m "Initial setup - $30 paper trade başlangıç"
git push
```

### Adım 3: GitHub Actions'ı Etkinleştir

1. Repo sayfasında **Actions** sekmesine git
2. "I understand my workflows, go ahead and enable them" butonuna bas
3. Artık her 4 saatte bir otomatik çalışacak!

### Adım 4: GitHub Pages Dashboard'u Aç

1. Repo sayfasında **Settings** → **Pages** bölümüne git
2. Source: "Deploy from a branch"
3. Branch: `main`, folder: `/ (root)`
4. **Save** butonuna bas
5. 2-3 dakika bekle, dashboard şu adreste açılacak:
   `https://SENIN-USERNAME.github.io/polymarket-paper-trader/`

### Adım 5: İlk Manuel Çalıştırma

1. **Actions** sekmesine git
2. Sol menüden "Polymarket Paper Trader" seç
3. "Run workflow" butonuna bas
4. Mode: `scan` seç → **Run workflow**
5. Çalışmasını izle (1-2 dakika sürer)

---

## 📊 Track Record Nerede?

### 1. Web Dashboard (Birincil)
`https://SENIN-USERNAME.github.io/polymarket-paper-trader/`

Otomatik güncellenen dashboard'da şunları görürsün:
- Equity (toplam portföy değeri)
- Return % (başlangıçtan bu yana getiri)
- Win Rate
- Açık pozisyonlar
- Son trade'ler
- Strateji bazlı performans
- Equity curve grafiği

### 2. GitHub Commit History
Repo'nun commit geçmişinde her scan'in sonucunu görebilirsin.
Her commit mesajında o anki equity yazıyor:
```
📊 Scan 2026-03-24 08:00 UTC | Equity: $31.45
📊 Scan 2026-03-24 12:00 UTC | Equity: $32.10
📊 Scan 2026-03-25 00:00 UTC | Equity: $33.80
```

### 3. JSON Dosyaları (Ham Veri)
- `portfolio.json` — Anlık portföy durumu
- `trade_log.json` — Tüm trade geçmişi (her giriş/çıkış)
- `scan_log.json` — Her scan'in özeti
- `dashboard_data.json` — Dashboard için işlenmiş veri

---

## ⚙️ Nasıl Çalışıyor?

```
Her 4 saatte bir (GitHub Actions cron):
  ┌─────────────────────────────────────────┐
  │  1. Resolution Check                     │
  │     Açık pozisyonlar çözüldü mü?        │
  │     → Evet: P&L hesapla, kapat          │
  │     → Hayır: Fiyat güncelle             │
  ├─────────────────────────────────────────┤
  │  2. Market Scan                          │
  │     500+ aktif marketi tara              │
  │     Tüm kategoriler: spor, politika,    │
  │     kripto, jeopolitik, kültür...        │
  ├─────────────────────────────────────────┤
  │  3. Strategy Engine                      │
  │     5 strateji paralel çalışır:         │
  │     • PENNY_PICK (düşük risk)           │
  │     • VALUE_BET (mispricing)            │
  │     • CALENDAR (zaman çürümesi)         │
  │     • MOMENTUM (trend takibi)           │
  │     • MEAN_REVERT (aşırı tepki)         │
  ├─────────────────────────────────────────┤
  │  4. Position Sizing (Kelly Criterion)    │
  │     Edge × Confidence → Pozisyon büyükl.│
  │     Phase'e göre max limit uygula       │
  ├─────────────────────────────────────────┤
  │  5. Execute Paper Trades                 │
  │     Slippage + komisyon simülasyonu      │
  │     Stop loss kontrol                    │
  ├─────────────────────────────────────────┤
  │  6. Commit & Push                        │
  │     Sonuçları repo'ya kaydet            │
  │     Dashboard otomatik güncellenir       │
  └─────────────────────────────────────────┘
```

---

## 💰 Maliyet

| Bileşen | Maliyet |
|---------|---------|
| GitHub (public repo) | $0/ay |
| GitHub Actions (public repo) | $0/ay — sınırsız dakika |
| GitHub Pages (dashboard) | $0/ay |
| Polymarket API | $0/ay — public API |
| **TOPLAM** | **$0/ay** |

---

## 🔧 Manuel Kontrol

GitHub Actions sayfasından "Run workflow" ile istediğin zaman tetikleyebilirsin:

| Mode | Ne yapar |
|------|----------|
| `scan` | Tam tarama + trade execution |
| `dry` | Sadece tarama, trade yapmaz |
| `check` | Sadece resolution kontrolü |
| `status` | Portföy durumunu göster |

---

## 📱 Telegram Bildirimleri (Opsiyonel)

İleride eklenecek: Her trade açıldığında/kapandığında Telegram'a mesaj.

1. @BotFather'dan bot oluştur → Token al
2. GitHub repo → Settings → Secrets → New:
   - `TELEGRAM_BOT_TOKEN`: Bot tokenin
   - `TELEGRAM_CHAT_ID`: Senin chat ID'n

---

## ⚠️ Önemli Notlar

- Bu %100 PAPER TRADE'dir. Gerçek para kullanılmaz.
- Polymarket API'den gerçek fiyatlar çekilir, trade'ler simüle edilir.
- Slippage (0.5%) ve komisyon (kazançta 2%) dahil edilir.
- Sistem kendi kendine öğrenmez, sabit kurallarla çalışır.
- Phase 2'ye geçince ($100+ equity) stratejiler otomatik genişler.

---

## 📈 Hedefler

| Tarih | Hedef Equity | Phase |
|-------|-------------|-------|
| 23 Mart 2026 | $30 (başlangıç) | 1 - Survival |
| 15 Nisan 2026 | $100+ | 2 - Growth |
| 30 Nisan 2026 | $250-600 | 2-3 |
| Haziran 2026 | $1,000+ | 3 - Scale |
