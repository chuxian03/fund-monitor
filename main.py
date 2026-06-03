"""
基金每日监控 V5 — 三栏布局：行业板块 + 持仓 + 仅监控

用法:
  python main.py             生成 HTML 看板后退出
  python main.py --serve     启动本地 HTTP 服务
"""

import os, sys, json, time, traceback, threading, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from config import FUND_CATALOG, MONITORED_FUNDS
from data_fetcher import (
    fetch_indices, fetch_market_flow, fetch_sector_flows,
    fetch_realtime_estimates, fetch_history, fetch_fund_names,
    fetch_fund_history_range,
)
from analyzer import compute_signal
from dashboard import build_dashboard
import db

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==== P0: 断点续传 ====
EVAL_CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "temp", "eval_checkpoint.json")

def _load_checkpoint(mode):
    """加载断点。返回 (results, done_idx, codes) 或 (None, None, None)"""
    try:
        with open(EVAL_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            cp = json.load(f)
        if cp.get("mode") == mode:
            return cp.get("results", []), cp.get("done_idx", 0), cp.get("codes", [])
    except Exception:
        pass
    return None, None, None

def _save_checkpoint(mode, codes, done_idx, results):
    """保存断点"""
    try:
        os.makedirs(os.path.dirname(EVAL_CHECKPOINT_FILE), exist_ok=True)
        with open(EVAL_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "codes": codes, "done_idx": done_idx, "results": results}, f, ensure_ascii=False)
    except Exception:
        pass

def _clear_checkpoint():
    try:
        os.remove(EVAL_CHECKPOINT_FILE)
    except Exception:
        pass

_lock = threading.Lock()
_cached_data = None

# ---- 动态监控：用户搜索后加入的基金 ----
_searched_funds = {}      # code -> {"name","ftype","company","added_at"}
_searched_lock = threading.Lock()

# ---- 用户手动移除的目录基金（本会话隐藏） ----
_hidden_codes = set()
_hidden_lock = threading.Lock()

# ---- 全量评估状态 ----
_eval_state = {
    "running": False,
    "total": 0,
    "done": 0,
    "start_time": 0,
    "current": "",
    "error": "",
}
_eval_results = []
_eval_lock = threading.Lock()

_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://fund.eastmoney.com/",
}


def _build_code_to_cat():
    m = {}
    for cat, info in FUND_CATALOG.items():
        for code in info["codes"]:
            m[code] = cat
    return m


def _all_catalog_codes():
    seen = set()
    codes = []
    for info in FUND_CATALOG.values():
        for c in info["codes"]:
            if c not in seen:
                seen.add(c)
                codes.append(c)
    return codes


def _all_monitored_codes():
    """监控集 = 基础监控 + 用户搜索添加 - 用户手动移除"""
    base = set(MONITORED_FUNDS)
    with _searched_lock:
        extra = set(_searched_funds.keys())
    with _hidden_lock:
        hidden = _hidden_codes.copy()
    return (base | extra) - hidden


def _get_searched_snapshot():
    with _searched_lock:
        return dict(_searched_funds)


def _refresh_single_fund(code):
    """异步局部刷新：只拉取单只基金数据，合并到 _cached_data["results"]"""
    searched_info = _get_searched_snapshot()
    fund_info = searched_info.get(code, {})
    name = fund_info.get("name", "")
    ftype = fund_info.get("ftype", "")

    if not name:
        names = fetch_fund_names([code])
        name = names.get(code, "")

    estimates = fetch_realtime_estimates([code])
    history = fetch_history([code], days=60)

    est = estimates.get(code, {})
    hist = history.get(code, [])

    nav = ""
    change = 0.0
    if est:
        nav = est.get("estimate_nav", "") or est.get("nav", "")
        try:
            change = float(est.get("estimate_change", 0))
        except Exception:
            pass

    with _lock:
        sector_flows = (_cached_data or {}).get("sector_flows", [])
    sig = compute_signal(hist, fund_code=code, sector_flows=sector_flows)

    code_to_cat = _build_code_to_cat()
    cat = code_to_cat.get(code, "搜索添加")
    is_searched = code in searched_info

    result = {
        "code": code, "name": name, "category": cat,
        "nav": nav, "change": round(change, 2),
        "signal": sig["signal"], "score": sig["score"],
        "rsi": sig["details"].get("rsi"),
        "momentum": sig["details"].get("momentum_5d"),
        "drawdown": sig["details"].get("drawdown"),
        "monitored": True, "searched": is_searched,
        "ftype": ftype,
    }

    with _lock:
        if _cached_data is None:
            return False
        results = list(_cached_data.get("results", []))
        replaced = False
        for i, r in enumerate(results):
            if r["code"] == code:
                results[i] = result
                replaced = True
                break
        if not replaced:
            results.append(result)
        _cached_data["results"] = results
        _cached_data["monitored_count"] = sum(1 for r in results if r.get("monitored"))

    print(f"  [异步刷新] {code} {name} 信号:{sig['signal']} 评分:{sig['score']}", flush=True)
    return True


