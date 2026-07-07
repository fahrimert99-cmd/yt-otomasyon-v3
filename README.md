# YouTube Otomasyon v3 — Kısa + Uzun Video, Gemini, Erkek Ses, Public

Faceless YouTube kanalı için **tamamen ücretsiz** üretim ve yayınlama boru hattı.
Günde iki video otomatik: sabah **Shorts**, akşam **uzun form**.

## Mimari

```
GitHub Actions (cron: sabah 08:00, akşam 18:00)
   ↓
Gemini API (2.5 Flash — ücretsiz)
   → Türkçe senaryo + başlık + etiket JSON
   ↓
video.py  (edge-tts erkek sesi + Pexels stok video + Pollinations AI görsel
           + karaoke alt yazı + fon müziği ducking)
   ↓ output/kisa-video.mp4  veya  output/uzun-video.mp4
   ↓
youtube_yukle.py  →  YouTube (public)
```

### İki Video Modu

| Mod | Format | Süre | Kelime |
|---|---|---|---|
| **kisa** | 1080×1920 (Shorts) | ~50 sn | 180 |
| **uzun** | 1920×1080 (long-form) | ~8 dk | 1200 |

Zamanlama `.github/workflows/uret.yml` içinde. TR saati:
- Kısa: her gün 08:00
- Uzun: her gün 18:00

## Niş Rotasyonu (config.json)

Her tetiklemede rastgele bir niş seçilir:
- Bilim ve Uzay Gizemleri
- Psikoloji ve Davranış Bilimleri
- Tarih Gizemleri ve Antik Uygarlıklar
- İlginç Bilgi Kırıntıları
- Motivasyon ve Kişisel Gelişim

## Maliyet

**0 TL.** Tüm servisler ücretsiz katmanda kalır:
- Gemini 2.5 Flash: günde 1500 istek (kullanım: 2)
- Pexels API: saatte 200 istek (kullanım: ~20)
- Pollinations.ai: sınırsız, anahtarsız
- edge-tts: Microsoft, ücretsiz
- GitHub Actions: public repo'da sınırsız
- YouTube Data API: günde 10.000 kota birimi (video yükleme = 1600 birim)

## Kurulum

Detaylı adım adım kurulum için: **KURULUM.md**

Özet:
1. Repo'yu GitHub'a yükleyin
2. Üç API anahtarı alın (hepsi ücretsiz):
   - Google AI Studio → `GEMINI_API_KEY`
   - Pexels → `PEXELS_API_KEY`
   - Google Cloud → YouTube OAuth credentials
3. GitHub Secrets'a beş secret ekleyin
4. `assets/muzik/` klasörüne 3-5 telifsiz fon müziği koyun
5. Manuel test: Actions → "Run workflow" → mod: kisa

## Manuel Tetikleme

GitHub → Actions → "YouTube Otomasyon" → **Run workflow** butonu:
- **mod**: kisa / uzun seçin
- **nis**: (opsiyonel) belirli bir niş yazın, boşsa rastgele

## Yerel Test

```bash
export GEMINI_API_KEY="..."
export PEXELS_API_KEY="..."
python3 gemini_uret.py --mod kisa > senaryo.json
python3 video.py --script senaryo.json --dikey --ses erkek
```
