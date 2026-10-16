# D.L CloudStream Builder — Integrated Engine Edition

Mobil HTML paneli + sınırlı site analiz motoru + Kotlin provider üreticisi + GitHub Actions derleme hattı.

## Neler entegre edildi?

- Aynı alan adıyla sınırlı HTML keşfi; `robots.txt` denetimi, sayfa sınırı, DNS/IP güvenlik kontrolü ve dış alan adına yönlendirmeyi takip etmeme.
- Başlık, açıklama, OpenGraph görseli, poster, kategori benzeri bağlantılar, iframe ve açık medya URL ipuçları, JSON-LD ve WordPress işaretleri.
- Analiz raporundan çalışan bir Kotlin CloudStream sağlayıcı iskeleti üretme: ana sayfa, genel arama, detay/bölüm çıkarımı ve iframe/extractor akışı.
- CloudStream Gradle proje iskeleti, GitHub Actions CI derlemesi, `.cs3` ZIP/manifest doğrulaması ve artifact yükleme.
- Üretilen Kotlin kaynak için temel otomatik testler.

## Kurulum (telefonla)

1. ZIP'i indirip çıkart.
2. İçindeki dosyaları hedef GitHub deposunun köküne yükle; klasör yapısını koru.
3. GitHub → Settings → Actions → General kısmında gerekli workflow izinlerini aç.
4. `index.html` dosyasını tarayıcıda aç. Owner/repo/branch/workflow değerlerini kontrol et.
5. Site adresini, içerik türünü ve eklenti kimliğini gir. Yalnızca analiz etmeye yetkili olduğun kaynak için onayı işaretle.
6. “Analizi ve derlemeyi başlat” düğmesine bas. GitHub Actions çalışmasının bitmesini bekle.
7. Actions → ilgili çalışma → Artifacts bölümünden `dl-cloudstream-builder-*` paketini indir. Başarılı derlemede `.cs3` dosyası ve doğrulama raporu bulunur.

## GitHub token güvenliği

Token'ı yalnızca kendi cihazında açtığın HTML paneline gir. Panel token'ı localStorage'a yazmaz; sayfa belleğinde kullanır. Token'ı dosyaya, sohbet mesajına veya repoya ekleme. Gereken en düşük izinleri ver ve işin bitince token'ı temizle/iptal et. Güvenlik için mümkünse yalnızca workflow dispatch ve Actions okuma yetkisi olan ince kapsamlı token kullan.

## Gerçekçi sınırlar

- Genel amaçlı HTML tarayıcı her siteyi doğru anlayamaz. Site JavaScript ile içerik yüklüyorsa, giriş/captcha istiyorsa, imzalı API kullanıyorsa veya oynatıcı özel akış gerektiriyorsa rapor ve üretilen provider manuel uyarlama gerektirebilir.
- Genel provider, yaygın WordPress/HTML kalıplarını dener; siteye özel CSS seçicilerinin kusursuz olduğu varsayılmaz. Üretim öncesi analiz JSON'u kontrol et.
- Derleme başarılı olması, CloudStream'de videonun oynadığı anlamına gelmez. Oynatma, altyazı, kaynak seçimi ve farklı bölüm türleri gerçek uygulamada ayrıca test edilmelidir.
- DRM, oturum koruması veya erişim kısıtlamalarını aşmaya yönelik kod üretilmez. Yalnızca izinli ve hukuka uygun kaynaklar için kullan.
- CloudStream Gradle eklentisi ve Android/Kotlin araç zinciri sürümleri değişebilir; CI'nin ilk çalışması sürüm uyumsuzluğu gösterirse hata çıktısına göre güncelleme gerekebilir.

## Orijinal proje ve mimari referans

Bu paket, [Wiojelt/CloudStream-Builder](https://github.com/Wiojelt/CloudStream-Builder) projesinde açıklanan analiz → sağlayıcı → derleme → doğrulama yaklaşımını temel alır. Orijinal depodaki her kaynak dosyanın birebir kopyası değildir; bu pakette telefon üzerinden kullanılabilir CI/HTML entegrasyonu ve bağımsız bir genel motor bulunur. Orijinal proje MIT lisanslıdır; burada yeni oluşturulan entegrasyon dosyaları için de MIT lisans dosyası eklenmiştir.
