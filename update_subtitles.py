import json
import requests
import os
import time

# --- AYARLAR ---
# Senin verdiğin API Key buraya gömüldü:
API_KEY = "Vh6X0uRepaL9tL4eIXhoZskewjud2yrE" 

# Dosya isminin repondakiyle BİREBİR aynı olduğundan emin ol:
JSON_FILE = 'filmler_tmdb.json' 

# Her çalıştığında kaç film tarasın? 
# (Çok yüksek yapma, API ban atabilir. 250 idealdir.)
LIMIT_PER_RUN = 250  

# İstekler arası bekleme süresi (Saniye)
SLEEP_TIME = 1.2     

HEADERS = {
    'Api-Key': API_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'TrMovieArchive v1.2' 
}

def get_subtitles(tmdb_id):
    url = "https://api.opensubtitles.com/api/v1/subtitles"
    params = {
        'tmdb_id': tmdb_id,
        'languages': 'tr,en',     # Önce Türkçe, sonra İngilizce ara
        'order_by': 'download_count', # En popülerleri getir
        'page': 1
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        
        # Eğer çok hızlı istek attıysak (429 Hatası)
        if response.status_code == 429:
            print("⚠️ API Hız limitine takıldık! 10 saniye soğutma yapılıyor...")
            time.sleep(10)
            return None # Bu turu pas geç
            
        response.raise_for_status()
        data = response.json()
        
        # En iyi 3 altyazının direkt linkini (veya detay sayfasını) al
        links = []
        for item in data.get('data', [])[:3]:
            # 'url' genelde altyazı sayfasıdır.
            links.append(item['attributes']['url'])
            
        return links
        
    except Exception as e:
        print(f"❌ Hata oluştu (TMDB: {tmdb_id}): {e}")
        return []

def main():
    if not os.path.exists(JSON_FILE):
        print(f"HATA: {JSON_FILE} dosyası bulunamadı! İsmi kontrol et.")
        return

    print(f"📖 {JSON_FILE} okunuyor...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    processed_count = 0
    updated_count = 0
    stop_signal = False

    # JSON yapısı: {"Aksiyon": [...], "Dram": [...]} şeklinde olduğu için:
    for category, movies in data.items():
        if stop_signal: break
        
        # Boş kategorileri atla
        if not movies: continue
            
        print(f"📂 Kategori taranıyor: {category}")
        
        for movie in movies:
            # 1. Limit Kontrolü
            if processed_count >= LIMIT_PER_RUN:
                print(f"🛑 Bu seferlik işlem limiti ({LIMIT_PER_RUN}) doldu. Kaydedip çıkılıyor.")
                stop_signal = True
                break

            # 2. Zaten altyazı var mı? (Varsa atla, boşuna API harcama)
            if movie.get('altyazi') and movie.get('altyazi') != "":
                continue

            # 3. TMDB ID var mı?
            tmdb_id = movie.get('tmdb_id')
            if not tmdb_id:
                continue

            # 4. API'ye sor
            print(f"[{processed_count + 1}] Aranıyor: {movie.get('name')} (ID: {tmdb_id})")
            
            subs = get_subtitles(tmdb_id)
            
            # Eğer API 'dur' dediyse (None döndüyse)
            if subs is None:
                stop_signal = True
                break

            # 5. Veriyi JSON alanlarına yerleştir
            if len(subs) > 0: movie['altyazi'] = subs[0]
            if len(subs) > 1: movie['altyazi2'] = subs[1]
            if len(subs) > 2: movie['altyazi3'] = subs[2]
            
            processed_count += 1
            if subs:
                updated_count += 1
            
            # Bekle (Ban yememek için)
            time.sleep(SLEEP_TIME)

    # Dosyayı kaydet
    if updated_count > 0:
        print(f"💾 Dosya kaydediliyor... ({updated_count} yeni film eklendi)")
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ İşlem başarıyla tamamlandı.")
    else:
        print("💤 Herhangi bir değişiklik yapılmadı (Limit dolmuş veya yeni film yok).")

if __name__ == "__main__":
    main()
