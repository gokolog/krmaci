# Çok botlu Binance **Testnet** trader (deney)

Para kazandırma garantisi YOKTUR. Amaç: sistemi gerçek para olmadan test etmek ve **ücret sonrası net sonucu** ölçmek.

## Roller
| Rol | Tür | Görev |
|---|---|---|
| Hacim Tarayıcı | kod (`scanner.py`) | hacim z-score + fiyat hareketi |
| Haberci | LLM + web arama | sebep bulur, **kaynak zorunlu** (kaynaksız → BEKLE) |
| Stratejist | LLM | giriş/stop/hedef |
| Şüpheci | LLM | itiraz eder, engelleyici itiraz → GEÇ |
| Karar Masası | LLM | LONG / SHORT / BEKLE / GEÇ |
| Risk Yöneticisi | **kod** (`risk.py`) | veto hakkı; stop, R/R, günlük/toplam zarar, işlem sayısı |
| Yürütücü | kod (`executor.py`) | paper veya testnet emri |
| Günlükçü | kod (`journal.py`) | tüm konuşmalar + brüt/net sonuçlar → `data/journal.jsonl` |

Spot'ta SHORT yürütülmez; sadece sinyal olarak loglanır.

## Kurulum
```bash
cd trader
pip install -r requirements.txt
cp .env.example .env   # anahtarları doldur, sonra: set -a; source .env; set +a
```
Testnet anahtarı: https://testnet.binance.vision (GitHub ile giriş → Generate HMAC-SHA-256 Key). Para çekme izni zaten yok.

## Çalıştırma (sırayla)
```bash
python -m pytest -q                 # testler
python main.py --mode paper --once  # tek tur dene
python main.py --mode paper         # 2-4 hafta sahte bakiyeyle
python main.py --mode testnet       # testnet emirleri
```
Başlangıç bakiyesi/limitler: `config.py` (10$, günlük max zarar 1$, toplam 3$ kill-switch, günde max 5 işlem).

## Sonucu okuma
`data/journal.jsonl` içinde `kind=close` satırları `gross`, `fees`, `net` verir. 2 hafta sonra toplam **net** sıfırın altındaysa strateji çalışmıyor demektir; gerçek paraya geçme.

## Bilinen sınırlar
- Stop/hedef botun döngüsünde kontrol edilir (bot kapalıyken çalışmaz). Sonraki adım: Binance OCO emri.
- Bu ortamdan testnet'e erişilemedi; Binance istemcisi gerçek testnet'e karşı test EDİLMEDİ, yalnızca sahte istemciyle test edildi. İlk çalıştırmada `--once` ile izle.
- Haberci'nin web arama aracı (`web_search_20250305`) ve LLM çıktı formatı gerçek API'ye karşı denenmedi.
- Testnet likiditesi/fiyatları gerçek piyasayı yansıtmaz; sonuçlar sadece mekanik doğrulama içindir.
