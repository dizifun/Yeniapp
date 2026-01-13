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
TIMEOUT = 15
MAX_WORKERS = 10  # Aynı anda kaç sayfa taransın (Hız için artırılabilir)

# Dosya İsimleri
FILE_LIVE = 'canli.m3u'
FILE_MOVIES = 'filmler.m3u'
FILE_SERIES = 'diziler.m3u'

class RecTVScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'okhttp/4.12.0',
            'Referer': 'https://twitter.com/'
        }
        self.main_url = "https://m.prectv60.lol" # Fallback
        self.sw_key = ""
        self.found_items = {"live": 0, "movies": 0, "series": 0}
        
        # M3U İçerik Tamponları
        self.buffer_live = ["#EXTM3U"]
        self.buffer_movies = ["#EXTM3U"]
        self.buffer_series = ["#EXTM3U"]

    def log(self, message):
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def fetch_github_config(self):
        """GitHub'dan güncel Key ve URL bilgilerini çeker"""
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
            # Main URL
            m_url = re.search(r'override\s+var\s+mainUrl\s*=\s*"([^"]+)"', content)
            if m_url: self.main_url = m_url.group(1)
            
            # SwKey
            s_key = re.search(r'private\s+(val|var)\s+swKey\s*=\s*"([^"]+)"', content)
            if s_key: self.sw_key = s_key.group(2)
            
            # User Agent
            ua = re.search(r'headers\s*=\s*mapOf\([^)]*"user-agent"[^)]*to[^"]*"([^"]+)"', content, re.IGNORECASE)
            if ua: self.headers['User-Agent'] = ua.group(1)

            # Referer
            ref = re.search(r'headers\s*=\s*mapOf\([^)]*"Referer"[^)]*to[^"]*"([^"]+)"', content, re.IGNORECASE)
            if ref: self.headers['Referer'] = ref.group(1)
            
            self.log(f"Config Güncellendi: URL={self.main_url} | KEY=...{self.sw_key[-10:]}")
            return True
        return False

    def find_working_domain(self):
        """1'den 60'a kadar domainleri tarar veya GitHub'dan geleni doğrular"""
        # Önce GitHub'dan geleni dene
        if self.test_domain(self.main_url):
            self.log(f"GitHub domaini çalışıyor: {self.main_url}")
            return

        self.log("GitHub domaini yanıt vermedi. 1-60 arası taranıyor...")
        
        # 60'tan geriye veya 1'den ileriye tarayabiliriz. Genelde en yüksek sayı en günceldir.
        for i in range(65, 0, -1):
            domain = f"https://m.prectv{i}.lol"
            if self.test_domain(domain):
                self.main_url = domain
                self.log(f"Çalışan domain bulundu: {domain}")
                return
        
        self.log("UYARI: Hiçbir domain çalışmıyor olabilir. Varsayılan ile devam ediliyor.")

    def test_domain(self, url):
        """Bir domainin API'sinin çalışıp çalışmadığını test eder"""
        try:
            test_url = f"{url}/api/channel/by/filtres/0/0/0/{self.sw_key}"
            r = requests.get(test_url, headers=self.headers, timeout=5, verify=False)
            return r.status_code == 200 and isinstance(r.json(), list)
        except:
            return False

    def get_dub_sub_info(self, title, categories):
        """Başlık ve kategoriden Dublaj/Altyazı bilgisi çıkarır"""
        tag = ""
        lower_title = title.lower()
        cat_str = "".join([c['title'].lower() for c in categories]) if categories else ""

        if "dublaj" in lower_title or "tr" in lower_title or "türkçe" in cat_str:
            tag = " [TR Dublaj]"
        elif "altyazı" in lower_title or "al tyazı" in lower_title:
            tag = " [Altyazılı]"
        
        # Temiz başlık (Gereksiz parantezleri temizleyebilirsiniz isterseniz)
        return title + tag

    def process_content(self, items, content_type, category_name="Genel"):
        """Gelen JSON verisini işler ve buffer'a ekler"""
        count = 0
        for item in items:
            if 'sources' not in item: continue
            
            for source in item['sources']:
                if source.get('type') == 'm3u8' and source.get('url'):
                    title = item.get('title', 'Bilinmeyen')
                    image = item.get('image', '')
                    if image and not image.startswith('http'):
                        image = urljoin(self.main_url, image)
                    
                    # ID ve Kategori
                    tid = item.get('id', 0)
                    
                    # Entry Oluşturma
                    entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{title}" tvg-logo="{image}" group-title="{category_name}", {title}'
                    
                    # Film/Dizi ise dil etiketi ekle
                    if content_type != "live":
                        full_title = self.get_dub_sub_info(title, item.get('categories', []))
                        entry = f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{full_title}" tvg-logo="{image}" group-title="{category_name}", {full_title}'

                    entry += f'\n#EXTVLCOPT:http-user-agent={M3U_USER_AGENT}'
                    entry += f'\n#EXTVLCOPT:http-referrer={self.headers["Referer"]}'
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
        """Belirli bir kategoriyi sonuna kadar tarar (Pagination)"""
        page = start_page
        empty_streak = 0
        
        while True:
            # URL Hazırla
            url = f"{self.main_url}/{api_template.replace('SAYFA', str(page))}{self.sw_key}"
            try:
                r = requests.get(url, headers=self.headers, timeout=TIMEOUT, verify=False)
                if r.status_code != 200: break
                
                data = r.json()
                if not data or not isinstance(data, list):
                    break # Veri bitti

                count = self.process_content(data, content_type, category_name)
                
                if count == 0:
                    empty_streak += 1
                else:
                    empty_streak = 0
                
                # Eğer 3 sayfa üst üste boş gelirse dur (Güvenlik)
                if empty_streak >= 3: break
                
                page += 1
                # Çok fazla yüklenmemek için minik bekleme (opsiyonel)
                # time.sleep(0.1) 

            except Exception as e:
                self.log(f"Hata ({category_name} - Syf {page}): {e}")
                break

    def run(self):
        # 1. Ayarları Al
        if not self.fetch_github_config():
            self.log("GitHub config alınamadı, varsayılanlar kullanılıyor.")
        
        # 2. Domain Bul
        self.find_working_domain()

        # 3. Kategori Listesi (PHP kodundaki geniş liste)
        # Format: (API Yolu, Görünen İsim, Tip)
        tasks = [
            # --- CANLI TV (Genelde tek endpoint page page gider) ---
            ("api/channel/by/filtres/0/0/SAYFA/", "Canlı TV", "live"),
            
            # --- DİZİLER ---
            ("api/serie/by/filtres/0/created/SAYFA/", "Son Eklenen Diziler", "series"),
            ("api/serie/by/filtres/1/created/SAYFA/", "Aksiyon Dizileri", "series"),
            
            # --- FİLMLER (Detaylı Kategoriler) ---
            ("api/movie/by/filtres/0/created/SAYFA/", "Son Eklenen Filmler", "movies"),
            ("api/movie/by/filtres/14/created/SAYFA/", "Aile", "movies"),
            ("api/movie/by/filtres/1/created/SAYFA/", "Aksiyon", "movies"),
            ("api/movie/by/filtres/13/created/SAYFA/", "Animasyon", "movies"),
            ("api/movie/by/filtres/19/created/SAYFA/", "Belgesel", "movies"),
            ("api/movie/by/filtres/4/created/SAYFA/", "Bilim Kurgu", "movies"),
            ("api/movie/by/filtres/2/created/SAYFA/", "Dram", "movies"),
            ("api/movie/by/filtres/10/created/SAYFA/", "Fantastik", "movies"),
            ("api/movie/by/filtres/3/created/SAYFA/", "Komedi", "movies"),
            ("api/movie/by/filtres/8/created/SAYFA/", "Korku", "movies"),
            ("api/movie/by/filtres/17/created/SAYFA/", "Macera", "movies"),
            ("api/movie/by/filtres/5/created/SAYFA/", "Romantik", "movies"),
            ("api/movie/by/filtres/15/created/SAYFA/", "Suç", "movies"),
            ("api/movie/by/filtres/6/created/SAYFA/", "Gerilim", "movies"),
            ("api/movie/by/filtres/23/created/SAYFA/", "Yerli Filmler", "movies"),
        ]

        self.log("Tarama başlıyor... (Bu işlem içerik sayısına göre zaman alabilir)")

        # Paralel İşleme (Thread Pool)
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(self.scrape_category, t[0], t[1], t[2]): t 
                for t in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                task = future_to_url[future]
                try:
                    future.result()
                    self.log(f"Tamamlandı: {task[1]}")
                except Exception as exc:
                    self.log(f"Task hatası {task[1]}: {exc}")

        # 4. Dosyaları Kaydet
        self.save_file(FILE_LIVE, self.buffer_live)
        self.save_file(FILE_MOVIES, self.buffer_movies)
        self.save_file(FILE_SERIES, self.buffer_series)
        
        self.log("="*30)
        self.log(f"TOPLAM BULUNAN:")
        self.log(f"Canlı TV: {self.found_items['live']}")
        self.log(f"Filmler : {self.found_items['movies']}")
        self.log(f"Diziler : {self.found_items['series']}")
        self.log("="*30)

    def save_file(self, filename, content_list):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_list))
        self.log(f"Dosya kaydedildi: {filename}")

if __name__ == "__main__":
    # SSL Hatalarını gizle
    requests.packages.urllib3.disable_warnings()
    
    scraper = RecTVScraper()
    scraper.run()
