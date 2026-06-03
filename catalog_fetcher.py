"""
全量基金目录下载器 — 从东方财富获取完整基金列表
"""
import json
import re
import requests
import urllib3
urllib3.disable_warnings()

import db

CATALOG_URL = "http://fund.eastmoney.com/js/fundcode_search.js"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://fund.eastmoney.com/",
}


def download():
    """下载全量基金列表并写入SQLite"""
    print("  正在下载全量基金目录...", flush=True)
    try:
        r = requests.get(CATALOG_URL, headers=HEADERS, timeout=30, verify=False)
        r.encoding = "utf-8"
        text = r.text
    except Exception as e:
        print(f"  [ERROR] 基金目录下载失败: {e}", flush=True)
        return

    match = re.search(r"var r = (\[.*?\]);", text, re.DOTALL)
    if not match:
        print("  [ERROR] 无法解析基金目录数据", flush=True)
        return

    try:
        raw_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"  [ERROR] JSON解析失败: {e}", flush=True)
        return

    # 字段顺序: [code, jp, name, ftype, py]
    funds = []
    for item in raw_data:
        if len(item) < 4:
            continue
        funds.append({
            "code": item[0],
            "jp": item[1],
            "name": item[2],
            "ftype": item[3],
            "company": item[4] if len(item) > 4 else "",
        })

    db.load_catalog_batch(funds)
    print(f"  成功写入 {len(funds)} 只基金到本地数据库", flush=True)


if __name__ == "__main__":
    db.init_catalog()
    download()
    print(f"  目录总数: {db.get_catalog_count()}", flush=True)