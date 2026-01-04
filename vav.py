import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

# --- AYARLAR ---
OUTPUT_FILE = "vavoo.m3u"
MAX_WORKERS = 10 

# --- 1. AKILLI SIRALAMA MANTIĞI ---
def get_sort_key(channel_item):
    """
    Sıralama Anahtarı (Tuple döndürür):
    (Grup Önceliği, İçerik Önceliği, Kanal Adı)
    
    Küçük sayılar her zaman daha üstte yer alır.
    """
    name = channel_item['name'].lower()
    group = channel_item['group'] # Grup ismini tam olarak alıyoruz
    
    # --- AŞAMA 1: Grup Önceliği ---
    # Eğer grup tam olarak "Turkey ➾ Sports" ise en tepeye (0).
    # Değilse (1).
    if "Turkey ➾ Sports" in group:
        p_group = 0
    else:
        p_group = 1
        
    # --- AŞAMA 2: İçerik Önceliği (Sizin Mantığınız) ---
    is_bein_spor = "bein" in name and "spor" in name
    is_spor = "spor" in name or "sport" in name
    
    if is_bein_spor:
        p_content = 0
    elif is_spor:
        p_content = 1
    else:
        p_content = 2
        
    # Tuple döndür: (Grup, İçerik, İsim)
    # Bu sayede önce "Turkey Sports" grubu, 
    # SONRA o grup içindeki Bein'ler,
    # SONRA o grup içindeki diğer sporlar sıralanır.
    # Ardından diğer gruplara geçilir.
    return (p_group, p_content, name)

