[app]
title = 基金监控
package.name = fundmonitor
package.domain = com.fundmonitor
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,db,html,css,js
version = 1.0
requirements = python3,kivy,requests,urllib3,certifi,charset-normalizer,idna,android,pillow
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 1
android.permissions = INTERNET
android.api = 34
android.minapi = 26
android.ndk = 25b
android.sdk = 34
android.gradle_dependencies = 
android.arch = arm64-v8a
android.allow_backup = True
android.presplash_color = #0f1923
android.splash_color = #0f1923

# 复制项目文件到 APK
source.include_patterns = main.py,config.py,data_fetcher.py,analyzer.py,dashboard.py,db.py,funds.db,catalog_fetcher.py

[buildozer]
log_level = 2
warn_on_root = 1