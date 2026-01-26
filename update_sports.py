import requests
import json
import re

# --- AYARLAR ---
# Buraya tüm M3U linklerini ekle
URLS = [
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/Pixelsports.m3u8",

"https://raw.githubusercontent.com/undefinedtv/undefinedtv/main/karisik.m3u",

"https://raw.githubusercontent.com/StarLIVE-TV/digitaltivi.m3u/main/mobiltv.m3u",
    "https://raw.githubusercontent.com/SuperNova-Repo/Vavuu-IPTV/refs/heads/main/Vavoo-IPTV-Turkey.m3u8",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/istplay_streams.m3u",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/androiptv.m3u8",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/Roxiestreams.m3u",
    "https://raw.githubusercontent.com/Playtvapp/Playdeneme/main/StreamedSU.m3u8"
]

OUTPUT_FILE = "spor_listesi.json"

# --- AKILLI KATEGORİ MOTORU ---
# Sol taraf: Senin uygulamasında görmek istediğin temiz isim.
# Sağ taraf: Linkin içinde arayacağımız kelimeler (Küçük harfle yaz).
CATEGORY_RULES = [
    # Önce SPOR (En önemlisi)
    ("Spor Kanalları", ["spor", "sport", "mac", "lig", "futbol", "soccer", "basket", "nba", "bein", "ssport", "tivibu", "exxen"]),
    
    # Haberler (Yabancı, Yerli fark etmez hepsini toplar)
    ("Haberler", ["haber", "news", "cnn", "trt haber", "ntv", "a haber"]),
    
    # Sinema ve Diziler (Sinema, Yabancı Sinema, Dizi vb. hepsini toplar)
    ("Film & Dizi", ["sinema", "cinema", "film", "movie", "dizi", "series", "vod", "netflix", "blutv", "action", "aksiyon", "komedi"]),
    
    # Belgesel
    ("Belgesel", ["belgesel", "docu", "animal", "history", "wild", "nat geo"]),
    
    # Çocuk
    ("Çocuk & Aile", ["cocuk", "kid", "cartoon", "disney", "anime", "cizgi"]),
    
    # Ulusal Kanallar (TR, Ulusal, Genel, Yerli vb. birleştirir)
    ("Ulusal Kanallar", ["ulusal", "genel", "yerli", "turk", "tr ", "turkiye", "atv", "kanald", "show", "star", "tv8"]),
    
    # Müzik
    ("Müzik", ["muzik", "music", "pop", "kral", "powerturk", "radio"])
]

def clean_name(name):
    """
    Kanal ismini temizler. 'TR: beIN Sports 1 HD' ile 'beIN Sports 1' i aynı yapar.
    """
    # Köşeli ve normal parantezleri sil
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    
    # Kalabalık yapan ekleri sil
    bad_words = [
        'TR:', 'TR ', 'tr:', 'tr ', '|', '-', 'HD', 'FHD', 'SD', '4K', 'HEVC', 
        '1080p', '720p', 'HQ', 'VIP', 'CANLI', 'YENI', 'GUNCEL', 'BACKUP'
    ]
    
    for word in bad_words:
        name = name.replace(word, '')
        name = name.replace(word.lower(), '')
        
    # Başta/sonda kalan boşlukları ve çift boşlukları temizle
    name = name.strip()
    name = re.sub(' +', ' ', name)
    return name

def get_smart_category(raw_group):
    """
    M3U'dan gelen karışık kategori ismini kurallarımıza göre düzenler.
    """
    if not raw_group:
        return "Diğer Kanallar"
    
    raw_lower = raw_group.lower()
    
    # Kuralları sırayla kontrol et
    for target_cat, keywords in CATEGORY_RULES:
        for keyword in keywords:
            # Eğer anahtar kelime, gelen ismin içinde geçiyorsa
            # Örn: 'yabancı sinema kanalları' içinde 'sinema' geçiyor -> Film & Dizi yap.
            if keyword in raw_lower:
                return target_cat
                
    # Eğer hiçbir kurala uymuyorsa, orijinal ismin baş harfini büyütüp döndür
    return raw_group.title()

def parse_m3u(url):
    print(f"İndiriliyor: {url}")
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        # UTF-8 hatası almamak için
        response.encoding = response.apparent_encoding
        content = response.text.splitlines()
    except Exception as e:
        print(f"HATA - Link bozuk: {url} | {e}")
        return []

    channels = []
    current_channel = {}
    
    for line in content:
        line = line.strip()
        if line.startswith("#EXTINF"):
            # Kategori bulma
            group_match = re.search(r'group-title="([^"]+)"', line)
            raw_group = group_match.group(1) if group_match else "Diğer"
            
            # Logo bulma
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = logo_match.group(1) if logo_match else ""
            
            # İsim bulma (Virgülden sonrası)
            raw_name = line.split(",")[-1].strip()
            
            # --- KRİTİK NOKTA: KATEGORİYİ BURADA DÜZELTİYORUZ ---
            final_category = get_smart_category(raw_group)
            
            current_channel = {
                "clean_name": clean_name(raw_name),
                "category": final_category,
                "logo": logo
            }
        elif line.startswith("http") or line.startswith("rtmp"):
            if current_channel:
                current_channel["url"] = line
                channels.append(current_channel)
                current_channel = {}
                
    return channels

def main():
    all_data = {} 
    
    # Tüm linkleri gez
    for url in URLS:
        channels = parse_m3u(url)
        
        for ch in channels:
            cat = ch["category"]
            name = ch["clean_name"]
            
            # İsim çok kısaysa (1-2 harf) veya boşsa atla (Çöp veri)
            if len(name) < 2:
                continue

            if cat not in all_data:
                all_data[cat] = []
            
            # --- BİRLEŞTİRME MANTIĞI ---
            # Aynı kategoride, aynı isimli kanal var mı?
            found = False
            for existing_ch in all_data[cat]:
                # İsimler aynıysa (büyük küçük harf duyarsız)
                if name.lower() == existing_ch["name"].lower():
                    # Var olan kanala yeni kaynak (source) ekle
                    existing_ch["sources"].append({
                        "url": ch["url"],
                        "label": f"Alternatif {len(existing_ch['sources']) + 1}" # Kaynak 2, Kaynak 3...
                    })
                    # Eğer eskisinde logo yoksa yenisini kullan
                    if not existing_ch["logo"] and ch["logo"]:
                        existing_ch["logo"] = ch["logo"]
                    
                    found = True
                    break
            
            if not found:
                # Yoksa yeni kanal olarak ekle
                new_entry = {
                    "name": name,
                    "logo": ch["logo"],
                    "sources": [
                        {
                            "url": ch["url"],
                            "label": "Kaynak 1"
                        }
                    ]
                }
                all_data[cat].append(new_entry)

    # Dosyayı kaydet
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"Bitti! Dosya hazır: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
