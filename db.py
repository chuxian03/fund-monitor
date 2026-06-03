"""
SQLite 持久层 — 基金监控数据本地持久化
"""

import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "funds.db")

_local = threading.local()

def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _local.conn


def init_db():
    """建表（幂等）"""
    c = _get_conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS watched_funds (
            code TEXT PRIMARY KEY,
            name TEXT,
            ftype TEXT,
            company TEXT,
            added_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS hidden_funds (
            code TEXT PRIMARY KEY,
            hidden_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fund_catalog (
            code TEXT PRIMARY KEY,
            name TEXT,
            ftype TEXT,
            company TEXT,
            jp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            ftype TEXT,
            amount REAL DEFAULT 0,
            buy_nav REAL DEFAULT 1.0,
            buy_date TEXT,
            buy_time TEXT DEFAULT '15:00',
            shares REAL DEFAULT 0,
            category TEXT DEFAULT 'position',
            added_at TEXT
        )
    """)
    c.commit()


# ---- Fund Catalog ----

def init_catalog():
    """建fund_catalog表（幂等）"""
    c = _get_conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS fund_catalog (
            code TEXT PRIMARY KEY,
            name TEXT,
            ftype TEXT,
            company TEXT,
            jp TEXT
        )
    """)
    c.commit()


def load_catalog_batch(funds):
    """批量INSERT OR REPLACE，funds是[{code,name,ftype,company,jp}]列表"""
    c = _get_conn()
    c.executemany(
        """INSERT OR REPLACE INTO fund_catalog (code, name, ftype, company, jp)
           VALUES (?, ?, ?, ?, ?)""",
        [(f["code"], f["name"], f["ftype"], f["company"], f["jp"]) for f in funds]
    )
    c.commit()


def search_catalog(keyword, limit=20, ftype=None):
    """模糊搜索：code或name包含keyword，可选按类型过滤"""
    c = _get_conn()
    like = f"%{keyword}%"
    if ftype:
        rows = c.execute(
            "SELECT code, name, ftype, company FROM fund_catalog WHERE (code LIKE ? OR name LIKE ?) AND ftype = ? LIMIT ?",
            (like, like, ftype, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT code, name, ftype, company FROM fund_catalog WHERE code LIKE ? OR name LIKE ? LIMIT ?",
            (like, like, limit)
        ).fetchall()
    return [{"code": r[0], "name": r[1], "ftype": r[2], "company": r[3]} for r in rows]


def get_names_by_codes(codes):
    """批量获取基金名称，返回 {code: name}"""
    if not codes:
        return {}
    try:
        conn = sqlite3.connect(DB_PATH)
        placeholders = ",".join(["?"] * len(codes))
        rows = conn.execute(
            f"SELECT code, name FROM fund_catalog WHERE code IN ({placeholders})",
            codes
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


def get_catalog_count():
    """返回目录总数"""
    c = _get_conn()
    n = c.execute("SELECT COUNT(*) FROM fund_catalog").fetchone()[0]
    return n


def get_all_catalog_codes():
    """返回全量基金目录的所有代码列表"""
    c = _get_conn()
    rows = c.execute("SELECT code FROM fund_catalog").fetchall()
    return [row[0] for row in rows]


# ---- Portfolio ----

def add_position(code, name, ftype, amount, buy_nav, buy_date, buy_time="15:00", category="position"):
    """插入持仓，自动计算shares=净申购金额/buy_nav"""
    from datetime import datetime
    net_amount = amount / 1.0015 if amount > 0 else 0  # 扣除0.15%申购费
    shares = round(net_amount / buy_nav, 4) if buy_nav > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = _get_conn()
    c.execute(
        """INSERT INTO portfolio (code, name, ftype, amount, buy_nav, buy_date, buy_time, shares, category, added_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, name, ftype, amount, buy_nav, buy_date, buy_time, shares, category, now)
    )
    c.commit()
    rowid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return rowid


def update_position(id, amount=None, buy_nav=None, buy_date=None, buy_time=None):
    """更新持仓，重算shares"""
    c = _get_conn()
    row = c.execute("SELECT amount, buy_nav, buy_date, buy_time FROM portfolio WHERE id = ?", (id,)).fetchone()
    if not row:
        return False
    cur_amount, cur_nav, cur_date, cur_time = row
    new_amount = amount if amount is not None else cur_amount
    new_nav = buy_nav if buy_nav is not None else cur_nav
    new_date = buy_date if buy_date is not None else cur_date
    new_time = buy_time if buy_time is not None else cur_time
    net_amount = new_amount / 1.0015 if new_amount > 0 else 0
    shares = round(net_amount / new_nav, 4) if new_nav > 0 else 0
    c.execute(
        """UPDATE portfolio SET amount=?, buy_nav=?, buy_date=?, buy_time=?, shares=?
           WHERE id=?""",
        (new_amount, new_nav, new_date, new_time, shares, id)
    )
    c.commit()
    return True


def remove_position(id):
    """删除持仓"""
    try:
        c = _get_conn()
        c.execute("DELETE FROM portfolio WHERE id = ?", (id,))
        c.commit()
        return True
    except Exception:
        return False


def load_positions():
    """返回所有持仓记录列表"""
    c = _get_conn()
    rows = c.execute(
        "SELECT id, code, name, ftype, amount, buy_nav, buy_date, buy_time, shares, category, added_at FROM portfolio ORDER BY id"
    ).fetchall()
    return [
        {
            "id": r[0], "code": r[1], "name": r[2], "ftype": r[3],
            "amount": r[4], "buy_nav": r[5], "buy_date": r[6], "buy_time": r[7],
            "shares": r[8], "category": r[9], "added_at": r[10],
        }
        for r in rows
    ]


def get_position_by_code(code):
    """按code查持仓"""
    c = _get_conn()
    row = c.execute(
        "SELECT id, code, name, ftype, amount, buy_nav, buy_date, buy_time, shares, category, added_at FROM portfolio WHERE code = ?",
        (code,)
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "code": row[1], "name": row[2], "ftype": row[3],
        "amount": row[4], "buy_nav": row[5], "buy_date": row[6], "buy_time": row[7],
        "shares": row[8], "category": row[9], "added_at": row[10],
    }


# ---- Watched / Hidden (existing) ----

def load_watched():
    """返回 {code: {name, ftype, company, added_at}, ...} 字典"""
    c = _get_conn()
    rows = c.execute("SELECT code, name, ftype, company, added_at FROM watched_funds").fetchall()
    result = {}
    for code, name, ftype, company, added_at in rows:
        result[code] = {
            "name": name, "ftype": ftype,
            "company": company, "added_at": added_at,
        }
    return result


def add_watched(code, name, ftype, company):
    """插入或更新，返回 bool"""
    try:
        c = _get_conn()
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            """INSERT INTO watched_funds (code, name, ftype, company, added_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
               name=excluded.name, ftype=excluded.ftype,
               company=excluded.company, added_at=excluded.added_at""",
            (code, name, ftype, company, now)
        )
        c.commit()
        return True
    except Exception:
        return False


def remove_watched(code):
    """删除，返回 bool"""
    try:
        c = _get_conn()
        c.execute("DELETE FROM watched_funds WHERE code = ?", (code,))
        c.commit()
        return True
    except Exception:
        return False


def load_hidden():
    """返回 set of codes"""
    c = _get_conn()
    rows = c.execute("SELECT code FROM hidden_funds").fetchall()
    return {row[0] for row in rows}


def add_hidden(code):
    """插入，返回 bool"""
    try:
        c = _get_conn()
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT OR IGNORE INTO hidden_funds (code, hidden_at) VALUES (?, ?)",
            (code, now)
        )
        c.commit()
        return True
    except Exception:
        return False


def remove_hidden(code):
    """删除，返回 bool"""
    try:
        c = _get_conn()
        c.execute("DELETE FROM hidden_funds WHERE code = ?", (code,))
        c.commit()
        return True
    except Exception:
        return False