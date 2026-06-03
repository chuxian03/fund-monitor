"""
数据获取模块 V2 - 实时估值 + 历史净值 + 资金流向 + 指数行情
"""

import json, re, time, requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://fund.eastmoney.com/",
}

INDEX_MAP = {"上证指数": "1.000001", "深证成指": "0.399001", "创业板指": "0.399006", "沪深300": "1.000300", "科创50": "1.000688"}

# ==== P0: Session 复用 ====
_session_eastmoney = None
_session_fundgz = None

def _get_session_eastmoney():
    global _session_eastmoney
    if _session_eastmoney is None:
        _session_eastmoney = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=Retry(total=2, backoff_factor=0.3))
        _session_eastmoney.mount("https://", adapter)
        _session_eastmoney.mount("http://", adapter)
    return _session_eastmoney

def _get_session_fundgz():
    global _session_fundgz
    if _session_fundgz is None:
        _session_fundgz = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=Retry(total=2, backoff_factor=0.3))
        _session_fundgz.mount("https://", adapter)
        _session_fundgz.mount("http://", adapter)
    return _session_fundgz

def _get(url, retry=3):
    if "fundgz.1234567" in url:
        session = _get_session_fundgz()
    else:
        session = _get_session_eastmoney()
    for attempt in range(retry):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retry - 1:
                raise
            time.sleep(0.5 * (attempt + 1))

# ==== P0: 全局线程池 ====
_GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=10)

def _concurrent_fetch(items, fetch_func, desc="", timeout=20):
    if not items:
        return {}
    results = {}
    futures = {_GLOBAL_EXECUTOR.submit(fetch_func, item): item for item in items}
    for future in as_completed(futures, timeout=timeout):
        try:
            key, data = future.result()
            if data:
                results[key] = data
        except Exception:
            pass
    return results

# ==== P0: 内存缓存层 ====
_estimate_cache = {}  # {code: (timestamp, data)}
_ESTIMATE_CACHE_TTL = 30

def _get_cached_estimate(code):
    entry = _estimate_cache.get(code)
    if entry:
        ts, data = entry
        if time.time() - ts < _ESTIMATE_CACHE_TTL:
            return data
    return None

def _set_cached_estimate(code, data):
    _estimate_cache[code] = (time.time(), data)


def fetch_indices():
    """获取五大指数实时行情"""
    secids = ",".join(INDEX_MAP.values())
    url = (f"http://push2.eastmoney.com/api/qt/ulist.np/get?"
           f"fltt=2&invt=2&fields=f2,f3,f4,f12,f14"
           f"&secids={secids}&ut=b2884a393a59ad64002292a3e90d46a5")
    try:
        data = _get(url).json()
        result = {}
        for item in data.get("data", {}).get("diff", []):
            result[item["f14"]] = {
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "change_val": item.get("f4", 0),
            }
        return result
    except Exception as e:
        print(f"  [WARN] 指数行情获取失败: {e}")
        return {}


def fetch_market_flow():
    """大盘资金流向（上证）"""
    url = ("http://push2.eastmoney.com/api/qt/stock/fflow/kline/get?"
           "lmt=0&klt=1&secid=1.000001"
           "&fields1=f1,f2,f3,f7"
           "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
           "&ut=b2884a393a59ad64002292a3e90d46a5")
    try:
        data = _get(url).json()
        klines = data.get("data", {}).get("klines", [])
        if klines:
            p = klines[-1].split(",")
            return {"date": p[0], "main_net": float(p[1]) / 1e8, "small_net": float(p[2]) / 1e8,
                    "mid_net": float(p[3]) / 1e8, "large_net": float(p[4]) / 1e8, "super_large_net": float(p[5]) / 1e8}
    except Exception as e:
        print(f"  [WARN] 大盘资金流获取失败: {e}")
    return None


