import requests
import json
import re
from cloudscraper import CloudScraper

class RecTVUrlFetcher:
    def __init__(self):
        self.session = CloudScraper()
    
    def get_rectv_domain(self):
        try:
            response = self.session.post(
                url="https://firebaseremoteconfig.googleapis.com/v1/projects/791583031279/namespaces/firebase:fetch",
                headers={
                    "X-Goog-Api-Key": "AIzaSyBbhpzG8Ecohu9yArfCO5tF13BQLhjLahc",
                    "X-Android-Package": "com.rectv.shot",
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
                },
                json={
                    "platformVersion": "25",
                    "appInstanceId": "fSrUnUPXQOCIN37mjVhnJo",
                    "packageName": "com.rectv.shot",
                    "appVersion": "19.3",
                    "countryCode": "TR",
                    "sdkVersion": "22.0.1",
                    "appBuild": "104",
                    "firstOpenTime": "2025-12-21T20:00:00.000Z",
                    "analyticsUserProperties": {},
                    "appId": "1:791583031279:android:244c3d507ab299fcabc01a",
                    "languageCode": "tr-TR",
                    "timeZone": "Africa\/Nairobi"
                }
            )
            print(f"{response.json()}")
            domains_str = response.json().get("entries", {}).get("ab_rotating_live_tv_domains", "[]")
            domains_list = json.loads(domains_str)
            main_url = domains_list[0] if domains_list else "https://cloudlyticsapp.lol"
            base_domain = main_url
            print(f"🟢 Güncel RecTV domain alındı: {base_domain}")
            return base_domain
        except Exception as e:
            print("🔴 RecTV domain alınamadı!")
            print(f"Hata: {type(e).__name__} - {e}")
            return None
    
    def update_m3u_domains(self, m3u_file_path, new_domain):
        """
        M3U dosyasındaki TÜM domain'leri yeni domain ile değiştirir
        
        Args:
            m3u_file_path: M3U dosyasının yolu
            new_domain: Yeni domain (örn: https://cloudlyticsapp.lol)
        """
        try:
            # M3U dosyasını oku
            with open(m3u_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Tüm URL'lerdeki domain'leri bul ve değiştir
            # Regex ile https://domain.com kısmını yakala ve yeni domain ile değiştir
            updated_content = re.sub(
                r'https?://[^/]+',  # https:// veya http:// ile başlayan ve / ile biten kısım
                new_domain,          # Yeni domain
                content              # İçerik
            )
            
            # Güncellenmiş içeriği dosyaya yaz
            with open(m3u_file_path, 'w', encoding='utf-8') as file:
                file.write(updated_content)
            
            # Kaç adet değişiklik yapıldığını hesapla
            changes_count = len(re.findall(r'https?://[^/]+', content))
            
            print(f"✅ M3U dosyası güncellendi: {changes_count} adet domain değiştirildi -> {new_domain}")
            return True
                
        except Exception as e:
            print(f"❌ M3U dosyası güncellenirken hata oluştu: {type(e).__name__} - {e}")
            return False

if __name__ == "__main__":
    fetcher = RecTVUrlFetcher()
    domain = fetcher.get_rectv_domain()
    
    if domain:
        # M3U dosyasını güncelle
        fetcher.update_m3u_domains("rec.m3u", domain)