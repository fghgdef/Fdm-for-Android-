#!/usr/bin/env python3
"""
يدمج هذا السكربت ملفات الكوتلن المخصصة (محرك التنزيل) داخل مشروع
android/ الذي يُنشئه أمر `npx cap add android` تلقائيًا، ويضيف
الأذونات والخدمة والاعتمادات اللازمة.

مهم: السكربت لا يفترض مسار حزمة (package) ثابت — يكتشفه تلقائيًا
من ملف MainActivity.java الحقيقي الذي يولّده Capacitor، ويضع كل
ملفاتنا بنفس تلك الحزمة بالضبط، لتفادي أي خطأ ناتج عن افتراض خاطئ
للمسار (وهو ما كان يسبب فشل تسجيل الإضافة بصمت).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID = os.path.join(ROOT, "android")
JAVA_ROOT = os.path.join(ANDROID, "app", "src", "main", "java")
MANIFEST = os.path.join(ANDROID, "app", "src", "main", "AndroidManifest.xml")
BUILD_GRADLE = os.path.join(ANDROID, "app", "build.gradle")
ROOT_BUILD_GRADLE = os.path.join(ANDROID, "build.gradle")
NATIVE_SRC = os.path.join(ROOT, "native-src")

def fail(msg):
    print(f"[patch-android] خطأ: {msg}", file=sys.stderr)
    sys.exit(1)

def find_main_activity():
    for root, _dirs, files in os.walk(JAVA_ROOT):
        if "MainActivity.java" in files:
            return os.path.join(root, "MainActivity.java")
    fail("لم يُعثر على MainActivity.java داخل android/app/src/main/java — "
         "تأكد أن `npx cap add android` نفّذ بنجاح قبل هذا السكربت")

def read_package(java_file_path):
    with open(java_file_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*package\s+([\w.]+)\s*;", line)
            if m:
                return m.group(1)
    fail(f"تعذّر قراءة سطر package من {java_file_path}")

def step1_discover():
    main_activity_path = find_main_activity()
    pkg = read_package(main_activity_path)
    pkg_dir = os.path.dirname(main_activity_path)
    print(f"[patch-android] الحزمة الحقيقية المكتشفة: {pkg}")
    print(f"[patch-android] المسار: {pkg_dir}")
    return main_activity_path, pkg, pkg_dir

def step2_copy_kotlin_sources(pkg, pkg_dir):
    os.makedirs(pkg_dir, exist_ok=True)
    src_dir = os.path.join(NATIVE_SRC, "java", "com", "example", "fdm")
    for fname in os.listdir(src_dir):
        with open(os.path.join(src_dir, fname), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("package com.example.fdm", f"package {pkg}", 1)
        with open(os.path.join(pkg_dir, fname), "w", encoding="utf-8") as f:
            f.write(content)
    print("[patch-android] تم نسخ ملفات Kotlin الخاصة بمحرك التنزيل إلى الحزمة الصحيحة")

def step3_patch_main_activity(main_activity_path, pkg):
    src = os.path.join(NATIVE_SRC, "MainActivity.java")
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("package com.example.fdm;", f"package {pkg};", 1)
    with open(main_activity_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[patch-android] تم تحديث MainActivity الحقيقي مباشرة في: {main_activity_path}")

def step4_patch_manifest():
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

def step5_ensure_kotlin_plugin():
    kotlin_version = "1.9.24"
    with open(ROOT_BUILD_GRADLE, "r", encoding="utf-8") as f:
        root = f.read()
    if "kotlin-gradle-plugin" not in root:
        root = root.replace(
            "dependencies {",
            f'dependencies {{\n        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:{kotlin_version}"',
            1
        )
        with open(ROOT_BUILD_GRADLE, "w", encoding="utf-8") as f:
            f.write(root)

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

def step6_patch_build_gradle_deps():
    with open(BUILD_GRADLE, "r", encoding="utf-8") as f:
        content = f.read()
    deps_to_add = [
        'implementation "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1"',
        'implementation "androidx.core:core-ktx:1.13.1"',
    ]
    changed = False
    for d in deps_to_add:
        key = d.split(":")[0]
        if key not in content:
            content = content.replace("dependencies {", "dependencies {\n    " + d, 1)
            changed = True
    if changed:
        with open(BUILD_GRADLE, "w", encoding="utf-8") as f:
            f.write(content)
    print("[patch-android] تم تحديث اعتماديات build.gradle")

def step7_verify(pkg_dir):
    expected = ["DownloadTask.kt", "SegmentDownloader.kt", "DownloadEngine.kt",
                "DownloadManagerPlugin.kt", "DownloadForegroundService.kt"]
    missing = [f for f in expected if not os.path.exists(os.path.join(pkg_dir, f))]
    if missing:
        fail(f"ملفات ناقصة بعد الدمج: {missing}")
    with open(os.path.join(pkg_dir, "MainActivity.java"), "r", encoding="utf-8") as f:
        if "registerPlugin(DownloadManagerPlugin.class)" not in f.read():
            fail("MainActivity لا يحتوي على استدعاء registerPlugin — فشل الدمج")
    print("[patch-android] تحقّق نهائي ناجح: كل الملفات والتسجيل في مكانهم الصحيح ✅")

if __name__ == "__main__":
    main_activity_path, pkg, pkg_dir = step1_discover()
    step2_copy_kotlin_sources(pkg, pkg_dir)
    step3_patch_main_activity(main_activity_path, pkg)
    step4_patch_manifest()
    step5_ensure_kotlin_plugin()
    step6_patch_build_gradle_deps()
    step7_verify(pkg_dir)
    print("[patch-android] اكتمل الدمج بنجاح ✅")
