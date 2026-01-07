import requests
import json
import time
import os

# --- AYARLAR ---

# Verdiğin M3U dosyasının "RAW" (Ham) hali. 
# GitHub blob linkini raw.githubusercontent.com'a çevirdim, doğrusu budur:
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists/video/sources/www-kanald-com-tr/arsiv-diziler/kuzey-guney.m3u"

OUTPUT_FILE = "api/kuzey_guney_live.json"
GITHUB_USER = "dizifun"  # <-- Kendi Kullanıcı Adın
GITHUB_REPO = "Yeniapp"  # <-- Kendi Repo Adın

# 1 Saat 47 Dakika = 6420 Saniye
DEFAULT_DURATION = 6420 

def create_channel():
    print("📡 M3U Listesi İndiriliyor...")
    
    try:
        response = requests.get(M3U_URL)
        content = response.text
    except Exception as e:
        print(f"❌ Hata: M3U indirilemedi. {e}")
        return

    # --- LİNKLERİ AYIKLA ---
    episodes = []
    lines = content.splitlines()
    episode_counter = 1
    
    for line in lines:
        line = line.strip()
        # Eğer satır http ile başlıyorsa bu bir videodur
        if line.startswith("http"):
            episodes.append({
                "title": f"Kuzey Güney - {episode_counter}. Bölüm",
                "url": line,
                "duration": DEFAULT_DURATION
            })
            episode_counter += 1
            
    if not episodes:
        print("❌ Hata: M3U içinde hiç link bulunamadı!")
        return

    print(f"✅ Toplam {len(episodes)} bölüm bulundu ve sıraya dizildi.")

    # --- ZAMAN HESAPLAMASI (CANLI YAYIN MOTORU) ---
    
    # 1. Toplam Süre (Tüm dizi kaç saniye sürüyor?)
    total_playlist_duration = len(episodes) * DEFAULT_DURATION
    
    # 2. Şu anki Evrensel Zaman (Unix Time)
    current_time = int(time.time())
    
    # 3. Döngü Hesabı (Loop)
    loop_position = current_time % total_playlist_duration
    
    # 4. Şu an hangi bölüm oynamalı?
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
    
    # Sıradaki bölümü belirle
    next_index = (current_index + 1) % len(episodes)
    next_episode = episodes[next_index]

    # --- JSON ÇIKTISI ---
    channel_data = {
        "channel_name": "Kuzey Güney 7/24",
        "timestamp": current_time,
        "now_playing": {
            "title": now_playing["title"],
            "url": now_playing["url"],
            "total_duration": now_playing["duration"],
            
            # ANDROID İÇİN KRİTİK VERİ (seekTo):
            "start_at_second": start_offset 
        },
        "next_episode": {
            "title": next_episode["title"],
            "url": next_episode["url"]
        }
    }

    # Dosyayı Kaydet
    os.makedirs("api", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ YAYIN AKTİF: {now_playing['title']}")
    print(f"🕒 Konum: {start_offset}. saniyeden başlatılacak.")

def purge_cache():
    # jsDelivr Önbelleğini Temizle
    url = f"https://purge.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/{OUTPUT_FILE}"
    try:
        requests.get(url)
        print("🚀 CDN Önbelleği Temizlendi.")
    except:
        pass

if __name__ == "__main__":
    create_channel()
    purge_cache()