def _evaluate_all_funds_thread(codes, label=""):
    """后台线程：对指定基金列表分批获取数据并计算信号"""
    global _eval_state, _eval_results

    code_to_cat = _build_code_to_cat()

    # 尝试加载断点
    checkpoint_results, cp_done_idx, cp_codes = _load_checkpoint(label)
    if checkpoint_results is not None and cp_codes == codes:
        _eval_results = checkpoint_results
        start_batch_idx = cp_done_idx
        print(f"  [全量评估] 从断点恢复，已完成 {cp_done_idx} 批 ({len(_eval_results)} 只)", flush=True)
    else:
        _eval_results = []
        start_batch_idx = 0

    BATCH_SIZE = 20
    batches = [codes[i:i+BATCH_SIZE] for i in range(0, len(codes), BATCH_SIZE)]

    with _eval_lock:
        _eval_state["total"] = len(codes)
        _eval_state["done"] = start_batch_idx * BATCH_SIZE
        _eval_state["start_time"] = time.time()
        _eval_state["running"] = True
        _eval_state["error"] = ""
        _eval_state["current"] = ""

    print(f"  [全量评估] 开始评估 {len(codes)} 只基金 ({label})，分 {len(batches)} 批", flush=True)

    for batch_idx in range(start_batch_idx, len(batches)):
        batch_codes = batches[batch_idx]
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                f_est = executor.submit(fetch_realtime_estimates, batch_codes)
                f_hist = executor.submit(fetch_history, batch_codes, 30)
                estimates = f_est.result(timeout=90)
                history_map = f_hist.result(timeout=90)

            sector_flows = _cached_data.get("sector_flows", []) if _cached_data else []

            for code in batch_codes:
                est = estimates.get(code, {})
                hist = history_map.get(code, [])
                nav = ""
                change = 0.0
                if est:
                    nav = est.get("estimate_nav", "") or est.get("nav", "")
                    try:
                        change = float(est.get("estimate_change", 0))
                    except:
                        pass

                sig = compute_signal(hist, fund_code=code, sector_flows=sector_flows)
                cat = code_to_cat.get(code, "")
                name = _get_name(code)

                _eval_results.append({
                    "code": code, "name": name, "category": cat,
                    "nav": nav, "change": round(change, 2),
                    "signal": sig["signal"], "score": sig["score"],
                    "rsi": sig["details"].get("rsi"),
                    "momentum_5d": sig["details"].get("momentum_5d"),
                    "drawdown": sig["details"].get("drawdown"),
                    "ma_status": sig["details"].get("ma_status", ""),
                    "vol_status": sig["details"].get("vol_status", ""),
                    "reasons": sig.get("reasons", []),
                })

                with _eval_lock:
                    _eval_state["done"] += 1
                    _eval_state["current"] = code

            # 每批保存断点
            _save_checkpoint(label, codes, batch_idx + 1, _eval_results)

            if batch_idx < len(batches) - 1:
                time.sleep(0.3)

        except Exception as e:
            with _eval_lock:
                _eval_state["error"] = str(e)
            _save_checkpoint(label, codes, batch_idx, _eval_results)
            print(f"  [全量评估] 批次 {batch_idx+1} 出错: {e}，已保存断点", flush=True)
            break

    with _eval_lock:
        _eval_state["running"] = False
        _eval_state["current"] = ""

    # 完成后清除断点 + 定时清理内存
    if _eval_state["done"] >= len(codes):
        _clear_checkpoint()
        def _cleanup_eval_results():
            time.sleep(600)
            global _eval_results
            _eval_results = []
            print("  [全量评估] 内存已清理", flush=True)
        threading.Thread(target=_cleanup_eval_results, daemon=True).start()

    buy_count = sum(1 for r in _eval_results if r["signal"] in {"strong_buy", "buy"})
    elapsed = time.time() - _eval_state["start_time"]
    print(f"  [全量评估] 完成！{len(_eval_results)} 只，买入信号 {buy_count} 只，耗时 {elapsed:.1f}s", flush=True)


