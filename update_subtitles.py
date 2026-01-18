import json
import requests
import os
import time

# --- AYARLAR ---
# API Keylerini buraya gir
API_KEYS = [
    "Vh6X0uRepaL9tL4eIXhoZskewjud2yrE", 
    "IKINCI_ANAHTARIN",
    "UCUNCU_ANAHTARIN",
    "DORDUNCU_ANAHTARIN"
]

JSON_FILE = 'filmler_tmdb.json' 
LIMIT_PER_RUN = 50  # DİKKAT: Direkt indirme linki aldığımız için bu sayıyı DÜŞÜK tutmalısın!
SLEEP_TIME = 2      # İndirme isteği hassastır, bekleme süresini artırdık.

def get_headers(api_key):
    return {
        'Api-Key': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'TrMovieBot v3.0'
    }

def get_direct_download_link(file_id, api_key):
    """
    Dosya ID'sini kullanarak direkt indirme linki (.srt) oluşturur.
    Bu işlem kotadan düşer!
    """
    url = "https://api.opensubtitles.com/api/v1/download"
    payload = {"file_id": file_id}
    
    try:
        response = requests.post(url, headers=get_headers(api_key), json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Direkt linki döndürür
            return data.get('link')
        elif response.status_code == 429:
            print(f"⚠️ Bu anahtar ({api_key[:5]}...) indirme limitine takıldı!")
            return "LIMIT_REACHED"
        else:
            print(f"❌ İndirme linki alınamadı: {response.status_code}")
            return None
    except Exception as e:
        print(f"Hata: {e}")
        return None

def search_subtitles(tmdb_id, api_key):
    """
    Filmi arar ve dosya ID'lerini bulur.
    """
    url = "https://api.opensubtitles.com/api/v1/subtitles"
    params = {
        'tmdb_id': tmdb_id,
        'languages': 'tr,en,de,id', # Türkçe, İngilizce, Almanca, Endonezce
        'order_by': 'download_count',
        'page': 1
    }
    
    try:
        response = requests.get(url, headers=get_headers(api_key), params=params)
        if response.status_code == 429: return "LIMIT_REACHED"
        response.raise_for_status()
        return response.json().get('data', [])
    except Exception as e:
        print(f"Arama hatası: {e}")
        return []

def main():
    if not os.path.exists(JSON_FILE):
        print("JSON dosyası bulunamadı.")
        return

    # Geçerli anahtarları al
    active_keys = [k for k in API_KEYS if "ANAHTARIN" not in k]
    if not active_keys:
        print("Lütfen geçerli API Keylerinizi girin!")
        return
        
    total_keys = len(active_keys)
    print(f"🚀 Sistem {total_keys} API Anahtarı ile .srt linklerini toplayacak.")

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    processed_count = 0
    updated_count = 0
    stop_signal = False

    for category, movies in data.items():
        if stop_signal: break
        if not movies: continue
        
        print(f"📂 Kategori: {category}")
        
        for movie in movies:
            if processed_count >= LIMIT_PER_RUN:
                print(f"🛑 Günlük işlem limiti ({LIMIT_PER_RUN}) doldu.")
                stop_signal = True
                break

            # Eğer zaten altyazı doluysa atla
            if movie.get('altyazi') and "opensubtitles.com/download" in movie.get('altyazi'):
                continue

            tmdb_id = movie.get('tmdb_id')
            if not tmdb_id: continue

            # Key seçimi
            current_key = active_keys[processed_count % total_keys]
            
            print(f"[{processed_count + 1}] Aranıyor: {movie.get('name')}...")

            # 1. ADIM: ARAMA YAP
            search_results = search_subtitles(tmdb_id, current_key)
            
            if search_results == "LIMIT_REACHED":
                continue # Diğer filme/keye geç

            if not search_results:
                processed_count += 1
                continue

            # 2. ADIM: DİLLERE GÖRE AYIKLA
            # Türkçe (tr), İngilizce (en) ve Diğerleri diye ayıralım
            tr_subs = [s for s in search_results if s['attributes']['language'] == 'tr']
            en_subs = [s for s in search_results if s['attributes']['language'] == 'en']
            other_subs = [s for s in search_results if s['attributes']['language'] not in ['tr', 'en']]

            final_links = []
            
            # --- STRATEJİ: TÜRK 1, TÜRK 2, İNGİLİZCE ---
            # İndirilecek adayları belirle (En fazla 3 tane)
            files_to_download = []
            
            # 1. Slot: En iyi Türkçe
            if tr_subs: files_to_download.append(tr_subs[0])
            # 2. Slot: Varsa ikinci Türkçe, yoksa en iyi İngilizce
            if len(tr_subs) > 1: 
                files_to_download.append(tr_subs[1])
            elif en_subs:
                files_to_download.append(en_subs[0])
            # 3. Slot: Diğer diller veya kalan İngilizceler
            if other_subs:
                files_to_download.append(other_subs[0])
            elif len(en_subs) > 1 and len(files_to_download) < 3:
                files_to_download.append(en_subs[1])

            # 3. ADIM: SEÇİLENLERİN DİREKT LİNKİNİ AL (POST İSTEĞİ)
            movie_updated = False
            for index, sub_item in enumerate(files_to_download):
                file_id = sub_item['attributes']['files'][0]['file_id']
                lang_code = sub_item['attributes']['language']
                
                # İndirme linkini iste
                direct_link = get_direct_download_link(file_id, current_key)
                
                if direct_link == "LIMIT_REACHED":
                    stop_signal = True # İndirme limiti bittiyse komple dur
                    break
                
                if direct_link:
                    # JSON'a yaz (altyazi, altyazi2, altyazi3)
                    key_name = 'altyazi' if index == 0 else f'altyazi{index + 1}'
                    # İstersen linkin başına dil kodunu not düşebiliriz ama
                    # player bozulmasın diye sadece linki koyuyoruz:
                    movie[key_name] = direct_link
                    movie_updated = True
                    print(f"   ✅ {lang_code.upper()} linki alındı -> {key_name}")
                    
                time.sleep(1) # Ardışık indirme yaparken bekle

            processed_count += 1
            if movie_updated:
                updated_count += 1
            
            # Film arası bekleme
            time.sleep(SLEEP_TIME)

    if updated_count > 0:
        print(f"💾 Kaydediliyor... ({updated_count} filme direkt link eklendi)")
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        print("💤 Değişiklik yok.")

if __name__ == "__main__":
    main()
