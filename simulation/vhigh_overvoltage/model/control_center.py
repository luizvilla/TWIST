#!/usr/bin/env python3
"""Writes out/control-center.html: where the TWIST VHigh overvoltage study stands (Core2 control-center style).

Reads catalogue.json and the sim.log / summary.json of every campaign under out/; changes nothing else.
Usage: python3 -I control_center.py
"""
from pathlib import Path
import datetime as dt, fnmatch, html, json, re, sys

HERE = Path(__file__).resolve().parent
e = html.escape
STATES = [('fail', '✗', 'Failing'), ('known', '✗', 'Failing (known)'), ('pass', '✓', 'Passed'), ('info', 'i', 'Run (INFO only)'),
          ('not_run', '○', 'Not run yet'), ('planned', '◌', 'Not implemented')]
LABEL = {k: (i, w) for k, i, w in STATES}


def parse(log):
    rows = []
    for line in log.read_text().splitlines():
        f = line.split('\t')
        if len(f) >= 6 and f[0] == '@@':
            rows.append(dict(id=f[1], verdict=f[2], desc=f[3], limit=f[4], measured=f[5]))
    return rows


def campaigns(out):
    found = []
    for d in out.iterdir() if out.exists() else []:
        if d.is_dir() and (d / 'sim.log').exists():
            s = json.loads((d / 'summary.json').read_text()) if (d / 'summary.json').exists() else {'cases': {}}
            found.append({'dir': d, 'rows': parse(d / 'sim.log'), 'when': (d / 'sim.log').stat().st_mtime, 'summary': s})
    return sorted(found, key=lambda c: -c['when'])


def latest(camps):
    res = {}
    for c in camps:
        by = {}
        for r in c['rows']:
            by.setdefault(r['id'].split('.')[0], []).append(r)
        for cid, rows in by.items():
            res.setdefault(cid, (c, rows))
    return res


def finding_for(rid, findings):
    case = rid.split('.')[0]
    return next((f for f in findings if any(fnmatch.fnmatch(case, g) or fnmatch.fnmatch(rid, g) for g in f['criteria'])), None)


def state_of(t, res, findings):
    if res is None:
        return 'planned' if t['status'] == 'planned' else 'not_run'
    fails = [r for r in res[1] if r['verdict'] == 'FAIL']
    if fails:
        return 'known' if all(finding_for(r['id'], findings) for r in fails) else 'fail'
    return 'pass' if any(r['verdict'] == 'PASS' for r in res[1]) else 'info'


def ago(ts):
    d = dt.datetime.now() - dt.datetime.fromtimestamp(ts)
    if d.days:
        return f'{d.days} d ago'
    h = d.seconds // 3600
    return f'{h} h ago' if h else f'{d.seconds // 60} min ago'


def bar(counts):
    segs = ''.join(f'<span class="seg s-{k}" style="flex:{counts[k]}" title="{e(LABEL[k][1])}: {counts[k]}"></span>'
                   for k, _, _ in STATES if counts.get(k))
    return f'<div class="bar" role="img" aria-label="progress">{segs}</div>'


def summary_text(counts):
    return ' · '.join(f'{LABEL[k][0]} {counts[k]} {LABEL[k][1].lower()}' for k, _, _ in STATES if counts.get(k))


def badge(k):
    i, w = LABEL[k]
    return f'<span class="badge b-{k}">{i} {e(w)}</span>'


