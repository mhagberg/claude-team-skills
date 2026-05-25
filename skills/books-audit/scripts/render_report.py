#!/usr/bin/env python3
"""Render the consolidated books-audit findings to a styled, self-contained HTML
report and open it in the browser.

The orchestrator (Claude) assembles the 10 agents' returns into a JSON file and
calls this renderer. Every actionable finding carries an `action` string — a
ready-to-paste Claude Code prompt — rendered with a one-click Copy button so the
user can paste it straight back into Claude Code to execute the fix.

Usage:
    python render_report.py <findings.json> [out.html]   # default: /tmp/books_audit_report.html

findings.json schema (all keys optional; renderer is defensive):
{
  "generated": "2026-05-25T16:00:00",
  "companies": [
    {"name":"Xcel Software","company_id":1,"balanced":true,
     "revenue":216285.12,"expenses":93653.94,"net_income":122631.18,
     "margin":"56.7%","drafts":"1 draft bill"}
  ],
  "rating_spread": {"min":3,"median":6,"max":8},
  "ratings": [{"n":1,"lens":"Trial-balance integrity","rating":8,"top_finding":"..."}],
  "sections": [
    {"title":"Critical Issues",
     "items":[{"severity":"CRITICAL","company":"Hagberg","text":"...","action":"<paste-ready prompt>"}]}
  ],
  "tax_opportunities":[{"text":"...","est_savings":"~$17k-$23k","rule":"IRC §179","action":"..."}],
  "tax_red_flags":[{"text":"...","exposure":"high"}],
  "cfo_perspective":{"summary":"...","recommendations":[{"text":"...","action":"..."}]},
  "biggest_action":{"text":"...","action":"..."}
}
"""
import html
import json
import platform
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

SEV_CLASS = {
    "CRITICAL": "sev-critical", "HIGH": "sev-high", "MEDIUM": "sev-medium",
    "LOW": "sev-low", "INFO": "sev-info", "OPP": "sev-opp", "CROSS-LENS": "sev-info",
}

CSS = """
:root{--bg:#0f1419;--card:#1a2230;--ink:#e6edf3;--muted:#9aa7b4;--line:#2a3543;
--crit:#ff4d4f;--high:#ff8c42;--med:#ffd23f;--low:#7d8b99;--info:#4aa3ff;--opp:#3ecf8e;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px 80px;}
h1{font-size:26px;margin:0 0 4px} h2{font-size:19px;margin:34px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);font-size:13px;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--opp)} .neg{color:var(--crit)}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:.03em}
.sev-critical{background:rgba(255,77,79,.15);color:var(--crit);border:1px solid var(--crit)}
.sev-high{background:rgba(255,140,66,.15);color:var(--high);border:1px solid var(--high)}
.sev-medium{background:rgba(255,210,63,.13);color:var(--med);border:1px solid var(--med)}
.sev-low{background:rgba(125,139,153,.15);color:var(--low);border:1px solid var(--low)}
.sev-info{background:rgba(74,163,255,.13);color:var(--info);border:1px solid var(--info)}
.sev-opp{background:rgba(62,207,142,.13);color:var(--opp);border:1px solid var(--opp)}
.item{margin:14px 0;padding:14px 16px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px}
.item.sev-critical{border-left-color:var(--crit)} .item.sev-high{border-left-color:var(--high)}
.item.sev-medium{border-left-color:var(--med)} .item.sev-opp{border-left-color:var(--opp)}
.item.sev-low{border-left-color:var(--low)} .item.sev-info{border-left-color:var(--info)}
.item .co{color:var(--muted);font-size:12px;font-weight:600;margin-left:6px}
.item .txt{margin:6px 0 0}
.action{margin-top:10px}
.action-head{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);margin-bottom:4px}
.action pre{margin:0;background:#0b0f14;border:1px solid var(--line);border-radius:6px;padding:10px 12px;
white-space:pre-wrap;word-break:break-word;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#cfe3ff}
button.copy{cursor:pointer;background:#243042;color:var(--ink);border:1px solid var(--line);
border-radius:6px;padding:3px 10px;font-size:12px;font-weight:600}
button.copy:hover{background:#2e3c52}
.spread{display:flex;gap:18px;margin:6px 0 0}
.spread div{font-size:13px;color:var(--muted)} .spread b{color:var(--ink);font-size:18px}
.kpi{font-size:22px;font-weight:700}
.big{background:linear-gradient(135deg,#1a2230,#22304a);border:1px solid var(--info);border-radius:10px;padding:18px;margin-top:18px}
.big .lbl{color:var(--info);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.footer{color:var(--muted);font-size:12px;margin-top:40px;text-align:center}
@media print{body{background:#fff;color:#000}.card,.item{break-inside:avoid}}
"""

