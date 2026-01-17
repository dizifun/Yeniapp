import requests
import json
import re
import time

# --- AYARLAR ---
M3U_URL = "https://cdn.jsdelivr.net/gh/dizifun/Yeniapp@main/filmler.m3u"
JSON_URL = "https://raw.githubusercontent.com/dizifun/Filmdizi/main/veritabani.json"
OUTPUT_FILE = "filmler_tmdb.json"

# TMDB API ANAHTARI
TMDB_API_KEY = "6fabef7bd74e01efcd81d35c39c4a049" 
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Tür ID'lerini İsimlere Çevirmek İçin
GENRE_MAP = {
    28: "Aksiyon", 12: "Macera", 16: "Animasyon", 35: "Komedi",
    80: "Suç", 99: "Belgesel", 18: "Dram", 10751: "Aile",
    14: "Fantastik", 36: "Tarih", 27: "Korku", 10402: "Müzik",
    9648: "Gizem", 10749: "Romantik", 878: "Bilim Kurgu",
    10770: "TV Filmi", 53: "Gerilim", 10752: "Savaş", 37: "Vahşi Batı"
}

def clean_name(name):
    """Filmin ismini arama için temizler ve yılı ayıklar."""
    year_match = re.search(r'\((\d{4})\)', name)
    year = year_match.group(1) if year_match else None

    name = re.sub(r'\[.*?\]|\(.*?\)', '', name)
    name = re.sub(r'\b(TV|TR|EN|SUB|DUB|HD|FHD|4K|1080p|720p|HEVC|Filmbol|DUAL)\b', '', name, flags=re.IGNORECASE)
    name = name.replace('|', '').replace('_', ' ').strip()
    name = re.sub(' +', ' ', name)

    return name, year

def get_tmdb_info(query_name, year=None):
    """TMDB'den ID ve Tür bilgisini çeker."""
    if not TMDB_API_KEY:
        return None, "Kategorisiz"

    search_url = f"{TMDB_BASE_URL}/search/movie"
    params = {'api_key': TMDB_API_KEY, 'query': query_name, 'language': 'tr-TR', 'page': 1}
    if year: params['year'] = year

    try:
        r = requests.get(search_url, params=params, timeout=5)
        data = r.json()
        if data['results']:
            best_match = data['results'][0]
            movie_id = best_match['id']
            genre_ids = best_match.get('genre_ids', [])
            main_category = GENRE_MAP.get(genre_ids[0], "Diğer Filmler") if genre_ids else "Diğer Filmler"
            return movie_id, main_category
        else:
            return None, "Bulunamayanlar"
    except:
        return None, "Hata"

def main():
    organized_data = {} # Hedef: { "Aksiyon": [ {film}, {film} ] }
    processed_urls = set()

    # 1. M3U DOSYASINI İŞLE
    print("M3U İndiriliyor...")
    try:
        m3u_res = requests.get(M3U_URL)
        lines = m3u_res.text.splitlines()
        temp_name = None
        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF"):
                temp_name = line.split(",")[-1].strip()
            elif line.startswith("http") and temp_name:
                url = line
                if url not in processed_urls:
                    clean_title, year = clean_name(temp_name)
                    tmdb_id, category = get_tmdb_info(clean_title, year)
                    
                    entry = {
                        "name": clean_title,
                        "tmdb_id": tmdb_id,
                        "year": year,
                        "url": url,
                        "altyazi_url": None # M3U'da genellikle altyazı olmaz
                    }
                    if category not in organized_data: organized_data[category] = []
                    organized_data[category].append(entry)
                    processed_urls.add(url)
                temp_name = None
                time.sleep(0.05)
    except Exception as e: print(f"M3U Hatası: {e}")

    # 2. JSON VERİTABANINI İŞLE
    print("JSON Veritabanı İşleniyor...")
    try:
        json_res = requests.get(JSON_URL)
        db_items = json_res.json()
        for item in db_items:
            url = item.get("video_url")
            if url and url not in processed_urls:
                raw_name = item.get("baslik")
                clean_title, year = clean_name(raw_name)
                tmdb_id, category = get_tmdb_info(clean_title, year)

                # TMDB bulamazsa JSON'daki orijinal kategoriyi dene
                if tmdb_id is None:
                    category = item.get("kategori", "Kategorisiz")

                # Altyazı temizliği
                sub = item.get("altyazi")
                if sub in ["YOK", "null", "", None]: sub = None

                entry = {
                    "name": clean_title,
                    "tmdb_id": tmdb_id,
                    "year": year,
                    "url": url,
                    "altyazi_url": sub
                }
                
                if category not in organized_data: organized_data[category] = []
                organized_data[category].append(entry)
                processed_urls.add(url)
                time.sleep(0.05)
    except Exception as e: print(f"JSON Hatası: {e}")

    # JSON Kaydet (Senin uygulamanın istediği format)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(organized_data, f, ensure_ascii=False, indent=2)

    print(f"\nBitti! {OUTPUT_FILE} oluşturuldu. Toplam Kategori: {len(organized_data)}")

if __name__ == "__main__":
    main()
