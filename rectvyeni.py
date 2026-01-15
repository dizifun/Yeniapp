import requests
import json
import re
import concurrent.futures
import time
from urllib.parse import urljoin, quote

# ==================== AYARLAR ====================
GITHUB_SOURCE_URL = 'https://raw.githubusercontent.com/nikyokki/nik-cloudstream/refs/heads/master/RecTV/src/main/kotlin/com/keyiflerolsun/RecTV.kt'
PROXY_URL = 'https://api.codetabs.com/v1/proxy/?quest=' + requests.utils.quote(GITHUB_SOURCE_URL)

# Linkleri sarmalayacak Worker Proxy (Referans koddan alındı)
WORKER_PREFIX = "https://1.nejyoner19.workers.dev/?url="

# Sabitler
M3U_USER_AGENT = 'googleusercontent'
TIMEOUT = 15
MAX_WORKERS = 5  # Dizi detayına girildiği için worker sayısını çok artırmamak sunucu sağlığı için iyidir

# Dosya İsimleri
FILE_LIVE = 'canli.m3u'
FILE_MOVIES = 'filmler.m3u'
FILE_SERIES = 'diziler.m3u'

class RecTVScraper:
    def __init__(self):
        # Varsayılan (Canlı TV için)
        self.headers_default = {
            'User-Agent': 'okhttp/4.12.0',
            'Referer': 'https://twitter.com/'
        }
        
        # VOD (Film/Dizi için - Dart/3.7 isteğin üzerine)
        self.headers_vod = {
            'User-Agent': 'Dart/3.7 (dart:io)',
            'Referer': 'https://twitter.com/'
        }
        
        self.main_url = "https://m.prectv60.lol" 
        self.sw_key = ""
        self.found_items = {"live": 0, "movies": 0, "series": 0}
        
        # Tamponlar
        self.buffer_live = ["#EXTM3U"]
        self.buffer_movies = ["#EXTM3U"]
        self.buffer_series = ["#EXTM3U"]

    def log(self, message):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def get_headers(self, content_type):
        return self.headers_default if content_type == "live" else self.headers_vod

    def fetch_github_config(self):
        """GitHub'dan konfigürasyon çeker"""
        self.log("GitHub'dan yapılandırma çekiliyor...")
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
            m_url = re.search(r'override\s+var\s+mainUrl\s*=\s*"([^"]+)"', content)
            if m_url: self.main_url = m_url.group(1)
            
            s_key = re.search(r'private\s+(val|var)\s+swKey\s*=\s*"([^"]+)"', content)
            if s_key: self.sw_key = s_key.group(2)
            
            # Canlı TV User-Agent güncelle
            ua = re.search(r'headers\s*=\s*mapOf\([^)]*"user-agent"[^)]*to[^"]*"([^"]+)"', content, re.IGNORECASE)
            if ua: self.headers_default['User-Agent'] = ua.group(1)
            
            self.log(f"Config Güncellendi: URL={self.main_url}")
            return True
        return False

    def find_working_domain(self):
        """Domain taraması yapar"""
        if self.test_domain(self.main_url):
            self.log(f"GitHub domaini çalışıyor: {self.main_url}")
            return

        self.log("GitHub domaini yanıt vermedi. 1-60 arası taranıyor...")
        for i in range(65, 0, -1):
            domain = f"https://m.prectv{i}.lol"
            if self.test_domain(domain):
                self.main_url = domain
                self.log(f"Çalışan domain bulundu: {domain}")
                return
        self.log("UYARI: Hiçbir domain çalışmıyor olabilir.")

    def test_domain(self, url):
        try:
            test_url = f"{url}/api/channel/by/filtres/0/0/0/{self.sw_key}"
            r = requests.get(test_url, headers=self.headers_default, timeout=5, verify=False)
            return r.status_code == 200 and isinstance(r.json(), list)
        except:
            return False

    def get_dub_sub_info(self, title, categories):
        """Film başlığına dublaj/altyazı bilgisi ekler"""
        tag = ""
        lower_title = title.lower()
        cat_str = "".join([c['title'].lower() for c in categories]) if categories else ""

        if "dublaj" in lower_title or "tr" in lower_title or "türkçe" in cat_str:
            tag = " [TR Dublaj]"
        elif "altyazı" in lower_title or "al tyazı" in lower_title:
            tag = " [Altyazılı]"
        return title + tag

    def fetch_series_episodes(self, serie_id, serie_title, serie_image, serie_year):
        """
        REFERANS KODDAN ENTEGRE EDİLDİ:
        Bir dizinin ID'sini alıp, sezonlarını ve bölümlerini çeker.
        """
        episode_entries = []
        url = f"{self.main_url}/api/season/by/serie/{serie_id}/{self.sw_key}"
        
        try:
            # Diziler için VOD header kullan
            r = requests.get(url, headers=self.headers_vod, timeout=10, verify=False)
            if r.status_code != 200: return []
            
            seasons = r.json()
            if not seasons or not isinstance(seasons, list): return []

            # M3U Group Title olarak DİZİ ADINI kullanıyoruz
            group_title = serie_title

            for season in seasons:
                season_name = season.get("title", "Sezon")
                episodes = season.get("episodes", [])
                
                for ep in episodes:
                    ep_name = ep.get("title", "Bölüm")
                    
                    if 'sources' in ep:
                        for source in ep['sources']:
                            if source.get('url') and str(source.get('url')).endswith('.m3u8'):
                                raw_url = source['url']
                                # WORKER PROXY EKLEME
                                final_url = f"{WORKER_PREFIX}{raw_url}"
                                
                                # Başlık Formatı: Dizi Adı - Sezon X - Bölüm Y
                                full_title = f"{serie_title} - {season_name} - {ep_name}"
                                
                                entry = f'#EXTINF:-1 tvg-id="{serie_id}" tvg-name="{full_title}" tvg-logo="{serie_image}" group-title="{group_title}", {full_title}'
                                entry += f'\n#EXTVLCOPT:http-user-agent=okhttp/4.12.0' # Oynatıcı için header
                                entry += f'\n#EXTVLCOPT:http-referrer=https://twitter.com'
                                entry += f'\n{final_url}'
                                
                                episode_entries.append(entry)
            
            # Sunucuyu boğmamak için minik bekleme
            time.sleep(0.2)
            
        except Exception as e:
            self.log(f"Bölüm çekme hatası ({serie_title}): {e}")
            
        return episode_entries

    def process_content(self, items, content_type, category_name="Genel"):
        count = 0
        current_headers = self.get_headers(content_type)

        for item in items:
            title = item.get('title', 'Bilinmeyen')
            image = item.get('image', '')
            if image and not image.startswith('http'):
                image = urljoin(self.main_url, image)
            tid = item.get('id', 0)
            
            # ========== DİZİ İŞLEME MANTIĞI (YENİ) ==========
            if content_type == "series":
                # Dizinin sadece bilgilerini alıp, detay için yeni fonksiyona yolluyoruz
                year = item.get('year', '')
                episodes = self.fetch_series_episodes(tid, title, image, year)
                
                if episodes:
                    self.buffer_series.extend(episodes)
                    self.found_items["series"] += 1 # Dizi sayısı
                    count += 1
                continue # Dizi bitti, sonraki item'a geç
            
            # ========== CANLI TV VE FİLM İŞLEME MANTIĞI ==========
            if 'sources' not in item: continue
            
            for source in item['sources']:
                if (source.get('type') == 'm3u8' or source.get('type') == 'mp4') and source.get('url'):
                    raw_url = source['url']
                    
                    # Başlık belirle
                    if content_type == "movies":
                        full_title = self.get_dub_sub_info(title, item.get('categories', []))
                        # Filmler için de Proxy kullanalım (genelde daha iyi çalışır)
                        final_url = f"{WORKER_PREFIX}{raw_url}"
                    else:
                        full_title = title # Canlı TV
                        final_url = raw_url # Canlı TV'de proxy kullanma (genelde bozabilir)

                    # M3U Entry
                    entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{full_title}" tvg-logo="{image}" group-title="{category_name}", {full_title}'
                    entry += f'\n#EXTVLCOPT:http-user-agent={M3U_USER_AGENT}'
                    entry += f'\n#EXTVLCOPT:http-referrer={current_headers["Referer"]}'
                    entry += f'\n{final_url}'

                    if content_type == "live":
                        self.buffer_live.append(entry)
                        self.found_items["live"] += 1
                    elif content_type == "movies":
                        self.buffer_movies.append(entry)
                        self.found_items["movies"] += 1
                    
                    count += 1
        return count

    def scrape_category(self, api_template, category_name, content_type, start_page=0):
        page = start_page
        empty_streak = 0
        current_headers = self.get_headers(content_type)
        
        while True:
            # URL Oluştur
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            try:
                r = requests.get(url, headers=current_headers, timeout=TIMEOUT, verify=False)
                if r.status_code != 200: break
                
                data = r.json()
                if not data or not isinstance(data, list): break 

                # İşle
                count = self.process_content(data, content_type, category_name)
                
                if count == 0: empty_streak += 1
                else: empty_streak = 0
                
                # Güvenlik çıkışı
                if empty_streak >= 3: break
                page += 1
                
            except Exception as e:
                self.log(f"Hata ({category_name} - Syf {page}): {e}")
                break

    def run(self):
        # 1. Ayarlar
        if not self.fetch_github_config():
            self.log("Config alınamadı, varsayılanlar kullanılacak.")
        
        # 2. Domain
        self.find_working_domain()

        # 3. Görev Listesi
        tasks = [
            # CANLI TV
            ("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"),
            
            # DİZİLER (Referans kod mantığıyla işlenecek)
            ("api/serie/by/filtres/0/created/SAYFA/", "Son Diziler", "series"),
            ("api/serie/by/filtres/1/created/SAYFA/", "Aksiyon Dizileri", "series"),
            ("api/serie/by/filtres/2/created/SAYFA/", "Dram Dizileri", "series"),
            ("api/serie/by/filtres/3/created/SAYFA/", "Komedi Dizileri", "series"),
            
            # FİLMLER
            ("api/movie/by/filtres/0/created/SAYFA/", "Son Filmler", "movies"),
            ("api/movie/by/filtres/1/created/SAYFA/", "Aksiyon", "movies"),
            ("api/movie/by/filtres/2/created/SAYFA/", "Dram", "movies"),
            ("api/movie/by/filtres/3/created/SAYFA/", "Komedi", "movies"),
            ("api/movie/by/filtres/4/created/SAYFA/", "Bilim Kurgu", "movies"),
            ("api/movie/by/filtres/8/created/SAYFA/", "Korku", "movies"),
            ("api/movie/by/filtres/23/created/SAYFA/", "Yerli Filmler", "movies"),
        ]

        self.log(f"Tarama başlıyor... (Worker Proxy Aktif)")
        self.log(f"Canlı: Orjinal | Dizi/Film: Worker Proxy + Dart Header")

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
