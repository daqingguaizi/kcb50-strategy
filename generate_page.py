#!/usr/bin/env python3
"""生成手机端看盘 HTML — 内置实时自动更新

页面加载后：
  - 立即显示静态数据（秒开，不依赖 API）
  - JS 自动连接 API，交易时段每 10s 拉取实时 ETF 价格
  - 收盘后 15:35 自动全量刷新（cron 已更新数据）
  - 手机切回页面时立即刷新
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent))

from config import PARAMS, DATA_FILE, INITIAL_CAPITAL, ETF_CODE
from strategy import generate_signals, get_trades
from backtest import compute_equity, compute_metrics


def calc_all():
    """运行策略，返回所有数据"""
    from updater import update
    update(str(DATA_FILE))

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    signals = generate_signals(df, **PARAMS)
    trades = get_trades(signals, df["close"])
    equity = compute_equity(signals, df["close"], INITIAL_CAPITAL)
    metrics = compute_metrics(equity, trades)

    today = df.index[-1]
    current_signal = int(signals.iloc[-1])
    current_price = float(df["close"].iloc[-1])

    if len(df) >= 2:
        daily_change = round((df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100, 2)
    else:
        daily_change = 0

    entry_date = entry_price = hold_days = pnl = None
    if current_signal == 1:
        entry_idx = None
        for i in range(len(signals) - 1, -1, -1):
            if signals.iloc[i] == 0:
                entry_idx = i + 1
                break
        if entry_idx is None:
            entry_idx = 0
        entry_date = signals.index[entry_idx]
        entry_price = float(df["close"].iloc[entry_idx])
        hold_days = (today - entry_date).days
        pnl = round((current_price / entry_price - 1) * 100, 2)

    recent_trades = []
    for t in trades[-6:]:
        recent_trades.append({
            "entry": t["entry"][:10],
            "exit": t["exit"][:10],
            "return": round(t["return"] * 100, 1),
            "days": t["days"],
        })

    return {
        "data_date": today.strftime("%Y-%m-%d"),
        "signal": current_signal,
        "entry_date": entry_date.strftime("%Y-%m-%d") if entry_date else None,
        "entry_price": round(entry_price, 2) if entry_price else None,
        "hold_days": hold_days,
        "pnl": pnl,
        "index_price": round(current_price, 2),
        "daily_change": daily_change,
        "metrics": {
            "total_return": round(metrics["total_return"] * 100, 1),
            "annual_return": round(metrics["annual_return"] * 100, 1),
            "max_drawdown": round(metrics["max_drawdown"] * 100, 1),
            "sharpe": round(metrics["sharpe_ratio"], 2),
            "win_rate": round(metrics["win_rate"] * 100, 1),
            "profit_factor": round(metrics["profit_factor"], 2),
            "total_trades": metrics["total_trades"],
            "avg_hold_days": round(metrics["avg_hold_days"]),
        },
        "recent_trades": recent_trades,
        "params": {"period": PARAMS["period"], "signal_period": PARAMS["signal_period"]},
    }


# ═══════════════════════════════════════════════════════════
# HTML — 包含完整 JS 自动更新逻辑
# ═══════════════════════════════════════════════════════════

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0f0f12">
<title>科创50策略看盘</title>
<style>
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Helvetica Neue", sans-serif;
    background: #0f0f12;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 16px;
    -webkit-font-smoothing: antialiased;
    -webkit-tap-highlight-color: transparent;
  }
  .header { text-align: center; padding: 8px 0 4px; }
  .header .t { font-size: 15px; color: #888; letter-spacing: 2px; }
  .status-bar {
    display: flex; align-items: center; justify-content: center;
    gap: 8px; margin-top: 6px; font-size: 11px; color: #555;
  }
  .live-dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
    animation: pulse 2s infinite;
  }
  .live-dot.on  { background: #00d4aa; }
  .live-dot.off { background: #f44; animation: none; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  .refresh-btn {
    background: #1a1a24; border:1px solid #2a2a3a; color:#00d4aa;
    padding:4px 12px; border-radius:12px; font-size:11px;
    cursor:pointer; -webkit-tap-highlight-color:transparent; user-select:none;
  }
  .refresh-btn:active { background:#2a2a3a; }

  .signal-card {
    background: linear-gradient(135deg, #1a1a24 0%, #1f1f2e 100%);
    border: 1px solid #2a2a3a; border-radius: 16px;
    padding: 24px 20px; text-align: center;
    margin-bottom: 12px; position: relative; overflow: hidden;
    transition: border-color 0.3s;
  }
  .signal-card::before { content:''; position:absolute; top:0;left:0;right:0; height:3px; }
  .signal-card.long::before  { background: #00d4aa; }
  .signal-card.cash::before  { background: #555; }
  .signal-badge {
    display: inline-block; padding: 6px 18px; border-radius: 20px;
    font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 12px;
  }
  .long .signal-badge  { background:#00d4aa22; color:#00d4aa; border:1px solid #00d4aa44; }
  .cash .signal-badge  { background:#44444422; color:#888;    border:1px solid #44444444; }
  .pnl {
    font-size: 48px; font-weight: 800; letter-spacing: -1px;
    line-height: 1; margin: 8px 0; transition: color 0.3s;
  }
  .pnl.pos  { color: #00d4aa; }
  .pnl.neg  { color: #ff4d6a; }
  .pnl.none { color: #888; }
  .sub { font-size: 12px; color: #666; margin-top: 6px; }
  .sub .h  { color: #00d4aa; }
  .sub .d  { color: #ff4d6a; }
  .sub .w  { color: #999; }
  .sub .live-tag { font-size:10px; color:#00d4aa; animation:pulse 1.5s infinite; }

  .grid-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:12px; }
  .stat-box {
    background: #1a1a24; border:1px solid #2a2a3a;
    border-radius:12px; padding:14px 12px; text-align:center;
  }
  .stat-box .label { font-size:11px; color:#666; letter-spacing:.5px; margin-bottom:4px; }
  .stat-box .value { font-size:20px; font-weight:700; }
  .stat-box .value.g  { color: #00d4aa; }
  .stat-box .value.r  { color: #ff4d6a; }
  .stat-box .value.w  { color: #e0e0e0; }

  .section-title { font-size:13px; color:#666; letter-spacing:2px; padding:8px 4px; }
  .trade-table {
    width:100%; background:#1a1a24; border:1px solid #2a2a3a;
    border-radius:12px; overflow:hidden; margin-bottom:12px;
  }
  .trade-table table { width:100%; border-collapse:collapse; font-size:13px; }
  .trade-table th { color:#555; font-weight:500; font-size:11px; letter-spacing:1px;
    padding:10px 12px 6px; text-align:left; }
  .trade-table td { padding:8px 12px; border-top:1px solid #1f1f2a; }
  .trade-table .win  { color:#00d4aa; }
  .trade-table .loss { color:#ff4d6a; }
  .trade-table .holding { color:#00d4aa; font-size:11px; }

  .footer { text-align:center; padding:12px 0 24px; font-size:11px; color:#444; line-height:1.6; }
  .footer span { color:#555; }
</style>
</head>
<body>

<!-- 初始值由 Python 生成填入，JS 启动后接管更新 -->
<div class="header">
  <div class="t">🔬 科创50 · TRIX策略</div>
  <div class="status-bar">
    <span class="live-dot on" id="dot"></span>
    <span id="st">已连接</span>
    <span style="color:#444">|</span>
    <span id="ts">--:--:--</span>
    <button class="refresh-btn" ontouchend="refresh()" onclick="refresh()">⟳ 刷新</button>
  </div>
</div>

<!-- 信号卡片 -->
<div class="signal-card {{CARD_CLS}}" id="card">
  <div class="signal-badge" id="badge">{{BADGE}}</div>
  <div class="pnl {{PNL_CLS}}" id="pnl">{{PNL}}</div>
  <div class="sub" id="info">{{INFO}}</div>
  <div class="sub" style="margin-top:4px" id="daily">{{DAILY}}</div>
</div>

<!-- 指标 -->
<div class="grid-3">
  <div class="stat-box"><div class="label">累计收益</div><div class="value g" id="v0">{{V0}}</div></div>
  <div class="stat-box"><div class="label">年化收益</div><div class="value g" id="v1">{{V1}}</div></div>
  <div class="stat-box"><div class="label">最大回撤</div><div class="value r" id="v2">{{V2}}</div></div>
</div>
<div class="grid-3">
  <div class="stat-box"><div class="label">夏普比率</div><div class="value w" id="v3">{{V3}}</div></div>
  <div class="stat-box"><div class="label">胜率</div><div class="value w" id="v4">{{V4}}</div></div>
  <div class="stat-box"><div class="label">盈亏比</div><div class="value w" id="v5">{{V5}}</div></div>
</div>

<div class="section-title">📋 最近交易</div>
<div class="trade-table"><table>
  <thead><tr><th>入场</th><th>出场</th><th style="text-align:right">收益</th><th style="text-align:right">天数</th></tr></thead>
  <tbody id="trades">{{TRADES}}</tbody>
</table></div>

<div class="grid-3">
  <div class="stat-box"><div class="label">总交易</div><div class="value w" id="v6">{{V6}}</div></div>
  <div class="stat-box"><div class="label">平均持仓</div><div class="value w" id="v7">{{V7}}</div></div>
  <div class="stat-box"><div class="label">数据日期</div><div class="value w" style="font-size:14px" id="v8">{{V8}}</div></div>
</div>

<div class="footer">
  标的: 科创50ETF (588000) · 参数: period=9, signal=17<br>
  <span>交易日15:30自动更新 · 策略信号仅供参考，不构成投资建议</span>
</div>

<script>
// ═══════════════════════════════════════════
// 实时更新引擎
// ═══════════════════════════════════════════

var API = '/api/status';
var POLL_FAST = 10e3;   // 交易时段 10s
var POLL_SLOW = 60e3;   // 非交易时段 60s
var QUIET_POLL = 5 * 60e3; // GitHub Pages 模式：5分钟检查一次
var REFRESH_MIN = 15;
var REFRESH_HOUR = 15;

var timer = null;
var ctrl = null;
var cache = null;
var failCount = 0;
var isCloud = false;       // true = GitHub Pages（无后端API）

function E(id){ return document.getElementById(id); }
function S(v){ return v>=0 ? '+' : ''; }
function G(v){ return v>=0 ? 'g' : 'r'; }

function refresh(){
  location.reload();
}

// 切换到云端静态模式（无需后端 API，页面数据由 GitHub Actions 每日更新）
function enterCloudMode(){
  isCloud = true;
  // 页面数据已内嵌在 HTML 中，直接显示即可
  E('dot').className = 'live-dot on';
  E('st').innerHTML = '☁️ 云端托管';
  E('st').style.color = '#888';
  E('ts').textContent = '静态模式';
}

function poll_success(data){
  failCount = 0;
  cache = data;
  update(data.signal, data.quote);

  E('dot').className = 'live-dot on';
  E('st').innerHTML = data.market_open ? '🟢 实时监控中' : '已连接';
  if(isCloud){ E('st').style.color = '#00d4aa'; isCloud = false; }
  E('ts').textContent = data.ts ? data.ts.substring(11,19) : '';

  // 收盘后自动全量刷新
  var n = new Date();
  var today = n.getFullYear() + '-' + String(n.getMonth()+1).padStart(2,'0') + '-' + String(n.getDate()).padStart(2,'0');
  if(n.getDay()>=1 && n.getDay()<=5 && n.getHours()>=REFRESH_HOUR && n.getMinutes()>=REFRESH_MIN){
    if(data.signal && data.signal.data_date < today){
      refresh();
      return;
    }
  }
}

// 判断是否盘中
function isMarket(){
  var n = new Date();
  if(n.getDay()===0 || n.getDay()===6) return false;
  var t = n.getHours()*100 + n.getMinutes();
  return t >= 930 && t <= 1500;
}

function update(sig, q){
  var s = sig.signal;
  var m = sig.metrics;
  var card = E('card');
  var badge = E('badge');
  var pnlEl = E('pnl');
  var infoEl = E('info');
  var dailyEl = E('daily');

  // 信号状态
  if(s === 1){
    card.className = 'signal-card long';
    badge.textContent = '🟢 做多 LONG';
  } else {
    card.className = 'signal-card cash';
    badge.textContent = '⚪ 空仓 CASH';
  }

  // 浮盈（用指数价格算，ETF实时价单独显示）
  var dp = sig.pnl != null ? sig.pnl : 0;

  if(s === 1 && sig.entry_price){
    pnlEl.className = 'pnl ' + (dp>=0?'pos':'neg');
    pnlEl.textContent = S(dp) + dp.toFixed(1) + '%';
    var info = '入场 ¥' + sig.entry_price.toFixed(2) + ' · 持仓第' + sig.hold_days + '天 · 指数 ¥' + sig.index_price.toFixed(0);
    if(q && q.price){
      info += ' · <span style="color:#888">ETF ¥' + q.price.toFixed(3) + '</span>';
      if(data.market_open) info += ' <span class="live-tag">●</span>';
    }
    infoEl.innerHTML = info;
  } else {
    pnlEl.className = 'pnl none';
    pnlEl.textContent = '—';
    infoEl.textContent = '持币观望，等待下一次信号';
  }

  // 日内涨跌
  var dc = sig.daily_change != null ? sig.daily_change : 0;
  dailyEl.innerHTML = 'ETF 588000 今日 <span class="' + (dc>=0?'h':'d') + '">' + S(dc) + dc.toFixed(2) + '%</span>';
  if(q && q.change_pct != null){
    dailyEl.innerHTML += ' <span style="font-size:10px;color:#666">(盘中 <span class="' + (q.change_pct>=0?'h':'d') + '">' + S(q.change_pct) + q.change_pct.toFixed(2) + '%</span>)</span>';
  }

  // 指标
  E('v0').textContent = S(m.total_return) + m.total_return.toFixed(1) + '%';
  E('v0').className = 'value ' + G(m.total_return);
  E('v1').textContent = S(m.annual_return) + m.annual_return.toFixed(1) + '%';
  E('v1').className = 'value ' + G(m.annual_return);
  E('v2').textContent = '-' + Math.abs(m.max_drawdown).toFixed(1) + '%';
  E('v3').textContent = m.sharpe.toFixed(2);
  E('v4').textContent = m.win_rate.toFixed(1) + '%';
  E('v5').textContent = m.profit_factor.toFixed(2);
  E('v6').textContent = m.total_trades;
  E('v7').textContent = m.avg_hold_days + '天';
  E('v8').textContent = sig.data_date ? sig.data_date.substring(5) : '';

  // 交易列表
  var trades = sig.recent_trades || [];
  var rows = '';
  for(var i = trades.length-1; i >= 0; i--){
    var t = trades[i];
    var cs = t['return'] >= 0 ? 'win' : 'loss';
    var ss = t['return'] >= 0 ? '+' : '';
    var hold = t.exit && t.exit.indexOf('持仓中') >= 0;
    var exitDisp = hold ? t.exit.replace('(持仓中)', '<span class="holding">持仓中</span>') : t.exit;
    rows += '<tr><td>' + t.entry + '</td><td>' + exitDisp + '</td>' +
      '<td style="text-align:right" class="' + cs + '">' + ss + t['return'].toFixed(1) + '%</td>' +
      '<td style="text-align:right;color:#888">' + t.days + '天</td></tr>';
  }
  E('trades').innerHTML = rows;
}

async function poll(){
  clearTimeout(timer);
  if(ctrl) { try{ctrl.abort()}catch(e){} }
  ctrl = new AbortController();

  // 如果已确认云端模式，低频检查
  if(isCloud){
    try {
      var r = await fetch(API, {signal: ctrl.signal, cache: 'no-cache'});
      if(r.ok){
        var d = await r.json();
        if(d && d.ok){ poll_success(d); }
      }
    } catch(e){}
    timer = setTimeout(poll, QUIET_POLL);
    return;
  }

  try {
    var resp = await fetch(API, {signal: ctrl.signal, cache: 'no-cache'});
    if(!resp.ok) throw new Error('HTTP ' + resp.status);
    var data = await resp.json();
    if(!data.ok) throw new Error('not ok');
    poll_success(data);
  } catch(e){
    if(e.name === 'AbortError') return;
    failCount++;
    if(failCount >= 3){
      enterCloudMode();
    } else {
      E('dot').className = 'live-dot off';
      E('st').textContent = '重试中 (' + failCount + '/3)...';
    }
  }

  var interval = isCloud ? QUIET_POLL :
    (isMarket() ? POLL_FAST : POLL_SLOW);
  timer = setTimeout(poll, interval);
}

// 判断盘中（浏览器本地时间）
function isMarket(){
  var n = new Date();
  if(n.getDay()===0 || n.getDay()===6) return false;
  var t = n.getHours()*100 + n.getMinutes();
  return t >= 930 && t <= 1500;
}

// 页面切回时立即拉取
document.addEventListener('visibilitychange', function(){
  if(!document.hidden){
    clearTimeout(timer);
    timer = setTimeout(poll, 500);
  }
});

// 启动
document.addEventListener('DOMContentLoaded', function(){
  // 尝试连接 API
  poll();

  // 如果 15 秒内没连上 API，切换到云端显示模式
  setTimeout(function(){
    if(!cache && failCount > 0) enterCloudMode();
  }, 15000);
});

// 双击顶部强制刷新
document.querySelector('.header').addEventListener('dblclick', refresh);
</script>
</body>
</html>'''


def generate():
    data = calc_all()
    s = data["signal"]
    m = data["metrics"]
    pnl = data["pnl"]
    ep = data["entry_price"]
    ip = data["index_price"]
    hd = data["hold_days"]
    daily = data["daily_change"]

    # 信号卡片
    badge = "🟢 做多 LONG" if s == 1 else "⚪ 空仓 CASH"
    card_cls = "long" if s == 1 else "cash"
    if s == 1 and pnl is not None:
        pnl_str = f"{pnl:+.1f}%"
        pnl_cls = "pos" if pnl >= 0 else "neg"
        info_str = f"入场 ¥{ep:.2f} · 持仓第{hd}天 · 现价 ¥{ip:.2f}"
    else:
        pnl_str = "—"
        pnl_cls = "none"
        info_str = "持币观望，等待下一次信号"

    ds = "+" if daily >= 0 else ""
    dc = "h" if daily >= 0 else "d"
    daily_str = f'ETF 588000 今日 <span class="{dc}">{ds}{daily:.2f}%</span>'

    # 交易行
    trade_rows = ""
    for t in reversed(data["recent_trades"]):
        ret = t["return"]
        cs = "win" if ret >= 0 else "loss"
        ss = "+" if ret >= 0 else ""
        hold = "持仓中" in t["exit"]
        exit_d = t["exit"].replace(" (持仓中)", '<span class="holding">持仓中</span>') if hold else t["exit"]
        trade_rows += f'<tr><td>{t["entry"]}</td><td>{exit_d}</td>' \
                      f'<td style="text-align:right" class="{cs}">{ss}{ret:.1f}%</td>' \
                      f'<td style="text-align:right;color:#888">{t["days"]}天</td></tr>\n'

    # 填充
    html = HTML
    html = html.replace("{{CARD_CLS}}", card_cls)
    html = html.replace("{{BADGE}}", badge)
    html = html.replace("{{PNL_CLS}}", pnl_cls)
    html = html.replace("{{PNL}}", pnl_str)
    html = html.replace("{{INFO}}", info_str)
    html = html.replace("{{DAILY}}", daily_str)
    html = html.replace("{{V0}}", f"{S_TOTAL(m['total_return'])}{m['total_return']:.1f}%")
    html = html.replace("{{V1}}", f"{S_TOTAL(m['annual_return'])}{m['annual_return']:.1f}%")
    html = html.replace("{{V2}}", f"-{abs(m['max_drawdown']):.1f}%")
    html = html.replace("{{V3}}", f"{m['sharpe']:.2f}")
    html = html.replace("{{V4}}", f"{m['win_rate']:.1f}%")
    html = html.replace("{{V5}}", f"{m['profit_factor']:.2f}")
    html = html.replace("{{V6}}", str(m['total_trades']))
    html = html.replace("{{V7}}", f"{m['avg_hold_days']}天")
    html = html.replace("{{V8}}", data["data_date"][5:])
    html = html.replace("{{TRADES}}", trade_rows)

    out_path = Path(__file__).parent / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"  ✅ HTML页面已生成: {out_path}")
    if s == 1:
        print(f"  📊 当前信号: 做多 LONG | 浮盈: {pnl:+.1f}%")
    else:
        print(f"  📊 当前信号: 空仓 CASH")
    return out_path


def S_TOTAL(v):
    return "+" if v >= 0 else ""


if __name__ == "__main__":
    generate()
