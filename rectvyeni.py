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
TIMEOUT = 25  # Sunucu yavaşsa beklesin
MAX_RETRIES = 5  # Hata alırsa 5 kere denesin
MAX_WORKERS = 20 # Hızlandırmak için worker sayısını arttırdım (Kategori sayısı çok olduğu için)

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
        
        # SÖZLÜK YAPISI (ID bazlı kayıt - Mükerrer ve kayıp önleme için)
        self.live_dict = {}
        self.movies_dict = {}
        self.series_dict = {}

    def log(self, message):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def request_with_retry(self, url, headers):
        """İstek başarısız olursa pes etmez, tekrar dener"""
        for i in range(MAX_RETRIES):
            try:
                r = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
                if r.status_code == 200:
                    return r
                elif r.status_code == 404:
                    return None
                else:
                    time.sleep(1 + i) 
            except requests.exceptions.RequestException:
                time.sleep(1 + i)
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
        for i in range(80, 0, -1):
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
        """Bir dizinin tüm bölümlerini çeker"""
        episode_entries = []
        url = f"{self.main_url}/api/season/by/serie/{serie_id}/{self.sw_key}"
        
        r = self.request_with_retry(url, self.headers_vod)
        if not r: return []
        
        try:
            seasons = r.json()
            if not seasons or not isinstance(seasons, list): return []

            group_title = serie_title.replace(",", " ") 

            for season in seasons:
                season_name = season.get("title", "Sezon")
                episodes = season.get("episodes", [])
                
                for ep in episodes:
                    ep_name = ep.get("title", "Bölüm")
                    
                    if 'sources' in ep:
                        for source in ep['sources']:
                            if source.get('url') and str(source.get('url')).endswith('.m3u8'):
                                raw_url = source['url']
                                
                                full_title = f"{serie_title} - {season_name} - {ep_name}"
                                full_title = full_title.replace(",", " ")
                                
                                entry = f'#EXTINF:-1 tvg-id="{serie_id}" tvg-name="{full_title}" tvg-logo="{serie_image}" group-title="{group_title}", {full_title}'
                                entry += f'\n#EXTVLCOPT:http-user-agent=okhttp/4.12.0'
                                entry += f'\n#EXTVLCOPT:http-referrer=https://twitter.com'
                                entry += f'\n{raw_url}'
                                
                                episode_entries.append(entry)
        except Exception as e:
            pass
            
        return episode_entries

    def process_content(self, items, content_type, category_name="Genel"):
        count = 0
        current_headers = self.headers_default if content_type == "live" else self.headers_vod

        for item in items:
            tid = item.get('id', 0)
            if not tid: continue

            # Zaten varsa atla (Duplike önleme)
            if content_type == "movies" and tid in self.movies_dict: continue
            if content_type == "series" and tid in self.series_dict: continue
            
            title = item.get('title', 'Bilinmeyen')
            image = item.get('image', '')
            if image and not image.startswith('http'):
                image = urljoin(self.main_url, image)
            
            # --- DİZİLER ---
            if content_type == "series":
                episodes = self.fetch_series_episodes(tid, title, image)
                if episodes:
                    self.series_dict[tid] = episodes
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

                    full_title = full_title.replace(",", " ") 

                    entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{full_title}" tvg-logo="{image}" group-title="{category_name}", {full_title}'
                    entry += f'\n#EXTVLCOPT:http-user-agent={M3U_USER_AGENT}'
                    entry += f'\n#EXTVLCOPT:http-referrer={current_headers["Referer"]}'
                    entry += f'\n{raw_url}'

                    if content_type == "live":
                        self.live_dict[tid] = entry
                    elif content_type == "movies":
                        self.movies_dict[tid] = entry
                    
                    count += 1
        return count

    def scrape_category(self, api_template, category_name, content_type, start_page=0):
        page = start_page
        empty_streak = 0
        max_empty_streak = 20 if content_type == "series" else 10 # Toleransı arttırdım
        current_headers = self.headers_default if content_type == "live" else self.headers_vod
        
        while True:
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            
            r = self.request_with_retry(url, current_headers)
            
            if not r: 
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
                    # Eğer içerik geldi ama hepsi bizde varsa (duplike) count 0 olur.
                    # Ancak veri gelmeye devam ettiği sürece kesmemeliyiz.
                    if len(data) > 0:
                        empty_streak = 0 
                    else:
                        empty_streak += 1 

                if empty_streak >= max_empty_streak: 
                    # self.log(f"{category_name} bitti. (Son sayfa: {page})")
                    break
                
                page += 1
                
            except Exception as e:
                # self.log(f"Hata ({category_name} - Syf {page}): {e}")
                empty_streak += 1
                if empty_streak >= max_empty_streak: break

    def run(self):
        if not self.fetch_github_config():
            self.log("Config alınamadı, varsayılanlar kullanılacak.")
        
        self.find_working_domain()

        tasks = []
        
        # 1. CANLI TV
        tasks.append(("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"))
        
        # 2. DİZİLER - FULL TARAMA (Kategori ID 0'dan 25'e kadar dene)
        # Bu, sunucudaki her türlü dizi kategorisini bulur.
        for i in range(26):
            tasks.append((f"api/serie/by/filtres/{i}/created/SAYFA/", f"Dizi Kategori-{i}", "series"))

        # 3. FİLMLER - FULL TARAMA (Kategori ID 0'dan 45'e kadar dene)
        # Bu, Animasyon, Western, Belgesel, Yerli ne varsa hepsini bulur.
        for i in range(46):
            tasks.append((f"api/movie/by/filtres/{i}/created/SAYFA/", f"Film Kategori-{i}", "movies"))

        self.log(f"DEV TARAMA BAŞLIYOR... Toplam Görev: {len(tasks)}")
        self.log("Tüm kategoriler (0-45) taranıyor. Bu işlem biraz sürebilir.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self.scrape_category, t[0], t[1], t[2]): t 
                for t in tasks
            }
            
            count_done = 0
            for future in concurrent.futures.as_completed(future_to_url):
                task = future_to_url[future]
                count_done += 1
                # Ekrana çok fazla yazı basmaması için sadece her 10 görevde bir bilgi ver
                if count_done % 10 == 0:
                    self.log(f"İlerleme: {count_done}/{len(tasks)} kategori tamamlandı.")
                try:
                    future.result()
                except Exception as exc:
                    pass

        # KAYDETME AŞAMASI
        self.log("Veriler işleniyor, sıralanıyor ve kaydediliyor...")

        # Canlı TV
        final_live = ["#EXTM3U"] + list(self.live_dict.values())
        
        # Filmler (Sıralı)
        sorted_movies = sorted(self.movies_dict.values(), key=lambda x: x.split(',')[1])
        final_movies = ["#EXTM3U"] + sorted_movies

        # Diziler (Sıralı)
        all_episodes = []
        for ep_list in self.series_dict.values():
            all_episodes.extend(ep_list)
        
        sorted_series = sorted(all_episodes, key=lambda x: x.split(',')[1])
        final_series = ["#EXTM3U"] + sorted_series

        self.save_file(FILE_LIVE, final_live)
        self.save_file(FILE_MOVIES, final_movies)
        self.save_file(FILE_SERIES, final_series)
        
        self.log("="*30)
        self.log(f"Canlı TV: {len(self.live_dict)} kanal")
        self.log(f"Filmler : {len(self.movies_dict)} film")
        self.log(f"Diziler : {len(self.series_dict)} dizi (Toplam {len(sorted_series)} bölüm)")
        self.log("="*30)

    def save_file(self, filename, content_list):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_list))
        self.log(f"Dosya kaydedildi: {filename}")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    scraper = RecTVScraper()
    scraper.run()
