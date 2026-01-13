import requests
import json
import re
import concurrent.futures
import time
from urllib.parse import urljoin

# ==================== AYARLAR ====================
GITHUB_SOURCE_URL = 'https://raw.githubusercontent.com/nikyokki/nik-cloudstream/refs/heads/master/RecTV/src/main/kotlin/com/keyiflerolsun/RecTV.kt'
PROXY_URL = 'https://api.codetabs.com/v1/proxy/?quest=' + requests.utils.quote(GITHUB_SOURCE_URL)

# Sabit VLC Header (M3U dosyası içine yazılan)
M3U_USER_AGENT = 'googleusercontent'
TIMEOUT = 15
MAX_WORKERS = 10 

# Dosya İsimleri
FILE_LIVE = 'canli.m3u'
FILE_MOVIES = 'filmler.m3u'
FILE_SERIES = 'diziler.m3u'

class RecTVScraper:
    def __init__(self):
        # Varsayılan (Canlı TV için kullanılacak - Fallback)
        self.headers_default = {
            'User-Agent': 'okhttp/4.12.0',
            'Referer': 'https://twitter.com/'
        }
        
        # Özel (Film ve Diziler için SENİN İSTEDİĞİN)
        self.headers_vod = {
            'User-Agent': 'Dart/3.7 (dart:io)',
            'Referer': 'https://twitter.com/'
        }

        self.main_url = "https://m.prectv60.lol" 
        self.sw_key = "" # Otomatik dolacak
        
        self.found_items = {"live": 0, "movies": 0, "series": 0}
        self.buffer_live = ["#EXTM3U"]
        self.buffer_movies = ["#EXTM3U"]
        self.buffer_series = ["#EXTM3U"]

    def log(self, message):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def get_headers(self, content_type):
        """İçerik türüne göre doğru Header'ı seçer"""
        if content_type == "live":
            return self.headers_default
        else:
            # content_type 'movies' veya 'series' ise Dart header kullan
            return self.headers_vod

    def fetch_github_config(self):
        """GitHub'dan Canlı TV için gerekli Key ve URL bilgilerini çeker"""
        self.log("GitHub'dan yapılandırma ve anahtarlar çekiliyor...")
        content = None
        try:
            r = requests.get(GITHUB_SOURCE_URL, timeout=10)
            if r.status_code == 200: content = r.text
        except: pass
        
        if not content:
            try:
                r = requests.get(PROXY_URL, timeout=10)
                if r.status_code == 200: content = r.text
            except: pass

        if content:
            # Main URL
            m_url = re.search(r'override\s+var\s+mainUrl\s*=\s*"([^"]+)"', content)
            if m_url: self.main_url = m_url.group(1)
            
            # SwKey (API Anahtarı)
            s_key = re.search(r'private\s+(val|var)\s+swKey\s*=\s*"([^"]+)"', content)
            if s_key: self.sw_key = s_key.group(2)
            
            # User Agent (Sadece Canlı TV için güncelliyoruz, VOD sabit kalacak)
            ua = re.search(r'headers\s*=\s*mapOf\([^)]*"user-agent"[^)]*to[^"]*"([^"]+)"', content, re.IGNORECASE)
            if ua: self.headers_default['User-Agent'] = ua.group(1)

            self.log(f"Config Güncellendi: URL={self.main_url}")
            self.log(f"Live User-Agent: {self.headers_default['User-Agent']}")
            self.log(f"VOD User-Agent : {self.headers_vod['User-Agent']}")
            return True
        return False

    def find_working_domain(self):
        """Domain taraması yapar"""
        # Önce mevcut URL'yi (GitHub'dan gelen veya varsayılan) dene
        if self.test_domain(self.main_url):
            self.log(f"Mevcut domain çalışıyor: {self.main_url}")
            return

        self.log("Domain yanıt vermedi. 1-60 arası taranıyor...")
        
        # En yüksek sayıdan geriye doğru tara (Genelde güncel olanlar sondadır)
        for i in range(65, 0, -1):
            domain = f"https://m.prectv{i}.lol"
            if self.test_domain(domain):
                self.main_url = domain
                self.log(f"YENİ Çalışan domain bulundu: {domain}")
                return
        
        self.log("UYARI: Hiçbir domain çalışmıyor olabilir.")

    def test_domain(self, url):
        """Domainin API'sinin çalışıp çalışmadığını test eder (Canlı TV headerı ile)"""
        try:
            # Test için canlı TV endpointi kullanılır
            test_url = f"{url}/api/channel/by/filtres/0/0/0/{self.sw_key}"
            r = requests.get(test_url, headers=self.headers_default, timeout=5, verify=False)
            return r.status_code == 200 and isinstance(r.json(), list)
        except:
            return False

    def get_dub_sub_info(self, title, categories):
        """Başlık ve kategoriden dil bilgisi çıkarır"""
        tag = ""
        lower_title = title.lower()
        cat_str = "".join([c['title'].lower() for c in categories]) if categories else ""

        if "dublaj" in lower_title or "tr" in lower_title or "türkçe" in cat_str:
            tag = " [TR Dublaj]"
        elif "altyazı" in lower_title or "al tyazı" in lower_title:
            tag = " [Altyazılı]"
        
        return title + tag

    def process_content(self, items, content_type, category_name="Genel"):
        count = 0
        current_headers = self.get_headers(content_type) # Hangi header kullanılacak?

        for item in items:
            if 'sources' not in item: continue
            
            for source in item['sources']:
                # m3u8 veya mp4 kaynaklarını al
                if (source.get('type') == 'm3u8' or source.get('type') == 'mp4') and source.get('url'):
                    title = item.get('title', 'Bilinmeyen')
                    image = item.get('image', '')
                    if image and not image.startswith('http'):
                        image = urljoin(self.main_url, image)
                    
                    tid = item.get('id', 0)
                    
                    # Film/Dizi ise isme etiket ekle
                    if content_type != "live":
                        full_title = self.get_dub_sub_info(title, item.get('categories', []))
                    else:
                        full_title = title

                    # M3U Formatı
                    entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{full_title}" tvg-logo="{image}" group-title="{category_name}", {full_title}'
                    entry += f'\n#EXTVLCOPT:http-user-agent={M3U_USER_AGENT}'
                    entry += f'\n#EXTVLCOPT:http-referrer={current_headers["Referer"]}' # Referer'ı dinamik al
                    entry += f'\n{source["url"]}'

                    if content_type == "live":
                        self.buffer_live.append(entry)
                        self.found_items["live"] += 1
                    elif content_type == "movies":
                        self.buffer_movies.append(entry)
                        self.found_items["movies"] += 1
                    elif content_type == "series":
                        self.buffer_series.append(entry)
                        self.found_items["series"] += 1
                    count += 1
        return count

    def scrape_category(self, api_template, category_name, content_type, start_page=0):
        page = start_page
        empty_streak = 0
        current_headers = self.get_headers(content_type)
        
        while True:
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            try:
                # Burada ilgili içerik türüne göre header seçilip gönderiliyor
                r = requests.get(url, headers=current_headers, timeout=TIMEOUT, verify=False)
                
                if r.status_code != 200: 
                    # Hata durumunda log bas (Diziler için önemli)
                    if content_type == "series" and page == 0:
                        self.log(f"DİZİ HATASI (HTTP {r.status_code}): Erişim reddedildi veya endpoint yanlış.")
                    break
                
                data = r.json()
                if not data or not isinstance(data, list):
                    break 

                count = self.process_content(data, content_type, category_name)
                
                if count == 0:
                    empty_streak += 1
                else:
                    empty_streak = 0
                
                if empty_streak >= 5: break # 5 sayfa boş gelirse dur
                
                page += 1
            except Exception as e:
                self.log(f"Hata ({category_name} - Syf {page}): {e}")
                break

    def run(self):
        # 1. Config Çek
        self.fetch_github_config()
        
        # 2. Domain Doğrula
        self.find_working_domain()

        # 3. Kategori Listesi
        tasks = [
            # --- CANLI TV (Default Header Kullanır) ---
            ("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"),
            
            # --- DİZİLER (Dart Header Kullanır) ---
            # Diziler için 0 filtresi genellikle "Son Eklenenler"dir.
            ("api/serie/by/filtres/0/created/SAYFA/", "Son Eklenen Diziler", "series"),
            ("api/serie/by/filtres/1/created/SAYFA/", "Aksiyon Dizileri", "series"),
            ("api/serie/by/filtres/2/created/SAYFA/", "Dram Dizileri", "series"),
            ("api/serie/by/filtres/3/created/SAYFA/", "Komedi Dizileri", "series"),
            
            # --- FİLMLER (Dart Header Kullanır) ---
            ("api/movie/by/filtres/0/created/SAYFA/", "Son Eklenen Filmler", "movies"),
            ("api/movie/by/filtres/1/created/SAYFA/", "Aksiyon", "movies"),
            ("api/movie/by/filtres/2/created/SAYFA/", "Dram", "movies"),
            ("api/movie/by/filtres/3/created/SAYFA/", "Komedi", "movies"),
            ("api/movie/by/filtres/4/created/SAYFA/", "Bilim Kurgu", "movies"),
            ("api/movie/by/filtres/8/created/SAYFA/", "Korku", "movies"),
            ("api/movie/by/filtres/23/created/SAYFA/", "Yerli Filmler", "movies"),
        ]

        self.log(f"Tarama başlıyor... (Canlı TV: Default | Film/Dizi: Dart)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self.scrape_category, t[0], t[1], t[2]): t 
                for t in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                task = future_to_url[future]
                try:
                    future.result()
                    self.log(f"Bitti: {task[1]}")
                except Exception as exc:
                    self.log(f"Task hatası {task[1]}: {exc}")

        # 4. Kaydet
        self.save_file(FILE_LIVE, self.buffer_live)
        self.save_file(FILE_MOVIES, self.buffer_movies)
        self.save_file(FILE_SERIES, self.buffer_series)
        
        self.log("="*30)
        self.log(f"Canlı TV: {self.found_items['live']}")
        self.log(f"Filmler : {self.found_items['movies']}")
        self.log(f"Diziler : {self.found_items['series']}")
        self.log("="*30)

    def save_file(self, filename, content_list):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_list))
        self.log(f"Dosya kaydedildi: {filename}")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    scraper = RecTVScraper()
    scraper.run()