JS = """
function copyText(btn){
  var pre = btn.closest('.action').querySelector('pre');
  var text = pre.innerText;
  function done(){btn.textContent='Copied ✓';setTimeout(function(){btn.textContent='Copy';},1500);}
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, fallback);
  } else { fallback(); }
  function fallback(){
    var ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);
    ta.select();try{document.execCommand('copy');done();}catch(e){}document.body.removeChild(ta);
  }
}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def money(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return esc(v)


def action_block(action):
    if not action:
        return ""
    return (
        '<div class="action"><div class="action-head">📋 Action — paste into Claude Code'
        '<button class="copy" onclick="copyText(this)">Copy</button></div>'
        f'<pre>{esc(action)}</pre></div>'
    )


def render(data):
    p = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>Books Audit Report</title>',
         f"<style>{CSS}</style></head><body><div class='wrap'>"]
    gen = data.get("generated") or datetime.now().isoformat(timespec="seconds")
    p.append("<h1>📋 Books Audit Report</h1>")
    p.append(f"<div class='sub'>Generated {esc(gen)} · read-only snapshot · nothing in Odoo was modified</div>")

    # Balance + P&L
    comps = data.get("companies", [])
    if comps:
        p.append("<h2>Balance &amp; P&amp;L</h2><div class='card'><table>")
        p.append("<tr><th>Company</th><th>Balanced</th><th class='num'>Revenue</th>"
                 "<th class='num'>Expenses</th><th class='num'>Net income</th>"
                 "<th class='num'>Margin</th><th>Drafts</th></tr>")
        for c in comps:
            ni = c.get("net_income", 0) or 0
            nicls = "pos" if (isinstance(ni, (int, float)) and ni >= 0) else "neg"
            bal = "✅" if c.get("balanced") else "⚠️"
            p.append(
                f"<tr><td>{esc(c.get('name'))}</td><td>{bal}</td>"
                f"<td class='num'>{money(c.get('revenue'))}</td>"
                f"<td class='num'>{money(c.get('expenses'))}</td>"
                f"<td class='num {nicls}'>{money(ni)}</td>"
                f"<td class='num'>{esc(c.get('margin'))}</td>"
                f"<td>{esc(c.get('drafts'))}</td></tr>")
        p.append("</table></div>")

    # Ratings
    ratings = data.get("ratings", [])
    if ratings:
        sp = data.get("rating_spread", {})
        p.append("<h2>Auditor ratings</h2>")
        if sp:
            p.append(f"<div class='spread'><div>min <b>{esc(sp.get('min'))}</b></div>"
                     f"<div>median <b>{esc(sp.get('median'))}</b></div>"
                     f"<div>max <b>{esc(sp.get('max'))}</b></div></div>")
        p.append("<div class='card'><table><tr><th>#</th><th>Lens</th><th class='num'>Rating</th><th>Top finding</th></tr>")
        for r in ratings:
            p.append(f"<tr><td>{esc(r.get('n'))}</td><td>{esc(r.get('lens'))}</td>"
                     f"<td class='num'>{esc(r.get('rating'))}/10</td><td>{esc(r.get('top_finding'))}</td></tr>")
        p.append("</table></div>")

    # Finding sections
    for sec in data.get("sections", []):
        p.append(f"<h2>{esc(sec.get('title'))}</h2>")
        for it in sec.get("items", []):
            sev = (it.get("severity") or "INFO").upper()
            cls = SEV_CLASS.get(sev, "sev-info")
            co = f"<span class='co'>{esc(it.get('company'))}</span>" if it.get("company") else ""
            p.append(f"<div class='item {cls}'><span class='badge {cls}'>{esc(sev)}</span>{co}"
                     f"<div class='txt'>{esc(it.get('text'))}</div>{action_block(it.get('action'))}</div>")

    # Tax opportunities
    opps = data.get("tax_opportunities", [])
    if opps:
        p.append("<h2>💰 Tax opportunities</h2>")
        for o in opps:
            head = esc(o.get("text"))
            meta = " · ".join(x for x in [o.get("est_savings"), o.get("rule")] if x)
            p.append(f"<div class='item sev-opp'><span class='badge sev-opp'>OPP</span>"
                     f"<div class='txt'>{head}{(' — <b>' + esc(o.get('est_savings')) + '</b>') if o.get('est_savings') else ''}"
                     f"{(' · ' + esc(o.get('rule'))) if o.get('rule') else ''}</div>{action_block(o.get('action'))}</div>")

    # Red flags
    flags = data.get("tax_red_flags", [])
    if flags:
        p.append("<h2>🚩 Tax red flags</h2><div class='card'><ol>")
        for f in flags:
            ex = f" — <span class='neg'>{esc(f.get('exposure'))}</span>" if f.get("exposure") else ""
            p.append(f"<li>{esc(f.get('text'))}{ex}</li>")
        p.append("</ol></div>")

    # CFO/CTO
    cfo = data.get("cfo_perspective")
    if cfo:
        p.append("<h2>🎯 CFO/CTO perspective</h2>")
        p.append(f"<div class='card'>{esc(cfo.get('summary'))}</div>")
        for r in cfo.get("recommendations", []):
            p.append(f"<div class='item sev-info'><div class='txt'>{esc(r.get('text'))}</div>{action_block(r.get('action'))}</div>")

    # Biggest action
    big = data.get("biggest_action")
    if big:
        p.append("<div class='big'><div class='lbl'>⚡ Biggest single action this week</div>"
                 f"<div class='txt' style='margin-top:6px'>{esc(big.get('text'))}</div>{action_block(big.get('action'))}</div>")

    p.append("<div class='footer'>Generated by the books-audit skill · read-only · re-run any time</div>")
    p.append("</div><script>" + JS + "</script></body></html>")
    return "".join(p)


def main():
    if len(sys.argv) < 2:
        print("usage: render_report.py <findings.json> [out.html]")
        sys.exit(1)
    data = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/books_audit_report.html")
    out.write_text(render(data))
    print(f"[report written to {out}]")
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", str(out)], check=False)
        elif platform.system() == "Windows":
            subprocess.run(["cmd", "/c", "start", "", str(out)], check=False)
        else:
            webbrowser.open(f"file://{out}")
        print(f"[opened {out}]")
    except Exception as e:
        print(f"[could not auto-open: {e!r}] open it manually: {out}")


if __name__ == "__main__":
    main()
