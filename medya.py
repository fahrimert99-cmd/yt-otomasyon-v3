#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medya.py — Ücretsiz medya kaynakları
--------------------------------------------------
1) Pexels Videos (dikey stok video, ücretsiz API)
2) Pollinations.ai (Flux model, anahtarsız AI görsel)
3) Anahtar kelime çıkarıcı: TR cümle -> EN arama sorgusu
"""

import os
import re
import urllib.parse
import requests

PEXELS_URL = "https://api.pexels.com/videos/search"
POLL_URL   = "https://image.pollinations.ai/prompt/"

# ---------------------------------------------------------
# TR->EN anahtar kelime sözlüğü (niş: bilim/psikoloji/tarih)
# Genişletmek için sadece bu sözlüğe ekleme yapın.
# ---------------------------------------------------------
TR_EN = {
    # Beyin & sinir
    "beyin":"brain", "beyni":"brain", "beyniniz":"brain", "nöron":"neuron",
    "sinir":"nerve", "hafıza":"memory", "hafiza":"memory",
    # Uyku & rüya
    "uyku":"sleep", "uykuda":"sleeping", "uyurken":"sleeping",
    "rüya":"dream", "ruya":"dream", "uykulu":"sleepy",
    # Vücut
    "vücut":"human body", "vucut":"human body", "kalp":"heartbeat",
    "kan":"blood cells", "hücre":"cell microscope", "hucre":"cell microscope",
    "göz":"eye closeup", "goz":"eye closeup", "el":"hands",
    "yüz":"face", "yuz":"face",
    # Uzay & bilim
    "uzay":"space", "yıldız":"stars", "yildiz":"stars",
    "galaksi":"galaxy", "gezegen":"planet", "astronot":"astronaut",
    "ay":"moon", "güneş":"sun", "gunes":"sun",
    # Zaman & psikoloji
    "zaman":"clock time", "saat":"clock", "yaşlanmak":"aging",
    "yaslanmak":"aging", "hız":"speed motion", "hiz":"speed motion",
    # Tarih & gizem
    "tarih":"ancient", "gizem":"mysterious", "sır":"secret",
    "sir":"secret", "antik":"ancient ruins", "kütüphane":"old library",
    "kutuphane":"old library", "kitap":"old books",
    # Duygu & davranış
    "korku":"fear dark", "sessizlik":"silence", "fısıltı":"whisper",
    "fisilti":"whisper", "bağırmak":"shout", "bagirmak":"shout",
    "düşünce":"thinking", "dusunce":"thinking",
    # Genel
    "ışık":"light rays", "isik":"light rays", "karanlık":"dark",
    "karanlik":"dark", "su":"water", "ateş":"fire", "ates":"fire",
    "doğa":"nature", "doga":"nature", "gökyüzü":"sky",
    "gokyuzu":"sky", "insan":"person silhouette",
    "kadın":"woman portrait", "kadin":"woman portrait",
    "erkek":"man portrait", "yol":"road path",
    "kayıp":"lost fog", "kayip":"lost fog",
}

STOP = {
    "ve","ile","ama","için","icin","bu","bir","o","şu","su","hem","ya",
    "de","da","mi","mı","mu","mü","ne","niye","neden","nasıl","nasil",
    "kim","hangi","aslında","aslinda","bazen","hep","hiç","hic","daha",
    "en","çok","cok","olan","olur","olmak","yapmak","etmek","değil","degil",
    "gibi","kadar","sonra","önce","onceki","sonraki","şey","sey","yani",
    "her","bazı","bazi",
}

def _kelimeleri_ayikla(cumle):
    kelimeler = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", cumle.lower())
    return [k for k in kelimeler if k not in STOP and len(k) >= 3]

def anahtar_kelime_uret(cumle, max_kelime=3):
    """TR cümleden EN arama sorgusu üretir. Bulamazsa TR kelimeleri döner."""
    kelimeler = _kelimeleri_ayikla(cumle)
    en_kelimeler = []
    for k in kelimeler:
        ceviri = TR_EN.get(k)
        if ceviri and ceviri not in en_kelimeler:
            en_kelimeler.append(ceviri)
        if len(en_kelimeler) >= max_kelime:
            break
    if en_kelimeler:
        return " ".join(en_kelimeler)
    # Fallback: TR kelimeleri direkt kullan (Pexels çok dilli destek)
    if kelimeler:
        return " ".join(kelimeler[:max_kelime])
    return "abstract cinematic"

# ---------------------------------------------------------
# PEXELS
# ---------------------------------------------------------
def pexels_ara(sorgu, api_key, min_yukseklik=1200, timeout=15):
    """
    Pexels'te dikey stok video arar. En uygun link + süre döner.
    Bulamazsa None.
    """
    if not api_key:
        return None
    try:
        r = requests.get(
            PEXELS_URL,
            headers={"Authorization": api_key},
            params={
                "query": sorgu,
                "orientation": "portrait",
                "size": "medium",
                "per_page": 8,
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        adaylar = []
        for v in data.get("videos", []):
            for f in v.get("video_files", []):
                w, h = f.get("width", 0), f.get("height", 0)
                if h >= w and h >= min_yukseklik and f.get("link"):
                    adaylar.append({
                        "url": f["link"],
                        "sure": v.get("duration", 0),
                        "yukseklik": h,
                    })
                    break  # her video için tek dosya al
        if not adaylar:
            return None
        # En yüksek çözünürlüklüyü seç
        adaylar.sort(key=lambda x: -x["yukseklik"])
        return adaylar[0]
    except Exception:
        return None

def pexels_indir(url, dst, timeout=60):
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(dst, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        return os.path.getsize(dst) > 10000
    except Exception:
        return False

# ---------------------------------------------------------
# POLLINATIONS.AI (ücretsiz, anahtarsız Flux)
# ---------------------------------------------------------
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC  = b"\x89PNG\r\n\x1a\n"

def pollinations_uret(prompt, dst, boyut=(1080, 1920), seed=42, timeout=90):
    """Flux ile dikey görsel üretir. Başarısızsa False."""
    W, H = boyut
    tam_prompt = (
        f"cinematic dramatic illustration, {prompt}, "
        f"vertical 9:16 composition, high detail, moody lighting, "
        f"professional color grading, no text, no watermark"
    )
    url = POLL_URL + urllib.parse.quote(tam_prompt)
    params = {
        "width": W, "height": H, "seed": seed,
        "nologo": "true", "model": "flux",
        "enhance": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code != 200:
            return False
        icerik = r.content
        if len(icerik) < 8000:
            return False
        if not (icerik.startswith(JPEG_MAGIC) or icerik.startswith(PNG_MAGIC)):
            return False
        with open(dst, "wb") as f:
            f.write(icerik)
        return True
    except Exception:
        return False

# ---------------------------------------------------------
# ORKESTRA: cümle -> medya dosyası
# ---------------------------------------------------------
def medya_al(cumle, dst_prefix, boyut, pexels_key, seed=42, tercih="auto"):
    """
    Bir cümle için medya kaynağı bulur.
    tercih: "auto" (Pexels->Pollinations), "pexels", "ai", "kart"
    Döner: (dosya_yolu, "video"|"image"|None)
    """
    sorgu = anahtar_kelime_uret(cumle)

    # 1) PEXELS video dene
    if tercih in ("auto", "pexels"):
        sonuc = pexels_ara(sorgu, pexels_key)
        if sonuc:
            dst = dst_prefix + ".mp4"
            if pexels_indir(sonuc["url"], dst):
                return dst, "video"

    # 2) POLLINATIONS AI görsel dene
    if tercih in ("auto", "ai"):
        dst = dst_prefix + ".jpg"
        # AI prompt için TR cümle + EN anahtarlar (Flux çok dilli)
        prompt = f"{sorgu}, {cumle}"
        if pollinations_uret(prompt, dst, boyut=boyut, seed=seed):
            return dst, "image"

    # 3) Hiçbiri olmadıysa None -> çağıran gradient karta düşecek
    return None, None
