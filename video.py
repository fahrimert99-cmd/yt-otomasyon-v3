#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
  YOUTUBE NIŞ VIDEO ÜRETIM HATTI  (v2 - Ücretsiz Sinematik)
  Metin -> Seslendirme + Karaoke Alt Yazı + Pexels/AI Görsel + Fon Müziği -> MP4
  Bağımlılık: python3, ffmpeg, edge-tts, Pillow, requests   (hepsi ücretsiz)
============================================================

Yenilikler (v2):
  * Pexels stok video (dikey) — anahtar kelimeye göre otomatik
  * Pollinations.ai (Flux) — AI görsel yedek
  * Karaoke (kelime-kelime vurgu) alt yazı
  * Fon müziği + sidechain ducking (konuşurken müzik kısılır)

KULLANIM:
    python3 video.py --script script.txt
    python3 video.py --script script.txt --ses erkek
    python3 video.py --script script.txt --dikey

Görsel kaynağı seçimi (config.json -> "gorsel_kaynak"):
    "auto"  : Pexels -> Pollinations -> gradient kart (VARSAYILAN)
    "pexels": Sadece Pexels (+ kart yedek)
    "ai"    : Sadece Pollinations AI (+ kart yedek)
    "kart"  : Sadece gradient kart (eski v1 davranışı)

Fon müziği:
    assets/muzik/ klasörüne .mp3/.m4a koy. Rastgele biri seçilip düşük sesle
    (config.muzik_ses) narration altına eklenir, sidechain ile duck edilir.
