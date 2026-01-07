import json
import time
import os
import requests

# --- AYARLAR ---
OUTPUT_FILE = "api/kuzey_guney_live.json"
GITHUB_USER = "dizifun"  # Kendi kullanıcı adın
GITHUB_REPO = "Yeniapp"  # Kendi repo adın

# --- YAYIN AKIŞI LİSTESİ ---
# Buraya elindeki tüm linkleri ve saniye cinsinden sürelerini ekle.
# 1 Saat 47 Dakika = 6420 Saniye
EPISODE_LIST = [
    {
        "title": "Kuzey Güney - 1. Bölüm",
        "url": "https://kanaldvod.duhnet.tv/S1/HLS_VOD/9ddd_1223/index.m3u8",
        "duration": 6420 
    },
    # İkinci bölümü eklersen buraya virgül koyup aşağıya kopyala:
    # {
    #     "title": "Kuzey Güney - 2. Bölüm",
    #     "url": "BAŞKA_LINK_BURAYA",
    #     "duration": 6420 
    # }
]

def create_channel():
    print("🎬 Kuzey Güney TV yayın akışı hesaplanıyor...")

    # 1. Toplam Döngü Süresini Hesapla
    total_playlist_duration = sum(item['duration'] for item in EPISODE_LIST)
    
    # 2. Şu anki zaman (Unix Time)
    current_time = int(time.time())
    
    # 3. Döngünün neresindeyiz? (Matematiksel Modülo)
    # Bu işlem sayesinde yayın sonsuza kadar döner.
    loop_position = current_time % total_playlist_duration
    
    # 4. Şu an hangi bölüm oynamalı?
    accumulated_time = 0
    now_playing = None
    start_offset = 0

    for episode in EPISODE_LIST:
        # Eğer döngü pozisyonu, bu videonun süresi içindeyse:
        if accumulated_time + episode["duration"] > loop_position:
            now_playing = episode
            # Videonun kaçıncı saniyesinden başlamalıyız?
            start_offset = loop_position - accumulated_time
            break
        accumulated_time += episode["duration"]
    
    # Bir sonraki bölümü bul (UI'da göstermek için)
    current_index = EPISODE_LIST.index(now_playing)
    next_index = (current_index + 1) % len(EPISODE_LIST)
    next_episode = EPISODE_LIST[next_index]

    # 5. JSON Verisini Oluştur
    channel_data = {
        "channel_name": "Kuzey Güney 7/24",
        "timestamp": current_time,
        "now_playing": {
            "title": now_playing["title"],
            "url": now_playing["url"],
            "total_duration": now_playing["duration"],
            
            # ANDROID İÇİN EN ÖNEMLİ KISIM:
            # Player.seekTo() komutuna gidecek saniye
            "start_at_second": start_offset 
        },
        "next_episode": {
            "title": next_episode["title"],
            "url": next_episode["url"]
        }
    }

    # 6. Dosyayı Kaydet
    os.makedirs("api", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ Canlı Yayın Ayarlandı!")
    print(f"Oynayan: {now_playing['title']}")
    print(f"Başlangıç: {start_offset}. saniyeden (seekTo)")

def purge_cache():
    # jsDelivr Önbelleğini Temizle
    url = f"https://purge.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/{OUTPUT_FILE}"
    try:
        requests.get(url)
        print("🚀 CDN Önbelleği Temizlendi.")
    except Exception as e:
        print(f"Purge Hatası: {e}")

if __name__ == "__main__":
    create_channel()
    purge_cache()