# --- 2. VAVOO API İMZALARI (utils.py mantığı) ---
def get_auth_signature():
    headers = {
        "user-agent": "okhttp/4.11.0",
        "accept": "application/json",
        "content-type": "application/json; charset=utf-8",
        "accept-encoding": "gzip"
    }
    payload = {
        "token": "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g",
        "reason": "app-blur", "locale": "de", "theme": "dark",
        "metadata": {"device": {"type": "Handset", "brand": "google", "model": "Nexus", "name": "21081111RG", "uniqueId": "d10e5d99ab665233"}, "os": {"name": "android", "version": "7.1.2", "abis": ["arm64-v8a", "armeabi-v7a", "armeabi"], "host": "android"}, "app": {"platform": "android", "version": "3.1.20", "buildId": "289515000", "engine": "hbc85", "signatures": ["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"], "installer": "app.revanced.manager.flutter"}, "version": {"package": "tv.vavoo.app", "binary": "3.1.20", "js": "3.1.20"}},
        "appFocusTime": 0, "playerActive": False, "playDuration": 0, "devMode": False, "hasAddon": True, "castConnected": False, "package": "tv.vavoo.app", "version": "3.1.20", "process": "app", "firstAppStart": 1743962904623, "lastAppStart": 1743962904623, "ipLocation": "", "adblockEnabled": True, "proxy": {"supported": ["ss", "openvpn"], "engine": "ss", "ssVersion": 1, "enabled": True, "autoServer": True, "id": "pl-waw"}, "iap": {"supported": False}
    }
    try:
        response = requests.post('https://www.vavoo.tv/api/app/ping', json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("addonSig")
    except Exception as e:
        print(f"HATA: Auth Signature alınamadı: {e}")
        return None

def get_ts_signature():
    vec = {"vec": "9frjpxPjxSNilxJPCJ0XGYs6scej3dW/h/VWlnKUiLSG8IP7mfyDU7NirOlld+VtCKGj03XjetfliDMhIev7wcARo+YTU8KPFuVQP9E2DVXzY2BFo1NhE6qEmPfNDnm74eyl/7iFJ0EETm6XbYyz8IKBkAqPN/Spp3PZ2ulKg3QBSDxcVN4R5zRn7OsgLJ2CNTuWkd/h451lDCp+TtTuvnAEhcQckdsydFhTZCK5IiWrrTIC/d4qDXEd+GtOP4hPdoIuCaNzYfX3lLCwFENC6RZoTBYLrcKVVgbqyQZ7DnLqfLqvf3z0FVUWx9H21liGFpByzdnoxyFkue3NzrFtkRL37xkx9ITucepSYKzUVEfyBh+/3mtzKY26VIRkJFkpf8KVcCRNrTRQn47Wuq4gC7sSwT7eHCAydKSACcUMMdpPSvbvfOmIqeBNA83osX8FPFYUMZsjvYNEE3arbFiGsQlggBKgg1V3oN+5ni3Vjc5InHg/xv476LHDFnNdAJx448ph3DoAiJjr2g4ZTNynfSxdzA68qSuJY8UjyzgDjG0RIMv2h7DlQNjkAXv4k1BrPpfOiOqH67yIarNmkPIwrIV+W9TTV/yRyE1LEgOr4DK8uW2AUtHOPA2gn6P5sgFyi68w55MZBPepddfYTQ+E1N6R/hWnMYPt/i0xSUeMPekX47iucfpFBEv9Uh9zdGiEB+0P3LVMP+q+pbBU4o1NkKyY1V8wH1Wilr0a+q87kEnQ1LWYMMBhaP9yFseGSbYwdeLsX9uR1uPaN+u4woO2g8sw9Y5ze5XMgOVpFCZaut02I5k0U4WPyN5adQjG8sAzxsI3KsV04DEVymj224iqg2Lzz53Xz9yEy+7/85ILQpJ6llCyqpHLFyHq/kJxYPhDUF755WaHJEaFRPxUqbparNX+mCE9Xzy7Q/KTgAPiRS41FHXXv+7XSPp4cy9jli0BVnYf13Xsp28OGs/D8Nl3NgEn3/eUcMN80JRdsOrV62fnBVMBNf36+LbISdvsFAFr0xyuPGmlIETcFyxJkrGZnhHAxwzsvZ+Uwf8lffBfZFPRrNv+tgeeLpatVcHLHZGeTgWWml6tIHwWUqv2TVJeMkAEL5PPS4Gtbscau5HM+FEjtGS+KClfX1CNKvgYJl7mLDEf5ZYQv5kHaoQ6RcPaR6vUNn02zpq5/X3EPIgUKF0r/0ctmoT84B2J1BKfCbctdFY9br7JSJ6DvUxyde68jB+Il6qNcQwTFj4cNErk4x719Y42NoAnnQYC2/qfL/gAhJl8TKMvBt3Bno+va8ve8E0z8yEuMLUqe8OXLce6nCa+L5LYK1aBdb60BYbMeWk1qmG6Nk9OnYLhzDyrd9iHDd7X95OM6X5wiMVZRn5ebw4askTTc50xmrg4eic2U1w1JpSEjdH/u/hXrWKSMWAxaj34uQnMuWxPZEXoVxzGyuUbroXRfkhzpqmqqqOcypjsWPdq5BOUGL/Riwjm6yMI0x9kbO8+VoQ6RYfjAbxNriZ1cQ+AW1fqEgnRWXmjt4Z1M0ygUBi8w71bDML1YG6UHeC2cJ2CCCxSrfycKQhpSdI1QIuwd2eyIpd4LgwrMiY3xNWreAF+qobNxvE7ypKTISNrz0iYIhU0aKNlcGwYd0FXIRfKVBzSBe4MRK2pGLDNO6ytoHxvJweZ8h1XG8RWc4aB5gTnB7Tjiqym4b64lRdj1DPHJnzD4aqRixpXhzYzWVDN2kONCR5i2quYbnVFN4sSfLiKeOwKX4JdmzpYixNZXjLkG14seS6KR0Wl8Itp5IMIWFpnNokjRH76RYRZAcx0jP0V5/GfNNTi5QsEU98en0SiXHQGXnROiHpRUDXTl8FmJORjwXc0AjrEMuQ2FDJDmAIlKUSLhjbIiKw3iaqp5TVyXuz0ZMYBhnqhcwqULqtFSuIKpaW8FgF8QJfP2frADf4kKZG1bQ99MrRrb2A="}
    try:
        response = requests.post('https://www.vavoo.tv/api/box/ping2', data=vec)
        response.raise_for_status()
        return response.json()['response'].get('signed')
    except Exception as e:
        print(f"HATA: TS Signature alınamadı: {e}")
        return None

# --- 3. GRUPLAR VE KANALLAR ---
def get_turkey_groups():
    try:
        print("Gruplar çekiliyor...")
        response = requests.get("https://www2.vavoo.to/live2/index?output=json")
        data = response.json()
        groups = set()
        for channel in data:
            if "group" in channel:
                # Sadece içinde "Turkey" geçenleri al
                if "turkey" in channel["group"].lower():
                    groups.add(channel["group"])
        return sorted(list(groups))
    except Exception as e:
        print(f"HATA: Gruplar alınamadı: {e}")
        return []

def get_channels_for_group(group, auth_sig, ts_sig):
    print(f" Taranıyor: {group}")
    headers = {
        "user-agent": "okhttp/4.11.0",
        "accept": "application/json",
        "content-type": "application/json; charset=utf-8",
        "mediahubmx-signature": auth_sig
    }
    
    channels = []
    cursor = 0
    
    while cursor is not None:
        try:
            payload = {
                "language": "de", "region": "AT", "catalogId": "iptv", "id": "iptv", "adult": False, "search": "", "sort": "name",
                "filter": {"group": group}, "cursor": cursor, "clientVersion": "3.0.2"
            }
            res = requests.post("https://vavoo.to/mediahubmx-catalog.json", json=payload, headers=headers)
            if res.status_code != 200: break
                
            data = res.json()
            items = data.get("items", [])
            
            for item in items:
                name = item["name"]
                raw_url = item["url"]
                
                try:
                    modified_base = raw_url.replace("vavoo-iptv", "live2")
                    if len(modified_base) > 12: base_url = modified_base[:-12]
                    else: base_url = modified_base 

                    final_url = f"{base_url}.ts?n=1&b=5&vavoo_auth={ts_sig}"
                    
                    # Kanalı sözlük olarak ekle
                    channels.append({
                        "name": name,
                        "group": group, # Grup ismi sıralama için önemli
                        "url": final_url
                    })
                except: continue

            cursor = data.get("nextCursor")
        except Exception as e:
            print(f"HATA ({group}): {e}")
            break
            
    return channels

# --- 4. ANA İŞLEM ---
def main():
    print("--- Vavoo Turkey Akıllı Sıralayıcı ---")
    
    auth_sig = get_auth_signature()
    ts_sig = get_ts_signature()
    
    if not auth_sig or not ts_sig:
        print("İmza alınamadı.")
        return

    turkey_groups = get_turkey_groups()
    if not turkey_groups:
        print("'Turkey' grubu bulunamadı.")
        return

    print(f"'Turkey' içeren {len(turkey_groups)} grup bulundu. Kanallar taranıyor...")

    all_channels = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(get_channels_for_group, group, auth_sig, ts_sig) for group in turkey_groups]
        for future in futures:
            result = future.result()
            if result:
                all_channels.extend(result)

    print(f"\nToplam {len(all_channels)} kanal bulundu. Sıralama uygulanıyor...")

    # --- SIRALAMA ---
    # get_sort_key fonksiyonuna göre listeyi sırala
    all_channels.sort(key=get_sort_key)

    # --- M3U YAZMA ---
    print(f"Dosya yazılıyor: {OUTPUT_FILE}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in all_channels:
            name = ch["name"].replace(",", " ").strip()
            url = ch["url"]
            
            # Hepsi Vavoo TV başlığı altında olsun
            f.write(f'#EXTINF:-1 group-title="Vavoo TV",{name}\n')
            f.write(f'#EXTVLCOPT:http-user-agent=VAVOO/2.6\n')
            f.write(f'#EXTVLCOPT:http-referrer=https://vavoo.tv\n')
            f.write(f"{url}\n")

    print(f"Tamamlandı! Listeniz hazır: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
