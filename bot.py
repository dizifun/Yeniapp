import requests
import json
import os
import subprocess

# --- AYARLAR ---
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists%2Fvideo%2Fsources%2Fwww-kanald-com-tr%2Farsiv-programlar%2Farkadasim-hosgeldin.m3u"
OUTPUT_FILE = "api/Arkdasim_Hosgeldin_full.json"
GITHUB_USER = "dizifun"
GITHUB_REPO = "Yeniapp"

def fix_github_url(url):
    """GitHub linkini düzeltir."""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def get_duration(url):
    """Videonun süresini saniye cinsinden (float) döndürür."""
    try:
        # ffprobe komutu: Videoyu indirmeden sadece başlık bilgisini okur
        komut = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            url
        ]
        # 10 saniye zaman aşımı koyduk, link bozuksa script donmasın
        sonuc = subprocess.run(komut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return float(sonuc.stdout.strip())
    except Exception as e:
        print(f"⚠️ Süre alınamadı: {e}")
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
    
    # Önce sadece geçerli linkleri bir listede toplayalım
    valid_urls = [line.strip() for line in lines if line.strip() and not line.startswith("#") and ("http" in line or line.endswith(".m3u8") or line.endswith(".mp4"))]

    print(f"⚙️ Toplam {len(valid_urls)} bölüm bulundu. Süreler hesaplanıyor...")

    for i, line in enumerate(valid_urls, 1):
        print(f"[{i}/{len(valid_urls)}] İşleniyor...") # Loglarda ilerlemeyi görmek için
        
        # Süreyi hesapla
        sure_saniye = get_duration(line)
        
        # Dakika:Saniye formatına çevir
        dakika = int(sure_saniye // 60)
        saniye = int(sure_saniye % 60)
        sure_metin = f"{dakika}:{saniye:02d}"

        episodes.append({
            "id": i,
            "title": f"Arkadaşım Hoşgeldin - {i}. Bölüm",
            "url": line,
            "type": "vod",
            "duration_sec": int(sure_saniye),       # Fake TV mantığı için ham saniye
            "duration_text": sure_metin             # Ekranda göstermek için (örn: 45:12)
        })

    if not episodes:
        print("❌ Hata: Liste boş!")
        return

    # JSON Olarak Kaydet
    data_to_save = {
        "playlist_name": "Arkadaşım Hoşgeldin Tüm Bölümler",
        "total_count": len(episodes),
        "streams": episodes
    }

    os.makedirs("api", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

    print(f"✅ JSON oluşturuldu! Toplam {len(episodes)} bölüm kaydedildi.")
    print(f"📁 Dosya yolu: {OUTPUT_FILE}")

def purge_cache():
    # Güncelleme sonrası CDN önbelleğini temizlemek için
    url = f"https://purge.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/{OUTPUT_FILE}"
    try:
        requests.get(url)
        print("🚀 CDN Önbelleği (Purge) tetiklendi.")
    except:
        pass

if __name__ == "__main__":
    create_playlist_json()
    purge_cache()
