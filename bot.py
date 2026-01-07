import requests
import json
import time
import os

# --- AYARLAR ---
# GitHub linkini olduğu gibi buraya yapıştır. Bot kendisi düzeltecek.
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists/video/sources/www-kanald-com-tr/arsiv-diziler/kuzey-guney.m3u"

OUTPUT_FILE = "api/kuzey_guney_live.json"
GITHUB_USER = "dizifun"
GITHUB_REPO = "Yeniapp"

# 1 Saat 47 Dakika = 6420 Saniye
DEFAULT_DURATION = 6420 

def fix_github_url(url):
    """GitHub 'blob' linkini otomatik 'raw' linkine çevirir."""
    if "github.com" in url and "/blob/" in url:
        print("🔧 Link düzeltiliyor: HTML -> RAW")
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def create_channel():
    print("🎬 Kuzey Güney TV hazırlanıyor...")
    
    # 1. Linki Düzelt ve İndir
    final_url = fix_github_url(M3U_URL)
    print(f"📡 Bağlanılıyor: {final_url}")
    
    try:
        response = requests.get(final_url)
        content = response.text
    except Exception as e:
        print(f"❌ Hata: Dosya indirilemedi. {e}")
        return

    # 2. Bölümleri Ayıkla (Daha Akıllı Yöntem)
    episodes = []
    lines = content.splitlines()
    episode_counter = 1
    
    for line in lines:
        line = line.strip()
        
        # Boş satırları ve yorumları (#) atla
        if not line or line.startswith("#"):
            continue
            
        # Eğer satırda m3u8, mp4 geçiyorsa veya http ile başlıyorsa bu bir videodur
        if "http" in line or line.endswith(".m3u8") or line.endswith(".mp4"):
            episodes.append({
                "title": f"Kuzey Güney - {episode_counter}. Bölüm",
                "url": line,
                "duration": DEFAULT_DURATION
            })
            episode_counter += 1

    if not episodes:
        print("❌ Hata: Listede hiç bölüm bulunamadı! M3U dosyasının içi boş olabilir.")
        # Debug için dosyanın ilk 5 satırını yazdıralım
        print("Dosya İçeriği (İlk 5 satır):")
        print('\n'.join(lines[:5]))
        return

    print(f"✅ BAŞARILI: Toplam {len(episodes)} bölüm bulundu.")

    # 3. Yayın Akışını Hesapla
    total_playlist_duration = len(episodes) * DEFAULT_DURATION
    current_time = int(time.time())
    loop_position = current_time % total_playlist_duration
    
    accumulated_time = 0
    now_playing = None
    start_offset = 0
    current_index = 0

    for i, episode in enumerate(episodes):
        if accumulated_time + episode["duration"] > loop_position:
            now_playing = episode
            start_offset = loop_position - accumulated_time
            current_index = i
            break
        accumulated_time += episode["duration"]
    
    next_index = (current_index + 1) % len(episodes)
    next_episode = episodes[next_index]

    # 4. JSON Kaydet
    channel_data = {
        "channel_name": "Kuzey Güney 7/24",
        "timestamp": current_time,
        "total_episodes": len(episodes), # Toplam bölüm sayısını da ekledim bilgi için
        "now_playing": {
            "title": now_playing["title"],
            "url": now_playing["url"],
            "total_duration": now_playing["duration"],
            "start_at_second": start_offset 
        },
        "next_episode": {
            "title": next_episode["title"],
            "url": next_episode["url"]
        }
    }

    os.makedirs("api", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ Yayın Akışı Güncellendi! Oynayan: {now_playing['title']}")

def purge_cache():
    url = f"https://purge.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/{OUTPUT_FILE}"
    try:
        requests.get(url)
        print("🚀 CDN Önbelleği Temizlendi.")
    except:
        pass

if __name__ == "__main__":
    create_channel()
    purge_cache()
