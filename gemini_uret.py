#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gemini_uret.py — Google Gemini API ile senaryo üretimi
--------------------------------------------------------
Make'e alternatif: GitHub Actions doğrudan Gemini API'sini çağırır ve
JSON formatında senaryo/başlık/etiket üretir.

Google AI Studio ücretsiz katmanı (2026):
  - Kredi kartı istemez
  - Gemini 2.5 Flash: günlük kota Shorts kanalı için efektif olarak sınırsız
  - API key alma: https://aistudio.google.com/apikey

Ortam değişkeni:
  GEMINI_API_KEY (zorunlu)

Kullanım:
  python3 gemini_uret.py --mod kisa --nis "Bilim ve Uzay Gizemleri"
  python3 gemini_uret.py --mod uzun

Çıktı: stdout'a JSON. `--kaydet script.json` ile dosyaya kaydeder.
"""

import os, re, sys, json, random, argparse, time
import urllib.request
import urllib.error


API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _prompt_uret(mod_cfg, nis, hedef_kelime):
    """Modu (kısa/uzun) ve nişi verilen Gemini prompt'unu üretir."""
    if mod_cfg == "kisa":
        format_talimat = (
            "YouTube Shorts formatı (dikey, ~50 saniye). "
            f"Senaryo TAM olarak {hedef_kelime} kelime civarında olmalı. "
            "İlk 3 saniyede güçlü bir merak boşluğu (curiosity gap) hook'u ile başla. "
            "Cümleler kısa, güçlü, seslendirilebilir olsun. Alt yazı ile takip edilebilir."
        )
    else:
        format_talimat = (
            "Uzun form YouTube videosu (yatay 16:9, ~8 dakika). "
            f"Senaryo TAM olarak {hedef_kelime} kelime civarında olmalı. "
            "3-5 alt bölüme organize edilmiş, giriş-gelişme-sonuç yapısında olsun. "
            "Her alt bölüm izleyiciyi sonraki bölüme çeken bir bağlantı cümlesiyle bitmeli. "
            "Anlatım akıcı, seslendirilebilir cümlelerden oluşsun."
        )

    prompt = f"""Sen viral YouTube senaryoları yazan uzman bir Türkçe içerik üreticisisin.

NİŞ: {nis}
FORMAT: {format_talimat}

KURALLAR:
- Tamamen Türkçe olacak.
- Yasal, doğrulanabilir bilgiler kullan (çelişkili, spekülatif ya da hurafe içeren iddialardan kaçın).
- Reklam, ürün tanıtımı, marka adı KULLANMA.
- Politik, dini, tıbbi tavsiye içeren cümle kurma.
- Küfür, argo, şiddet, cinsel içerik yasak.
- Başlık en fazla 60 karakter, curiosity gap içersin.
- 3-5 etiket üret (Türkçe, hashtag işareti olmadan).
- Açıklama 2-3 cümle, senaryo özeti ve #Shorts / kanal etiketleri içersin.

ÇIKTI FORMATINI KESİNLİKLE ŞU JSON YAPISINDA VER, BAŞKA HİÇBİR ŞEY YAZMA:
{{
  "baslik": "...",
  "script": "...",
  "aciklama": "...",
  "etiketler": ["...", "...", "..."]
}}
"""
    return prompt


def _api_cagir(model, api_key, prompt, timeout=90, deneme=3):
    """Gemini v1beta generateContent endpoint'ini çağırır. Retry ile."""
    url = f"{API_BASE}/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    data = json.dumps(body).encode("utf-8")
    for i in range(deneme):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            hata = e.read().decode("utf-8", errors="ignore")[:500]
            if e.code in (429, 500, 503) and i < deneme - 1:
                bekle = 2 ** (i + 1)
                print(f"  [Uyarı] Gemini {e.code} — {bekle}sn sonra yeniden deneniyor. {hata}",
                      file=sys.stderr)
                time.sleep(bekle)
                continue
            raise SystemExit(f"Gemini API hatası ({e.code}): {hata}")
        except Exception as e:
            if i < deneme - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise SystemExit(f"Gemini bağlantı hatası: {e}")


def _yanit_parse(yanit):
    """API yanıtından JSON metnini çıkarır ve parse eder."""
    try:
        aday = yanit["candidates"][0]
        if aday.get("finishReason") == "SAFETY":
            raise SystemExit("Gemini güvenlik filtresi tetiklendi. Prompt'u yumuşat.")
        metin = aday["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise SystemExit(f"Beklenmedik Gemini yanıt yapısı: {e}\nYanıt: {json.dumps(yanit)[:400]}")
    # ```json bloklarını temizle
    metin = metin.strip()
    metin = re.sub(r"^```(json)?", "", metin).strip()
    metin = re.sub(r"```$", "", metin).strip()
    try:
        return json.loads(metin)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Gemini JSON parse edilemedi: {e}\nMetin: {metin[:400]}")


def _dogrula(icerik):
    """Zorunlu alanları kontrol eder."""
    icin = ["baslik", "script", "aciklama", "etiketler"]
    eksik = [k for k in icin if not icerik.get(k)]
    if eksik:
        raise SystemExit(f"Gemini çıktısında eksik alan: {eksik}")
    if len(icerik["baslik"]) > 100:
        icerik["baslik"] = icerik["baslik"][:97] + "..."
    if not isinstance(icerik["etiketler"], list):
        icerik["etiketler"] = [
            e.strip() for e in str(icerik["etiketler"]).split(",") if e.strip()
        ]
    return icerik


def senaryo_uret(mod, nis, hedef_kelime, model=None, api_key=None):
    """Ana fonksiyon: mod + niş verilir, senaryo/başlık/etiket sözlüğü döner."""
    model = model or "gemini-2.5-flash"
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY ortam değişkeni bulunamadı.")
    prompt = _prompt_uret(mod, nis, hedef_kelime)
    print(f"  Gemini modeli: {model} | mod: {mod} | niş: {nis}", file=sys.stderr)
    yanit = _api_cagir(model, api_key, prompt)
    icerik = _yanit_parse(yanit)
    return _dogrula(icerik)


def main():
    ap = argparse.ArgumentParser(description="Gemini ile YouTube senaryosu üretici")
    ap.add_argument("--mod", choices=["kisa", "uzun"], default="kisa")
    ap.add_argument("--nis", default=None,
                    help="Belirtilmezse config.json'daki nis_karisimi'ndan rastgele seçilir.")
    ap.add_argument("--kaydet", default=None,
                    help="JSON çıktıyı dosyaya kaydet.")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}

    mod_cfg = cfg.get("modlar", {}).get(args.mod, {})
    hedef_kelime = int(mod_cfg.get("hedef_kelime", 180 if args.mod == "kisa" else 1200))
    model = cfg.get("gemini", {}).get("model", "gemini-2.5-flash")

    if args.nis:
        nis = args.nis
    else:
        havuz = cfg.get("gemini", {}).get("nis_karisimi") or [
            "Bilim ve Uzay Gizemleri"
        ]
        nis = random.choice(havuz)

    icerik = senaryo_uret(args.mod, nis, hedef_kelime, model=model)
    icerik["_mod"] = args.mod
    icerik["_nis"] = nis
    icerik["_hedef_kelime"] = hedef_kelime

    cikti = json.dumps(icerik, ensure_ascii=False, indent=2)
    if args.kaydet:
        with open(args.kaydet, "w", encoding="utf-8") as f:
            f.write(cikti)
        print(f"Kaydedildi: {args.kaydet}", file=sys.stderr)
    else:
        print(cikti)


if __name__ == "__main__":
    main()
