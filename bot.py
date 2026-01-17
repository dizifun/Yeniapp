import requests
import json
import os

# --- AYARLAR ---
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists%2Fvideo%2Fsources%2Fwww-kanald-com-tr%2Farsiv-programlar%2Farkadasim-hosgeldin.m3u"
OUTPUT_FILE = "api/Arkdasim_Hosgeldin_full.json" # Dosya adını içeriğe uygun değiştirdim
GITHUB_USER = "dizifun" # Senin kullanıcı adın (gerekirse değiştir)
GITHUB_REPO = "Yeniapp" # Senin repo adın (gerekirse değiştir)

def fix_github_url(url):
    """GitHub linkini düzeltir."""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

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
    episode_counter = 1

    print("⚙️ Linkler ayıklanıyor...")

    for line in lines:
        line = line.strip()

        # Boş satırları ve yorum satırlarını atla
        if not line or line.startswith("#"):
            continue

        # Link tespiti
        if "http" in line or line.endswith(".m3u8") or line.endswith(".mp4"):
            # Her bir bölüm için basit bir obje oluşturuyoruz
            episodes.append({
                "id": episode_counter,
                "title": f"Arkadaşım Hoşgeldin- {episode_counter}. Bölüm",
                "url": line,
                "type": "vod" # Uygulamanın bunun canlı değil video olduğunu anlaması için
            })
            episode_counter += 1

    if not episodes:
        print("❌ Hata: Liste boş!")
        return

    # JSON Olarak Kaydet (Sadece Dizi Listesi)
    data_to_save = {
        "playlist_name": "Arkadaşım Hoşgeldin Tüm Bölümler",
        "total_count": len(episodes),
        "streams": episodes # Tüm bölümler burada liste halindedir
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