"""

import os, re, sys, glob, json, math, random, asyncio, argparse
import subprocess, tempfile, shutil

import medya as M  # Pexels + Pollinations

# ----------------------------------------------------------
# AYARLAR
# ----------------------------------------------------------
CONFIG = {
    "sesler": {
        "kadin": "tr-TR-EmelNeural",
        "erkek": "tr-TR-AhmetNeural",
    },
    "varsayilan_ses": "kadin",
    "konusma_hizi":   "+0%",
    "yatay":  (1920, 1080),
    "dikey":  (1080, 1920),
    "fps": 30,
    "altyazi": {
        "font": "DejaVu Sans",
        "punto_yatay": 22,
        "punto_dikey": 15,
        "renk_normal":     "&H00FFFFFF",  # beyaz (henüz okunmamış)
        "renk_vurgu":      "&H0000E5FF",  # sarı-turuncu (o an okunuyor)
        "kenar_renk":      "&H00000000",  # siyah kenarlık
        "kenar_kalinlik":  4,
        "alt_bosluk":      120,
    },
    "altyazi_max_kelime": 5,    # karaoke için daha kısa satırlar
    "altyazi_max_sure":   3.0,
    "output_dir":  "output",
    "assets_dir":  "assets",
    "muzik_dir":   "assets/muzik",
    "gorsel_kaynak": "auto",
    "muzik_ses":     0.15,
    "pollinations_seed": 42,
}

# ----------------------------------------------------------
# 1. METİN OKUMA
# ----------------------------------------------------------
def metni_oku(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    lines = [l for l in raw.splitlines() if not l.strip().startswith("#")]
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    cumleler = re.split(r"(?<=[.!?])\s+", text)
    cumleler = [c.strip() for c in cumleler if c.strip()]
    return text, cumleler

# ----------------------------------------------------------
# 2. SESLENDIRME (edge-tts)
# ----------------------------------------------------------
async def _tts(text, voice, rate, mp3_path):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate)
    boundaries = []
    with open(mp3_path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                boundaries.append({
                    "start": ch["offset"] / 1e7,
                    "dur":   ch["duration"] / 1e7,
                    "text":  ch["text"],
                })
    return boundaries

def seslendir(text, voice, rate, mp3_path):
    return asyncio.run(_tts(text, voice, rate, mp3_path))

def cue_olustur(boundaries, max_kelime, max_sure):
    """WordBoundary listesini kısa alt yazı satırlarına gruplar."""
    cues, buf = [], []
    def flush():
        if not buf: return
        start = buf[0]["start"]
        end   = buf[-1]["start"] + buf[-1]["dur"]
        cues.append({
            "start": start, "end": end,
            "kelimeler": list(buf),
            "text": " ".join(w["text"] for w in buf),
        })
        buf.clear()
    for w in boundaries:
        buf.append(w)
        cumle_sonu = w["text"].endswith((".", "!", "?", ":", ";", ","))
        sure = (buf[-1]["start"] + buf[-1]["dur"]) - buf[0]["start"]
        if len(buf) >= max_kelime or sure >= max_sure or cumle_sonu:
            flush()
    flush()
    return cues

# ----------------------------------------------------------
# 3. KARAOKE ALT YAZI (.ass)
# ----------------------------------------------------------
def _ass_zaman(t):
    h = int(t // 3600); t -= h*3600
    m = int(t // 60);   t -= m*60
    s = int(t)
    cs = int((t - s) * 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def ass_yaz_karaoke(cues, path, cfg, dikey):
    """Her kelime tek tek renkle dolan karaoke stili ASS üretir."""
    a = cfg["altyazi"]
    punto = a["punto_dikey"] if dikey else a["punto_yatay"]
    px, py = (1080, 1920) if dikey else (1920, 1080)
    # PrimaryColour: vurgu rengi (kelime söylenince buna dönüşür)
    # SecondaryColour: normal renk (henüz söylenmemiş)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {px}
PlayResY: {py}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Def,{a['font']},{punto*4},{a['renk_vurgu']},{a['renk_normal']},{a['kenar_renk']},&H88000000,-1,0,1,{a['kenar_kalinlik']},1,2,80,80,{a['alt_bosluk']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(head)
        for c in cues:
            words = c["kelimeler"]
            if not words:
                continue
            line_start = c["start"]
            line_end   = c["end"]
            parts = []
            for i, w in enumerate(words):
                # kelimenin karaoke süresi (cs)
                if i < len(words) - 1:
                    dur_cs = int((words[i+1]["start"] - w["start"]) * 100)
                else:
                    dur_cs = int((line_end - w["start"]) * 100)
                dur_cs = max(dur_cs, 5)
                metin = w["text"].replace("{","(").replace("}",")")
                parts.append(f"{{\\kf{dur_cs}}}{metin}")
            satir = " ".join(parts)
            f.write(
                f"Dialogue: 0,{_ass_zaman(line_start)},{_ass_zaman(line_end)},"
                f"Def,,0,0,0,,{satir}\n"
            )

# ----------------------------------------------------------
# 4. GORSEL: gradient kart (Pexels ve AI yoksa yedek)
# ----------------------------------------------------------
def gradient_kart(metin, boyut, idx, path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = boyut
    img = Image.new("RGB", (W, H))
    tonlar = [(18,26,48),(30,20,44),(12,32,38),(40,26,22),(22,22,40)]
    c1 = tonlar[idx % len(tonlar)]
    c2 = tuple(max(0, v-14) for v in c1)
    for y in range(H):
        r = y / H
        col = tuple(int(c1[i]*(1-r)+c2[i]*r) for i in range(3))
        ImageDraw.Draw(img).line([(0,y),(W,y)], fill=col)
    d = ImageDraw.Draw(img)
    try:
        fs = int(H*0.055)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fs)
    except Exception:
        font = ImageFont.load_default()
    kelimeler = metin.split()
    satirlar, cur = [], ""
    maxw = W*0.82
    for k in kelimeler:
        test = (cur+" "+k).strip()
        if d.textlength(test, font=font) <= maxw:
            cur = test
        else:
            satirlar.append(cur); cur = k
    if cur: satirlar.append(cur)
    satirlar = satirlar[:6]
    lh = int(fs*1.35)
    ty = (H - lh*len(satirlar))//2
    for ln in satirlar:
        w = d.textlength(ln, font=font)
        d.text(((W-w)//2, ty), ln, font=font, fill=(240,240,245))
        ty += lh
    img.save(path, quality=90)

# ----------------------------------------------------------
# 5. MEDYA HAZIRLAMA (Pexels + AI + kart)
# ----------------------------------------------------------
def medya_hazirla(cumleler, boyut, tmp, cfg):
    """
    Her cümle için bir medya döner: (dosya, "video"|"image").
    Kaynak sırası config.gorsel_kaynak'a göre.
    """
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    tercih = cfg.get("gorsel_kaynak", "auto")
    seed_base = int(cfg.get("pollinations_seed", 42))

    # Kullanıcı elle assets/*.jpg koymuşsa v1 uyumluluk: doğrudan onları kullan
    if tercih == "kart":
        elle = sorted(
            glob.glob(os.path.join(cfg["assets_dir"], "*.jpg")) +
            glob.glob(os.path.join(cfg["assets_dir"], "*.jpeg")) +
            glob.glob(os.path.join(cfg["assets_dir"], "*.png"))
        )
        if elle:
            return [(p, "image") for p in elle]

    medyalar = []
    for i, cumle in enumerate(cumleler):
        prefix = os.path.join(tmp, f"medya_{i:03d}")
        # AI için seed'i sabit tut = karakter/stil tutarlılığı
        yol, tip = None, None
        if tercih != "kart":
            yol, tip = M.medya_al(
                cumle, prefix, boyut,
                pexels_key=pexels_key,
                seed=seed_base,       # SABIT seed = stil tutarlılığı
                tercih=tercih,
            )
        if not yol:
            # Fallback: gradient kart
            yol = prefix + ".jpg"
            gradient_kart(cumle, boyut, i, yol)
            tip = "image"
        medyalar.append((yol, tip))
        print(f"    [{i+1}/{len(cumleler)}] {tip:5s}  <- {os.path.basename(yol)}")
    return medyalar

# ----------------------------------------------------------
# 6. FFMPEG BİRLEŞTİRME
# ----------------------------------------------------------
def sure_al(path):
    out = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(out.stdout.strip())
    except Exception:
        return 0.0

def _segment_uret(src, tip, dst, sure, boyut, fps):
    """Bir medyayı (video ya da görsel) belirli süreye normalize eder."""
    W, H = boyut
    if tip == "video":
        # Yeterince uzunsa kes; kısa ise stream_loop ile döngüle
        kaynak_sure = sure_al(src)
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={fps},format=yuv420p")
        cmd = ["ffmpeg","-y"]
        if kaynak_sure > 0 and kaynak_sure < sure:
            cmd += ["-stream_loop","-1"]
        cmd += ["-i", src, "-t", f"{sure:.3f}",
                "-vf", vf, "-an",
                "-c:v","libx264","-preset","veryfast","-crf","23",
                "-r", str(fps), dst]
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        # Görsel -> yavaş zoom (Ken Burns)
        frames = int(sure * fps)
        zoom = (f"zoompan=z='min(zoom+0.0008,1.12)':"
                f"d={frames}:s={W}x{H}:fps={fps}")
        subprocess.run([
            "ffmpeg","-y","-loop","1","-i", src, "-t", f"{sure:.3f}",
            "-vf", f"scale={W}:{H},{zoom},format=yuv420p",
            "-r", str(fps),
            "-c:v","libx264","-preset","veryfast","-crf","23","-an",
            dst
        ], check=True, capture_output=True)

def _muzik_sec(cfg):
    """assets/muzik/ altından rastgele bir müzik seç. Yoksa None."""
    d = cfg.get("muzik_dir", "assets/muzik")
    if not os.path.isdir(d):
        return None
    adaylar = []
    for uzanti in ("*.mp3","*.m4a","*.wav","*.ogg","*.opus"):
        adaylar += glob.glob(os.path.join(d, uzanti))
    return random.choice(adaylar) if adaylar else None

def video_uret(medyalar, mp3, ass, cikti, boyut, fps, cfg):
    """Tüm segmentleri birleştir + alt yazı göm + narration + fon müziği."""
    toplam = sure_al(mp3)
    n = len(medyalar)
    # Her cümleye eşit süre paylaştır (min 2s)
    sure_her = max(2.0, toplam / n)

    tmp = tempfile.mkdtemp()
    parcalar = []
    for i, (src, tip) in enumerate(medyalar):
        seg = os.path.join(tmp, f"seg_{i:03d}.mp4")
        _segment_uret(src, tip, seg, sure_her, boyut, fps)
        parcalar.append(seg)

    # Concat
    liste = os.path.join(tmp, "list.txt")
    with open(liste, "w") as f:
        for p in parcalar:
            f.write(f"file '{p}'\n")
    birlesik = os.path.join(tmp, "video_nosub.mp4")
    subprocess.run(
        ["ffmpeg","-y","-f","concat","-safe","0","-i", liste,
         "-c","copy", birlesik],
        check=True, capture_output=True
    )

    # Alt yazı gömme (görsel)
    ass_esc = ass.replace("\\","/").replace(":","\\:")
    video_alt = os.path.join(tmp, "video_sub.mp4")
    subprocess.run([
        "ffmpeg","-y","-i", birlesik,
        "-vf", f"subtitles='{ass_esc}'",
        "-c:v","libx264","-preset","veryfast","-crf","20",
        "-an", video_alt
    ], check=True, capture_output=True)

    # Ses: narration + (opsiyonel) fon müziği + ducking
    muzik = _muzik_sec(cfg)
    muzik_ses = float(cfg.get("muzik_ses", 0.15))
    if muzik:
        print(f"    Fon müziği: {os.path.basename(muzik)} (ses: {muzik_ses})")
        # Sidechain ducking: narration konuşurken müzik ~%40'a düşer
        filtre = (
            f"[1:a]aloop=loop=-1:size=2e9,volume={muzik_ses}[bg];"
            f"[0:a]asplit=2[voice][sc];"
            f"[bg][sc]sidechaincompress=threshold=0.03:ratio=8:"
            f"level_sc=0.8:attack=15:release=250[bg_duck];"
            f"[voice][bg_duck]amix=inputs=2:duration=first:"
            f"dropout_transition=0[aout]"
        )
        subprocess.run([
            "ffmpeg","-y",
            "-i", mp3, "-i", muzik, "-i", video_alt,
            "-filter_complex", filtre,
            "-map","2:v","-map","[aout]",
            "-c:v","copy",
            "-c:a","aac","-b:a","192k",
            "-shortest", cikti
        ], check=True, capture_output=True)
    else:
        subprocess.run([
            "ffmpeg","-y","-i", video_alt, "-i", mp3,
            "-map","0:v","-map","1:a",
            "-c:v","copy",
            "-c:a","aac","-b:a","192k",
            "-shortest", cikti
        ], check=True, capture_output=True)

    shutil.rmtree(tmp, ignore_errors=True)
    return toplam

# ----------------------------------------------------------
# ANA AKIŞ
# ----------------------------------------------------------
def uret_video(script_path, cikti, ses="kadin", dikey=False, hiz="+0%",
               ekstra_config=None):
    """Orkestratör tarafından çağrılır: script -> mp4."""
    cfg = dict(CONFIG)
    if ekstra_config:
        cfg.update(ekstra_config)
    boyut = cfg["dikey"] if dikey else cfg["yatay"]
    voice = cfg["sesler"][ses]
    text, cumleler = metni_oku(script_path)

    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "narration.mp3")
    boundaries = seslendir(text, voice, hiz, mp3)
    cues = cue_olustur(boundaries,
                       cfg["altyazi_max_kelime"],
                       cfg["altyazi_max_sure"])
    ass = os.path.join(tmp, "sub.ass")
    ass_yaz_karaoke(cues, ass, cfg, dikey)
    medyalar = medya_hazirla(cumleler, boyut, tmp, cfg)

    os.makedirs(os.path.dirname(cikti) or ".", exist_ok=True)
    video_uret(medyalar, mp3, ass, cikti, boyut, cfg["fps"], cfg)
    shutil.rmtree(tmp, ignore_errors=True)
    return cikti


def main():
    ap = argparse.ArgumentParser(description="Faceless YouTube video üretici v2")
    ap.add_argument("--script", required=True)
    ap.add_argument("--ses", default=CONFIG["varsayilan_ses"],
                    choices=["kadin","erkek"])
    ap.add_argument("--dikey", action="store_true")
    ap.add_argument("--hiz", default=CONFIG["konusma_hizi"])
    ap.add_argument("--kaynak", default=None,
                    choices=["auto","pexels","ai","kart"],
                    help="Görsel kaynağı override (config.json'ı geçersiz kılar)")
    args = ap.parse_args()

    cfg = dict(CONFIG)
    # config.json varsa yükle
    if os.path.exists("config.json"):
        with open("config.json", encoding="utf-8") as f:
            dis_cfg = json.load(f)
        for k in ("gorsel_kaynak", "muzik_ses", "pollinations_seed"):
            if k in dis_cfg:
                cfg[k] = dis_cfg[k]
    if args.kaynak:
        cfg["gorsel_kaynak"] = args.kaynak

    boyut = cfg["dikey"] if args.dikey else cfg["yatay"]
    voice = cfg["sesler"][args.ses]
    os.makedirs(cfg["output_dir"], exist_ok=True)
    os.makedirs(cfg["assets_dir"], exist_ok=True)
    os.makedirs(cfg["muzik_dir"], exist_ok=True)
    ad = os.path.splitext(os.path.basename(args.script))[0]

    print(f"[1/5] Metin okunuyor: {args.script}")
    text, cumleler = metni_oku(args.script)
    print(f"      {len(cumleler)} cümle, ~{len(text.split())} kelime")

    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "narration.mp3")
    print(f"[2/5] Seslendirme ({voice}) ...")
    boundaries = seslendir(text, voice, args.hiz, mp3)
    cues = cue_olustur(boundaries,
                       cfg["altyazi_max_kelime"],
                       cfg["altyazi_max_sure"])
    print(f"      {len(cues)} karaoke satırı")

    ass = os.path.join(tmp, "sub.ass")
    ass_yaz_karaoke(cues, ass, cfg, args.dikey)

    print(f"[3/5] Medya hazırlanıyor (kaynak: {cfg['gorsel_kaynak']}) ...")
    medyalar = medya_hazirla(cumleler, boyut, tmp, cfg)

    cikti = os.path.join(cfg["output_dir"], f"{ad}.mp4")
    print(f"[4/5] Video birleştiriliyor (FFmpeg) ...")
    sure = video_uret(medyalar, mp3, ass, cikti, boyut, cfg["fps"], cfg)

    print(f"[5/5] TAMAM ✓  ->  {cikti}  ({sure:.0f} sn)")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
