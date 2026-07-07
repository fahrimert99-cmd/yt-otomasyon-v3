#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uret_dispatch.py — v3 Orkestratör
------------------------------------
Üç tetikleme yolunu da destekler:
  1) GitHub Actions cron  -> Gemini API doğrudan senaryo üretir
  2) Make repository_dispatch -> RAW_B64 içinde JSON gelir
  3) workflow_dispatch (elle) -> MOD ve NIS env ile

Ortam değişkenleri:
  MOD                  -> "kisa" | "uzun"  (öncelik: env > config.varsayilan_mod)
  NIS                  -> Belirli niş (opsiyonel)
  RAW_B64              -> Make'ten gelen base64 JSON (varsa Gemini yerine bu kullanılır)
  GEMINI_API_KEY       -> Gemini için (Make değilse zorunlu)
  PEXELS_API_KEY       -> Stok video için (opsiyonel, boşsa AI'ya düşer)
  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN -> YouTube yükleme
"""

import os, re, sys, json, base64, tempfile, random
import video as V


def _temizle(txt):
    txt = txt.strip()
    txt = re.sub(r"^```(json)?", "", txt).strip()
    txt = re.sub(r"```$", "", txt).strip()
    return txt


def _make_icerigi_al():
    b64 = os.environ.get("RAW_B64", "").strip()
    if not b64:
        return None
    try:
        ham = base64.b64decode(b64).decode("utf-8")
        return json.loads(_temizle(ham))
    except Exception as e:
        print(f"[Uyarı] Make base64 çözülemedi: {e}", file=sys.stderr)
        return None


def _gemini_icerigi_al(mod, nis, cfg):
    """GEMINI_API_KEY varsa doğrudan Gemini'yi çağırır."""
    import gemini_uret as G
    mod_cfg = cfg.get("modlar", {}).get(mod, {})
    hedef = int(mod_cfg.get("hedef_kelime", 180 if mod == "kisa" else 1200))
    model = cfg.get("gemini", {}).get("model", "gemini-2.5-flash")
    return G.senaryo_uret(mod, nis, hedef, model=model)


def main():
    cfg = {}
    if os.path.exists("config.json"):
        with open("config.json", encoding="utf-8") as f:
            cfg = json.load(f)

    # 1) Mod seçimi (env > config)
    mod = os.environ.get("MOD", "").strip().lower()
    if mod not in ("kisa", "uzun"):
        mod = cfg.get("varsayilan_mod", "kisa")
    mod_cfg = cfg.get("modlar", {}).get(mod, {})
    dikey = str(mod_cfg.get("format", "dikey")).lower() == "dikey"

    # 2) Niş seçimi (env > rastgele havuz)
    nis = os.environ.get("NIS", "").strip()
    if not nis:
        havuz = cfg.get("gemini", {}).get("nis_karisimi") or ["Bilim ve Uzay Gizemleri"]
        nis = random.choice(havuz)

    # 3) İçerik: önce Make (varsa), yoksa Gemini
    veri = _make_icerigi_al()
    kaynak = "make"
    if not veri:
        print(f"[1/3] Gemini'den senaryo isteniyor (mod: {mod}, niş: {nis}) ...")
        veri = _gemini_icerigi_al(mod, nis, cfg)
        kaynak = "gemini"

    script = (veri.get("script") or "").strip()
    if not script:
        raise SystemExit("Senaryo boş — üretim durduruldu.")

    baslik    = (veri.get("baslik") or "Video")[:100]
    aciklama  = veri.get("aciklama") or ""
    etiketler = veri.get("etiketler") or []
    if isinstance(etiketler, str):
        etiketler = [e.strip() for e in etiketler.split(",") if e.strip()]

    ses      = cfg.get("ses", "erkek")
    gizlilik = cfg.get("gizlilik", "public")
    kategori = str(cfg.get("kategori", "27"))
    cocuk    = bool(cfg.get("cocuk_icerigi", False))

    print(f"      Kaynak: {kaynak} | Kelime: {len(script.split())} | Başlık: {baslik}")

    tmp = tempfile.mkdtemp()
    sp = os.path.join(tmp, "script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write(script)

    os.makedirs("output", exist_ok=True)
    cikti = f"output/{mod}-video.mp4"

    ekstra = {
        "gorsel_kaynak":    cfg.get("gorsel_kaynak", "auto"),
        "muzik_ses":        cfg.get("muzik_ses", 0.13),
        "pollinations_seed": cfg.get("pollinations_seed", 42),
    }

    print(f"[2/3] Video üretiliyor (format: {'dikey' if dikey else 'yatay'}, ses: {ses}) ...")
    V.uret_video(sp, cikti, ses=ses, dikey=dikey, ekstra_config=ekstra)
    print(f"      Çıktı: {cikti}  ({os.path.getsize(cikti)//1024} KB)")

    print(f"[3/3] YouTube'a yükleniyor (gizlilik: {gizlilik}) ...")
    import youtube_yukle as YT
    vid = YT.yukle(
        cikti, baslik, aciklama, etiketler,
        gizlilik=gizlilik, kategori=kategori, cocuk_icerigi=cocuk,
    )
    print(f"TAMAM ✓  https://youtu.be/{vid}")


if __name__ == "__main__":
    main()