def _get_name(code):
    """优先从缓存/searched/DB获取基金名称"""
    with _lock:
        data = _cached_data
    if data:
        for r in data.get("results", []):
            if r["code"] == code:
                return r["name"]
    with _searched_lock:
        info = _searched_funds.get(code)
        if info:
            return info.get("name", "")
    names = db.search_catalog(code, limit=1)
    if names:
        return names[0].get("name", "")
    return ""


def fetch_all_data():
    t0 = time.time()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code_to_cat = _build_code_to_cat()

    all_catalog = _all_catalog_codes()
    monitor_set = _all_monitored_codes()
    searched_info = _get_searched_snapshot()

    # 所有需要出现在表中的代码 = 目录 + 搜索添加
    all_display = list(dict.fromkeys(all_catalog + list(searched_info.keys())))

    # P0: 并行化前4个HTTP调用
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_idx = executor.submit(fetch_indices)
        f_mf = executor.submit(fetch_market_flow)
        f_sf = executor.submit(fetch_sector_flows)
        f_names = executor.submit(fetch_fund_names, all_display)
        indices = f_idx.result(timeout=20)
        market_flow = f_mf.result(timeout=20)
        sector_flows = f_sf.result(timeout=20)
        names_map = f_names.result(timeout=20)

    # 仅监控子集获取实时数据
    monitored_codes = [c for c in all_display if c in monitor_set]
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_est = executor.submit(fetch_realtime_estimates, monitored_codes)
        future_hist = executor.submit(fetch_history, monitored_codes, 60)
        estimates = future_est.result(timeout=60)
        history = future_hist.result(timeout=60)

    results = []
    category_totals = {cat: 0 for cat in FUND_CATALOG}
    seen_cats = set(category_totals.keys())

    for code in all_display:
        cat = code_to_cat.get(code, "")
        name = names_map.get(code, searched_info.get(code, {}).get("name", ""))
        is_monitored = code in monitor_set
        is_searched = code in searched_info
        fund_type = searched_info.get(code, {}).get("ftype", "")

        if not cat and is_searched:
            cat = "搜索添加"

        if is_monitored:
            est = estimates.get(code, {})
            hist = history.get(code, [])
            nav = ""
            change = 0.0
            if est:
                nav = est.get("estimate_nav", "") or est.get("nav", "")
                try:
                    change = float(est.get("estimate_change", 0))
                except Exception:
                    pass
            sig = compute_signal(hist, fund_code=code, sector_flows=sector_flows)
            results.append({
                "code": code, "name": name, "category": cat,
                "nav": nav, "change": round(change, 2),
                "signal": sig["signal"], "score": sig["score"],
                "rsi": sig["details"].get("rsi"),
                "momentum": sig["details"].get("momentum_5d"),
                "drawdown": sig["details"].get("drawdown"),
                "monitored": True, "searched": is_searched,
                "ftype": fund_type,
            })
        else:
            results.append({
                "code": code, "name": name, "category": cat,
                "nav": "", "change": 0, "signal": "", "score": 0,
                "rsi": None, "momentum": None, "drawdown": None,
                "monitored": False, "searched": False,
                "ftype": fund_type,
            })

        if cat in category_totals:
            category_totals[cat] += 1
        elif cat not in seen_cats:
            category_totals[cat] = 1
            seen_cats.add(cat)

    elapsed = time.time() - t0
    mon_results = [r for r in results if r["monitored"]]
    buy_n = sum(1 for r in mon_results if r["signal"] in {"strong_buy", "buy"})
    sell_n = sum(1 for r in mon_results if r["signal"] in {"strong_sell", "sell"})
    log = (
        f"[{now}] 目录{len(all_display)}只 | "
        f"监控{len(monitored_codes)}只 | "
        f"买入{buy_n} 卖出{sell_n} | "
        f"耗时{elapsed:.1f}s"
    )

    # 构建分类精选数据
    categories_data = {}
    for cat in sorted(FUND_CATALOG.keys()):
        cat_results = [r for r in results if r.get("category") == cat and r.get("monitored")]
        cat_results.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
        categories_data[cat] = cat_results[:4]

    return {
        "update_time": now,
        "indices": indices,
        "market_flow": market_flow,
        "sector_flows": sector_flows,
        "results": results,
        "names_map": names_map,
        "monitored_count": len(monitored_codes),
        "category_totals": category_totals,
        "categories_data": categories_data,
        "log": log,
    }