def fetch_sector_flows():
    """行业板块资金流向 Top30"""
    url = ("http://push2.eastmoney.com/api/qt/clist/get?"
           "pn=1&pz=30&po=1&np=1&fltt=2&invt=2"
           "&fields=f12,f14,f62,f66,f69,f184"
           "&fid=f62&fs=m:90+t:2"
           "&ut=b2884a393a59ad64002292a3e90d46a5")
    try:
        text = _get(url).text
        if text.startswith("jQuery"):
            text = re.search(r"\((.*)\)", text, re.DOTALL).group(1)
        data = json.loads(text)
        results = []
        for item in data.get("data", {}).get("diff", []):
            results.append({
                "name": item["f14"], "code": item.get("f12", ""),
                "main_net": item.get("f62", 0) / 1e8,
                "super_large_net": item.get("f66", 0) / 1e8,
                "change_pct": item.get("f69", 0),
                "main_ratio": item.get("f184", 0),
            })
        return results
    except Exception as e:
        print(f"  [WARN] 板块资金流获取失败: {e}")
    return []


def fetch_fund_names(codes):
    """从本地 SQLite 数据库获取基金名称"""
    return db.get_names_by_codes(codes)


def _fetch_one_estimate(code):
    # 先查缓存
    cached = _get_cached_estimate(code)
    if cached is not None:
        return (code, cached)
    try:
        text = _get(f"http://fundgz.1234567.com.cn/js/{code}.js").text
        m = re.search(r"jsonpgz\((.+)\)", text)
        if m:
            d = json.loads(m.group(1))
            data = {
                "name": d.get("name", ""),
                "nav": d.get("dwjz", ""),
                "estimate_nav": d.get("gsz", ""),
                "estimate_change": d.get("gszzl", ""),
                "nav_date": d.get("jzrq", ""),
                "update_time": d.get("gztime", ""),
            }
            _set_cached_estimate(code, data)
            return (code, data)
    except:
        pass
    return (code, None)


def fetch_realtime_estimates(codes):
    return _concurrent_fetch(codes, _fetch_one_estimate, timeout=20)


def _fetch_one_history(code, days=60):
    try:
        url = f"http://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize={days}"
        data = _get(url).json()
        records = []
        for item in data.get("Data", {}).get("LSJZList", []):
            records.append({
                "date": item["FSRQ"],
                "nav": float(item["DWJZ"]),
                "change": item.get("JZZZL", "0"),
            })
        if records:
            records.reverse()
        return (code, records)
    except:
        pass
    return (code, None)


def fetch_history(codes, days=60):
    """批量并发获取历史净值"""
    def fetcher(code):
        return _fetch_one_history(code, days)
    return _concurrent_fetch(codes, fetcher, timeout=20)


def fetch_index_pe(index_code="000300"):
    """获取指数PE历史（用于估值分位判断）"""
    url = (f"http://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid=1.{index_code}&fields1=f1,f2,f3,f4,f5,f6"
           f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
           f"&klt=101&fqt=1&end=20500101&lmt=1500"
           f"&ut=b2884a393a59ad64002292a3e90d46a5")
    try:
        data = _get(url).json()
        klines = data.get("data", {}).get("klines", [])
        if klines:
            latest = klines[-1].split(",")
            return float(latest[2])
    except:
        pass
    return None


def fetch_fund_history_range(code, days_back=66):
    """获取基金历史净值（支持最长约1年，F10DataApi.aspx 接口）
    返回: [{date, nav, change}, ...] 按日期升序
    """
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=int(days_back * 1.6 + 10))).strftime("%Y-%m-%d")

    all_records = []
    page = 1
    while page <= 10:
        url = (f"http://fund.eastmoney.com/f10/F10DataApi.aspx?"
               f"type=lsjz&code={code}&page={page}&sdate={start_date}&edate={end_date}&per=49")
        try:
            text = _get(url).text
            m = re.search(r'content:"(.*?)",records:', text)
            if not m:
                break
            html = m.group(1).replace('\\"', '"')
            rows = re.findall(
                r'<tr>\s*<td>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
                html
            )
            if not rows:
                break
            for r in rows:
                try:
                    all_records.append({
                        "date": r[0].strip(),
                        "nav": float(r[1].strip()),
                        "change": r[3].strip().replace("%", ""),
                    })
                except (ValueError, IndexError):
                    pass
            if len(rows) < 49:
                break
            page += 1
        except Exception:
            break

    all_records.reverse()  # 最早日期在前
    if len(all_records) > days_back:
        return all_records[-days_back:]
    return all_records