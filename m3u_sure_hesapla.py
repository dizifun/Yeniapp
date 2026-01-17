import requests
import subprocess
import json
import os

# Senin verdiğin M3U adresi
M3U_URL = "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/main/lists%2Fvideo%2Fsources%2Fwww-kanald-com-tr%2Farsiv-programlar%2Farkadasim-hosgeldin.m3u"

def get_duration(url):
    try:
        # ffprobe ile videonun metadata'sını okuyoruz (indirmeden)
        # Timeout 10sn: Eğer link ölü ise scriptin donmasını engeller
        command = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            url
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Hata ({url}): {e}")
        return 0

def parse_m3u(url):
    print("M3U listesi indiriliyor...")
    response = requests.get(url)
    lines = response.text.splitlines()
    
    video_list = []
    current_title = "Bilinmeyen Bölüm"
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line.startswith("#EXTINF"):
            # Başlığı #EXTINF satırından çekmeye çalışalım (virgülden sonrası)
            parts = line.split(",", 1)
            if len(parts) > 1:
                current_title = parts[1].strip()
        elif line.startswith("http"):
            # Link satırı geldiğinde işlem yap
            video_list.append({"title": current_title, "url": line})
            current_title = "Bilinmeyen Bölüm" # Sıfırla
            
    return video_list

# --- ANA İŞLEM ---
print("İşlem başlıyor...")
videolar = parse_m3u(M3U_URL)
sonuc_listesi = []

print(f"Toplam {len(videolar)} video bulundu. Süreler hesaplanıyor...")

for i, video in enumerate(videolar, 1):
    duration = get_duration(video['url'])
    
    if duration > 0:
        dakika = int(duration // 60)
        saniye = int(duration % 60)
        
        # Fake TV için gerekli format
        data = {
            "id": i,
            "title": video['title'],
            "url": video['url'],
            "duration_seconds": int(duration),  # Matematiksel hesap için
            "duration_formatted": f"{dakika}:{saniye:02d}" # Ekranda göstermek için
        }
        sonuc_listesi.append(data)
        print(f"[{i}/{len(videolar)}] {data['title']} -> {data['duration_formatted']}")
    else:
        print(f"[{i}/{len(videolar)}] {video['title']} -> SÜRE ALINAMADI (Atlanıyor)")

# JSON Çıktısı
output_file = "arkadasim_hosgeldin_sureler.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(sonuc_listesi, f, indent=4, ensure_ascii=False)

print(f"Bitti! Veriler '{output_file}' dosyasına kaydedildi.")