def peaks_svg(cat, res):
    """@brief Two aligned bar panels, one row per case: peak Vds(Q201) and peak |iL|, with the limits. Bars link to the case."""
    rows = []
    for tab in cat['tabs']:
        for t in cat['tests']:
            if t['tab'] == tab['id'] and t['id'] in res:
                c = res[t['id']][0]
                s = c['summary']['cases'].get(t['id'])
                if s:
                    rows.append((tab['title'], t, s, c))
    if not rows:
        return '<p class="sub">No campaign yet.</p>'
    W, lab, gap, rh = 980, 300, 40, 22
    pw = (W - lab - gap - 20) // 2
    vmin, vmax, imax = 80.0, 400.0, 90.0
    groups = []
    for g, *_ in rows:
        if g not in groups:
            groups.append(g)
    H = 40 + len(rows) * rh + len(groups) * 22 + 24
    xv = lambda v: lab + (min(max(v, vmin), vmax) - vmin) / (vmax - vmin) * pw
    xi = lambda i: lab + pw + gap + min(i, imax) / imax * pw
    o = [f'<svg class="peaks" viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Peak Vds and inductor current per case">']
    o.append(f'<text x="{lab}" y="14" class="ax">Peak Vds(Q201), V (axis {vmin:g} to {vmax:g})</text>'
             f'<text x="{lab + pw + gap}" y="14" class="ax">Peak |iL|, A (axis 0 to {imax:g})</text>')
    y = 30
    cur = None
    for g, t, s, c in rows:
        if g != cur:
            cur = g
            o.append(f'<text x="0" y="{y + 15}" class="grp">{e(g)}</text>')
            y += 22
        link = f'{e(c["dir"].name)}/report.html#{e(t["id"])}'
        vbad, ibad = s['vds_pk'] > 150, s['iL_pk'] > 40
        title = f'{t["id"]}: {t["title"]} | Vds {s["vds_pk"]:.1f} V, |iL| {s["iL_pk"]:.1f} A'
        o.append(f'<a href="{link}"><g class="row"><title>{e(title)}</title>'
                 f'<rect x="0" y="{y}" width="{W}" height="{rh}" class="hit"/>'
                 f'<text x="8" y="{y + 15}" class="lab"><tspan class="id">{e(t["id"])}</tspan> {e(t["title"][:38] + ("…" if len(t["title"]) > 38 else ""))}</text>'
                 f'<rect x="{lab}" y="{y + 4}" width="{xv(s["vds_pk"]) - lab:.1f}" height="{rh - 8}" class="{"bbad" if vbad else "bok"}"/>'
                 f'<text x="{xv(s["vds_pk"]) + 4:.1f}" y="{y + 15}" class="val">{s["vds_pk"]:.0f}{" ✗" if vbad else ""}</text>'
                 f'<rect x="{lab + pw + gap}" y="{y + 4}" width="{xi(s["iL_pk"]) - lab - pw - gap:.1f}" height="{rh - 8}" class="{"bbad" if ibad else "bok"}"/>'
                 f'<text x="{xi(s["iL_pk"]) + 4:.1f}" y="{y + 15}" class="val">{s["iL_pk"]:.0f}{" ✗" if ibad else ""}</text></g></a>')
        y += rh
    for k, (v, cls, lbl) in enumerate(((110, 'lim2', '110 V abs max'), (150, 'lim', '150 V FET rating'))):
        o.append(f'<line x1="{xv(v):.1f}" x2="{xv(v):.1f}" y1="20" y2="{y}" class="{cls}"/><text x="{xv(v) + 3:.1f}" y="{y + 12 + 12 * k}" class="ax">{lbl}</text>')
    o.append(f'<line x1="{xi(40):.1f}" x2="{xi(40):.1f}" y1="20" y2="{y}" class="lim"/><text x="{xi(40) + 3:.1f}" y="{y + 10}" class="ax">40 A</text>')
    o.append('</svg>')
    return ''.join(o)


def test_row(t, res, state, findings):
    when, det = '', []
    if t.get('purpose'):
        det.append(f'<p><b>Purpose.</b> {e(t["purpose"])}</p>')
    if t.get('params'):
        det.append(f'<p><b>Changed from base.</b> <code>{e(json.dumps(t["params"]))}</code></p>')
    issues = sorted({f['id'] for r in (res[1] if res else []) if r['verdict'] == 'FAIL' for f in [finding_for(r['id'], findings)] if f})
    if res:
        c = res[0]
        link = f'{e(c["dir"].name)}/report.html#{e(t["id"])}'
        when = f'<a href="{link}">{dt.datetime.fromtimestamp(c["when"]).strftime("%Y-%m-%d %H:%M")}</a><div class="sub">{ago(c["when"])}</div>'
        det.append('<table class="crit"><tr><th>Criterion</th><th>Verdict</th><th>Limit</th><th>Measured</th></tr>' + ''.join(
            f'<tr><td>{e(r["id"])}</td><td>{e(r["verdict"])}</td><td>{e(r["limit"])}</td><td>{e(r["measured"])}</td></tr>' for r in res[1]) + '</table>')
        det.append(f'<p><a href="{link}">Open the case in the review page (conditions, interactive figures)</a></p>')
        s = c['summary']['cases'].get(t['id'], {})
        key = f'{s["vds_pk"]:.0f} V · {s["iL_pk"]:.0f} A' if s else ''
    else:
        key = ''
    return (f'<tr class="r-{state}"><td class="id">{e(t["id"])}</td><td><details><summary>{e(t["title"])}</summary>{"".join(det)}</details></td>'
            f'<td>{badge(state)}{"".join(f" <span class=sub>{e(i)}</span>" for i in issues)}</td><td class="num">{e(key)}</td><td>{when}</td></tr>')


