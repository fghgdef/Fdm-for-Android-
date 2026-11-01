#!/usr/bin/env python3
"""
يدمج هذا السكربت ملفات الكوتلن المخصصة (محرك التنزيل) داخل مشروع
android/ الذي يُنشئه أمر `npx cap add android` تلقائيًا، ويضيف
الأذونات والخدمة والاعتمادات اللازمة. يُستدعى من GitHub Actions
بعد كل `cap add android` / `cap sync android`.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID = os.path.join(ROOT, "android")
PKG_DIR = os.path.join(ANDROID, "app", "src", "main", "java", "com", "example", "fdm")
MANIFEST = os.path.join(ANDROID, "app", "src", "main", "AndroidManifest.xml")
BUILD_GRADLE = os.path.join(ANDROID, "app", "build.gradle")
MAIN_ACTIVITY_JAVA = os.path.join(PKG_DIR, "MainActivity.java")

def fail(msg):
    print(f"[patch-android] خطأ: {msg}", file=sys.stderr)
    sys.exit(1)

def step1_copy_kotlin_sources():
    if not os.path.isdir(ANDROID):
        fail("مجلد android/ غير موجود — شغّل `npx cap add android` أولاً")
    os.makedirs(PKG_DIR, exist_ok=True)
    src_dir = os.path.join(ROOT, "native-src", "java", "com", "example", "fdm")
    for fname in os.listdir(src_dir):
        shutil.copy(os.path.join(src_dir, fname), os.path.join(PKG_DIR, fname))
    print("[patch-android] تم نسخ ملفات Kotlin الخاصة بمحرك التنزيل")

def step2_patch_main_activity():
    src = os.path.join(ROOT, "native-src", "MainActivity.java")
    shutil.copy(src, MAIN_ACTIVITY_JAVA)
    print("[patch-android] تم تحديث MainActivity.java لتسجيل الإضافة المخصصة")

def step3_patch_manifest():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        content = f.read()

    permissions = [
        '<uses-permission android:name="android.permission.INTERNET" />',
        '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
        '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />',
        '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',
    ]
    for p in permissions:
        if p not in content:
            content = content.replace("<application", p + "\n\n    <application", 1)

    service_tag = (
        '        <service android:name=".DownloadForegroundService" '
        'android:exported="false" android:foregroundServiceType="dataSync" />\n'
    )
    if "DownloadForegroundService" not in content:
        content = content.replace("</application>", service_tag + "    </application>")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(content)
    print("[patch-android] تم تحديث AndroidManifest.xml")

ROOT_BUILD_GRADLE = os.path.join(ANDROID, "build.gradle")

def step4b_ensure_kotlin_plugin():
    # 1) تأكد من وجود classpath لإضافة Kotlin Gradle في ملف build.gradle الجذري
    with open(ROOT_BUILD_GRADLE, "r", encoding="utf-8") as f:
        root = f.read()
    kotlin_version = "1.9.24"
    if "kotlin-gradle-plugin" not in root:
        root = root.replace(
            "dependencies {",
            f'dependencies {{\n        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:{kotlin_version}"',
            1
        )
        with open(ROOT_BUILD_GRADLE, "w", encoding="utf-8") as f:
            f.write(root)

    # 2) تأكد من تطبيق plugin kotlin-android في app/build.gradle
    with open(BUILD_GRADLE, "r", encoding="utf-8") as f:
        content = f.read()
    if "kotlin-android" not in content:
        if "apply plugin: 'com.android.application'" in content:
            content = content.replace(
                "apply plugin: 'com.android.application'",
                "apply plugin: 'com.android.application'\napply plugin: 'kotlin-android'",
                1
            )
        else:
            content = "apply plugin: 'kotlin-android'\n" + content
        with open(BUILD_GRADLE, "w", encoding="utf-8") as f:
            f.write(content)
    print("[patch-android] تم التأكد من تفعيل Kotlin plugin")

def step4_patch_build_gradle():
    with open(BUILD_GRADLE, "r", encoding="utf-8") as f:
        content = f.read()

    deps_to_add = [
        'implementation "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1"',
        'implementation "androidx.core:core-ktx:1.13.1"',
    ]
    added = False
    for d in deps_to_add:
        key = d.split(":")[0]
        if key not in content:
            content = content.replace(
                "dependencies {",
                "dependencies {\n    " + d,
                1
            )
            added = True
    if added:
        with open(BUILD_GRADLE, "w", encoding="utf-8") as f:
            f.write(content)
    print("[patch-android] تم تحديث build.gradle")
    
