import requests
import json
import re
import concurrent.futures
import time
from urllib.parse import urljoin

# ==================== AYARLAR ====================
GITHUB_SOURCE_URL = 'https://raw.githubusercontent.com/nikyokki/nik-cloudstream/refs/heads/master/RecTV/src/main/kotlin/com/keyiflerolsun/RecTV.kt'
PROXY_URL = 'https://api.codetabs.com/v1/proxy/?quest=' + requests.utils.quote(GITHUB_SOURCE_URL)

# Sabitler
M3U_USER_AGENT = 'googleusercontent'
TIMEOUT = 20 # Zaman aşımını biraz arttırdım
MAX_WORKERS = 5 

# Dosya İsimleri
FILE_LIVE = 'canli.m3u'
FILE_MOVIES = 'filmler.m3u'
FILE_SERIES = 'diziler.m3u'

class RecTVScraper:
    def __init__(self):
        self.headers_default = {
            'User-Agent': 'okhttp/4.12.0',
            'Referer': 'https://twitter.com/'
        }
        self.headers_vod = {
            'User-Agent': 'Dart/3.7 (dart:io)',
            'Referer': 'https://twitter.com/'
        }
        
        self.main_url = "https://m.prectv60.lol" 
        self.sw_key = ""
        self.found_items = {"live": 0, "movies": 0, "series": 0}
        
        self.buffer_live = []
        self.buffer_movies = []
        self.buffer_series = []

    def log(self, message):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def request_with_retry(self, url, headers, retries=3):
        """Bir istek başarısız olursa belirtilen sayıda tekrar dener"""
        for i in range(retries):
            try:
                r = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
                if r.status_code == 200:
                    return r
                elif r.status_code == 404:
                    return None # Sayfa yoksa tekrar deneme
            except requests.exceptions.RequestException:
                time.sleep(1) # Hata durumunda 1 saniye bekle
                continue
        return None

    def fetch_github_config(self):
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
            
            ua = re.search(r'headers\s*=\s*mapOf\([^)]*"user-agent"[^)]*to[^"]*"([^"]+)"', content, re.IGNORECASE)
            if ua: self.headers_default['User-Agent'] = ua.group(1)
            
            self.log(f"Config Güncellendi: URL={self.main_url}")
            return True
        return False

    def find_working_domain(self):
        if self.test_domain(self.main_url):
            self.log(f"GitHub domaini çalışıyor: {self.main_url}")
            return

        self.log("GitHub domaini yanıt vermedi. Taramaya geçiliyor...")
        # 70'ten geriye doğru tara (Geleceğe yönelik arttırdım)
        for i in range(70, 0, -1):
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
        tag = ""
        lower_title = title.lower()
        cat_str = "".join([c['title'].lower() for c in categories]) if categories else ""

        if "dublaj" in lower_title or "tr" in lower_title or "türkçe" in cat_str:
            tag = " [TR Dublaj]"
        elif "altyazı" in lower_title or "al tyazı" in lower_title:
            tag = " [Altyazılı]"
        return title + tag

    def fetch_series_episodes(self, serie_id, serie_title, serie_image):
        episode_entries = []
        url = f"{self.main_url}/api/season/by/serie/{serie_id}/{self.sw_key}"
        
        # Retry mekanizması ile istek at
        r = self.request_with_retry(url, self.headers_vod)
        if not r: return []
        
        try:
            seasons = r.json()
            if not seasons or not isinstance(seasons, list): return []

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
                                # WORKER KALDIRILDI: Direkt URL kullanılıyor
                                
                                full_title = f"{serie_title} - {season_name} - {ep_name}"
                                
                                entry = f'#EXTINF:-1 tvg-id="{serie_id}" tvg-name="{full_title}" tvg-logo="{serie_image}" group-title="{group_title}", {full_title}'
                                entry += f'\n#EXTVLCOPT:http-user-agent=okhttp/4.12.0'
                                entry += f'\n#EXTVLCOPT:http-referrer=https://twitter.com'
                                entry += f'\n{raw_url}'
                                
                                episode_entries.append(entry)
        except Exception as e:
            self.log(f"Bölüm hatası ({serie_title}): {e}")
            
        return episode_entries

    def process_content(self, items, content_type, category_name="Genel"):
        count = 0
        current_headers = self.headers_default if content_type == "live" else self.headers_vod

        for item in items:
            title = item.get('title', 'Bilinmeyen')
            image = item.get('image', '')
            if image and not image.startswith('http'):
                image = urljoin(self.main_url, image)
            tid = item.get('id', 0)
            
            # --- DİZİLER ---
            if content_type == "series":
                episodes = self.fetch_series_episodes(tid, title, image)
                if episodes:
                    self.buffer_series.extend(episodes)
                    self.found_items["series"] += 1
                    count += 1
                continue 
            
            # --- FİLM & CANLI ---
            if 'sources' not in item: continue
            
            for source in item['sources']:
                if (source.get('type') == 'm3u8' or source.get('type') == 'mp4') and source.get('url'):
                    raw_url = source['url']
                    
                    if content_type == "movies":
                        full_title = self.get_dub_sub_info(title, item.get('categories', []))
                    else:
                        full_title = title 

                    entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{full_title}" tvg-logo="{image}" group-title="{category_name}", {full_title}'
                    entry += f'\n#EXTVLCOPT:http-user-agent={M3U_USER_AGENT}'
                    entry += f'\n#EXTVLCOPT:http-referrer={current_headers["Referer"]}'
                    entry += f'\n{raw_url}'

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
        max_empty_streak = 5 # Kaç boş sayfadan sonra dursun? (Diziler için önemli)
        
        # Dizilerde içerik kaybı olmaması için toleransı arttırıyoruz
        if content_type == "series":
            max_empty_streak = 10 
        
        current_headers = self.headers_default if content_type == "live" else self.headers_vod
        
        while True:
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            
            # Retry mekanizması ile istek at
            r = self.request_with_retry(url, current_headers)
            
            if not r: 
                # Eğer retry'lara rağmen cevap yoksa bu sayfayı atla ama döngüyü kırma (belki diğer sayfa çalışır)
                empty_streak += 1
                if empty_streak >= max_empty_streak: break
                page += 1
                continue

            try:
                data = r.json()
                if not data or not isinstance(data, list):
                    empty_streak += 1
                else:
                    count = self.process_content(data, content_type, category_name)
                    if count == 0: empty_streak += 1
                    else: empty_streak = 0 # Veri bulundu, sayacı sıfırla

                if empty_streak >= max_empty_streak: 
                    self.log(f"{category_name} bitti. (Son sayfa: {page})")
                    break
                
                page += 1
                
            except Exception as e:
                self.log(f"JSON Hatası ({category_name} - Syf {page}): {e}")
                empty_streak += 1
                if empty_streak >= max_empty_streak: break

    def run(self):
        if not self.fetch_github_config():
            self.log("Config alınamadı, varsayılanlar kullanılacak.")
        
        self.find_working_domain()

        # DİZİLER: "Son Eklenenler" (0) en kapsamlısıdır. Diğerleri kategori bazlıdır.
        # Çakışmaları önlemek ve tümünü çekmek için temel filtreleri koruyoruz.
        tasks = [
            ("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"),
            
            ("api/serie/by/filtres/0/created/SAYFA/", "Tüm Diziler (Son Eklenen)", "series"),
            ("api/serie/by/filtres/1/created/SAYFA/", "Aksiyon Dizileri", "series"),
            ("api/serie/by/filtres/2/created/SAYFA/", "Dram Dizileri", "series"),
            ("api/serie/by/filtres/3/created/SAYFA/", "Komedi Dizileri", "series"),
            
            ("api/movie/by/filtres/0/created/SAYFA/", "Son Filmler", "movies"),
            ("api/movie/by/filtres/1/created/SAYFA/", "Aksiyon", "movies"),
            ("api/movie/by/filtres/2/created/SAYFA/", "Dram", "movies"),
            ("api/movie/by/filtres/3/created/SAYFA/", "Komedi", "movies"),
            ("api/movie/by/filtres/4/created/SAYFA/", "Bilim Kurgu", "movies"),
            ("api/movie/by/filtres/8/created/SAYFA/", "Korku", "movies"),
            ("api/movie/by/filtres/23/created/SAYFA/", "Yerli Filmler", "movies"),
        ]

        self.log(f"Tarama başlıyor... (Retry Aktif - Worker Yok)")

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

        # 4. Kaydet ve SIRALA (Sorting)
        # Github'daki "değişiklik" sorununu çözmek için içerikleri alfabetik sıralıyoruz.
        self.log("Veriler sıralanıyor ve kaydediliyor...")
        
        self.buffer_live.sort()
        self.buffer_movies.sort()
        self.buffer_series.sort()

        # Başlarına #EXTM3U ekle
        self.buffer_live.insert(0, "#EXTM3U")
        self.buffer_movies.insert(0, "#EXTM3U")
        self.buffer_series.insert(0, "#EXTM3U")

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
