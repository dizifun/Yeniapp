# Birleştirilecek dosya adları
#goals = 'goals.m3u'
inattv = 'inattv.m3u'
selcuk = 'selcuk.m3u'
andro = 'androtv.m3u'
tabii = 'tabii.m3u'
yeni = 'yeni.m3u'
vavoo = 'vavoo.m3u'
rec = 'rec.m3u'
rec2 = 'rec2.m3u'
cikis_dosyasi = 'karisik.m3u'

# M3U dosyalarının içeriğini oku
def oku_m3u(dosya_adi):
    with open(dosya_adi, 'r', encoding='utf-8') as f:
        return [satir.strip() for satir in f if satir.strip()]

# İçerikleri oku
inattv_icerik = oku_m3u(inattv)
selcuk_icerik = oku_m3u(selcuk)
andro_icerik = oku_m3u(andro)
tabii_icerik = oku_m3u(tabii)
yeni_icerik = oku_m3u(yeni)
vavoo_icerik = oku_m3u(vavoo)
rec_icerik = oku_m3u(rec)
rec2_icerik = oku_m3u(rec2)

# Birleştir
birlesik_icerik = rec_icerik + rec2_icerik + inattv_icerik + selcuk_icerik + andro_icerik + tabii_icerik + yeni_icerik

# Yeni dosyaya yaz
with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    for satir in birlesik_icerik:
        f.write(satir + '\n')

print(f"{cikis_dosyasi} dosyası başarıyla oluşturuldu.")
