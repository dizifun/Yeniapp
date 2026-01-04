import requests
import json
import re
import os

# --- AYARLAR ---
URLS = [
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/Pixelsports.m3u8",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/justintv_proxy_kanallar.m3u8",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/istplay_streams.m3u",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/androiptv.m3u8",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/Roxiestreams.m3u",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/StreamedSU.m3u8"
]

# Kategori Eşleştirme Haritası (Senin istediğin mantık)
CATEGORY_MAPPING = {
    # Basketbol Birleştirmeleri
    "NBA": "Basketbol",
    "EUROLEAGUE": "Basketbol",
    "BASKETBOL": "Basketbol",
    "BASKET": "Basketbol",
    
    # Futbol Birleştirmeleri
    "GLOBAL FUTBOL": "Futbol",
    "FOOTBALL": "Futbol",
    "SOCCER": "Futbol",
    "PREMIER LEAGUE": "Futbol",
    "LA LIGA": "Futbol",
    "BUNDESLIGA": "Futbol",
    "SUPER LIG": "Futbol",
    "UEFA": "Futbol",
    
    # Amerikan Futbolu
    "NFL": "Amerikan Futbolu",
    "NFL ACTIONS": "Amerikan Futbolu",
    "AMERICAN FOOTBALL": "Amerikan Futbolu",
    
    # Dövüş Sporları
    "UFC": "Dövüş Sporları",
    "BOXING": "Dövüş Sporları",
    "MMA": "Dövüş Sporları",
    "WWE": "Dövüş Sporları",
    
    # Motor Sporları
    "F1": "Motor Sporları",
    "FORMULA 1": "Motor Sporları",
    "MOTOGP": "Motor Sporları"
}

OUTPUT_FILE = "spor_listesi.json"

def clean_name(name):
    """
    Kanal ismindeki [TR], (HD), 1080p gibi fazlalıkları temizler.
    Eşleştirme başarısını artırır.
    """
    # Köşeli ve normal parantez içindekileri sil (Örn: [TR] veya (HD))
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    # Çözünürlük ve bitrate bilgilerini sil
    name = re.sub(r'\b(HD|FHD|SD|4K|HEVC|1080p|720p)\b', '', name, flags=re.IGNORECASE)
    # Gereksiz karakterleri ve boşlukları temizle
    name = name.replace('|', '').replace('-', ' ').strip()
    # Çift boşlukları teke indir
    name = re.sub(' +', ' ', name)
    return name

def get_clean_category(group_title):
    """
    M3U'dan gelen karışık grup ismini senin istediğin ana kategoriye çevirir.
    """
    if not group_title:
        return "Diğer Sporlar"
    
    upper_title = group_title.upper()
    
    # Haritadaki anahtar kelimeleri kontrol et
    for key, value in CATEGORY_MAPPING.items():
        if key in upper_title:
            return value
            
    # Eğer haritada yoksa olduğu gibi ama baş harfi büyük döndür
    return group_title.title()

def parse_m3u(url):
    print(f"İndiriliyor: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text.splitlines()
    except Exception as e:
        print(f"HATA - Link indirilemedi: {url} | {e}")
        return []

    channels = []
    current_channel = {}
    
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            # Metadata ayıklama
            # Logo bulma
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = logo_match.group(1) if logo_match else ""
            
            # Grup (Kategori) bulma
            group_match = re.search(r'group-title="([^"]+)"', line)
            raw_group = group_match.group(1) if group_match else "Genel"
            
            # Kanal Adı bulma (Virgülden sonrası)
            name_part = line.split(",")[-1].strip()
            
            current_channel = {
                "raw_name": name_part,
                "clean_name": clean_name(name_part),
                "group": get_clean_category(raw_group), # Kategoriyi sadeleştir
                "logo": logo
            }
        elif line.startswith("http"):
            if current_channel:
                current_channel["url"] = line
                channels.append(current_channel)
                current_channel = {} # Sıfırla
                
    return channels

def main():
    all_data = {} # Yapı: { "Futbol": [ {name: "FB-GS", sources: []} ] }
    
    # 1. Tüm linkleri gez ve veriyi topla
    for url in URLS:
        channels = parse_m3u(url)
        
        for ch in channels:
            cat = ch["group"]
            name = ch["clean_name"]
            
            if cat not in all_data:
                all_data[cat] = []
            
            # Bu kanalı daha önce ekledik mi? (İsim kontrolü)
            found = False
            for existing_ch in all_data[cat]:
                # Eğer temizlenmiş isimler %100 aynıysa veya biri diğerinin içindeyse
                if name.lower() == existing_ch["name"].lower() or \
                   (len(name) > 4 and name.lower() in existing_ch["name"].lower()):
                    
                    # Mevcut kanala yeni kaynak ekle
                    existing_ch["sources"].append({
                        "url": ch["url"],
                        "label": f"Kaynak {len(existing_ch['sources']) + 1}"
                    })
                    # Eğer logosu yoksa ve yenisinde varsa güncelle
                    if not existing_ch["logo"] and ch["logo"]:
                        existing_ch["logo"] = ch["logo"]
                    
                    found = True
                    break
            
            if not found:
                # Yeni kanal oluştur
                new_entry = {
                    "name": name, # Temiz isim
                    "logo": ch["logo"],
                    "sources": [
                        {
                            "url": ch["url"],
                            "label": "Kaynak 1"
                        }
                    ]
                }
                all_data[cat].append(new_entry)

    # 2. JSON'a Kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"İşlem Tamam! {OUTPUT_FILE} oluşturuldu.")

if __name__ == "__main__":
    main()
