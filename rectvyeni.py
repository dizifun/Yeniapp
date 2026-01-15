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
TIMEOUT = 30  # Zaman aşımı süresi arttırıldı (Sunucu yavaşsa beklemesi için)
MAX_RETRIES = 5  # Hata alırsa kaç kez tekrar denesin?
MAX_WORKERS = 10 

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
                    # 500 veya 502 hatası alırsa bekle ve tekrar dene
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
        # 80'den geriye doğru tara
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
        
        # Retry mekanizması kritik (Dizilerin eksik gelmemesi için)
        r = self.request_with_retry(url, self.headers_vod)
        if not r: return []
        
        try:
            seasons = r.json()
            if not seasons or not isinstance(seasons, list): return []

            group_title = serie_title.replace(",", " ") # M3U formatını bozmamak için virgülleri temizle

            for season in seasons:
                season_name = season.get("title", "Sezon")
                episodes = season.get("episodes", [])
                
                for ep in episodes:
                    ep_name = ep.get("title", "Bölüm")
                    
                    if 'sources' in ep:
                        for source in ep['sources']:
                            if source.get('url') and str(source.get('url')).endswith('.m3u8'):
                                raw_url = source['url']
                                # PROXY YOK - Direkt URL
                                
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

            # Eğer bu ID zaten kaydedildiyse tekrar işleme (Zaman kazan ve duplike önle)
            if content_type == "movies" and tid in self.movies_dict: continue
            if content_type == "series" and tid in self.series_dict: continue
            
            title = item.get('title', 'Bilinmeyen')
            image = item.get('image', '')
            if image and not image.startswith('http'):
                image = urljoin(self.main_url, image)
            
            # --- DİZİLER ---
            if content_type == "series":
                # Dizinin bölümlerini çek
                episodes = self.fetch_series_episodes(tid, title, image)
                if episodes:
                    # ID'yi anahtar olarak kullanıp listeye ekliyoruz
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

                    full_title = full_title.replace(",", " ") # M3U hatası önlemek için

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
        
        # Diziler için toleransı çok yüksek tutuyoruz
        max_empty_streak = 20 if content_type == "series" else 5
        
        current_headers = self.headers_default if content_type == "live" else self.headers_vod
        
        while True:
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            
            # Güçlendirilmiş İstek
            r = self.request_with_retry(url, current_headers)
            
            if not r: 
                empty_streak += 1
                if empty_streak >= max_empty_streak: break
                page += 1
                continue

            try:
                data = r.json()
                # Liste boşsa veya liste değilse
                if not data or not isinstance(data, list):
                    empty_streak += 1
                else:
                    count = self.process_content(data, content_type, category_name)
                    # Eğer içerik geldi ama hepsi zaten bizde varsa (duplike) count 0 döner
                    # Bu durumda API bitmemiş olabilir, devam etmeliyiz.
                    if count == 0 and len(data) > 0:
                        empty_streak = 0 # Veri var, sadece bizde kayıtlı. Devam.
                    elif count > 0:
                        empty_streak = 0 # Yeni veri bulundu.
                    else:
                        empty_streak += 1 # Veri yok.

                if empty_streak >= max_empty_streak: 
                    self.log(f"{category_name} bitti. (Son sayfa: {page})")
                    break
                
                page += 1
                
            except Exception as e:
                self.log(f"Hata ({category_name} - Syf {page}): {e}")
                empty_streak += 1
                if empty_streak >= max_empty_streak: break

    def run(self):
        if not self.fetch_github_config():
            self.log("Config alınamadı, varsayılanlar kullanılacak.")
        
        self.find_working_domain()

        tasks = [
            ("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"),
            
            # Diziler için geniş filtreler
            ("api/serie/by/filtres/0/created/SAYFA/", "Tüm Diziler", "series"),
            ("api/serie/by/filtres/1/created/SAYFA/", "Aksiyon", "series"),
            
            # Filmler için geniş filtreler
            ("api/movie/by/filtres/0/created/SAYFA/", "Son Filmler", "movies"),
            ("api/movie/by/filtres/1/created/SAYFA/", "Aksiyon", "movies"),
            ("api/movie/by/filtres/2/created/SAYFA/", "Dram", "movies"),
            ("api/movie/by/filtres/3/created/SAYFA/", "Komedi", "movies"),
            ("api/movie/by/filtres/4/created/SAYFA/", "Bilim Kurgu", "movies"),
            ("api/movie/by/filtres/8/created/SAYFA/", "Korku", "movies"),
            ("api/movie/by/filtres/23/created/SAYFA/", "Yerli Filmler", "movies"),
        ]

        self.log(f"Tarama başlıyor... (Proxy KAPALI - Retry AKTİF)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self.scrape_category, t[0], t[1], t[2]): t 
                for t in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                task = future_to_url[future]
                try:
                    future.result()
                    self.log(f"Kategori Tamamlandı: {task[1]}")
                except Exception as exc:
                    self.log(f"Task hatası {task[1]}: {exc}")

        # KAYDETME AŞAMASI
        self.log("Veriler işleniyor ve kaydediliyor...")

        # Sözlükleri Listeye Çevir (Böylece ID'ler tekil olur)
        
        # Canlı TV
        final_live = ["#EXTM3U"] + list(self.live_dict.values())
        
        # Filmler (İsme göre alfabetik sırala)
        sorted_movies = sorted(self.movies_dict.values(), key=lambda x: x.split(',')[1])
        final_movies = ["#EXTM3U"] + sorted_movies

        # Diziler (Sözlükteki her değer bir liste olduğu için onları düzleştirmemiz lazım)
        all_episodes = []
        for ep_list in self.series_dict.values():
            all_episodes.extend(ep_list)
        
        # Dizileri isme göre sırala
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
