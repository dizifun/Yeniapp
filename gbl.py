import requests
import json
import gzip
from io import BytesIO

def get_current_token():
    """GitHub'dan güncel tokeni çeker ve formatlar."""
    token_url = "https://raw.githubusercontent.com/koprulu555/kbl-token-store/main/token.txt"
    
    try:
        print("🌍 GitHub üzerinden güncel token kontrol ediliyor...")
        response = requests.get(token_url, timeout=15)
        response.raise_for_status()
        
        # Tokenın başındaki/sonundaki boşlukları temizle
        token = response.text.strip()
        
        if not token:
            print("❌ GitHub'daki token dosyası boş!")
            return None
            
        # Eğer token dosyasında 'Bearer ' yazmıyorsa, biz ekleyelim
        # (Çoğu zaman sadece hash koyulur, bu yüzden kontrol edip eklemek garantidir)
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
            
        print("✅ Güncel token başarıyla alındı.")
        return token
        
    except Exception as e:
        print(f"❌ Token alınırken hata oluştu: {e}")
        return None

def get_canli_tv_m3u():
    # 1. Adım: Önce güncel tokeni al
    token = get_current_token()
    
    if not token:
        print("❌ Token alınamadığı için işlem durduruluyor.")
        return False

    url = "https://core-api.kablowebtv.com/api/channels"
    
    # 2. Adım: Alınan tokeni header içine yerleştir
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Referer": "https://tvheryerde.com",
        "Origin": "https://tvheryerde.com",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip",
        "Authorization": token  # DİNAMİK TOKEN BURAYA GELİYOR
    }

    params = {
        "checkip": "false"
    }

    try:
        print(f"📡 CanliTV API'den veri alınıyor...")

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        try:
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
                content = gz.read().decode('utf-8')
        except:
            content = response.content.decode('utf-8')

        data = json.loads(content)

        if not data.get('IsSucceeded') or not data.get('Data', {}).get('AllChannels'):
            print("❌ CanliTV API'den geçerli veri alınamadı! (Token süresi dolmuş veya hatalı olabilir)")
            return False

        channels = data['Data']['AllChannels']
        print(f"✅ {len(channels)} kanal bulundu")

        with open("yeni.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            kanal_sayisi = 0
            kanal_index = 1  

            for channel in channels:
                name = channel.get('Name')
                stream_data = channel.get('StreamData', {})
                hls_url = stream_data.get('HlsStreamUrl') if stream_data else None
                logo = channel.get('PrimaryLogoImageUrl', '')
                categories = channel.get('Categories', [])

                if not name or not hls_url:
                    continue

                group = categories[0].get('Name', 'Genel') if categories else 'Genel'

                if group == "Bilgilendirme":
                    continue

                tvg_id = str(kanal_index)

                f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{name}\n')
                f.write(f'{hls_url}\n')

                kanal_sayisi += 1
                kanal_index += 1  

        print(f"📺 yeni.m3u dosyası oluşturuldu! ({kanal_sayisi} kanal)")
        return True

    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

if __name__ == "__main__":
    get_canli_tv_m3u()
