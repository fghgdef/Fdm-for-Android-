# مدير التنزيلات — تطبيق أندرويد (ويب + كود أصلي Kotlin)

تطبيق أندرويد حقيقي، تنزيلاته فعلية (ليست محاكاة): يدعم تقسيم الملف
لعدة أجزاء تُنزَّل بالتوازي (Range requests)، إيقاف مؤقت، استئناف من
نفس النقطة، وإشعار دائم أثناء التنزيل في الخلفية — بنفس فكرة FDM.

الواجهة مبنية بـ HTML/JS، ومحرك التنزيل الفعلي مكتوب بلغة Kotlin
ويعمل داخل خدمة Foreground Service، ومرتبطان ببعضهما عبر إضافة
Capacitor مخصّصة (`DownloadManager`).

البناء بالكامل يتم عبر **GitHub Actions** — لا تحتاج تثبيت Android
Studio على جهازك إطلاقًا.

## 1) إنشاء المستودع

1. أنشئ حسابًا على github.com إن لم يكن لديك واحد.
2. أنشئ مستودعًا جديدًا (New repository)، اسمه مثلًا `fdm-android`.
3. ارفع كل محتويات هذا المجلد إلى المستودع. أسهل طريقة من المتصفح:
   اضغط **Add file → Upload files**، واسحب كل الملفات والمجلدات
   (بما فيها `.github/` و `native-src/` و `scripts/` و `www/`) ثم
   اعمل Commit مباشرة على فرع `main`.
   - أو عبر Git من جهازك:
     ```
     git init
     git remote add origin https://github.com/USERNAME/fdm-android.git
     git add .
     git commit -m "إعداد المشروع الأولي"
     git branch -M main
     git push -u origin main
     ```

## 2) تشغيل البناء

بمجرد أن يصل الـ Push إلى فرع `main`، سيبدأ GitHub Actions تلقائيًا
(الملف `.github/workflows/build-apk.yml`). لمتابعته:

1. افتح تبويب **Actions** في صفحة المستودع.
2. ستجد تشغيلًا باسم "Build Android APK" قيد التنفيذ (دائرة صفراء).
3. انتظر حتى تتحول إلى علامة ✅ خضراء (يأخذ عادة 3–6 دقائق).

إذا أردت إعادة التشغيل يدويًا بدون Push جديد: من تبويب Actions اختر
الـ workflow ثم **Run workflow**.

## 3) تحميل ملف APK

1. داخل صفحة التشغيل الناجح (✅)، انزل لأسفل إلى قسم **Artifacts**.
2. حمّل `app-debug-apk` (ملف مضغوط يحتوي `app-debug.apk`).
3. انقله لهاتف الأندرويد، فعّل "السماح بالتثبيت من مصادر غير معروفة"
   لتطبيق الملفات/المتصفح الذي ستفتح منه الملف، ثم ثبّته.

> ملاحظة: هذا APK موقّع بتوقيع تجريبي (debug) — مناسب للتجربة والتثبيت
> المباشر على جهازك، لكن غير مخصص للنشر على متجر Google Play كما هو.

## هيكل المشروع

```
fdm-android/
├── package.json, capacitor.config.json     إعداد Capacitor
├── www/index.html                          واجهة التطبيق (HTML/JS)
├── native-src/                             الكود الأصلي (Kotlin) — يُدمج تلقائيًا
│   ├── java/com/example/fdm/
│   │   ├── DownloadTask.kt                 نموذج بيانات المهمة والأجزاء
│   │   ├── SegmentDownloader.kt            تنزيل جزء واحد عبر Range request
│   │   ├── DownloadEngine.kt               المحرك: تجزئة، تنزيل متوازٍ، إيقاف/استئناف
│   │   ├── DownloadManagerPlugin.kt        إضافة Capacitor (الجسر بين JS و Kotlin)
│   │   └── DownloadForegroundService.kt    خدمة خلفية + إشعار دائم
│   └── MainActivity.java                   يسجّل الإضافة المخصصة
├── scripts/patch-android.py                يدمج native-src داخل مشروع android/ المُولَّد
└── .github/workflows/build-apk.yml         خط بناء GitHub Actions
```

عند كل تشغيل لـ Actions: يولّد Capacitor مجلد `android/` من الصفر
(`npx cap add android`)، ثم يدمج سكربت `patch-android.py` ملفات
Kotlin والأذونات والخدمة داخله تلقائيًا، ثم يبني الـ APK. مجلد
`android/` نفسه **لا يُرفع** للمستودع (مُستثنى في `.gitignore`) لأنه
يُعاد توليده في كل مرة — هذا يبقي المستودع نظيفًا وصغيرًا.

## حدود مهمة يجب معرفتها

- **التقسيم لأجزاء متعددة يعمل فقط إذا كان الخادم يدعم Range
  requests** (أغلب خوادم الملفات المباشرة تدعمها). إن لم يدعمها
  الخادم، يتحول التطبيق تلقائيًا لتنزيل بجزء واحد.
- **الاستئناف الحقيقي** يعتمد أيضًا على دعم الخادم لنفس الميزة؛
  التطبيق يكمل من آخر بايت تم تنزيله فعليًا لكل جزء.
- روابط التنزيل المباشر فقط (مثل `.zip`, `.apk`, `.mp4`...). روابط
  صفحات تتطلب تسجيل دخول أو جلسة متصفح أو تتحقق من JavaScript (مثل
  Google Drive أو مواقع تحميل تعرض إعلانات قبل الرابط الحقيقي) غير
  مدعومة — وهذا نفس القيد الموجود في FDM الأصلي لمثل هذه الروابط.
- الملفات تُحفظ داخل مساحة التطبيق الخاصة (`Android/data/com.example.fdm/files/Downloads`)
  ولا تحتاج إذن تخزين خاص؛ إن أردت حفظها في مجلد "Downloads" العام
  المشترك يحتاج الأمر تعديلًا إضافيًا (نسخ عبر MediaStore) يمكن
  إضافته لاحقًا عند الطلب.

## تعديل اسم التطبيق / الحزمة

- اسم التطبيق: غيّر `appName` في `capacitor.config.json`.
- معرّف الحزمة (`com.example.fdm`): يتطلب تغييره في كل الملفات تحت
  `native-src/` وفي `capacitor.config.json` (`appId`) معًا، لأنه
  مرتبط بمسار حزمة الكود (package) أيضًا.