def page(cat, camps):
    findings = cat['findings']
    res = latest(camps)
    states = {t['id']: state_of(t, res.get(t['id']), findings) for t in cat['tests']}
    now = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    p = [f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TWIST simulation control center</title><style>
:root{{--bg:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--line:#e4e2dc;
--good:#008300;--bad:#d03b3a;--warn:#b07800;--none:#c9c7c0;--none2:#e9e7e1;--accent:#2a78d6;--hover:#f1efe9}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161615;--panel:#1e1e1c;--ink:#f1f0ec;--ink2:#b5b3ad;--muted:#8a8984;--line:#34332f;
--good:#3fb950;--bad:#f0605f;--warn:#e0a521;--none:#5a5953;--none2:#3a3935;--accent:#6aa7ee;--hover:#262624}}}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:1100px;margin:auto}} h1{{font-size:22px;margin:0}} h2{{font-size:18px;margin:28px 0 6px}}
.sub{{color:var(--ink2);font-size:13px}} a{{color:var(--accent)}}
.overview{{display:grid;gap:8px;margin:16px 0}} .ov{{display:grid;grid-template-columns:150px 1fr;gap:4px 16px;align-items:center;
 background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;cursor:pointer;text-align:left;font:inherit;color:inherit}}
.ov:hover{{border-color:var(--accent)}} .ov b{{font-size:15px}} .ov .sub{{grid-column:2}}
.bar{{display:flex;gap:2px;height:12px;border-radius:4px;overflow:hidden;background:var(--none2)}} .seg{{min-width:3px}}
.s-pass,.s-info{{background:var(--good)}} .s-fail,.s-known{{background:var(--bad)}} .s-not_run{{background:var(--none)}} .s-planned{{background:var(--none2)}}
.tabs{{display:flex;flex-wrap:wrap;gap:4px;border-bottom:2px solid var(--line);margin-top:24px}}
.tabs button{{font:inherit;font-size:14px;background:none;border:0;border-bottom:3px solid transparent;margin-bottom:-2px;padding:6px 12px;cursor:pointer;color:var(--ink2)}}
.tabs button[aria-selected=true]{{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}}
section[hidden]{{display:none}} .q{{margin:12px 0 4px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}} table.tests{{table-layout:fixed}} table.tests col.c1{{width:96px}} table.tests col.c3{{width:160px}} table.tests col.c4{{width:110px}} table.tests col.c5{{width:120px}}
td,th{{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}} td.num{{font-variant-numeric:tabular-nums;white-space:nowrap}}
th{{color:var(--ink2);font-weight:600}} td.id{{white-space:nowrap;font-family:ui-monospace,monospace;font-size:12px}}
details summary{{cursor:pointer}} details p{{margin:6px 0;color:var(--ink2)}} details[open] summary{{font-weight:600}}
table.crit{{margin:6px 0 10px;font-size:12px}} code{{font-size:12px;word-break:break-all}}
.badge{{display:inline-block;padding:0 8px;border-radius:10px;font-size:12px;font-weight:600;border:1px solid var(--line);white-space:nowrap}}
.b-pass,.b-info{{color:var(--good)}} .b-fail{{background:var(--bad);color:#fff;border-color:var(--bad)}} .b-known{{color:var(--bad);border-color:var(--bad)}}
.b-not_run,.b-planned{{color:var(--ink2)}}
.wrap{{overflow-x:auto}} .latest,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 14px;margin:12px 0}}
.latest ul{{margin:4px 0;padding-left:18px}} .note{{border-left:3px solid var(--line);padding:2px 12px;color:var(--ink2);font-size:13px;margin:8px 0}}
svg.peaks{{min-width:760px;font:12px system-ui,sans-serif}} svg.peaks .lab{{fill:var(--ink)}} svg.peaks .id{{font-family:ui-monospace,monospace;fill:var(--ink2)}}
svg.peaks .grp{{fill:var(--ink2);font-weight:600;text-transform:uppercase;letter-spacing:.04em;font-size:11px}} svg.peaks .ax{{fill:var(--ink2);font-size:11px}}
svg.peaks .val{{fill:var(--ink);font-variant-numeric:tabular-nums}} svg.peaks .bok{{fill:var(--accent)}} svg.peaks .bbad{{fill:var(--bad)}}
svg.peaks .hit{{fill:transparent}} svg.peaks a:hover .hit{{fill:var(--hover)}}
svg.peaks .lim{{stroke:var(--bad);stroke-dasharray:6 4}} svg.peaks .lim2{{stroke:var(--ink2);stroke-dasharray:8 3 2 3}}
@media (max-width:640px){{.ov{{grid-template-columns:1fr}} .ov .sub{{grid-column:1}}}}
</style></head><body><main>
<h1>TWIST simulation control center</h1>
<div class="sub">Generated {e(now)} · catalogue {e(cat["version"])} (<code>catalogue.json</code>) · simulation code: <code>simulation/vhigh_overvoltage/model</code> · run: <code>python3 -I run_campaign.py</code> · regenerate: <code>python3 -I control_center.py</code> · investigation notes: <a href="../README.md">README.md</a></div>
<p class="q">{e(cat["title"])}. Why did high-side FETs die when VHigh was disconnected, and what protection prevents it? Level D cases run the averaged model of one leg; level L2 cases are bench confirmations still to run. A test's result is its newest campaign.</p>
''']
    p.append('<div class="latest"><b>Latest runs</b> <span class="sub">(newest first; reload after a run)</span><ul>' + ''.join(
        f'<li><a href="{e(c["dir"].name)}/report.html">{e(c["dir"].name)}</a> <span class="sub">{ago(c["when"])} · '
        + ' · '.join(f'{sum(r["verdict"] == v for r in c["rows"])} {v}' for v in ('PASS', 'FAIL', 'INFO')) + '</span></li>'
        for c in camps[:5]) + '</ul></div>')
    p.append('<div class="overview">')
    for tab in cat['tabs']:
        tests = [t for t in cat['tests'] if t['tab'] == tab['id']]
        counts = {k: sum(states[t['id']] == k for t in tests) for k, _, _ in STATES}
        p.append(f'<button class="ov" data-go="{e(tab["id"])}"><b>{e(tab["title"])}</b>{bar(counts)}<span class="sub">{len(tests)} tests: {e(summary_text(counts))}</span></button>')
    p.append('</div><div class="sub">Legend: ✓ passed · ✗ failing (filled: new, outlined: known finding) · ○ implemented, not run yet · ◌ not implemented</div>')
    tabs = [('summary', 'Summary')] + [(t['id'], t['title']) for t in cat['tabs']] + [('runs', 'Runs')]
    p.append('<nav class="tabs" role="tablist">' + ''.join(f'<button role="tab" data-tab="{e(i)}" aria-selected="false">{e(n)}</button>' for i, n in tabs) + '</nav>')
    # Summary tab
    p.append('<section id="tab-summary" hidden><h2>Peak stress per case</h2><p class="sub">Newest result of each case. '
             'Red bars cross a limit; dashed lines: 150 V FET rating (red), 110 V absolute maximum of VHigh (dash-dot), 40 A. Values beyond the axis are drawn to its end and written in full. '
             'Click a row to open the case with its interactive figures.</p><div class="wrap panel">' + peaks_svg(cat, res) + '</div>')
    p.append('<h2>Field failures and the cases that model them</h2><div class="wrap"><table><tr><th>Field failure</th><th>Cases</th><th>Note</th></tr>')
    for ff in cat['field_failures']:
        cells = []
        for cid in ff['cases']:
            st = states.get(cid, 'not_run')
            link = f'{e(res[cid][0]["dir"].name)}/report.html#{e(cid)}' if cid in res else '#'
            cells.append(f'<a href="{link}"><code>{e(cid)}</code></a> {badge(st)}')
        p.append(f'<tr><td>{e(ff["what"])}</td><td>{"<br>".join(cells) or "—"}</td><td class="sub">{e(ff.get("note", ""))}</td></tr>')
    p.append('</table></div><h2>Findings</h2><div class="wrap"><table><tr><th>ID</th><th>Finding</th><th>Cases failing on it</th></tr>')
    for f in findings:
        hits = sorted({t['id'] for t in cat['tests'] if t['id'] in res and any(r['verdict'] == 'FAIL' and finding_for(r['id'], [f]) for r in res[t['id']][1])})
        p.append(f'<tr><td class="id">{e(f["id"])}</td><td>{e(f["title"])}</td><td>{e(", ".join(hits)) or "none"}</td></tr>')
    p.append('</table></div></section>')
    for tab in cat['tabs']:
        tests = [t for t in cat['tests'] if t['tab'] == tab['id']]
        counts = {k: sum(states[t['id']] == k for t in tests) for k, _, _ in STATES}
        p.append(f'<section id="tab-{e(tab["id"])}" hidden><p class="q"><b>{e(tab["question"])}</b></p>{bar(counts)}<div class="sub">{len(tests)} tests: {e(summary_text(counts))}</div>')
        for note in tab.get('notes', []):
            p.append(f'<div class="note">{e(note)}</div>')
        for lv, name in (('D', 'D · averaged model: fast evaluation of ideas, never a verdict on the board'), ('L2', 'L2 · on the board (bench)')):
            rows = [t for t in tests if t['level'] == lv]
            if not rows:
                continue
            p.append(f'<h2>{e(name)}</h2><div class="wrap"><table class="tests"><colgroup><col class="c1"><col><col class="c3"><col class="c4"><col class="c5"></colgroup>'
                     '<tr><th>ID</th><th>Case (click for definition and results)</th><th>State</th><th>Peaks</th><th>Last run</th></tr>')
            for t in rows:
                p.append(test_row(t, res.get(t['id']), states[t['id']], findings))
            p.append('</table></div>')
        p.append('</section>')
    p.append('<section id="tab-runs" hidden><h2>Campaigns</h2><div class="wrap"><table><tr><th>Campaign</th><th>When</th><th>Results</th><th>Files</th></tr>')
    for c in camps[:30]:
        v = {k: sum(r['verdict'] == k for r in c['rows']) for k in ('PASS', 'FAIL', 'INFO')}
        n = e(c['dir'].name)
        p.append(f'<tr><td><a href="{n}/report.html">{n}</a></td><td>{dt.datetime.fromtimestamp(c["when"]).strftime("%Y-%m-%d %H:%M")}</td>'
                 f'<td>{v["PASS"]} PASS · {v["FAIL"]} FAIL · {v["INFO"]} INFO</td>'
                 f'<td><a href="{n}/record.md">record.md</a> · <a href="{n}/sim.log">sim.log</a> · <a href="{n}/summary.json">summary.json</a> · <a href="{n}/traces/">traces/</a></td></tr>')
    p.append('</table></div></section>')
    p.append('''<script>
const tabs=[...document.querySelectorAll('[data-tab]')];
function show(id){if(!document.getElementById('tab-'+id))id=tabs[0].dataset.tab;
 tabs.forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===id));
 document.querySelectorAll('section[id^=tab-]').forEach(s=>s.hidden=s.id!=='tab-'+id);
 try{history.replaceState(null,'','#'+id)}catch(_){}}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.tab));
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>{show(b.dataset.go);document.querySelector('.tabs').scrollIntoView()});
show(location.hash.slice(1));
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));
</script></main></body></html>''')
    return '\n'.join(p)


def write(out):
    cat = json.loads((HERE / 'catalogue.json').read_text())
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'control-center.html'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(page(cat, campaigns(out)), encoding='utf-8')
    tmp.replace(target)
    return target


if __name__ == '__main__':
    sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'common'))
    from run_campaign import OUT
    print(write(OUT))
