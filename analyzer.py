"""
信号分析模块 - 综合5维度买卖信号判断（纯Python实现，无numpy依赖）
"""

import math
from config import RSI_PERIOD, MA_SHORT, MA_LONG, MOMENTUM_DAYS, WEIGHTS, SIGNAL_LABELS


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0


def _max(vals):
    return max(vals) if vals else 0


def _min(vals):
    return min(vals) if vals else 0


def calc_rsi(navs, period=RSI_PERIOD):
    """RSI 计算"""
    if len(navs) < period + 1:
        return None, None
    window = navs[-period-1:]
    gains = [max(window[i] - window[i-1], 0) for i in range(1, len(window))]
    losses = [abs(min(window[i] - window[i-1], 0)) for i in range(1, len(window))]
    avg_gain = _mean(gains)
    avg_loss = _mean(losses)
    if avg_loss == 0:
        return 100.0, dev_rsi(100.0)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1), dev_rsi(rsi)


def dev_rsi(rsi_val):
    """RSI → 归一化信号分 0~100（高RSI=超买=卖出信号分低）"""
    if rsi_val is None:
        return 50
    if rsi_val <= 25:
        return 90
    elif rsi_val <= 40:
        return 70
    elif rsi_val <= 60:
        return 50
    elif rsi_val <= 75:
        return 30
    else:
        return 10


def calc_ma_signal_with_info(navs, ma_info):
    """MA金叉死叉信号 — 使用预计算的均线值"""
    ma_short = ma_info["ma_short"]
    ma_long = ma_info["ma_long"]
    prev_ma_short = ma_info["prev_ma_short"]
    prev_ma_long = ma_info["prev_ma_long"]

    if prev_ma_short <= prev_ma_long and ma_short > ma_long:
        return 85, "金叉"
    elif prev_ma_short >= prev_ma_long and ma_short < ma_long:
        return 15, "死叉"
    elif ma_short > ma_long:
        return 65, "多头排列"
    elif ma_short < ma_long:
        return 35, "空头排列"
    return 50, "震荡"


def calc_momentum_signal(navs):
    """近5日动量信号"""
    if len(navs) < MOMENTUM_DAYS + 1:
        return None
    pct = (navs[-1] - navs[-MOMENTUM_DAYS-1]) / navs[-MOMENTUM_DAYS-1] * 100
    if pct > 5:
        return 80
    elif pct > 2:
        return 65
    elif pct > -2:
        return 50
    elif pct > -5:
        return 35
    else:
        return 20


def calc_drawdown_signal(navs):
    """最大回撤信号（近期回撤越大越偏买）"""
    if len(navs) < 20:
        return None
    peak = _max(navs)
    trough = _min(navs[-20:])
    dd = (peak - trough) / peak * 100
    if dd > 15:
        return 75
    elif dd > 10:
        return 65
    elif dd > 5:
        return 50
    elif dd > 2:
        return 35
    else:
        return 30


def calc_volume_trend_signal(fund_code, sector_flows):
    """资金流向信号：基于板块资金流入/流出"""
    if not sector_flows:
        return 50

    # 尝试从板块资金流中找到匹配的板块
    from config import FUND_CATALOG
    fund_category = ""
    for cat, info in FUND_CATALOG.items():
        if fund_code in info.get("codes", []):
            fund_category = cat
            break

    if not fund_category:
        return 50

    # 匹配板块资金流
    for sector in sector_flows:
        sname = sector.get("name", "")
        if fund_category in sname or sname in fund_category:
            inflow = float(sector.get("main_net", 0) or 0)
            if inflow > 5:
                return 75
            elif inflow > 1:
                return 65
            elif inflow > 0:
                return 55
            elif inflow < -5:
                return 25
            elif inflow < -1:
                return 35
            elif inflow < 0:
                return 45
            return 50

    return 50


def compute_signal(nav_history, fund_code="", sector_flows=None):
    """综合计算买入/卖出信号"""
    if not nav_history or len(nav_history) < MA_LONG:
        return {"signal": "hold", "score": None, "details": {}}

    navs = [r["nav"] for r in nav_history]

    # 预计算均线（一次计算，多处复用）
    if len(navs) >= MA_LONG + 1:
        ma_short = _mean(navs[-MA_SHORT:])
        ma_long = _mean(navs[-MA_LONG:])
        prev_closes = navs[:-1]
        prev_ma_short = _mean(prev_closes[-MA_SHORT:]) if len(prev_closes) >= MA_SHORT else ma_short
        prev_ma_long = _mean(prev_closes[-MA_LONG:]) if len(prev_closes) >= MA_LONG else ma_long
    else:
        ma_short = _mean(navs[-MA_SHORT:]) if len(navs) >= MA_SHORT else 0
        ma_long = _mean(navs)
        prev_ma_short = ma_short
        prev_ma_long = ma_long

    ma_info = {
        "ma_short": ma_short,
        "ma_long": ma_long,
        "prev_ma_short": prev_ma_short,
        "prev_ma_long": prev_ma_long,
    }

    rsi_val, rsi_score = calc_rsi(navs)
    ma_score, ma_status = calc_ma_signal_with_info(navs, ma_info)
    mom_score = calc_momentum_signal(navs)
    dd_score = calc_drawdown_signal(navs)
    vol_score = calc_volume_trend_signal(fund_code, sector_flows)

    details = {
        "rsi": rsi_val,
        "ma_short": round(ma_info["ma_short"], 4),
        "ma_long": round(ma_info["ma_long"], 4),
        "momentum_5d": round((navs[-1]/navs[-MOMENTUM_DAYS-1]-1)*100, 2) if len(navs) > MOMENTUM_DAYS else None,
        "drawdown": round((max(navs) - min(navs[-20:])) / max(navs) * 100, 2) if len(navs) >= 20 else None,
        "ma_status": ma_status,
        "vol_status": "",
    }

    scores = [s for s in [rsi_score, ma_score, mom_score, dd_score, vol_score] if s is not None]
    if not scores:
        return {"signal": "hold", "score": None, "details": details}

    w_keys = ["rsi", "ma_cross", "momentum", "drawdown", "volume_trend"]
    weighted = sum(s * WEIGHTS[k] for s, k in zip(scores, w_keys))
    total_w = sum(WEIGHTS[k] for s, k in zip(scores, w_keys))
    final = weighted / total_w if total_w > 0 else 50

    if final >= 80:
        signal = "strong_buy"
    elif final >= 60:
        signal = "buy"
    elif final >= 40:
        signal = "hold"
    elif final >= 20:
        signal = "sell"
    else:
        signal = "strong_sell"

    return {"signal": signal, "score": round(final, 1), "details": details}


def get_signal_summary(results):
    """按类别汇总信号"""
    buy_count = sum(1 for r in results if r["signal"] in {"strong_buy", "buy"})
    sell_count = sum(1 for r in results if r["signal"] in {"strong_sell", "sell"})
    hold_count = sum(1 for r in results if r["signal"] == "hold")
    trend = "偏多" if buy_count > sell_count else ("偏空" if sell_count > buy_count else "震荡")
    return f"{trend}（买入{buy_count} / 持有{hold_count} / 卖出{sell_count}）"