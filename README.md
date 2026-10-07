# UMUT Scanner

Windows masaüstünde çalışan, Binance Spot USDT piyasasını halka açık verilerle tarayan teknik analiz uygulaması.

> Bu yazılım yatırım tavsiyesi değildir. Skorlar olasılık veya başarı garantisi değil, teknik koşul uyum skorlarıdır.

## V1 kapsamı

- Binance Spot USDT evreni
- Hacme göre en likit pariteleri tarama
- EMA 20 / 50 / 200
- ADX + DI
- RSI
- MACD histogram
- ROC
- RVOL
- ATR
- Onaylı swing high / swing low piyasa yapısı
- Üst zaman dilimi doğrulaması
- Trend / Setup / Entry / Genel skor
- AL / GÜÇLÜ AL / NÖTR / SAT / GÜÇLÜ SAT sınıflaması
- Windows masaüstü arayüzü
- GitHub Actions ile otomatik `UmutScanner.exe` üretimi

## Güvenlik

V1 **API anahtarı istemez ve emir göndermez**. Yalnızca Binance'in halka açık piyasa verilerini okur.

## Yerel çalıştırma

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Windows EXE

Repository içindeki **Actions → Build Windows EXE** iş akışı tamamlandıktan sonra çalıştırmanın `Artifacts` bölümünden `UmutScanner-Windows` paketini indir. ZIP içinden çıkan `UmutScanner.exe` dosyasını masaüstüne koyup çalıştırabilirsin.

## Varsayılan tarama mantığı

- Trend: EMA dizilimi + EMA eğimi + EMA200 konumu
- Momentum: RSI + MACD histogram + ROC
- Hacim: RVOL
- Trend gücü: ADX + DI
- Yapı: onaylanmış HH/HL veya LH/LL
- Risk: ATR ve EMA20'den ATR bazlı uzaklık
- MTF: üst zaman diliminde EMA20/50/200 yapısı

Skorlar 0–100 aralığındadır. `84/100`, `%84 kazanma ihtimali` anlamına gelmez.