def _find_in_cache(code):
    """从缓存中查找某基金的实时数据"""
    with _lock:
        data = _cached_data
    if not data:
        return None
    for r in data.get("results", []):
        if r["code"] == code:
            return r
    return None


def _build_api_data(data):
    """从 fetch_all_data 结果提取前端需要的标准格式"""
    return {
        "update_time": data["update_time"],
        "indices": data["indices"],
        "market_flow": data["market_flow"],
        "sector_flows": data["sector_flows"],
        "results": data["results"],
        "names_map": data["names_map"],
        "monitored_count": data["monitored_count"],
        "category_totals": data["category_totals"],
        "categories_data": data["categories_data"],
    }


# ---- 新闻获取 ----
_news_cache = {}  # {code: [news_items]}

def _fetch_news_background(code):
    global _news_cache
    name = ""
    with _lock:
        data = _cached_data or {}
    for r in data.get("results", []):
        if r["code"] == code:
            name = r["name"]
            break
    news = _fetch_news_via_web(code, name)
    _news_cache[code] = news

def _fetch_news_via_web(fund_code, fund_name):
    """从基金详情页抓取资讯"""
    news = []
    try:
        url = f"https://fundf10.eastmoney.com/xwgg_{fund_code}_2.html"
        r = requests.get(url, headers=_SEARCH_HEADERS, timeout=6)
        r.encoding = "utf-8"
        pattern = r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, r.text)
        seen = set()
        for href, title in matches:
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            if title_clean and len(title_clean) > 5 and title_clean not in seen:
                seen.add(title_clean)
                if not href.startswith("http"):
                    href = "https://fund.eastmoney.com" + href
                news.append({"title": title_clean, "url": href})
            if len(news) >= 5:
                break
    except Exception:
        pass

    if not news:
        try:
            url = f"https://so.eastmoney.com/news/s?keyword={fund_name}"
            r = requests.get(url, headers=_SEARCH_HEADERS, timeout=6)
            r.encoding = "utf-8"
            pattern = r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, r.text)
            seen = set()
            for href, title in matches:
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                if title_clean and not title_clean.startswith("<") and title_clean not in seen and len(title_clean) > 6:
                    seen.add(title_clean)
                    news.append({"title": title_clean, "url": href})
                if len(news) >= 5:
                    break
        except Exception:
            pass

    return news[:5]


