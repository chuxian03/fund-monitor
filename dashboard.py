"""
HTML 看板生成模块 V5 — 三栏布局：行业板块 + 持仓 + 仅监控
"""

import json
from config import SIGNAL_LABELS

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>基金实时监控看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:#0f1923;color:#e0e0e0;min-height:100vh}

/* 顶部 */
.header{background:linear-gradient(135deg,#1a2a3a,#0f1923);padding:10px 20px;border-bottom:1px solid #2a3a4a;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.header-left h1{font-size:18px;color:#ffd700}
.header-left .meta{font-size:11px;color:#8899aa;margin-top:2px}
.header-right{display:flex;align-items:center;gap:10px}

.auto-toggle{display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;font-size:12px;color:#8899aa}
.auto-toggle .switch{position:relative;width:36px;height:20px;background:#2a3a4a;border-radius:20px;transition:.2s}
.auto-toggle .switch::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;background:#8899aa;border-radius:50%;transition:.2s}
.auto-toggle.on .switch{background:#ffd700}
.auto-toggle.on .switch::after{left:18px;background:#0f1923}
.auto-toggle.on{color:#ffd700}
.auto-interval{color:#8899aa;font-size:11px}

.refresh-btn{padding:7px 18px;border-radius:6px;background:#ffd700;color:#0f1923;border:none;font-size:13px;font-weight:700;cursor:pointer;transition:.2s;display:flex;align-items:center;gap:6px}
.refresh-btn:hover{background:#ffed4a}
.refresh-btn:disabled{opacity:.6;cursor:wait}
.refresh-btn .spinner{display:none;width:14px;height:14px;border:2px solid #0f1923;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite}
.refresh-btn.loading .spinner{display:inline-block}
.refresh-btn.loading .btn-text{display:none}
@keyframes spin{to{transform:rotate(360deg)}}

/* 指数卡片 */
.index-cards{display:flex;gap:10px;padding:10px 20px;flex-wrap:wrap}
.idx-card{flex:1;min-width:130px;background:#1a2a3a;border-radius:6px;padding:10px 14px;border:1px solid #2a3a4a}
.idx-card .label{font-size:11px;color:#8899aa}
.idx-card .value{font-size:20px;font-weight:700;margin:2px 0}
.idx-card .sub{font-size:11px}
.up{color:#ff4444}.down{color:#22bb44}.neutral{color:#ffa500}

/* ==== 主导航 Tab ==== */
.tab-nav{display:flex;gap:0;padding:0 20px;border-bottom:2px solid #2a3a4a}
.tab-btn{padding:10px 24px;background:transparent;border:none;color:#8899aa;font-size:14px;font-weight:600;cursor:pointer;position:relative;transition:.15s;border-bottom:3px solid transparent;margin-bottom:-2px}
.tab-btn:hover{color:#e0e0e0}
.tab-btn.active{color:#ffd700;border-bottom-color:#ffd700}
.tab-panel{display:none;padding:16px 20px}
.tab-panel.active{display:block}

/* ==== Tab1: 行业板块 ==== */
.sector-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.sector-card{background:#1a2a3a;border-radius:8px;padding:14px;border:1px solid #2a3a4a;transition:.15s}
.sector-card:hover{border-color:#ffd700}
.sector-card .sc-header{cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.sector-card .sc-header .sc-arrow{font-size:12px;color:#8899aa;transition:transform .2s}
.sector-card .sc-header.expanded .sc-arrow{transform:rotate(90deg)}
.sector-card .sc-name{font-size:14px;font-weight:700;color:#e0e0e0;margin-bottom:6px}
.sector-card .sc-stats{display:flex;gap:16px;font-size:12px;margin-bottom:8px}
.sector-card .sc-tag{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
.sector-card .sc-body{display:none;margin-top:10px;border-top:1px solid #2a3a4a;padding-top:8px;max-height:360px;overflow-y:auto}
.sector-card .sc-body .sc-loading{padding:12px;text-align:center;color:#8899aa;font-size:12px}
.sc-table{width:100%;border-collapse:collapse;font-size:11px}
.sc-table th{background:#0f1923;padding:5px 6px;text-align:left;font-weight:600;color:#8899aa;border-bottom:1px solid #2a3a4a;white-space:nowrap;font-size:10px;position:sticky;top:0;z-index:1}
.sc-table td{padding:4px 6px;border-bottom:1px solid #1a2a3a;white-space:nowrap}
.sc-table tr.fund-row{cursor:pointer;transition:background .1s}
.sc-table tr.fund-row:hover{background:#1f3142}
.sc-table tr.fund-row td:first-child{color:#ffd700;font-family:monospace}
.sc-tag.attention{background:rgba(255,99,71,.2);color:#ff6347}
.sc-tag.strong{background:#dc143c;color:#fff}
.sc-tag.avoid{background:rgba(34,187,68,.2);color:#22bb44}
.sc-tag.watch{background:#2a3a4a;color:#8899aa}

/* ==== Tab2: 详情分布 ==== */
.cat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.cat-card{background:#1a2a3a;border-radius:8px;border:1px solid #2a3a4a;overflow:hidden}
.cat-card-header{padding:10px 14px;background:#1f3142;font-size:14px;font-weight:700;color:#ffd700;border-bottom:1px solid #2a3a4a;display:flex;justify-content:space-between;align-items:center}
.cat-card-header .count{font-size:11px;color:#8899aa;font-weight:400}
.cat-card-body{padding:8px 0}
.cat-fund-row{display:flex;align-items:center;padding:8px 14px;cursor:pointer;transition:background .12s;border-bottom:1px solid #1a2a3a;gap:10px}
.cat-fund-row:hover{background:#1f3142}
.cat-fund-row:last-child{border-bottom:none}
.cat-fund-row .cfr-code{font-family:monospace;font-size:12px;color:#ffd700;width:60px;flex-shrink:0}
.cat-fund-row .cfr-name{flex:1;font-size:13px;color:#e0e0e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cat-fund-row .cfr-score{font-size:12px;font-weight:700;width:36px;text-align:right}
.cat-fund-row .cfr-change{font-size:12px;width:60px;text-align:right}
.cat-fund-empty{padding:20px;text-align:center;color:#556677;font-size:13px}

/* ==== Tab3: 持仓 ==== */
.portfolio-summary{display:flex;gap:16px;margin-bottom:14px;flex-wrap:wrap}
.pf-sum-card{flex:1;min-width:140px;background:#1a2a3a;border-radius:6px;padding:12px 16px;border:1px solid #2a3a4a;text-align:center}
.pf-sum-card .ps-label{font-size:11px;color:#8899aa}
.pf-sum-card .ps-value{font-size:18px;font-weight:700;margin-top:4px}
.pf-table{width:100%;border-collapse:collapse;font-size:12px}
.pf-table th{background:#1a2a3a;padding:8px 8px;text-align:left;font-weight:600;color:#8899aa;border-bottom:2px solid #2a3a4a;white-space:nowrap;font-size:11px}
.pf-table td{padding:7px 8px;border-bottom:1px solid #1a2a3a;vertical-align:middle}
.pf-table td input{background:#0f1923;border:1px solid #2a3a4a;color:#e0e0e0;padding:4px 6px;border-radius:4px;font-size:12px;width:80px}
.pf-table td input:focus{outline:none;border-color:#ffd700}
.pf-table td input.pf-date{width:95px}
.pf-table td input.pf-time{width:55px}
.pf-table td input.pf-readonly{background:transparent;border:1px solid transparent;color:#8899aa;cursor:default;width:70px}
.pf-table .pf-code{font-family:monospace;color:#ffd700}
.pf-table .pf-advice{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;white-space:nowrap}
.pf-empty{text-align:center;padding:48px 20px;color:#8899aa;font-size:14px}
.pf-empty a{color:#ffd700;text-decoration:underline;cursor:pointer}
.pf-remove-btn{background:none;border:1px solid transparent;color:#556677;cursor:pointer;font-size:14px;padding:2px 6px;border-radius:3px}
.pf-remove-btn:hover{color:#ff6347;border-color:#ff6347}
.pf-new-hint{border:1px dashed #ffd700!important;background:rgba(255,215,0,.05)!important;padding:4px 6px;width:85px!important}

/* ==== Tab4: 仅监控 ==== */
.watch-controls{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center}
.watch-controls .ctrl-btn{padding:5px 12px;border-radius:5px;background:#1a2a3a;color:#8899aa;border:1px solid #2a3a4a;cursor:pointer;font-size:12px;transition:.15s;white-space:nowrap}
.watch-controls .ctrl-btn:hover,.watch-controls .ctrl-btn.active{background:#ffd700;color:#0f1923;border-color:#ffd700}
.watch-controls .ctrl-sep{width:1px;height:20px;background:#2a3a4a;margin:0 4px}
.watch-table-wrap{overflow-x:auto}
.watch-table{width:100%;border-collapse:collapse;font-size:12px}
.watch-table th{background:#1a2a3a;padding:8px 8px;text-align:left;font-weight:600;color:#8899aa;border-bottom:2px solid #2a3a4a;cursor:pointer;white-space:nowrap;font-size:11px}
.watch-table th:hover{color:#ffd700}
.watch-table td{padding:7px 8px;border-bottom:1px solid #1a2a3a;white-space:nowrap}
.watch-table tr.fund-row{cursor:pointer;transition:background .1s}
.watch-table tr.fund-row:hover{background:#1f3142}
.watch-table tr.fund-row td:first-child{color:#ffd700;font-family:monospace}

.signal-tag{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;color:#fff}
.signal-strong_buy{background:#dc143c}.signal-buy{background:#ff6347}
.signal-hold{background:#ffa500;color:#333}.signal-sell{background:#2e8b57}
.signal-strong_sell{background:#228b22}
.score-bar{display:inline-block;width:40px;height:4px;background:#2a3a4a;border-radius:2px;vertical-align:middle;margin-left:4px;overflow:hidden}
.score-fill{height:100%;border-radius:2px}

/* 搜索 */
.search-wrap{position:relative;display:inline-block}
.search-wrap input.search-box{padding:6px 12px;border-radius:5px;border:1px solid #2a3a4a;background:#1a2a3a;color:#e0e0e0;width:220px;font-size:12px}
.search-wrap input.search-box:focus{outline:none;border-color:#ffd700}
.search-dropdown{display:none;position:absolute;top:100%;left:0;width:380px;background:#1a2a3a;border:1px solid #2a3a4a;border-radius:6px;max-height:380px;overflow-y:auto;z-index:500;margin-top:4px;box-shadow:0 6px 24px rgba(0,0,0,.6)}
.search-dropdown.show{display:block}
.sd-item{padding:8px 12px;border-bottom:1px solid #1a2a3a;display:flex;align-items:center;gap:10px;justify-content:space-between}
.sd-item:hover{background:#1f3142}
.sd-info{flex:1;min-width:0}
.sd-code{color:#ffd700;font-family:monospace;font-size:12px;margin-right:8px}
.sd-name{color:#e0e0e0;font-size:13px;font-weight:600}
.sd-meta{font-size:10px;color:#8899aa;margin-top:2px}
.sd-actions{display:flex;gap:4px;flex-shrink:0}
.sd-btn{padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid;transition:.12s;white-space:nowrap}
.sd-btn-position{color:#ffd700;border-color:#ffd700;background:transparent}
.sd-btn-position:hover{background:rgba(255,215,0,.15)}
.sd-btn-watch{color:#8899aa;border-color:#2a3a4a;background:transparent}
.sd-btn-watch:hover{background:#1f3142;border-color:#8899aa}
.sd-loading,.sd-empty{padding:16px;color:#8899aa;font-size:12px;text-align:center}

/* Toast / Modal */
.toast{position:fixed;top:16px;right:16px;background:#ffd700;color:#0f1923;padding:10px 20px;border-radius:6px;font-weight:700;z-index:10000;opacity:0;transform:translateY(-10px);transition:.25s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}

.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:9998;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal{background:#152231;border-radius:12px;border:1px solid #2a3a4a;width:90vw;max-width:860px;max-height:90vh;overflow-y:auto;box-shadow:0 8px 40px rgba(0,0,0,.5)}
.modal-header{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-bottom:1px solid #2a3a4a}
.modal-header h2{font-size:16px;color:#ffd700;margin:0}
.modal-header .close-btn{background:none;border:none;color:#8899aa;font-size:22px;cursor:pointer;padding:0 4px;line-height:1}
.modal-header .close-btn:hover{color:#e0e0e0}
.modal-body{padding:16px 20px}
.modal-info{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px}
.modal-info .item{font-size:13px;color:#8899aa}
.modal-info .item span{color:#e0e0e0;font-weight:600}
.range-tabs{display:flex;gap:6px;margin-bottom:14px}
.range-tab{padding:5px 16px;border-radius:16px;cursor:pointer;background:#1a2a3a;border:1px solid #2a3a4a;font-size:12px;color:#8899aa;transition:.15s;user-select:none}
.range-tab:hover{border-color:#ffd700;color:#ffd700}
.range-tab.active{background:#ffd700;color:#0f1923;border-color:#ffd700;font-weight:700}
#fund-chart{width:100%;height:380px}
.chart-loading,.chart-error{display:flex;justify-content:center;align-items:center;height:380px;color:#8899aa;font-size:13px}

/* 买入信号按钮 */
.buy-sig-btn{padding:7px 14px;border-radius:6px;background:transparent;color:#ff6347;border:1px solid #ff6347;font-size:12px;font-weight:600;cursor:pointer;transition:.2s;white-space:nowrap}
.buy-sig-btn:hover{background:rgba(255,99,71,.15)}
.buy-sig-btn.has-sig{animation:pulse 2s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,99,71,.4)}50%{box-shadow:0 0 0 6px rgba(255,99,71,0)}}

/* 侧边栏 */
.side-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:9990}
.side-overlay.show{display:block}
.side-panel{position:fixed;top:0;right:-440px;width:420px;height:100vh;background:#0f1923;border-left:1px solid #2a3a4a;z-index:9991;transition:right .3s ease;display:flex;flex-direction:column;box-shadow:-4px 0 30px rgba(0,0,0,.5)}
.side-panel.show{right:0}
.side-panel-header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#1a2a3a;border-bottom:1px solid #2a3a4a;flex-shrink:0}
.side-panel-header h2{font-size:16px;color:#ffd700;margin:0}
.side-panel-close{background:none;border:none;color:#8899aa;font-size:22px;cursor:pointer;padding:0 6px;line-height:1}
.side-panel-body{flex:1;overflow-y:auto;padding:12px 16px}
.side-panel-empty{text-align:center;padding:48px 16px;color:#8899aa;font-size:14px}
.sig-item{background:#1a2a3a;border-radius:8px;margin-bottom:8px;border:1px solid #2a3a4a;overflow:hidden}
.sig-item-header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;cursor:pointer}
.sig-item-header:hover{background:#1f3142}
.sig-item-body{display:none;padding:0 14px 12px;border-top:1px solid #2a3a4a}
.sig-item.expanded .sig-item-body{display:block}
.news-link{display:block;padding:4px 0;font-size:12px;color:#c0c0c0;text-decoration:none;border-bottom:1px solid #1a2a3a}
.news-link:hover{color:#ffd700}

.eval-card{background:#1a2a3a;border-radius:8px;border:1px solid #2a3a4a;margin-bottom:8px;overflow:hidden}
.eval-card-header{display:flex;align-items:center;padding:12px 16px;cursor:pointer;gap:12px;transition:.15s}
.eval-card-header:hover{background:#1f3142}
.eval-card-header .ec-code{font-family:monospace;font-size:13px;color:#ffd700;width:70px}
.eval-card-header .ec-name{font-size:14px;font-weight:600;color:#e0e0e0;flex:1}
.eval-card-header .ec-score{font-size:14px;font-weight:700;width:40px;text-align:right}
.eval-card-header .ec-change{font-size:13px;width:60px;text-align:right}
.eval-card-header .ec-arrow{color:#8899aa;font-size:12px;transition:.2s}
.eval-card.expanded .ec-arrow{transform:rotate(180deg)}
.eval-card-body{display:none;padding:0 16px 14px;border-top:1px solid #1f3142}
.eval-card.expanded .eval-card-body{display:block}
.eval-reason{padding:6px 0;font-size:12px;color:#c0c0c0;border-bottom:1px solid #1a2a3a}
.eval-reason:last-child{border-bottom:none}
.eval-reason .er-label{color:#8899aa;margin-right:8px}
.eval-reason .er-value{color:#ffd700;font-weight:600}
.eval-filter-btn{padding:4px 12px;border-radius:14px;border:1px solid #334455;background:transparent;color:#8899aa;cursor:pointer;font-size:12px;transition:.2s}
.eval-filter-btn:hover{background:#1a2a3a;color:#ccddee}
.eval-filter-active{background:#ffd700!important;color:#0f1923!important;border-color:#ffd700!important}
.eval-monitor-badge{display:none;padding:2px 8px;border-radius:10px;background:#2a6e3f;color:#90ee90;font-size:10px;margin-left:6px}
</style>
</head>
<body>

<div id="toast" class="toast"></div>

<!-- 弹窗 -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header">
      <h2 id="modalTitle">基金走势</h2>
      <button class="close-btn" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body">
      <div class="modal-info" id="modalInfo"></div>
      <div class="range-tabs" id="rangeTabs">
        <span class="range-tab active" data-range="1m">1个月</span>
        <span class="range-tab" data-range="3m">3个月</span>
        <span class="range-tab" data-range="6m">6个月</span>
        <span class="range-tab" data-range="1y">1年</span>
      </div>
      <div class="chart-loading" id="chartLoading">加载中...</div>
      <div class="chart-error" id="chartError" style="display:none">数据加载失败</div>
      <div id="fund-chart"></div>
    </div>
  </div>
</div>

<!-- 买入信号侧边栏 -->
<div class="side-overlay" id="sideOverlay" onclick="if(event.target===this)closeBuyPanel()"></div>
<div class="side-panel" id="sidePanel">
  <div class="side-panel-header">
    <div style="display:flex;align-items:center">
      <h2>买入信号</h2>
      <span style="font-size:12px;color:#8899aa;margin-left:8px" id="sigStat"></span>
    </div>
    <button class="side-panel-close" onclick="closeBuyPanel()">&times;</button>
  </div>
  <div class="side-panel-body" id="sideBody">
    <div id="sigList"></div>
  </div>
</div>

<!-- 主界面 -->
<div class="header">
  <div class="header-left">
    <h1>基金实时监控看板</h1>
    <div class="meta">数据时间: <strong id="updateTime">{{update_time}}</strong> &nbsp;|&nbsp; 来源：东方财富 &nbsp;|&nbsp; 监控<strong id="monCount">{{monitored_count}}</strong>只 / 目录<strong id="totalCount">{{total_count}}</strong>只</div>
  </div>
  <div class="header-right">
    <div class="search-wrap">
      <input type="text" class="search-box" id="search" placeholder="搜索基金代码/名称..." oninput="handleSearchInput()" autocomplete="off">
      <select id="search-filter-type" onchange="handleSearchInput()" style="padding:4px 8px;border-radius:4px;background:#1a2a3a;color:#ccddee;border:1px solid #334455;font-size:12px;margin-left:6px">
        <option value="">全部类型</option>
        <option value="ETF">ETF</option>
        <option value="LOF">LOF</option>
        <option value="QDII">QDII</option>
        <option value="混合型">混合型</option>
        <option value="股票型">股票型</option>
      </select>
      <div id="search-dropdown" class="search-dropdown"></div>
    </div>
    <button class="buy-sig-btn" id="buySigBtn" onclick="openBuyPanel()">买入信号</button>
    <div class="auto-toggle on" id="autoToggle" onclick="toggleAuto()">
      <div class="switch"></div><span>自动刷新</span>
    </div>
    <span class="auto-interval" id="countdownText">60s</span>
    <button class="refresh-btn" id="refreshBtn" onclick="refreshData(false)">
      <span class="btn-text">刷新数据</span><span class="spinner"></span>
    </button>
  </div>
</div>

<div class="index-cards">{{index_cards}}</div>

<!-- 主导航 Tab -->
<div class="tab-nav">
  <button class="tab-btn active" data-tab="sector">行业板块</button>
  <button class="tab-btn" data-tab="portfolio">持仓</button>
  <button class="tab-btn" data-tab="watch">仅监控</button>
  <button class="tab-btn" data-tab="evaluate">建议买入</button>
</div>

<!-- Tab1: 行业板块 -->
<div class="tab-panel active" id="panel-sector">
  <div class="sector-grid" id="sector-grid"></div>
  <div style="margin-top:16px">
    <div class="chart-box" style="background:#1a2a3a;border-radius:8px;padding:10px;border:1px solid #2a3a4a;height:340px">
      <h3 style="font-size:13px;color:#8899aa;margin-bottom:6px">行业板块资金流 Top15</h3>
      <div id="sector-chart" style="width:100%;height:300px"></div>
    </div>
  </div>
</div>

<!-- Tab2: 持仓 -->
<div class="tab-panel" id="panel-portfolio">
  <div class="portfolio-summary" id="pf-summary"></div>
  <div style="overflow-x:auto">
    <table class="pf-table" id="pf-table">
      <thead><tr>
        <th>代码</th><th>名称</th><th>投入金额</th><th>买入净值</th><th>买入日期</th><th>时间</th>
        <th>份额</th><th>最新净值</th><th>当日收益</th><th>累计收益</th><th>收益率</th>
        <th>信号</th><th>建议</th><th></th>
      </tr></thead>
      <tbody id="pf-body"></tbody>
    </table>
  </div>
  <div class="pf-empty" id="pf-empty" style="display:none">
    暂无持仓。在搜索框中搜索基金，点击 <strong>【加持仓】</strong> 添加。
  </div>
</div>

<!-- Tab3: 仅监控 -->
<div class="tab-panel" id="panel-watch">
  <div class="watch-controls">
    <input type="text" placeholder="过滤代码/名称..." id="watchFilter" oninput="renderWatchTable()" style="padding:5px 10px;border-radius:5px;border:1px solid #2a3a4a;background:#1a2a3a;color:#e0e0e0;width:160px;font-size:12px">
    <span class="ctrl-sep"></span>
    <button class="ctrl-btn active" data-signal="all" onclick="setWatchSignal('all',this)">全部</button>
    <button class="ctrl-btn" data-signal="strong_buy,buy" onclick="setWatchSignal('strong_buy,buy',this)" style="color:#ff6347">买入</button>
    <button class="ctrl-btn" data-signal="hold" onclick="setWatchSignal('hold',this)" style="color:#ffa500">持有</button>
    <button class="ctrl-btn" data-signal="sell,strong_sell" onclick="setWatchSignal('sell,strong_sell',this)" style="color:#2e8b57">卖出</button>
    <span class="ctrl-sep"></span>
    <button class="ctrl-btn" onclick="setWatchSort('score',-1)">评分↓</button>
    <button class="ctrl-btn" onclick="setWatchSort('score',1)">评分↑</button>
    <button class="ctrl-btn" onclick="setWatchSort('change',-1)">涨幅↓</button>
  </div>
  <div class="watch-table-wrap">
    <table class="watch-table" id="watch-table"><thead><tr>
      <th onclick="setWatchSort('code')">代码 ↕</th>
      <th onclick="setWatchSort('name')">名称 ↕</th>
      <th onclick="setWatchSort('category')">分类 ↕</th>
      <th onclick="setWatchSort('nav')">净值 ↕</th>
      <th onclick="setWatchSort('change')">涨跌 ↕</th>
      <th onclick="setWatchSort('rsi')">RSI ↕</th>
      <th onclick="setWatchSort('momentum')">5日动量 ↕</th>
      <th onclick="setWatchSort('score')">评分 ↕</th>
      <th>信号</th>
    </tr></thead><tbody id="watch-body"></tbody></table>
  </div>
</div>

<!-- Tab4: 建议买入 -->
<div class="tab-panel" id="panel-evaluate">
  <div id="eval-entry" style="text-align:center;padding:60px 20px">
    <div style="font-size:48px;color:#2a3a4a;margin-bottom:16px">&#9889;</div>
    <div style="font-size:16px;color:#8899aa;margin-bottom:8px">全量基金买入信号评估</div>
    <div style="font-size:12px;color:#556677;margin-bottom:24px">
      目录基金约 {{total_count}} 只代表性基金，预计耗时 15~25 秒<br/>
      所有基金约 20000 只，预计耗时 8~15 分钟，消耗较多流量<br/>
      结果仅展示建议买入指数最高的前 100 只
    </div>
    <div style="display:flex;gap:12px;justify-content:center">
      <button onclick="startEvaluate('catalog')" style="padding:12px 28px;font-size:14px;font-weight:700;border-radius:8px;background:#ffd700;color:#0f1923;border:none;cursor:pointer;transition:.2s">计算目录基金</button>
      <button onclick="startEvaluate('all')" style="padding:12px 28px;font-size:14px;font-weight:700;border-radius:8px;background:#1a2a3a;color:#ffd700;border:2px solid #ffd700;cursor:pointer;transition:.2s">计算所有基金</button>
    </div>
  </div>
  <div id="eval-progress" style="display:none;text-align:center;padding:40px 20px">
    <div style="margin-bottom:16px">
      <div style="font-size:12px;color:#8899aa;margin-bottom:4px">评估范围: <span id="eval-mode-label">--</span></div>
      <div style="font-size:14px;color:#ffd700;margin-bottom:8px">评估进行中...</div>
      <div style="font-size:12px;color:#8899aa">
        已完成 <span id="eval-done">0</span> / <span id="eval-total">0</span> 只
      </div>
      <div style="width:400px;max-width:80vw;height:6px;background:#2a3a4a;border-radius:3px;margin:12px auto;overflow:hidden">
        <div id="eval-bar" style="height:100%;background:linear-gradient(90deg,#ffd700,#ff6347);border-radius:3px;width:0%;transition:width .3s"></div>
      </div>
      <div style="font-size:12px;color:#8899aa">
        预计剩余: <span id="eval-remaining">--</span> 秒
      </div>
    </div>
  </div>
  <div id="eval-results" style="display:none">
    <div style="margin-bottom:12px;font-size:13px;color:#8899aa">
      共评估 <strong id="eval-total-result">0</strong> 只基金，发现 <strong style="color:#ff6347" id="eval-buy-count">0</strong> 个买入信号
    </div>
    <button id="eval-batch-add-btn" onclick="batchAddToWatch()" style="padding:8px 20px;border-radius:6px;background:#ff6347;color:#fff;border:none;font-size:13px;font-weight:600;cursor:pointer;margin-bottom:12px;transition:.2s">一键加入监控</button>
    <div id="eval-filters" style="margin-bottom:12px;display:flex;flex-wrap:wrap;gap:6px"></div>
    <div id="eval-signals-list"></div>
    <div id="eval-reset-area" style="text-align:center;padding:20px;display:none"><button onclick="resetEvaluate()" style="padding:8px 20px;border-radius:6px;background:#1a2a3a;color:#ffd700;border:1px solid #ffd700;cursor:pointer;font-size:13px">重新评估</button></div>
  </div>
</div>

<script>
var RAW = {{raw_json}};
var SECTOR = {{sector_json}};
var stateWatch = {signal:"all", sortKey:"score", sortDir:-1};
var currentEvalSignals = [];
var fundChart = null;
var currentFund = null;
var activeTab = "sector";

// 自动刷新
var AUTO_INTERVAL = 60;
var autoOn = true;
var autoTimer = null;
var countdown = AUTO_INTERVAL;

function updateCountdown(){ document.getElementById("countdownText").textContent = countdown + "s"; }
function startAuto(){
  if(autoTimer) clearInterval(autoTimer);
  countdown = AUTO_INTERVAL; updateCountdown();
  autoTimer = setInterval(function(){
    countdown--; updateCountdown();
    if(countdown <= 0){ countdown = AUTO_INTERVAL; if(autoOn) refreshData(true); }
  }, 1000);
}
function toggleAuto(){
  autoOn = !autoOn; var el = document.getElementById("autoToggle");
  if(autoOn){ el.classList.add("on"); startAuto(); }
  else { el.classList.remove("on"); clearInterval(autoTimer); autoTimer=null; }
}

// Tab切换
document.querySelectorAll(".tab-btn").forEach(function(btn){
  btn.addEventListener("click", function(){
    document.querySelectorAll(".tab-btn").forEach(function(b){b.classList.remove("active")});
    document.querySelectorAll(".tab-panel").forEach(function(p){p.classList.remove("active")});
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    document.getElementById("panel-" + activeTab).classList.add("active");
    if(activeTab === "portfolio") loadPortfolio();
    if(activeTab === "sector") renderSectorCards();
    if(activeTab === "watch") renderWatchTable();
    if(activeTab === "evaluate") { /* 无需预加载，按钮触发 */ }
  });
});

// ---- 刷新 ----
async function refreshData(silent){
  var btn = document.getElementById("refreshBtn");
  btn.classList.add("loading"); btn.disabled = true;
  try{
    var r = await fetch("/api/refresh", {method:"POST"});
    var j = await r.json();
    if(j.ok){
      var newData = j.data;
      RAW = newData.results;
      SECTOR = newData.sector_flows;
      sectorCache = {};
      document.getElementById("updateTime").textContent = newData.update_time;
      document.getElementById("monCount").textContent = newData.monitored_count;
      document.getElementById("totalCount").textContent = newData.results.length;
      if(activeTab==="sector") renderSectorCards();
      if(activeTab==="portfolio") loadPortfolio();
      if(activeTab==="watch") renderWatchTable();
      updateBuySigBadge();
      if(!silent) showToast("已更新 (" + j.update_time + ")");
      if(autoOn){ countdown = AUTO_INTERVAL; updateCountdown(); }
    } else { if(!silent) showToast("失败: " + j.error); }
  } catch(e){ if(!silent) showToast("网络错误"); console.error(e); }
  btn.classList.remove("loading"); btn.disabled = false;
}

// ---- Tab1: 行业板块 ----
var sectorCache = {};
function renderSectorCards(){
  var grid = document.getElementById("sector-grid");
  if(!SECTOR||!SECTOR.length){ grid.innerHTML='<div style="color:#8899aa">暂无板块数据</div>'; return; }
  grid.innerHTML = SECTOR.map(function(s,idx){
    var chg = s.change_pct || 0;
    var chgCls = chg>0?"up":"down";
    var chgSign = chg>0?"+":"";
    var mn = s.main_net || 0;
    var tag, tagCls;
    if(chg > 2 && mn > 5){ tag="强烈关注"; tagCls="strong"; }
    else if(chg > 0 && mn > 0){ tag="建议关注"; tagCls="attention"; }
    else if(chg < -2 && mn < 0){ tag="暂时回避"; tagCls="avoid"; }
    else { tag="观望"; tagCls="watch"; }
    return '<div class="sector-card">'+
      '<div class="sc-header" onclick="toggleSector('+idx+',\''+esc(s.name)+'\')">'+
        '<div>'+
          '<div class="sc-name">'+esc(s.name)+'</div>'+
          '<div class="sc-stats">'+
            '<span class="'+chgCls+'">涨幅 '+chgSign+chg.toFixed(2)+'%</span>'+
            '<span class="'+((mn>0)?"up":"down")+'">主力 '+mn.toFixed(2)+'亿</span>'+
          '</div>'+
          '<span class="sc-tag '+tagCls+'">'+tag+'</span>'+
        '</div>'+
        '<span class="sc-arrow">&#9654;</span>'+
      '</div>'+
      '<div class="sc-body" id="sc-body-'+idx+'"><div class="sc-loading">点击展开查看基金列表</div></div>'+
    '</div>';
  }).join("");
  renderSectorChart();
}

function toggleSector(idx, name){
  var body = document.getElementById("sc-body-"+idx);
  var header = body.previousElementSibling;
  if(body.style.display === "block"){
    body.style.display = "none";
    header.classList.remove("expanded");
    return;
  }
  header.classList.add("expanded");
  if(sectorCache[name]){
    body.innerHTML = sectorCache[name];
    body.style.display = "block";
    return;
  }
  body.style.display = "block";
  body.innerHTML = '<div class="sc-loading">加载中...</div>';
  fetch("/api/sector-funds?sector=" + encodeURIComponent(name))
    .then(function(r){return r.json()})
    .then(function(data){
      var funds = data.funds||[];
      if(!funds.length){
        body.innerHTML = '<div class="sc-loading">该板块暂无相关基金</div>';
        return;
      }
      var html = '<table class="sc-table"><thead><tr>'+
        '<th>代码</th><th>名称</th><th>净值</th><th>涨跌</th><th>类型</th></tr></thead><tbody>';
      funds.forEach(function(f){
        var chCls = f.change>0?"up":f.change<0?"down":"neutral";
        var chSign = f.change>0?"+":"";
        html += '<tr class="fund-row" data-code="'+f.code+'" data-name="'+esc(f.name)+'">'+
          '<td>'+f.code+'</td>'+
          '<td>'+esc(f.name)+'</td>'+
          '<td>'+(f.nav||"-")+'</td>'+
          '<td class="'+chCls+'">'+chSign+(f.change||0)+'%</td>'+
          '<td style="font-size:10px;color:#8899aa">'+(f.category||f.ftype||"")+'</td>'+
        '</tr>';
      });
      html += '</tbody></table>';
      sectorCache[name] = html;
      body.innerHTML = html;
    }).catch(function(){
      body.innerHTML = '<div class="sc-loading">加载失败</div>';
    });
}

var scChart = null;
function renderSectorChart(){
  if(!SECTOR||!SECTOR.length) return;
  var top = SECTOR.slice(0,15).reverse();
  var dom = document.getElementById("sector-chart");
  if(!scChart) scChart = echarts.init(dom);
  scChart.setOption({
    tooltip:{trigger:"axis",formatter:function(p){return p[0].name+"<br/>主力净流入: "+p[0].value+"亿<br/>涨幅: "+p[0].data.chg+"%"}},
    grid:{left:78,right:40,top:8,bottom:16},
    xAxis:{type:"value",axisLabel:{color:"#8899aa",fontSize:10,formatter:"{value}亿"}},
    yAxis:{type:"category",data:top.map(function(s){return s.name}),axisLabel:{color:"#e0e0e0",fontSize:10}},
    series:[{type:"bar",data:top.map(function(s){return{
      value:Number(s.main_net.toFixed(2)),chg:s.change_pct,
      itemStyle:{color:s.main_net>0?"#ff4444":"#22bb44"}
    }}),barWidth:"60%",label:{show:true,position:"right",color:"#8899aa",fontSize:9,formatter:"{c}亿"}}]
  });
}

// ---- Tab2: 持仓 ----
var pfData = [];
async function loadPortfolio(){
  try{
    var r = await fetch("/api/portfolio");
    var j = await r.json();
    pfData = j.positions||[];
    renderPortfolio();
  } catch(e){ console.error(e); }
}
function renderPortfolio(){
  var body = document.getElementById("pf-body");
  var empty = document.getElementById("pf-empty");
  var summary = document.getElementById("pf-summary");
  if(!pfData.length){
    body.innerHTML = ""; empty.style.display = "block"; summary.innerHTML = "";
    return;
  }
  empty.style.display = "none";
  var totalAmount=0, totalMarket=0, totalDaily=0, totalProfit=0;
  body.innerHTML = pfData.map(function(p){
    var amt = p.amount||0; var nav = p.buy_nav||0; var cn = p.current_nav||0;
    var shares = p.shares||0;
    var marketVal = cn ? (shares*cn) : 0;
    var dp = p.daily_profit||0; var tp = p.total_profit||0;
    var rr = p.return_rate||0;
    totalAmount += amt; totalMarket += marketVal; totalDaily += dp; totalProfit += tp;
    var dpCls = dp>=0?"up":"down"; var dpSign = dp>=0?"+":"";
    var tpCls = tp>=0?"up":"down"; var tpSign = tp>=0?"+":"";
    var rrCls = rr>=0?"up":"down"; var rrSign = rr>=0?"+":"";
    var sig = sigInfo(p.signal||"hold");
    var advice = adviceText(p.signal||"");
    var isNew = amt === 0;
    var inputCls = isNew ? "pf-new-hint" : "";
    return '<tr data-id="'+p.id+'">'+
      '<td class="pf-code">'+esc(p.code)+'</td>'+
      '<td>'+esc(p.name||"")+'</td>'+
      '<td><input type="number" class="'+inputCls+'" value="'+amt+'" data-field="amount" onblur="savePf(this)" placeholder="输入金额"'+(isNew?' autofocus':'')+'></td>'+
      '<td><input type="number" class="'+inputCls+'" value="'+nav+'" data-field="buy_nav" step="0.0001" onblur="savePf(this)" placeholder="买入净值"></td>'+
      '<td><input type="date" class="pf-date" value="'+(p.buy_date||"")+'" data-field="buy_date" onchange="savePf(this)"></td>'+
      '<td><input type="text" class="pf-time" value="'+(p.buy_time||"15:00")+'" data-field="buy_time" onblur="savePf(this)"></td>'+
      '<td><input type="text" class="pf-readonly" value="'+(shares||0)+'" readonly></td>'+
      '<td><input type="text" class="pf-readonly" value="'+(cn||"-")+'" readonly></td>'+
      '<td class="'+dpCls+'">'+dpSign+dp.toFixed(2)+'</td>'+
      '<td class="'+tpCls+'">'+tpSign+tp.toFixed(2)+'</td>'+
      '<td class="'+rrCls+'">'+rrSign+rr.toFixed(2)+'%</td>'+
      '<td><span class="signal-tag signal-'+(p.signal||'hold')+'">'+sig[0]+'</span></td>'+
      '<td><span class="pf-advice signal-'+(p.signal||'hold')+'">'+advice+'</span></td>'+
      '<td><button class="pf-remove-btn" onclick="removePf('+p.id+')" title="移除">x</button></td>'+
    '</tr>';
  }).join("");
  var dpClsS = totalDaily>=0?"up":"down"; var tpClsS = totalProfit>=0?"up":"down";
  body.innerHTML += '<tr style="background:#1a2a3a;font-weight:700;font-size:12px">'+
    '<td colspan="2">汇总</td>'+
    '<td>'+totalAmount.toFixed(2)+'</td><td>-</td><td colspan="2">-</td>'+
    '<td>-</td><td>-</td>'+
    '<td class="'+dpClsS+'">'+(totalDaily>=0?"+":"")+totalDaily.toFixed(2)+'</td>'+
    '<td class="'+tpClsS+'">'+(totalProfit>=0?"+":"")+totalProfit.toFixed(2)+'</td>'+
    '<td class="'+(totalProfit>=0?"up":"down")+'">'+(totalAmount>0?(totalProfit/totalAmount*100).toFixed(2):"0.00")+'%</td>'+
    '<td colspan="3"></td></tr>';
  summary.innerHTML =
    '<div class="pf-sum-card"><div class="ps-label">总投入</div><div class="ps-value" style="color:#ffd700">'+totalAmount.toFixed(2)+'</div></div>'+
    '<div class="pf-sum-card"><div class="ps-label">总市值</div><div class="ps-value">'+totalMarket.toFixed(2)+'</div></div>'+
    '<div class="pf-sum-card"><div class="ps-label">当日收益</div><div class="ps-value '+dpClsS+'">'+(totalDaily>=0?"+":"")+totalDaily.toFixed(2)+'</div></div>'+
    '<div class="pf-sum-card"><div class="ps-label">累计收益</div><div class="ps-value '+tpClsS+'">'+(totalProfit>=0?"+":"")+totalProfit.toFixed(2)+'</div></div>';
}

async function savePf(el){
  var row = el.closest("tr");
  var id = parseInt(row.dataset.id);
  var field = el.dataset.field;
  var val = el.value;
  if(field === "amount" || field === "buy_nav") val = parseFloat(val)||0;
  try{
    var body = {id:id};
    body[field] = val;
    var r = await fetch("/api/portfolio/update",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(body)
    });
    var j = await r.json();
    if(j.ok){ loadPortfolio(); }
  } catch(e){ console.error(e); }
}

async function removePf(id){
  if(!confirm("确认移除此持仓？")) return;
  try{
    var r = await fetch("/api/portfolio/remove",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({id:id})
    });
    var j = await r.json();
    if(j.ok){ loadPortfolio(); showToast("已移除"); }
  } catch(e){ console.error(e); }
}

function adviceText(signal){
  var m = {"strong_buy":"强烈建议加仓","buy":"可适当加仓","hold":"继续持有","sell":"可考虑减仓","strong_sell":"建议清仓"};
  return m[signal]||"继续持有";
}

// ---- Tab3: 仅监控 ----
function renderWatchTable(){
  var rows = RAW.filter(function(r){ return r.monitored; });
  if(stateWatch.signal !== "all"){
    var sigs = stateWatch.signal.split(",");
    rows = rows.filter(function(r){ return sigs.indexOf(r.signal)>=0; });
  }
  var q = document.getElementById("watchFilter").value.toLowerCase();
  if(q) rows = rows.filter(function(r){ return (r.name||"").toLowerCase().indexOf(q)>=0||(r.code||"").indexOf(q)>=0; });
  var sk = stateWatch.sortKey, sd = stateWatch.sortDir;
  rows.sort(function(a,b){
    var va = (sk==="name"||sk==="category"||sk==="code")?String(a[sk]||""):Number(a[sk]||0);
    var vb = (sk==="name"||sk==="category"||sk==="code")?String(b[sk]||""):Number(b[sk]||0);
    if(typeof va==="string") return sd*va.localeCompare(vb,"zh");
    if(isNaN(va)) va=0; if(isNaN(vb)) vb=0;
    return sd*(va-vb);
  });
  document.getElementById("watch-body").innerHTML = rows.map(function(r){
    var ch = r.change>0?"up":r.change<0?"down":"neutral";
    var chSign = r.change>0?"+":"";
    var sig = sigInfo(r.signal);
    var sc = r.score||50;
    var bc = sc>=70?"#ff6347":sc>=50?"#ffa500":"#2e8b57";
    var mom = r.momentum;
    return '<tr class="fund-row" data-code="'+r.code+'" data-name="'+esc(r.name)+'">'+
      '<td>'+r.code+'</td><td>'+esc(r.name)+'</td>'+
      '<td style="font-size:11px;color:#8899aa">'+r.category+'</td>'+
      '<td>'+(r.nav||"-")+'</td>'+
      '<td class="'+ch+'">'+chSign+(r.change||"0")+'%</td>'+
      '<td>'+(r.rsi!=null?r.rsi:"-")+'</td>'+
      '<td class="'+(mom>0?"up":"down")+'">'+(mom!=null?mom+"%":"-")+'</td>'+
      '<td><span style="color:'+bc+'">'+sc+'</span>'+
        '<div class="score-bar"><div class="score-fill" style="width:'+sc+'%;background:'+bc+'"></div></div></td>'+
      '<td><span class="signal-tag signal-'+r.signal+'">'+sig[0]+'</span>'+
        ' <button class="pf-remove-btn" data-code="'+r.code+'" onclick="event.stopPropagation();removeWatch(\''+r.code+'\',\''+(r.name||"").replace(/'/g,"\\'")+'\')">x</button></td>'+
    '</tr>';
  }).join("");
}

function setWatchSignal(s, btn){
  stateWatch.signal = s;
  document.querySelectorAll("#panel-watch .ctrl-btn[data-signal]").forEach(function(b){b.classList.remove("active")});
  btn.classList.add("active");
  renderWatchTable();
}
function setWatchSort(key, dir){
  if(!dir) dir = stateWatch.sortKey===key ? -stateWatch.sortDir : 1;
  stateWatch.sortKey = key; stateWatch.sortDir = dir;
  renderWatchTable();
}

async function removeWatch(code, name){
  if(!confirm("确认将 "+(name||code)+" 从监控中移除？")) return;
  var r = await fetch("/api/remove-watch",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({code:code})
  });
  var j = await r.json();
  if(j.ok){ RAW = RAW.filter(function(rr){return rr.code!==code;}); renderWatchTable(); showToast("已移除: "+(name||code)); }
}

// ---- 行点击弹窗 ----
document.getElementById("watch-body").addEventListener("click",function(e){
  var row = e.target.closest("tr.fund-row");
  if(!row) return;
  currentFund = {code:row.dataset.code, name:row.dataset.name};
  openModal();
});

document.getElementById("sector-grid").addEventListener("click",function(e){
  var row = e.target.closest("tr.fund-row");
  if(!row) return;
  currentFund = {code:row.dataset.code, name:row.dataset.name};
  openModal();
});

document.getElementById("pf-body").addEventListener("click",function(e){
  if(e.target.tagName==="INPUT"||e.target.tagName==="BUTTON") return;
  var row = e.target.closest("tr[data-id]");
  if(!row) return;
  var codeEl = row.querySelector(".pf-code");
  var nameEl = row.querySelectorAll("td")[1];
  var code = codeEl ? codeEl.textContent.trim() : "";
  var name = nameEl ? nameEl.textContent.trim() : "";
  if(!code) return;
  currentFund = {code:code, name:name};
  openModal();
});


function openModal(){
  document.getElementById("modalOverlay").classList.add("show");
  document.getElementById("modalTitle").textContent = currentFund.name + " (" + currentFund.code + ")";
  var r = null;
  for(var i=0;i<RAW.length;i++){ if(RAW[i].code===currentFund.code){ r=RAW[i]; break; } }
  var info = "";
  if(r){
    var chCls = r.change>0?"up":r.change<0?"down":"neutral";
    var chSign = r.change>0?"+":"";
    info += '<div class="item">最新净值 <span>'+r.nav+'</span></div>';
    info += '<div class="item '+chCls+'">涨跌幅 <span class="'+chCls+'">'+chSign+r.change+'%</span></div>';
    var si = sigInfo(r.signal);
    info += '<div class="item">信号 <span style="color:'+si[1]+'">'+si[0]+'</span></div>';
    info += '<div class="item">评分 <span>'+r.score+'</span></div>';
  }
  document.getElementById("modalInfo").innerHTML = info;
  document.querySelectorAll(".range-tab").forEach(function(t){t.classList.remove("active")});
  document.querySelector(".range-tab[data-range='3m']").classList.add("active");
  loadChart("3m");
}
function closeModal(){
  document.getElementById("modalOverlay").classList.remove("show");
  if(fundChart){ fundChart.dispose(); fundChart = null; }
  currentFund = {};
}
document.getElementById("rangeTabs").addEventListener("click", function(e){
  if(!e.target.classList.contains("range-tab")) return;
  document.querySelectorAll(".range-tab").forEach(function(t){t.classList.remove("active")});
  e.target.classList.add("active");
  loadChart(e.target.dataset.range);
});
function buildChartOption(data){
  var dates = data.records.map(function(d){return d.date});
  var navs = data.records.map(function(d){return d.nav});
  var changes = data.records.map(function(d){var v=parseFloat(d.change); return isNaN(v)?0:v;});
  return {
    tooltip:{trigger:"axis",formatter:function(ps){return ps[0].axisValue+"<br/>净值: <b>"+ps[0].value+"</b><br/>日涨幅: "+(ps[1]?ps[1].value+"%":"-");}},
    legend:{data:["单位净值","日涨幅"],bottom:0,textStyle:{color:"#8899aa",fontSize:11}},
    grid:{left:60,right:60,top:16,bottom:36},
    xAxis:{type:"category",data:dates,axisLabel:{color:"#8899aa",fontSize:10,rotate:dates.length>60?45:0},axisLine:{lineStyle:{color:"#2a3a4a"}}},
    yAxis:[
      {type:"value",name:"净值",nameTextStyle:{color:"#8899aa"},axisLabel:{color:"#8899aa",fontSize:10},splitLine:{lineStyle:{color:"#1a2a3a"}}},
      {type:"value",name:"涨跌%",nameTextStyle:{color:"#8899aa"},axisLabel:{color:"#8899aa",fontSize:10,formatter:"{value}%"},splitLine:{show:false}}
    ],
    series:[
      {name:"单位净值",type:"line",data:navs,smooth:true,lineStyle:{color:"#ffd700",width:2},itemStyle:{color:"#ffd700"},symbol:"none",
       markArea:{silent:true,data:[[{yAxis:Math.min.apply(null,navs),itemStyle:{color:"rgba(255,215,0,.08)"}},{yAxis:Math.max.apply(null,navs)}]]}},
      {name:"日涨幅",type:"bar",yAxisIndex:1,data:changes.map(function(v){return{value:v,itemStyle:{color:v>=0?"#ff4444":"#22bb44"}}}),barWidth:"60%"}
    ]
  };
}

function loadChart(range){
  document.getElementById("chartLoading").style.display = "flex";
  document.getElementById("chartError").style.display = "none";
  var chartDom = document.getElementById("fund-chart");
  chartDom.style.display = "none";
  fetch("/api/fund/" + currentFund.code + "?range=" + range)
    .then(function(r){return r.json()})
    .then(function(data){
      document.getElementById("chartLoading").style.display = "none";
      chartDom.style.display = "";
      if(!data.records||data.records.length===0){
        document.getElementById("chartError").style.display = "flex"; return;
      }
      if(fundChart && fundChart._currentCode === currentFund.code && fundChart._currentRange === range){
        fundChart.setOption(buildChartOption(data), true);
        return;
      }
      if(!fundChart){
        fundChart = echarts.init(chartDom);
      }
      fundChart._currentCode = currentFund.code;
      fundChart._currentRange = range;
      fundChart.setOption(buildChartOption(data), true);
    }).catch(function(){
      document.getElementById("chartLoading").style.display = "none";
      document.getElementById("chartError").style.display = "flex";
    });
}

// ---- 搜索 ----
var searchDebounce = null;
var searchAbort = null;

function handleSearchInput(){
  var q = document.getElementById("search").value.trim();
  var dd = document.getElementById("search-dropdown");
  var typeFilter = document.getElementById("search-filter-type").value;
  if(searchDebounce) clearTimeout(searchDebounce);
  if(q.length < 1){ dd.classList.remove("show"); return; }
  dd.classList.add("show");
  dd.innerHTML = '<div class="sd-loading">搜索中...</div>';
  searchDebounce = setTimeout(function(){
    if(searchAbort) searchAbort.abort();
    var ctrl = new AbortController();
    searchAbort = ctrl;
    var url = "/api/search?q=" + encodeURIComponent(q);
    if(typeFilter) url += "&ftype=" + encodeURIComponent(typeFilter);
    fetch(url, {signal:ctrl.signal})
      .then(function(r){return r.json()})
      .then(function(data){
        var items = data.datas||[];
        if(!items.length){ dd.innerHTML='<div class="sd-empty">无匹配结果</div>'; return; }
        dd.innerHTML = items.map(function(d){
          return '<div class="sd-item">'+
            '<div class="sd-info"><span class="sd-code">'+esc(d.code)+'</span><span class="sd-name">'+esc(d.name)+'</span>'+
            '<div class="sd-meta">'+(d.ftype||"")+(d.company?" | "+d.company:"")+'</div></div>'+
            '<div class="sd-actions">'+
              '<button class="sd-btn sd-btn-position" data-code="'+esc(d.code)+'" data-name="'+esc(d.name)+'" data-ftype="'+esc(d.ftype||"")+'" data-company="'+esc(d.company||"")+'" data-action="position">加持仓</button>'+
              '<button class="sd-btn sd-btn-watch" data-code="'+esc(d.code)+'" data-name="'+esc(d.name)+'" data-ftype="'+esc(d.ftype||"")+'" data-company="'+esc(d.company||"")+'" data-action="watch">加监控</button>'+
            '</div></div>';
        }).join("");
      }).catch(function(e){
        if(e.name !== "AbortError"){ dd.innerHTML='<div class="sd-empty">搜索失败</div>'; }
      });
  }, 200);
}

document.getElementById("search-dropdown").addEventListener("click", function(e){
  var btn = e.target.closest(".sd-btn");
  if(!btn) return;
  var code = btn.dataset.code;
  var name = btn.dataset.name;
  var ftype = btn.dataset.ftype;
  var company = btn.dataset.company;
  var action = btn.dataset.action;
  var category = action === "position" ? "position" : "watch";

  fetch("/api/add-watch", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({code:code, name:name, ftype:ftype, company:company, category:category})
  }).then(function(r){return r.json()}).then(function(j){
    if(j.ok){
      document.getElementById("search-dropdown").classList.remove("show");
      document.getElementById("search").value = "";
      if(category === "position"){
        showToast("已添加持仓: "+name);
        document.querySelectorAll(".tab-btn").forEach(function(b){b.classList.remove("active")});
        document.querySelector(".tab-btn[data-tab='portfolio']").classList.add("active");
        document.querySelectorAll(".tab-panel").forEach(function(p){p.classList.remove("active")});
        document.getElementById("panel-portfolio").classList.add("active");
        activeTab = "portfolio";
        loadPortfolio();
      } else {
        showToast("已添加监控: "+name);
        RAW.push({
          code:code, name:name, category:"搜索添加", nav:"加载中...",
          change:0, signal:"", score:0, rsi:null, momentum:null, drawdown:null,
          monitored:true, searched:true, ftype:ftype
        });
        if(activeTab==="watch") renderWatchTable();
      }
      updateBuySigBadge();
    }
  });
});

document.addEventListener("click", function(e){
  var wrap = document.querySelector(".search-wrap");
  if(wrap && !wrap.contains(e.target)){
    document.getElementById("search-dropdown").classList.remove("show");
  }
});

// ---- 买入信号面板 ----
function openBuyPanel(){
  document.getElementById("sideOverlay").classList.add("show");
  document.getElementById("sidePanel").classList.add("show");
  document.getElementById("sigList").innerHTML = '<div style="text-align:center;padding:20px;color:#8899aa">加载中...</div>';
  fetch("/api/buy-signals")
    .then(function(r){return r.json()})
    .then(function(data){
      var signals = data.signals||[];
      document.getElementById("sigStat").textContent = "共 "+signals.length+" 条";
      if(!signals.length){
        document.getElementById("sigList").innerHTML='<div class="side-panel-empty">暂无买入信号</div>'; return;
      }
      document.getElementById("sigList").innerHTML = signals.map(function(r,i){
        var sl = sigInfo(r.signal);
        return '<div class="sig-item" id="sigItem'+i+'" data-code="'+esc(r.code)+'" data-name="'+esc(r.name)+'">'+
          '<div class="sig-item-header" data-idx="'+i+'">'+
            '<div style="flex:1">'+
              '<span style="color:#ffd700;font-family:monospace;font-size:12px">'+esc(r.code)+'</span>'+
              '<span style="color:#e0e0e0;font-size:13px;font-weight:600;margin-left:6px">'+esc(r.name)+'</span>'+
              '<div style="font-size:11px;color:#8899aa;margin-top:3px">'+
                '评分: <span style="color:'+(r.score>=70?'#ff6347':'#ffa500')+'">'+(r.score||50)+'</span>'+
              '</div>'+
            '</div>'+
            '<span class="signal-tag signal-'+r.signal+'">'+sl[0]+'</span>'+
          '</div>'+
        '</div>';
      }).join("");
    }).catch(function(){
      document.getElementById("sigList").innerHTML='<div class="side-panel-empty">加载失败</div>';
    });
}
function closeBuyPanel(){
  document.getElementById("sideOverlay").classList.remove("show");
  document.getElementById("sidePanel").classList.remove("show");
}

// ---- 工具函数 ----
function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }
function sigInfo(s){
  var m = {strong_buy:["强烈买入","#dc143c"],buy:["建议买入","#ff6347"],hold:["持有观望","#ffa500"],sell:["建议卖出","#2e8b57"],strong_sell:["强烈卖出","#228b22"]};
  return m[s]||["未知","#888"];
}
function showToast(msg){
  var t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  setTimeout(function(){t.classList.remove("show")}, 2200);
}
function updateBuySigBadge(){
  var buyCount = RAW.filter(function(r){return r.monitored&&(r.signal==="strong_buy"||r.signal==="buy")}).length;
  var btn = document.getElementById("buySigBtn");
  if(buyCount>0){ btn.textContent="买入信号 ("+buyCount+")"; btn.classList.add("has-sig"); }
  else { btn.textContent="买入信号"; btn.classList.remove("has-sig"); }
}

// ---- 建议买入评估 ----
var evalPollTimer = null;
var evalPollInterval = 800;

async function startEvaluate(mode){
  document.getElementById("eval-entry").style.display = "none";
  document.getElementById("eval-progress").style.display = "block";
  document.getElementById("eval-results").style.display = "none";
  evalPollInterval = 800;

  try{
    var r = await fetch("/api/evaluate-all", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({mode: mode})
    });
    var j = await r.json();
    if(!j.ok){ showToast("启动失败: "+j.error); document.getElementById("eval-entry").style.display="block"; document.getElementById("eval-progress").style.display="none"; return; }
    document.getElementById("eval-total").textContent = j.total;
    document.getElementById("eval-mode-label").textContent = j.label || "";
    evalPollTimer = setInterval(pollEvalProgress, evalPollInterval);
  } catch(e){ showToast("网络错误"); }
}

async function pollEvalProgress(){
  try{
    var r = await fetch("/api/evaluate-progress");
    var j = await r.json();
    if(j.error){
      clearInterval(evalPollTimer);
      showToast("评估出错: "+j.error);
      document.getElementById("eval-entry").style.display = "block";
      document.getElementById("eval-progress").style.display = "none";
      return;
    }
    document.getElementById("eval-done").textContent = j.done;
    document.getElementById("eval-total").textContent = j.total;
    var pct = j.total>0 ? Math.round(j.done/j.total*100) : 0;
    document.getElementById("eval-bar").style.width = pct+"%";
    var now = Date.now()/1000;
    if(j.start_time && j.done>0){
      var elapsed = now - j.start_time;
      var rate = j.done / elapsed;
      var remaining = j.total - j.done;
      var eta = rate>0 ? remaining / rate : 0;
      document.getElementById("eval-remaining").textContent = eta>0 ? eta.toFixed(0) : "--";

      // 动态退避
      var newInterval;
      if(eta < 30){ newInterval = 800; }
      else if(eta < 120){ newInterval = 1500; }
      else { newInterval = 3000; }
      if(newInterval !== evalPollInterval){
        evalPollInterval = newInterval;
        clearInterval(evalPollTimer);
        evalPollTimer = setInterval(pollEvalProgress, evalPollInterval);
      }
    }
    if(!j.running){
      clearInterval(evalPollTimer);
      evalPollTimer = null;
      evalPollInterval = 800;
      document.getElementById("eval-progress").style.display = "none";
      loadEvalResults();
    }
  } catch(e){ clearInterval(evalPollTimer); evalPollTimer=null; }
}

async function loadEvalResults(){
  try{
    var r = await fetch("/api/evaluate-results");
    var j = await r.json();
    if(!j.ok){ showToast(j.error); return; }
    document.getElementById("eval-results").style.display = "block";
    document.getElementById("eval-total-result").textContent = j.total;
    document.getElementById("eval-buy-count").textContent = j.buy_count;
    renderEvalResults(j.signals);
  } catch(e){ showToast("获取结果失败"); }
}

function renderEvalResults(signals){
  currentEvalSignals = signals;
  var listEl = document.getElementById("eval-signals-list");
  var filterEl = document.getElementById("eval-filters");
  var resetEl = document.getElementById("eval-reset-area");

  if(!signals || !signals.length){
    listEl.innerHTML = '<div style="text-align:center;padding:40px;color:#8899aa">暂未发现买入信号</div>';
    filterEl.innerHTML = '';
    resetEl.style.display = 'none';
    return;
  }

  // 提取所有分类
  var categories = [];
  var seen = {};
  signals.forEach(function(s){
    var cat = s.category || "未分类";
    if(!seen[cat]){ seen[cat]=true; categories.push(cat); }
  });

  // 分类筛选按钮
  var filterHtml = '<button onclick="filterEvalResults(\'all\')" class="eval-filter-btn eval-filter-active" data-cat="all">全部('+signals.length+')</button>';
  categories.forEach(function(cat){
    var count = signals.filter(function(s){return (s.category||"未分类")===cat;}).length;
    filterHtml += '<button onclick="filterEvalResults(\''+cat.replace(/'/g,"\\'")+'\')" class="eval-filter-btn" data-cat="'+esc(cat)+'">'+esc(cat)+'('+count+')</button>';
  });
  filterEl.innerHTML = filterHtml;

  // 渲染全部基金
  renderEvalSignalItems(signals);
  resetEl.style.display = 'block';
}

function filterEvalResults(cat){
  document.querySelectorAll(".eval-filter-btn").forEach(function(b){b.classList.remove("eval-filter-active")});
  var btn = document.querySelector('.eval-filter-btn[data-cat="'+cat.replace(/"/g,'&quot;')+'"]');
  if(btn) btn.classList.add("eval-filter-active");
  var filtered = cat==="all" ? currentEvalSignals : currentEvalSignals.filter(function(s){return (s.category||"未分类")===cat;});
  renderEvalSignalItems(filtered);
}

function renderEvalSignalItems(items){
  var listEl = document.getElementById("eval-signals-list");
  if(!items || !items.length){
    listEl.innerHTML = '<div style="text-align:center;padding:40px;color:#8899aa">该分类暂无买入信号</div>';
    return;
  }
  listEl.innerHTML = items.map(function(s){
    var chgCls = (s.change||0)>0?"up":"down";
    var chgSign = (s.change||0)>0?"+":"";
    var sl = sigInfo(s.signal);
    var sc = s.score||50;
    var bc = sc>=70?"#ff6347":sc>=50?"#ffa500":"#2e8b57";

    var reasons = [];
    if(s.rsi!=null){
      var rsiLabel = s.rsi<30?"RSI超卖(<30)，反弹概率高":s.rsi<40?"RSI偏低("+s.rsi+")，接近超卖区":"RSI中性";
      reasons.push({label:"RSI", value:s.rsi, desc:rsiLabel});
    }
    if(s.momentum_5d!=null){
      var momDesc = s.momentum_5d>0?"5日动量正值，短期趋势向好":"5日动量:"+s.momentum_5d;
      reasons.push({label:"5日动量", value:s.momentum_5d+"%", desc:momDesc});
    }
    if(s.drawdown!=null){
      reasons.push({label:"回撤", value:s.drawdown+"%", desc:"近期回撤幅度较大，存在反弹空间"});
    }
    if(s.ma_status){
      reasons.push({label:"均线", value:s.ma_status, desc:"均线形态有利"});
    }
    var estGain = sc>=80 ? "8%~15%" : sc>=70 ? "5%~10%" : sc>=60 ? "3%~7%" : "2%~5%";

    var reasonsHtml = reasons.map(function(rr){
      return '<div class="eval-reason"><span class="er-label">'+rr.label+':</span><span class="er-value">'+rr.value+'</span> &mdash; '+rr.desc+'</div>';
    }).join("");

    return '<div class="eval-card eval-fund-row">'+
      '<div class="eval-card-header" onclick="this.parentElement.classList.toggle(\'expanded\')">'+
        '<span class="ec-code">'+esc(s.code)+'</span>'+
        '<span class="ec-name">'+esc(s.name)+' <span class="signal-tag signal-'+(s.signal||'hold')+'" style="font-size:10px;margin-left:6px">'+sl[0]+'</span><span class="eval-monitor-badge">已监控</span></span>'+
        '<span class="ec-score" style="color:'+bc+'">'+sc+'</span>'+
        '<span class="ec-change '+chgCls+'">'+chgSign+(s.change||0)+'%</span>'+
        '<span class="ec-arrow">&#9660;</span>'+
      '</div>'+
      '<div class="eval-card-body">'+
        '<div style="margin-bottom:8px;font-size:13px;color:#ffd700">预估涨幅: '+estGain+' | 分类: '+(s.category||"--")+'</div>'+
        '<div style="margin-bottom:6px;font-size:12px;color:#8899aa">买入依据:</div>'+
        reasonsHtml+
        '<div style="margin-top:8px;font-size:11px;color:#556677">净值: '+(s.nav||"--")+' | 所属板块: '+(s.category||"--")+'</div>'+
      '</div>'+
    '</div>';
  }).join("");
}

function resetEvaluate(){
  document.getElementById("eval-entry").style.display = "block";
  document.getElementById("eval-progress").style.display = "none";
  document.getElementById("eval-results").style.display = "none";
  document.getElementById("eval-reset-area").style.display = "none";
  currentEvalSignals = [];
}

async function batchAddToWatch(){
  var btn = document.getElementById("eval-batch-add-btn");
  btn.disabled = true;
  btn.textContent = "添加中...";
  try{
    var r = await fetch("/api/batch-add-watch", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({codes: currentEvalSignals})
    });
    var j = await r.json();
    if(j.ok){
      showToast("已添加 "+j.added+" 只基金到监控");
      btn.textContent = "已添加 "+j.added+" 只";
      btn.style.background = "#2a6e3f";
      // 标记已监控
      document.querySelectorAll("#eval-signals-list .eval-fund-row .eval-monitor-badge").forEach(function(b){
        b.style.display = "inline-block";
      });
      refreshData(true);
    } else {
      showToast("添加失败: "+j.error);
      btn.disabled = false;
      btn.textContent = "一键加入监控";
    }
  } catch(e){
    showToast("网络错误");
    btn.disabled = false;
    btn.textContent = "一键加入监控";
  }
}

// ---- 初始化 ----
window.addEventListener("DOMContentLoaded", function(){
  renderSectorCards();
  updateBuySigBadge();
  startAuto();
  // 预加载持仓数据
  loadPortfolio();
});
window.addEventListener("resize", function(){
  if(scChart) scChart.resize();
});
</script>
</body></html>"""


def build_dashboard(update_time, indices, market_flow, sector_flows, results,
                    names_map, monitored_count, category_totals, log=None, categories_data=None):
    """生成完整 HTML 看板"""

    index_cards = ""
    for name, idx in indices.items():
        clz = "up" if idx["change_pct"] > 0 else ("down" if idx["change_pct"] < 0 else "neutral")
        sign = "+" if idx["change_pct"] > 0 else ""
        index_cards += (
            f'<div class="idx-card"><div class="label">{name}</div>'
            f'<div class="value {clz}">{idx["price"]:.2f}</div>'
            f'<div class="sub {clz}">{sign}{idx["change_pct"]:.2f}%  {sign}{idx["change_val"]:.2f}</div></div>\n'
        )

    if market_flow:
        mf = market_flow
        clz = "up" if mf["main_net"] > 0 else "down"
        index_cards += (
            f'<div class="idx-card"><div class="label">主力资金(亿)</div>'
            f'<div class="value {clz}">{mf["main_net"]:+.1f}</div>'
            f'<div class="sub">超大单 {mf["super_large_net"]:+.1f} | '
            f'大单 {mf["large_net"]:+.1f}</div></div>\n'
        )

    total = sum(category_totals.values())

    raw_json = json.dumps(results, ensure_ascii=False, default=str)
    sector_json = json.dumps(sector_flows, ensure_ascii=False, default=str)

    html = HTML_TEMPLATE.replace("{{update_time}}", update_time)
    html = html.replace("{{index_cards}}", index_cards)
    html = html.replace("{{total_count}}", str(total))
    html = html.replace("{{monitored_count}}", str(monitored_count))
    html = html.replace("{{raw_json}}", raw_json)
    html = html.replace("{{sector_json}}", sector_json)

    return html