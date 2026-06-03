[app]
title = 基金监控
package.name = fundmonitor
package.domain = com.fundmonitor
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db,html,css,js,md,bat,txt
version = 1.0
requirements = 'python3==3.11,kivy==2.3.0,requests,urllib3,certifi,charset-normalizer,idna,android,pillow'
orientation = portrait
fullscreen = 1

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 34
android.minapi = 26
android.ndk_path = 
android.sdk_path = 
android.archs = arm64-v8a
android.allow_backup = True
android.presplash_color = #0f1923
android.splash_color = #0f1923
android.logcat_filters = *:S python:D
android.add_src = 
android.gradle_dependencies = 

p4a.branch = develop
p4a.source_dir = 

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.12.2
ios.codesign.allowed = false

[buildozer]
log_level = 2
warn_on_root = 1