# ---- HTTP Handler ----
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        b = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(b))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def _html(self, s):
        b = s.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(b))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        qs = parse_qs(parsed.query)

        if p in ("/", "/dashboard.html"):
            global _cached_data
            with _lock:
                data = _cached_data
            if data is None:
                self._html("<h2>数据加载中...</h2>")
                return
            self._html(build_dashboard(**data))

        elif p == "/api/data":
            with _lock:
                self._json(_cached_data or {})

        elif p == "/api/search":
            q = qs.get("q", [""])[0].strip()
            ftype = qs.get("ftype", [None])[0]
            if len(q) < 1:
                self._json({"datas": []})
                return
            items = db.search_catalog(q, limit=20, ftype=ftype)
            self._json({"datas": items})

        elif p == "/api/categories":
            with _lock:
                data = _cached_data
            if data is None:
                self._json({"categories": {}})
                return
            categories = {}
            for r in data.get("results", []):
                if not r.get("monitored"):
                    continue
                cat = r.get("category", "")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(r)
            for cat in categories:
                categories[cat].sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
                categories[cat] = categories[cat][:4]
            self._json({"categories": categories})

        elif p == "/api/portfolio":
            positions = db.load_positions()
            result = []
            for pos in positions:
                r = _find_in_cache(pos["code"])
                current_nav = None
                daily_profit = 0
                total_profit = 0
                signal = ""
                score = 0
                if r:
                    try:
                        current_nav = float(r.get("nav", 0) or 0)
                    except Exception:
                        current_nav = 0
                    daily_change = float(r.get("change", 0) or 0)
                    if pos["shares"] and current_nav:
                        daily_profit = round(pos["shares"] * daily_change / 100 * current_nav, 2)
                        total_profit = round(pos["shares"] * (current_nav - pos["buy_nav"]), 2)
                    signal = r.get("signal", "")
                    score = r.get("score", 0)
                result.append({
                    **pos,
                    "current_nav": current_nav,
                    "daily_profit": daily_profit,
                    "total_profit": total_profit,
                    "return_rate": round(total_profit / (pos["amount"] / 1.0015) * 100, 2) if pos["amount"] > 0 else 0,
                    "signal": signal,
                    "score": score,
                })
            self._json({"positions": result})

        elif p == "/api/buy-signals":
            with _lock:
                data = _cached_data
            if data is None:
                self._json({"signals": []})
                return
            signals = [
                r for r in data["results"]
                if r.get("monitored") and r["signal"] in {"strong_buy", "buy"}
            ]
            self._json({"signals": signals})

        elif p == "/api/evaluate-progress":
            with _eval_lock:
                state = dict(_eval_state)
            elapsed = time.time() - state["start_time"] if state["start_time"] > 0 else 0
            remaining = 0
            if state["done"] > 0 and state["total"] > 0:
                rate = state["done"] / max(elapsed, 0.1)
                remaining = max(0, (state["total"] - state["done"]) / rate) if rate > 0 else 0
            self._json({
                "running": state["running"],
                "total": state["total"],
                "done": state["done"],
                "current": state["current"],
                "error": state["error"],
                "elapsed": round(elapsed, 1),
                "remaining": round(remaining, 1),
            })

        elif p == "/api/evaluate-results":
            with _eval_lock:
                running = _eval_state["running"]
            if running:
                self._json({"ok": False, "error": "评估仍在进行中"}, 409)
                return
            buy_signals = [r for r in _eval_results if r["signal"] in {"strong_buy", "buy"}]
            buy_signals.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
            buy_signals = buy_signals[:100]  # 仅展示前100
            self._json({"ok": True, "total": len(_eval_results), "buy_count": len(buy_signals), "signals": buy_signals})

        elif p == "/api/fund-news":
            code = qs.get("code", [""])[0]
            if not code:
                self._json({"news": []})
                return
            # 快速路径：后台抓取 + 立即返回缓存
            threading.Thread(target=_fetch_news_background, args=(code,), daemon=True).start()
            cached_news = _news_cache.get(code, [])
            self._json({"ok": True, "news": cached_news, "pending": not bool(cached_news)})

        elif p == "/api/sector-funds":
            sector = qs.get("sector", [""])[0].strip()
            if not sector:
                self._json({"funds": []})
                return
            items = db.search_catalog(sector, limit=200)
            codes = [item["code"] for item in items]
            monitor_set = _all_monitored_codes()
            estimates = fetch_realtime_estimates([c for c in codes if c in monitor_set])
            result = []
            for item in items:
                code = item["code"]
                name = item.get("name", "")
                ftype = item.get("ftype", "")
                cat = item.get("category", "")
                monitored = code in monitor_set
                nav = ""
                change = 0.0
                if monitored:
                    est = estimates.get(code, {})
                    if est:
                        nav = est.get("estimate_nav", "") or est.get("nav", "")
                        try:
                            change = float(est.get("estimate_change", 0))
                        except Exception:
                            pass
                result.append({
                    "code": code, "name": name, "category": cat,
                    "ftype": ftype, "nav": nav,
                    "change": round(change, 2), "monitored": monitored,
                })
            result.sort(key=lambda x: x["change"], reverse=True)
            result = result[:100]
            self._json({"funds": result})

        elif p.startswith("/api/fund/"):
            code = p.split("/")[-1]
            if not code or len(code) != 6:
                self._json({"error": "invalid code"}, 400)
                return
            params = qs
            range_days = {"1m": 22, "3m": 66, "6m": 132, "1y": 250}.get(
                params.get("range", ["3m"])[0], 66
            )
            try:
                records = fetch_fund_history_range(code, range_days)
                self._json({"code": code, "records": records})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path

        cl = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(cl).decode("utf-8")) if cl else {}

        if p == "/api/refresh":
            global _cached_data
            try:
                data = fetch_all_data()
                with _lock:
                    _cached_data = data
                print(data["log"])
                self._json({
                    "ok": True,
                    "update_time": data["update_time"],
                    "log": data["log"],
                    "data": _build_api_data(data),
                })
            except Exception as e:
                traceback.print_exc()
                self._json({"ok": False, "error": str(e)}, 500)

        elif p == "/api/evaluate-all":
            mode = body.get("mode", "catalog")  # "catalog" 或 "all"
            with _eval_lock:
                if _eval_state["running"]:
                    self._json({"ok": False, "error": "评估正在进行中"}, 409)
                    return
            if mode == "all":
                codes = db.get_all_catalog_codes()
                label = "全量基金"
            else:
                codes = list(_all_catalog_codes())
                label = "目录基金"
            threading.Thread(target=_evaluate_all_funds_thread, args=(codes, label), daemon=True).start()
            self._json({"ok": True, "total": len(codes), "mode": mode, "label": label})

        elif p == "/api/batch-add-watch":
            codes = body.get("codes", [])
            if not codes or not isinstance(codes, list):
                self._json({"ok": False, "error": "invalid codes"}, 400)
                return
            added = 0
            for item in codes:
                code = item.get("code", "")
                name = item.get("name", "")
                ftype = item.get("ftype", "")
                company = item.get("company", "")
                if not code or len(code) != 6:
                    continue
                with _searched_lock:
                    _searched_funds[code] = {
                        "name": name, "ftype": ftype,
                        "company": company,
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                db.add_watched(code, name, ftype, company)
                threading.Thread(target=_refresh_single_fund, args=(code,), daemon=True).start()
                added += 1
            print(f"[批量添加] 共添加 {added} 只基金到监控", flush=True)
            self._json({"ok": True, "added": added})

        elif p == "/api/add-watch":
            code = body.get("code", "")
            name = body.get("name", "")
            ftype = body.get("ftype", "")
            company = body.get("company", "")
            category = body.get("category", "watch")
            if not code or len(code) != 6:
                self._json({"ok": False, "error": "invalid code"}, 400)
                return
            today = datetime.now().strftime("%Y-%m-%d")
            pid = None

            with _searched_lock:
                _searched_funds[code] = {
                    "name": name, "ftype": ftype,
                    "company": company,
                    "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            db.add_watched(code, name, ftype, company)

            if category == "position":
                r = _find_in_cache(code)
                latest_nav = 1.0
                try:
                    latest_nav = float(r.get("nav", 1.0) or 1.0) if r else 1.0
                except Exception:
                    latest_nav = 1.0
                if not db.get_position_by_code(code):
                    pid = db.add_position(code, name, ftype, 0, latest_nav, today, "15:00", "position")

            threading.Thread(target=_refresh_single_fund, args=(code,), daemon=True).start()
            print(f"[搜索添加] {code} {name} ({ftype}) category={category} — 共 {len(_searched_funds)} 只")
            self._json({"ok": True, "code": code, "total": len(_searched_funds), "category": category, "id": pid})

        elif p == "/api/remove-watch":
            code = body.get("code", "")
            removed_catalog = False
            removed_searched = False
            with _searched_lock:
                removed = _searched_funds.pop(code, None)
                if removed:
                    removed_searched = True
            if not removed_searched:
                with _hidden_lock:
                    _hidden_codes.add(code)
                    removed_catalog = True
            if removed_searched:
                db.remove_watched(code)
            elif removed_catalog:
                db.add_hidden(code)
            with _lock:
                if _cached_data:
                    results = _cached_data.get("results", [])
                    if removed_searched:
                        _cached_data["results"] = [r for r in results if r["code"] != code]
                    else:
                        for r in results:
                            if r["code"] == code:
                                r["monitored"] = False
                                break
                    _cached_data["monitored_count"] = sum(
                        1 for r in _cached_data["results"] if r.get("monitored")
                    )
            if removed_searched:
                print(f"[移除-搜索] {code} {removed.get('name','')}")
            elif removed_catalog:
                print(f"[移除-目录] {code} — 本会话隐藏（已持久化）")
            self._json({"ok": True, "code": code})

        elif p == "/api/portfolio/update":
            pid = body.get("id")
            if not pid:
                self._json({"ok": False, "error": "missing id"}, 400)
                return
            db.update_position(
                pid,
                amount=body.get("amount"),
                buy_nav=body.get("buy_nav"),
                buy_date=body.get("buy_date"),
                buy_time=body.get("buy_time"),
            )
            self._json({"ok": True})

        elif p == "/api/portfolio/remove":
            pid = body.get("id")
            if not pid:
                self._json({"ok": False, "error": "missing id"}, 400)
                return
            db.remove_position(pid)
            self._json({"ok": True})

        else:
            self.send_response(404)
            self.end_headers()


# ---- 启动 ----
def run_serve(port=8080):
    import urllib3
    urllib3.disable_warnings()

    global _cached_data

    def _auto_refresh_loop():
        global _cached_data, _lock
        while True:
            time.sleep(60)
            try:
                data = fetch_all_data()
                with _lock:
                    _cached_data = data
                print(f"[自动刷新] {data['update_time']}", flush=True)
            except Exception as e:
                print(f"[自动刷新失败] {e}", flush=True)

    # 初始化数据库
    db.init_db()
    db.init_catalog()

    # 加载持久化状态
    with _searched_lock:
        _searched_funds.update(db.load_watched())
    with _hidden_lock:
        _hidden_codes.update(db.load_hidden())
    print(f"  从DB加载: {len(_searched_funds)} 只搜索添加, {len(_hidden_codes)} 只隐藏", flush=True)

    # 全量基金目录
    if db.get_catalog_count() == 0:
        print("  首次启动，下载全量基金目录...", flush=True)
        import catalog_fetcher
        catalog_fetcher.download()
        print(f"  目录已就绪：{db.get_catalog_count()} 只基金", flush=True)
    else:
        print(f"  从DB加载: {db.get_catalog_count()} 只基金目录", flush=True)

    print("=" * 50)
    print("  基金实时监控 V5 — 三栏布局")
    print("=" * 50)
    print("\n  首次数据采集（约15秒）...", flush=True)
    _cached_data = fetch_all_data()
    print(_cached_data["log"], flush=True)

    print(f"\n  本地服务: http://127.0.0.1:{port}")
    print(f"  自动刷新 60s | 搜索走本地SQLite极速模糊搜索")
    print(f"  搜索后的基金可分别导入持仓或监控")
    print(f"  按 Ctrl+C 停止")
    print("=" * 50, flush=True)

    threading.Thread(target=_auto_refresh_loop, daemon=True).start()

    # 打开浏览器（Android 平台跳过）
    if not hasattr(sys, 'getandroidapilevel'):
        def _open_browser():
            import webbrowser, subprocess
            time.sleep(0.5)
            url = f"http://127.0.0.1:{port}"
            try:
                webbrowser.open(url, new=2)
            except Exception:
                try:
                    os.startfile(url)
                except Exception:
                    subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
        threading.Thread(target=_open_browser, daemon=True).start()

    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def run_once():
    db.init_db()
    db.init_catalog()
    if db.get_catalog_count() == 0:
        import catalog_fetcher
        catalog_fetcher.download()

    data = fetch_all_data()
    print(data["log"])

    html = build_dashboard(**data)
    html_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  看板: {html_path}")

    mon_results = [r for r in data["results"] if r.get("monitored")]
    for label, keys in [
        ("买入", {"strong_buy", "buy"}),
        ("卖出", {"strong_sell", "sell"}),
    ]:
        items = [r for r in mon_results if r["signal"] in keys]
        if items:
            print(f"\n  {label}信号 ({len(items)}只):")
            for r in items:
                print(f"    [{r['signal']}] {r['code']} {r['name']} 评分{r['score']}")


if __name__ == "__main__":
    try:
        is_exe = getattr(sys, 'frozen', False)
        serve_mode = ("--serve" in sys.argv) or (is_exe and "--once" not in sys.argv)

        if serve_mode:
            port = 8080
            for a in sys.argv:
                if a.startswith("--port="):
                    port = int(a.split("=", 1)[1])
            run_serve(port)
        else:
            try:
                run_once()
            except Exception:
                traceback.print_exc()
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  用户中断，服务已停止。", flush=True)
    except Exception as e:
        traceback.print_exc()
        print(f"\n  启动失败: {e}", flush=True)
        input("\n  按回车键退出...")