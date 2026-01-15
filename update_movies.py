import requests
import json
import re
import time
import os

# --- AYARLAR ---
M3U_URL = "https://cdn.jsdelivr.net/gh/dizifun/Yeniapp@main/filmler.m3u"
OUTPUT_FILE = "filmler_tmdb.json"

# BURAYA KENDİ TMDB API ANAHTARINI YAZMALISIN!
TMDB_API_KEY = "6fabef7bd74e01efcd81d35c39c4a049" 
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Tür ID'lerini İsimlere Çevirmek İçin (TMDB Standart Listesi)
GENRE_MAP = {
    28: "Aksiyon", 12: "Macera", 16: "Animasyon", 35: "Komedi",
    80: "Suç", 99: "Belgesel", 18: "Dram", 10751: "Aile",
    14: "Fantastik", 36: "Tarih", 27: "Korku", 10402: "Müzik",
    9648: "Gizem", 10749: "Romantik", 878: "Bilim Kurgu",
    10770: "TV Filmi", 53: "Gerilim", 10752: "Savaş", 37: "Vahşi Batı"
}

def clean_name(name):
    """Filmin ismini arama için temizler ve yılı ayıklar."""
    # Yıl bulma (Parantez içinde 4 rakam: (1999))
    year_match = re.search(r'\((\d{4})\)', name)
    year = year_match.group(1) if year_match else None
    
    # Temizlik
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name) # Parantezleri sil
    name = re.sub(r'\b(TV|TR|EN|SUB|DUB|HD|FHD|4K|1080p|720p|HEVC)\b', '', name, flags=re.IGNORECASE)
    name = name.replace('|', '').replace('_', ' ').strip()
    name = re.sub(' +', ' ', name) # Çift boşlukları sil
    
    return name, year

def get_tmdb_info(query_name, year=None):
    """TMDB'den ID ve Tür bilgisini çeker."""
    if not TMDB_API_KEY or TMDB_API_KEY == "SENIN_API_KEY_BURAYA":
        print("HATA: API Key girilmemiş!")
        return None, "Kategorisiz"

    search_url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'query': query_name,
        'language': 'tr-TR',
        'page': 1
    }
    if year:
        params['year'] = year

    try:
        r = requests.get(search_url, params=params, timeout=5)
        data = r.json()
        
        if data['results']:
            # En iyi eşleşmeyi al
            best_match = data['results'][0]
            movie_id = best_match['id']
            genre_ids = best_match.get('genre_ids', [])
            
            # İlk türü ana kategori yap
            main_category = GENRE_MAP.get(genre_ids[0], "Diğer Filmler") if genre_ids else "Diğer Filmler"
            
            return movie_id, main_category
        else:
            return None, "Bulunamayanlar"
            
    except Exception as e:
        print(f"TMDB Hatası: {e}")
        return None, "Hata"

def main():
    print("M3U İndiriliyor...")
    response = requests.get(M3U_URL)
    lines = response.text.splitlines()

    organized_data = {} # { "Aksiyon": [ {film}, {film} ] }

    current_entry = {}
    
    # İşlem uzun sürebilir, sayacı takip et
    count = 0
    total_lines = len([l for l in lines if l.startswith("#EXTINF")])
    print(f"Toplam {total_lines} içerik işlenecek...")

    for line in lines:
        line = line.strip()
        
        if line.startswith("#EXTINF"):
            count += 1
            if count % 10 == 0: print(f"İşleniyor: {count}/{total_lines}")
            
            # Ham ismi al
            raw_name = line.split(",")[-1].strip()
            
            # İsmi temizle ve yılı al
            clean_title, year = clean_name(raw_name)
            
            # TMDB'ye sor (ID ve Kategori al)
            # NOT: Çok hızlı istek atarsan TMDB engelleyebilir, minik bekleme:
            tmdb_id, category = get_tmdb_info(clean_title, year)
            time.sleep(0.1) # 100ms bekleme
            
            current_entry = {
                "name": clean_title,
                "tmdb_id": tmdb_id, # İşte istediğin ID burada!
                "year": year
            }
            
            # Geçici olarak kategoriyi aklımızda tutalım
            current_entry["_temp_category"] = category
            
        elif line.startswith("http"):
            if current_entry:
                category = current_entry.pop("_temp_category")
                current_entry["url"] = line
                
                # Eğer ID bulunamadıysa (TMDB'de yoksa) "Diğer"e at
                if not current_entry["tmdb_id"]:
                    category = "Kategorisiz"
                
                if category not in organized_data:
                    organized_data[category] = []
                
                organized_data[category].append(current_entry)
                current_entry = {}

    # JSON Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(organized_data, f, ensure_ascii=False, indent=2)

    print(f"Bitti! {OUTPUT_FILE} oluşturuldu.")

if __name__ == "__main__":
    main()
