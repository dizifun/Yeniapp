import requests
import json
import os
import subprocess

# --- AYARLAR ---
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists%2Fvideo%2Fsources%2Fwww-tv8-com-tr%2Fall%2Fkirmizi-oda.m3u"
OUTPUT_FILE = "api/Kırmızı_Oda_full.json"
GITHUB_USER = "dizifun"
GITHUB_REPO = "Yeniapp"

def fix_github_url(url):
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def get_duration(url):
    """Videonun süresini saniye cinsinden (float) döndürür."""
    # Kanal D sunucularını kandırmak için tarayıcı kimliği (User-Agent)
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    try:
        komut = [
            "ffprobe",
            "-headers", headers,  # Header ekledik
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            url
        ]
        
        # Timeout süresini 20 saniyeye çıkardık
        sonuc = subprocess.run(komut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        
        if sonuc.returncode != 0:
            # Eğer ffprobe hata verdiyse hatayı loglara yazalım (Hata ayıklama için)
            print(f"⚠️ HATA DETAYI ({url[-15:]}): {sonuc.stderr.strip()}")
            return 0

        val = sonuc.stdout.strip()
        if not val:
            return 0
            
        return float(val)

    except Exception as e:
        print(f"⚠️ Python Hatası: {e}")
        return 0

def create_playlist_json():
    print("📥 M3U Listesi indiriliyor...")
    final_url = fix_github_url(M3U_URL)

    try:
        response = requests.get(final_url)
        content = response.text
    except Exception as e:
        print(f"❌ Hata: Dosya indirilemedi. {e}")
        return

    episodes = []
    lines = content.splitlines()
    valid_urls = [line.strip() for line in lines if line.strip() and not line.startswith("#") and ("http" in line or line.endswith(".m3u8") or line.endswith(".mp4"))]

    print(f"⚙️ Toplam {len(valid_urls)} bölüm bulundu. Süreler hesaplanıyor (Bu işlem biraz sürebilir)...")

    for i, line in enumerate(valid_urls, 1):
        sure_saniye = get_duration(line)
        
        dakika = int(sure_saniye // 60)
        saniye = int(sure_saniye % 60)
        sure_metin = f"{dakika}:{saniye:02d}"

        # Konsola bilgi verelim ki çalıştığını gör
        print(f"[{i}/{len(valid_urls)}] Süre: {sure_metin} | URL Son: ...{line[-15:]}")

        episodes.append({
            "id": i,
            "title": f"Kırmızı Oda - {i}. Bölüm",
            "url": line,
            "type": "vod",
            "duration_sec": int(sure_saniye),
            "duration_text": sure_metin
        })

    if not episodes:
        print("❌ Hata: Liste boş!")
        return

    data_to_save = {
        "playlist_name": "Kırmızı Oda Tüm Bölümler",
        "total_count": len(episodes),
        "streams": episodes
    }

    os.makedirs("api", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

    print(f"✅ JSON oluşturuldu! Toplam {len(episodes)} bölüm kaydedildi.")

def purge_cache():
    url = f"https://purge.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/{OUTPUT_FILE}"
    try:
        requests.get(url, timeout=5)
    except:
        pass

if __name__ == "__main__":
    create_playlist_json()
    purge_cache()
