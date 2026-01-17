import requests
import json
import re
import time

# --- AYARLAR ---
# Senin GitHub veritabanı linkin
DATA_URL = "https://raw.githubusercontent.com/dizifun/Filmdizi/main/veritabani.json"
OUTPUT_FILE = "filmler_tmdb.json"

# TMDB API Anahtarı
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
    """Filmin ismini arama için temizler ve varsa yılı ayıklar."""
    # Yıl bulma (Genellikle başlıkta yıl olmaz ama temizlik için önlem)
    year_match = re.search(r'\((\d{4})\)', name)
    year = year_match.group(1) if year_match else None

    # Temizlik (Gereksiz takıları temizler)
    name = re.sub(r'\[.*?\]|\(.*?\)', '', name)
    name = re.sub(r'\b(TV|TR|EN|SUB|DUB|HD|FHD|4K|1080p|720p|HEVC|DUAL|Filmbol)\b', '', name, flags=re.IGNORECASE)
    name = name.replace('|', '').replace('_', ' ').replace(':', '').strip()
    name = re.sub(' +', ' ', name)

    return name, year

def get_tmdb_info(query_name, year=None):
    """TMDB'den ID ve Tür bilgisini çeker."""
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
        r = requests.get(search_url, params=params, timeout=10)
        data = r.json()

        if data.get('results'):
            best_match = data['results'][0]
            movie_id = best_match['id']
            genre_ids = best_match.get('genre_ids', [])
            main_category = GENRE_MAP.get(genre_ids[0], "Diğer Filmler") if genre_ids else "Diğer Filmler"
            return movie_id, main_category
        return None, None
    except Exception as e:
        print(f"TMDB Hatası ({query_name}): {e}")
        return None, None

def main():
    print(f"Veritabanı indiriliyor: {DATA_URL}")
    try:
        response = requests.get(DATA_URL)
        raw_movies = response.json()
    except Exception as e:
        print(f"Veritabanı çekilemedi: {e}")
        return

    organized_data = {}
    total_movies = len(raw_movies)
    print(f"Toplam {total_movies} film işlenecek...")

    for count, movie in enumerate(raw_movies, 1):
        baslik = movie.get("baslik", "Bilinmeyen Film")
        video_url = movie.get("video_url")
        altyazi = movie.get("altyazi")
        poster = movie.get("poster")

        # Altyazı kontrolü: Eğer "YOK" veya null ise temizle
        if altyazi in ["YOK", "null", None]:
            altyazi = None

        # Başlığı temizle ve TMDB'den bilgi al
        clean_title, year = clean_name(baslik)
        tmdb_id, category = get_tmdb_info(clean_title, year)
        
        # Eğer TMDB kategorisi bulunamazsa JSON'daki orijinal kategoriyi kullan
        if not category:
            category = movie.get("kategori", "Kategorisiz")

        # Film objesini oluştur
        film_entry = {
            "baslik": baslik,
            "arama_ismi": clean_title,
            "tmdb_id": tmdb_id,
            "video_url": video_url,
            "altyazi_url": altyazi,
            "poster": poster,
            "yil": year
        }

        # Kategoriye göre grupla
        if category not in organized_data:
            organized_data[category] = []
        organized_data[category].append(film_entry)

        if count % 10 == 0:
            print(f"İşlenen: {count}/{total_movies} - {baslik}")
        
        # TMDB API limitlerine takılmamak için kısa bekleme
        time.sleep(0.1)

    # Yeni JSON dosyasına kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(organized_data, f, ensure_ascii=False, indent=2)

    print(f"\nİşlem tamamlandı! {OUTPUT_FILE} dosyası oluşturuldu.")

if __name__ == "__main__":
    main()
