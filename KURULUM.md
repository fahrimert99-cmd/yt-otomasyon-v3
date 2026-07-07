# KURULUM REHBERİ — v3

Bu rehber, sıfırdan tam çalışan bir otomasyona kadar tüm adımları içerir.
Tahmini kurulum süresi: **30 dakika**. Ücret: **0 TL**.

---

## 1. GitHub Deposu

1. GitHub'da yeni bir **public** repo açın (public'te Actions kotası sınırsız).
2. Bu klasördeki tüm dosyaları repoya yükleyin.
3. `.github/workflows/uret.yml` dosyasının doğru konumda olduğuna emin olun.

---

## 2. Google AI Studio → Gemini API Anahtarı (Ücretsiz)

Kredi kartı istemez. Günlük kota Shorts kanalı için pratik olarak sınırsızdır.

1. **https://aistudio.google.com/apikey** adresine gidin.
2. Google hesabınızla oturum açın.
3. **"Create API key"** → mevcut projeyi seçin veya yeni oluşturun.
4. Çıkan anahtarı kopyalayın (bir daha gösterilmez).

---

## 3. Pexels API Anahtarı (Ücretsiz)

1. **https://www.pexels.com/api/** → **Get Started**.
2. Ücretsiz üye olun (e-posta veya Google ile).
3. Panelde görünen API Key'i kopyalayın.

Limit: saatte 200 istek. Bir Shorts + bir uzun video için toplam ~20 istek.

---

## 4. YouTube OAuth (Yükleme İzni)

1. **https://console.cloud.google.com** → yeni proje oluşturun.
2. Sol menü → **APIs & Services → Enable APIs** → "YouTube Data API v3" arayıp etkinleştirin.
3. **OAuth consent screen** → External seçin, uygulama adı girin, kendi e-postanızı test kullanıcısı ekleyin.
4. **Credentials → Create Credentials → OAuth client ID → Desktop app** → indirin (`client_secret.json`).
5. Bu dosyayı kendi bilgisayarınıza kaydedin (repoya KOYMAYIN).
6. Kendi bilgisayarınızda terminal açın:

```bash
pip install google-auth-oauthlib
python3 token_al.py
```

Tarayıcı açılır, hesap seçin, izin verin. Çıkan üç değeri kopyalayın:
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

---

## 5. GitHub Secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Aşağıdaki **beş** secret'ı ekleyin:

| Secret Adı | Değer |
|---|---|
| `GEMINI_API_KEY` | Adım 2'den |
| `PEXELS_API_KEY` | Adım 3'ten |
| `YT_CLIENT_ID` | Adım 4'ten |
| `YT_CLIENT_SECRET` | Adım 4'ten |
| `YT_REFRESH_TOKEN` | Adım 4'ten |

---

## 6. Fon Müziği (Opsiyonel Ama Önerilir)

`assets/muzik/` klasörüne 3-5 telifsiz mp3 dosyası koyun.
Her video için rastgele biri seçilir ve konuşurken otomatik kısılır (sidechain ducking).

### Ücretsiz Kaynaklar

- YouTube Audio Library: https://studio.youtube.com → "Ses kütüphanesi"
- Pixabay Music: https://pixabay.com/music/
- FreePD (public domain): https://freepd.com/
- Free Music Archive: https://freemusicarchive.org/

Öneri: `cinematic ambient`, `documentary background` araması niş içeriğinize uygun sonuçlar verir.

Klasörü boş bırakırsanız video sadece narration ile üretilir, hata vermez.

---

## 7. İlk Manuel Test

1. GitHub → **Actions** sekmesi.
2. Sol menüden **"YouTube Otomasyon (Kisa + Uzun)"** seçin.
3. Sağ üstteki **"Run workflow"** butonuna tıklayın.
4. `mod: kisa`, `nis: boş` seçip **Run workflow**.
5. İş 3-6 dakikada tamamlanır.
6. YouTube Studio → yüklemelerinizi kontrol edin.

Uzun video için aynı adımı `mod: uzun` ile tekrarlayın (5-10 dakika sürer).

---

## 8. Otomatik Zamanlama

Zaten aktif. `.github/workflows/uret.yml` içinde iki cron var:

```yaml
- cron: "0 5 * * *"    # TR saati 08:00 — Kısa
- cron: "0 15 * * *"   # TR saati 18:00 — Uzun
```

Saati değiştirmek için UTC ↔ TR saat farkı 3 saattir. Örneğin sabah 07:00 TR = 04:00 UTC → `cron: "0 4 * * *"`.

---

## 9. Ayarlar (config.json)

| Alan | Açıklama | Varsayılan |
|---|---|---|
| `ses` | edge-tts sesi | `"erkek"` (Ahmet Neural) |
| `gizlilik` | Video yayın durumu | `"public"` |
| `kategori` | YouTube kategori kodu (27=Eğitim) | `"27"` |
| `cocuk_icerigi` | Kids içerik bayrağı | `false` |
| `varsayilan_mod` | Cron dışı çağrılarda mod | `"kisa"` |
| `gorsel_kaynak` | `auto` / `pexels` / `ai` / `kart` | `"auto"` |
| `muzik_ses` | Fon müzik seviyesi (0.0-1.0) | `0.13` |
| `gemini.model` | Kullanılacak Gemini modeli | `"gemini-2.5-flash"` |
| `gemini.nis_karisimi` | Rotasyona giren nişler | 5 niş |

### Ses Değiştirme

`config.json` içinde `"ses": "erkek"` → `"kadin"` yaparsanız kadın sesi (Emel Neural) kullanılır.

### Belirli Bir Nişe Kilitlenme

Manuel tetiklemede `nis` alanına belirli bir niş yazarsanız o niş kullanılır. Örneğin: `Uzayda kaybolan uygarlıklar`.

---

## Sorun Giderme

**"Gemini 429"** → Kotayı aştınız. Ücretsiz katman gün başında sıfırlanır. Model olarak `gemini-2.5-flash-lite` daha yüksek kotalıdır.

**"Pexels 401"** → API anahtarı yanlış veya secret eksik. Adım 5'i tekrar kontrol edin.

**"YouTube upload 403 quotaExceeded"** → Günlük 10.000 birim kotasını aştınız. Yüklemeler günde 5-6 videoya kadar sığar; 2 videolu setup için bol.

**Video üretiliyor ama kalite düşük** → `config.json` içinde `"gorsel_kaynak": "ai"` yaparsanız tüm sahneleri Pollinations AI ile üretir, daha tutarlı estetik verir.

**Karaoke alt yazı senkronu bozuk** → `video.py` içinde `CONFIG["altyazi_max_kelime"]` (varsayılan 5) düşürün.

---

Hazırlayan / Onaylayan: **Fahri Mert**
Rapor Kodu: ATER.KG.RPR.YT-OTOMASYON-V3
Tarih: 07.07.2026
