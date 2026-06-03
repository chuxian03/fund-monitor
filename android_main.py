"""
Kivy 壳子 — 启动后台 HTTP 服务 + WebView 展示看板
"""
import os
import sys
import threading
import time

# 将项目根目录加入 sys.path，确保能导入 main 模块
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform

# Android WebView
if platform == "android":
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread

    WebView = autoclass("android.webkit.WebView")
    WebViewClient = autoclass("android.webkit.WebViewClient")
    WebSettings = autoclass("android.webkit.WebSettings")
    LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
    LinearLayout = autoclass("android.widget.LinearLayout")
    Gravity = autoclass("android.view.Gravity")
    Color = autoclass("android.graphics.Color")
    View = autoclass("android.view.View")


class FundMonitorApp(App):
    server_started = False

    def build(self):
        # 启动后台 HTTP 服务
        threading.Thread(target=self._start_server, daemon=True).start()

        if platform == "android":
            return self._build_android()
        else:
            # Desktop 调试：Kivy label 提示用浏览器打开
            from kivy.uix.label import Label
            self._start_server()
            return Label(
                text="服务已启动\n请在浏览器打开 http://127.0.0.1:8080",
                font_size=20,
                halign="center",
                valign="middle",
            )

    def _start_server(self):
        """在后台线程启动 HTTP 服务"""
        # 延迟一下，确保 App 已完全初始化
        time.sleep(0.5)
        try:
            import main
            main.run_serve(port=8080)
        except Exception as e:
            print(f"[Kivy] 服务启动失败: {e}", flush=True)

    @run_on_ui_thread
    def _build_android(self):
        """构建 Android WebView 界面"""
        from android import mActivity

        layout = LinearLayout(mActivity)
        layout.setOrientation(LinearLayout.VERTICAL)
        layout.setGravity(Gravity.CENTER)
        layout.setBackgroundColor(Color.parseColor("#0f1923"))

        webview = WebView(mActivity)
        webview.setBackgroundColor(Color.parseColor("#0f1923"))

        settings = webview.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setDomStorageEnabled(True)
        settings.setAllowFileAccess(True)
        settings.setAllowContentAccess(True)
        settings.setCacheMode(WebSettings.LOAD_DEFAULT)

        webview.setWebViewClient(WebViewClient())

        # 隐藏滚动条
        webview.setVerticalScrollBarEnabled(False)
        webview.setHorizontalScrollBarEnabled(False)

        params = LinearLayout.LayoutParams(
            LayoutParams.MATCH_PARENT,
            LayoutParams.MATCH_PARENT,
        )
        webview.setLayoutParams(params)

        layout.addView(webview)

        # 等服务器启动后加载页面
        Clock.schedule_once(lambda dt: self._load_url(webview), 2)

        mActivity.setContentView(layout)
        return None  # Kivy 不需要返回 widget，直接用 Android 原生 view

    def _load_url(self, webview):
        webview.loadUrl("http://127.0.0.1:8080")


if __name__ == "__main__":
    FundMonitorApp().run()