import requests
import json
import re
import time

# --- AYARLAR ---
M3U_URL = "https://raw.githubusercontent.com/dizifun/Filmler/main/ana_filmler.m3u"
OUTPUT_FILE = "filmler_tmdb.json"

TMDB_API_KEY = "6fabef7bd74e01efcd81d35c39c4a049" 
TMDB_BASE_URL = "https://api.themoviedb.org/3"

GENRE_MAP = {
    28: "Aksiyon", 12: "Macera", 16: "Animasyon", 35: "Komedi",
    80: "Suç", 99: "Belgesel", 18: "Dram", 10751: "Aile",
    14: "Fantastik", 36: "Tarih", 27: "Korku", 10402: "Müzik",
    9648: "Gizem", 10749: "Romantik", 878: "Bilim Kurgu",
    10770: "TV Filmi", 53: "Gerilim", 10752: "Savaş", 37: "Vahşi Batı"
}

def clean_name(name):
    """Film ismini temizler ve yılı ayıklar."""
    year_match = re.search(r'\((\d{4})\)', name)
    year = year_match.group(1) if year_match else None
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name)
    name = re.sub(r'\b(TV|TR|EN|SUB|DUB|HD|FHD|4K|1080p|720p|HEVC|DUAL|Filmbol)\b', '', name, flags=re.IGNORECASE)
    name = name.replace('|', '').replace('_', ' ').strip()
    name = re.sub(' +', ' ', name)
    return name, year

def get_tmdb_info(query_name, year=None):
    """TMDB'den veri çeker."""
    search_url = f"{TMDB_BASE_URL}/search/movie"
    params = {'api_key': TMDB_API_KEY, 'query': query_name, 'language': 'tr-TR'}
    if year: params['year'] = year
    try:
        r = requests.get(search_url, params=params, timeout=5)
        data = r.json()
        if data.get('results'):
            best = data['results'][0]
            genre_ids = best.get('genre_ids', [])
            cat = GENRE_MAP.get(genre_ids[0], "Diğer Filmler") if genre_ids else "Diğer Filmler"
            return best['id'], cat, best.get('poster_path')
    except: pass
    return None, "Kategorisiz", None

def main():
    # Geçici depo: {(İsim, Yıl): {"urls": [], "subs": [], "posters": []}}
    movie_storage = {}

    print("1. Kaynaklar İndiriliyor...")
    # --- M3U İŞLEME ---
    try:
        m3u_text = requests.get(M3U_URL).text.splitlines()
        current_name = None
        for line in m3u_text:
            if line.startswith("#EXTINF"):
                current_name = line.split(",")[-1].strip()
            elif line.startswith("http") and current_name:
                c_name, c_year = clean_name(current_name)
                key = (c_name, c_year)
                if key not in movie_storage:
                    movie_storage[key] = {"urls": [], "subs": []}
                movie_storage[key]["urls"].append(line)
                movie_storage[key]["subs"].append(None) # M3U'da altyazı yoksa None
                current_name = None
    except: print("M3U Hatası!")

    # --- JSON İŞLEME ---
    try:
        json_data = requests.get(JSON_URL).json()
        for item in json_data:
            c_name, c_year = clean_name(item.get("baslik", ""))
            key = (c_name, c_year)
            if key not in movie_storage:
                movie_storage[key] = {"urls": [], "subs": []}
            
            sub = item.get("altyazi")
            if sub in ["YOK", "null", "", None]: sub = None
            
            movie_storage[key]["urls"].append(item.get("video_url"))
            movie_storage[key]["subs"].append(sub)
    except: print("JSON Hatası!")

    # --- TMDB VE SIRALAMA ---
    final_json = {}
    total = len(movie_storage)
    print(f"2. {total} adet film TMDB ile eşleştiriliyor...")

    for count, ((name, year), data) in enumerate(movie_storage.items(), 1):
        tmdb_id, category, poster_path = get_tmdb_info(name, year)
        
        # Poster URL oluşturma
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        # Uygulama Formatına Dönüştürme
        entry = {
            "name": name,
            "tmdb_id": tmdb_id,
            "year": year,
            "poster": poster_url,
            # Birinci Kaynak
            "url": data["urls"][0] if len(data["urls"]) > 0 else "",
            "altyazi": data["subs"][0] if len(data["subs"]) > 0 else None,
            # İkinci Kaynak (Eğer varsa)
            "url2": data["urls"][1] if len(data["urls"]) > 1 else "",
            "altyazi2": data["subs"][1] if len(data["subs"]) > 1 else None,
            # Üçüncü Kaynak (Eğer varsa)
            "url3": data["urls"][2] if len(data["urls"]) > 2 else "",
            "altyazi3": data["subs"][2] if len(data["subs"]) > 2 else None
        }

        if category not in final_json:
            final_json[category] = []
        final_json[category].append(entry)

        if count % 20 == 0: print(f"İşlenen: {count}/{total}")
        time.sleep(0.05) # API ban yememek için

    # 3. Dosyaya Yaz
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"\nİşlem Tamamlandı! {OUTPUT_FILE} hazır.")

if __name__ == "__main__":
    main()
