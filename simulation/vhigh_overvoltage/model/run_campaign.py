#!/usr/bin/env python3
"""Runs every implemented D-level case of catalogue.json as one campaign, in the style of Core2 tests/.

Writes $TWIST_SIM_OUT/<date>_<time>_sim/ (default: TWIST/simulation/vhigh_overvoltage/results) : sim.log (@@ result lines), record.md, summary.json, traces/<ID>.npz,
report.html (per case: 1 conditions and objectives, 2 model snapshot, 3 results, 4 interactive figures),
then regenerates control-center.html there.

Usage: python3 -I run_campaign.py [ID ...]      (no ID: every implemented case)
"""
from pathlib import Path
import datetime as dt, fnmatch, hashlib, html, json, multiprocessing as mp, sys, time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'common'))
import model  # noqa: E402
import interactive_plot as ip  # noqa: E402

e = html.escape
import os
# In the repository the results sit next to this folder; a working copy elsewhere writes to the repository.
OUT = Path(os.environ.get('TWIST_SIM_OUT') or (HERE.parent / 'results' if (HERE.parent / 'results').is_dir()
           else '/home/luiz-villa/Documents/HARDWARE/TWIST/simulation/vhigh_overvoltage/results'))
BLUE, ORANGE, GREEN, AMBER = ip.SERIES
INK, INK2, MUTED, GRID = '#0b0b0b', '#52514e', '#8a8984', '#e4e2dc'
SURFACE, CRITICAL, GOOD = '#fcfcfb', '#e34948', '#008300'

UNITS = {'L': ('uH', 1e6), 'C_H': ('uF', 1e6), 'Vs': ('V', 1), 'R_cab': ('ohm', 1), 'L_cab': ('uH', 1e6),
         'V_low': ('V', 1), 'R_low': ('ohm', 1), 'C_low': ('uF', 1e6), 'R_load': ('ohm', 1), 'C_mot': ('F', 1),
         'R_mot': ('ohm', 1), 'I_ref': ('A', 1), 't_dis': ('ms', 1e3), 't_step': ('ms', 1e3), 'ov_trip': ('V', 1),
         'trip_delay': ('us', 1e6), 'v_clamp': ('V', 1), 'i_limit': ('A', 1), 'duty_slew': ('1/ms', 1e-3),
         'V_feeder_min': ('V', 1), 'dt': ('ns', 1e9), 't_end': ('ms', 1e3), 'R_L': ('ohm', 1)}
LOW_TEXT = {'battery': 'battery (stiff source, series R_low)', 'cap': 'C_low || R_load (passive load)',
            'motor': 'motor + rider as equivalent capacitor C_mot (kinetic energy), series R_mot'}


def load_catalogue():
    return json.loads((HERE / 'catalogue.json').read_text())


def fmt(k, v):
    if v is None:
        return 'none'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, (int, float)) and k in UNITS:
        u, s = UNITS[k]
        return f'{v * s:g} {u}'
    return str(v)


def _run(item):
    tid, params = item
    t0 = time.time()
    r = model.run(params)
    r['wall'] = time.time() - t0
    return tid, r


def criteria(t, r):
    """@return result rows for one case: id, verdict, desc, limit, measured."""
    p = r['p']; rows = []
    a = r['vds_pk'] <= p['V_rating']
    rows.append(dict(id=f"{t['id']}.a", verdict='PASS' if a else 'FAIL', desc='Peak Vds(Q201) stays under the FET rating',
                     limit=f"<= {p['V_rating']:g} V", measured=f"{r['vds_pk']:.1f} V"))
    b = r['iL_pk'] <= p['I_rating']
    rows.append(dict(id=f"{t['id']}.b", verdict='PASS' if b else 'FAIL', desc='Peak |iL| stays under the L201/FET limit',
                     limit=f"<= {p['I_rating']:g} A", measured=f"{r['iL_pk']:.1f} A"))
    rows.append(dict(id=f"{t['id']}.c", verdict='INFO', desc='Margin to the 110 V absolute maximum of VHigh',
                     limit='', measured=f"{r['vds_pk'] - p['V_absmax']:+.1f} V"))
    ev = []
    if r['t_150'] is not None:
        ev.append(f"150 V crossed at {r['t_150'] * 1e3:.3f} ms")
    if r['trip_t'] is not None:
        ev.append(f"OV trip at {r['trip_t'] * 1e3:.3f} ms")
    tr = r['traces']; k = max(1, len(tr['t']) // 10)
    slope = (tr['vH'][-1] - tr['vH'][-k]) / (tr['t'][-1] - tr['t'][-k]) / 1e3
    ev.append(f"VHigh {tr['vH'][-1]:.1f} V at the end, {slope:+.1f} V/ms over the last 10 %"
              + (' (still rising: the run stops before the peak)' if slope > 0.5 else ''))
    rows.append(dict(id=f"{t['id']}.d", verdict='INFO', desc='Events and VHigh at the end of the run', limit='',
                     measured='; '.join(ev)))
    if p['v_clamp'] is not None:
        ok = r['e_clamp'] <= p['E_clamp_max']
        rows.append(dict(id=f"{t['id']}.e", verdict='PASS' if ok else 'FAIL',
                         desc='Energy dissipated by Q201 as a clamp (order of a single-pulse avalanche rating; to confirm on the IPD200N15N3 datasheet)',
                         limit=f"<= {p['E_clamp_max'] * 1e3:g} mJ",
                         measured=f"{r['e_clamp'] * 1e3:.0f} mJ, peak {r['p_clamp_pk'] / 1e3:.1f} kW"))
    return rows


def finding_for(rid, findings):
    case = rid.split('.')[0]
    return next((f for f in findings if any(fnmatch.fnmatch(case, g) or fnmatch.fnmatch(rid, g) for g in f['criteria'])), None)


def figure(t, r):
    p, tr = r['p'], r['traces']
    tm = tr['t'] * 1e3
    f = ip.Figure('ms')
    events = []
    if p['t_dis'] is not None and p['t_dis'] < p['t_end']:
        events.append({'t': p['t_dis'] * 1e3, 'label': 'supply disconnected'})
    if p['d_step'] is not None:
        events.append({'t': p['t_step'] * 1e3, 'label': f"duty step {p['d0']:g} to {p['d_step']:g}"})
    if r['trip_t'] is not None:
        events.append({'t': r['trip_t'] * 1e3, 'label': 'OV trip: PWM off'})
    if r['t_150'] is not None:
        events.append({'t': r['t_150'] * 1e3, 'label': '150 V crossed'})
    c = f.chart('V', 240)
    f.line(c, 'VHigh = Vds(Q201) while off (V)', tm, tr['vH'], BLUE, 2.5)
    f.line(c, 'supply set point (V)', tm, [p['Vs']] * len(tm), MUTED, 1, [6, 4])
    c['hlines'] = [{'v': p['V_rating'], 'color': CRITICAL, 'dash': [6, 4]},
                   {'v': p['V_absmax'], 'color': INK2, 'dash': [8, 3, 2, 3]}]
    if p['ov_trip'] is not None:
        c['hlines'].append({'v': p['ov_trip'], 'color': AMBER, 'dash': [2, 3]})
    c['events'] = events
    c2 = f.chart('A', 170)
    f.line(c2, 'iL L201 (A, + = buck)', tm, tr['iL'], BLUE, 2)
    f.line(c2, 'supply current (A)', tm, tr['iC'], ORANGE, 1.2)
    c2['hlines'] = [{'v': p['I_rating'], 'color': CRITICAL, 'dash': [6, 4]}, {'v': -p['I_rating'], 'color': CRITICAL, 'dash': [6, 4]}]
    c2['events'] = events
    c3 = f.chart('duty', 110)
    f.line(c3, 'duty d (gap: PWM off)', tm, tr['d'], GREEN, 1.5)
    c3['events'] = events
    if p['low'] != 'battery':
        c4 = f.chart('V', 110)
        f.line(c4, 'low-side voltage (V)', tm, tr['vL'], AMBER, 1.5)
        c4['events'] = events
    if p['v_clamp'] is not None:
        c5 = f.chart('kW', 130)
        f.line(c5, 'power dissipated in Q201 by the clamp (kW)', tm, tr['p_clamp'] / 1e3, CRITICAL, 1.5)
        c5['events'] = events
    return f.html(t['id'], f"{t['title']}: VHigh, inductor current and duty against time")


CAPTION = ('Top: VHigh, which Q201 sees across drain and source while it is off (thick blue); supply set point thin grey dashed; '
           'red dashed 150 V FET rating; dash-dot 110 V absolute maximum of VHigh; amber dotted the OV trip threshold when there is one. '
           'Middle: L201 current (blue) with its +/-40 A limits and the supply current (orange; it never goes negative, the lab supply cannot sink). '
           'Then the duty (gaps: PWM stopped) and, when present, the low-side voltage and the clamp power. Dotted verticals are events. '
           'Drag to zoom: all panels follow.')


def page_head(title):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>
:root{{color-scheme:light;--bg:{SURFACE};--ink:{INK};--ink2:{INK2};--line:{GRID};--bad:{CRITICAL};--good:{GOOD}}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;}}
main{{max-width:1000px;margin:auto}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:19px;margin:40px 0 4px;border-bottom:2px solid var(--line);padding-bottom:4px}}
h3{{font-size:15px;margin:20px 0 6px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em}}
.sub{{color:var(--ink2);font-size:13px}} .banner{{border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:16px 0}}
.banner.bad{{border-color:var(--bad)}} .counts span{{margin-right:18px;font-weight:600}} .purpose{{margin:6px 0 4px}}
.badge{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;border:1px solid var(--line);white-space:nowrap}}
.badge.pass{{color:var(--good)}} .badge.fail{{color:var(--bad)}} .badge.new{{background:var(--bad);color:#fff;border-color:var(--bad)}}
.badge.info{{color:var(--ink2)}} figure{{margin:12px 0 24px}} figcaption{{font-size:13px;color:var(--ink2)}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:4px 0}}
td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}} th{{color:var(--ink2);font-weight:600}}
table.kv td:first-child{{width:200px;color:var(--ink2)}} .check li{{margin:4px 0}} code{{font-size:12px}}
.wrap{{overflow-x:auto}} nav a{{margin-right:12px;font-size:13px}} .cols{{columns:2 320px}}
</style></head><body><main>
'''


def badge(r):
    v = r['verdict']
    tag = f" (known {r['finding']['id']})" if r.get('finding') else (' NEW' if v == 'FAIL' else '')
    cls = {'PASS': 'pass', 'FAIL': 'fail', 'INFO': 'info'}[v]
    icon = {'PASS': '✓', 'FAIL': '✗', 'INFO': 'i'}[v]
    return f'<span class="badge {cls}{" new" if tag == " NEW" else ""}">{icon} {v}{e(tag)}</span>'


def report(cat, camp, results, rows_by, snapshot):
    tests = {t['id']: t for t in cat['tests']}
    allrows = [r for rs in rows_by.values() for r in rs]
    cnt = {v: sum(r['verdict'] == v for r in allrows) for v in ('PASS', 'FAIL', 'INFO')}
    new = [r for r in allrows if r['verdict'] == 'FAIL' and not r.get('finding')]
    known = [r for r in allrows if r['verdict'] == 'FAIL' and r.get('finding')]
    p = [page_head(f'Review {camp.name}'),
         f'<h1>Review: {e(cat["title"])}</h1><div class="sub">Campaign <code>{e(camp.name)}</code> · level D (averaged model: '
         'fast evaluation of ideas, never a verdict on the board) · <a href="../control-center.html">control center</a></div>',
         f'<div class="banner{" bad" if new else ""}"><div class="counts"><span>✓ {cnt["PASS"]} PASS</span><span>✗ {cnt["FAIL"]} FAIL '
         f'({len(known)} known, {len(new)} new)</span><span>i {cnt["INFO"]} INFO</span></div>'
         f'<div class="sub">Known failures are the field failures the model is meant to reproduce (findings '
         + ', '.join(f'{e(f["id"])}' for f in cat['findings']) + '). A new failure is a surprise and needs a look.</div></div>']
    p.append('<nav><b>Test cases:</b> ' + ' '.join(
        f'<a href="#{e(tid)}">{"✗ " if any(r["verdict"] == "FAIL" for r in rows_by[tid]) else ""}{e(tid)}</a>' for tid in results) + '</nav>')
    p.append('''<h3>How to review</h3><ol class="check">
<li><b>Banner.</b> No new failures, and the known ones are the field failures?</li>
<li><b>Each case:</b> read the purpose and conditions before the plots; check the blue trace against the dashed limits.</li>
<li><b>Remember the model.</b> Averaged over a switching period: no ripple, no ringing, no device heating. It shows where the energy goes, not what the scope will show.</li></ol>''')
    for tid, r in results.items():
        t = tests[tid]; pr = r['p']; rows = rows_by[tid]
        bad = any(x['verdict'] == 'FAIL' for x in rows)
        p.append(f'<h2 id="{e(tid)}">{"✗ " if bad else ""}{e(tid)} · {e(t["title"])}</h2><p class="purpose">{e(t.get("purpose", ""))}</p>')
        p.append('<h3>1 · Test conditions and objectives</h3><div class="wrap"><table class="kv">')
        cond = [('Control', 'PI current loop on iL, reference ' + fmt('I_ref', pr['I_ref']) + (' (negative: power into VHigh)' if pr['I_ref'] < 0 else '')
                 if pr['mode'] == 'current' else f"open-loop duty {pr['d0']:g}" + (f" stepped to {pr['d_step']:g} at {fmt('t_step', pr['t_step'])}" if pr['d_step'] is not None else '')),
                ('Low side', LOW_TEXT[pr['low']] + ', ' + ', '.join(fmt(k, pr[k]) for k in
                    {'battery': ('V_low', 'R_low'), 'cap': ('C_low', 'R_load'), 'motor': ('V_low', 'C_mot', 'R_mot')}[pr['low']])),
                ('Supply on VHigh', f"{fmt('Vs', pr['Vs'])}, " + ('can sink current' if pr['psu_can_sink'] else 'cannot sink current (lab supply)')
                 + (f", disconnected at {fmt('t_dis', pr['t_dis'])}" if pr['t_dis'] is not None else ', stays connected')),
                ('Protection', ', '.join(x for x in [
                    f"OV trip {fmt('ov_trip', pr['ov_trip'])} after {fmt('trip_delay', pr['trip_delay'])}" if pr['ov_trip'] is not None else '',
                    f"duty slew {fmt('duty_slew', pr['duty_slew'])}" if pr['duty_slew'] is not None else '',
                    f"cycle-by-cycle current limit {fmt('i_limit', pr['i_limit'])}" if pr['i_limit'] is not None else '',
                    f"active clamp Q201 drain-gate at {fmt('v_clamp', pr['v_clamp'])}" if pr['v_clamp'] is not None else ''] if x) or 'none (current firmware)'),
                ('Self-supply', f"Feeder powered from VHigh (JP5001): PWM runs while VHigh > {fmt('V_feeder_min', pr['V_feeder_min'])}"),
                ('Simulated', f"{fmt('t_end', pr['t_end'])}, step {fmt('dt', pr['dt'])}, computed in {r['wall']:.1f} s")]
        for k, v in cond:
            p.append(f'<tr><td>{e(k)}</td><td>{e(v)}</td></tr>')
        p.append('</table></div><table><tr><th>Objective</th><th>What is checked</th><th>Limit</th></tr>')
        for x in rows:
            p.append(f'<tr><td>{e(x["id"])}</td><td>{e(x["desc"])}</td><td>{e(x["limit"])}</td></tr>')
        p.append('</table>')
        p.append('<h3>2 · Model snapshot</h3><div class="wrap"><table class="kv">'
                 f'<tr><td>Model</td><td><code>model.py</code> sha1 {e(snapshot["model_sha"][:12])}</td></tr>'
                 f'<tr><td>Leg</td><td>L201 {fmt("L", pr["L"])} ({fmt("R_L", pr["R_L"])}), VHigh caps {fmt("C_H", pr["C_H"])}, '
                 f'cable {fmt("L_cab", pr["L_cab"])} / {fmt("R_cab", pr["R_cab"])}</td></tr>'
                 f'<tr><td>Vds spike</td><td>{pr["L_loop"] * 1e9:g} nH loop x {pr["di_dt"] / 1e9:g} A/ns added while Q201 switches off load current</td></tr>'
                 f'<tr><td>Changed from base</td><td><code>{e(json.dumps(t["params"]))}</code></td></tr></table></div>')
        p.append('<h3>3 · Results</h3><table><tr><th>Criterion</th><th>Verdict</th><th>Measured</th></tr>')
        for x in rows:
            p.append(f'<tr><td>{e(x["id"])}</td><td>{badge(x)}</td><td>{e(x["measured"])}</td></tr>')
        p.append('</table><h3>4 · Figures</h3><figure>' + figure(t, r) + f'<figcaption>{e(CAPTION)}</figcaption></figure>')
    p.append(ip.assets() + '</main></body></html>')
    return '\n'.join(p)


def record_md(cat, camp, rows_by, snapshot):
    allrows = [r for rs in rows_by.values() for r in rs]
    cnt = {v: sum(r['verdict'] == v for r in allrows) for v in ('PASS', 'FAIL', 'INFO')}
    out = ['---', f'campaign: {camp.name}', f'model_sha1: {snapshot["model_sha"]}', f'cases: {len(rows_by)}',
           f'pass: {cnt["PASS"]}', f'fail: {cnt["FAIL"]}', f'info: {cnt["INFO"]}',
           f'new_failures: {sum(1 for r in allrows if r["verdict"] == "FAIL" and not r.get("finding"))}', 'reviewed: ', '---', '',
           f'# {cat["title"]}', '', '| Criterion | Verdict | Limit | Measured |', '|---|---|---|---|']
    for r in sorted(allrows, key=lambda r: ({'FAIL': 0, 'PASS': 1, 'INFO': 2}[r['verdict']], r['id'])):
        tag = f" (known {r['finding']['id']})" if r.get('finding') else (' NEW' if r['verdict'] == 'FAIL' else '')
        out.append(f"| {r['id']} | {r['verdict']}{tag} | {r['limit']} | {r['measured']} |")
    return '\n'.join(out) + '\n'


def main(ids):
    cat = load_catalogue()
    todo = [t for t in cat['tests'] if t['level'] == 'D' and t['status'] == 'implemented' and (not ids or t['id'] in ids)]
    camp = OUT / (dt.datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_sim')
    (camp / 'traces').mkdir(parents=True)
    snapshot = {'model_sha': hashlib.sha1((HERE / 'model.py').read_bytes()).hexdigest()}
    print(f'campaign {camp}  ({len(todo)} cases)', flush=True)
    with mp.Pool(min(len(todo), mp.cpu_count())) as pool:
        got = dict(pool.map(_run, [(t['id'], t['params']) for t in todo]))
    results = {t['id']: got[t['id']] for t in todo}
    rows_by, log, summary = {}, [], {}
    for t in todo:
        r = results[t['id']]
        rows = criteria(t, r)
        for x in rows:
            if x['verdict'] == 'FAIL':
                x['finding'] = finding_for(x['id'], cat['findings'])
            log.append('\t'.join(['@@', x['id'], x['verdict'], x['desc'], x['limit'], x['measured']]))
        rows_by[t['id']] = rows
        np.savez_compressed(camp / 'traces' / f"{t['id']}.npz", **r['traces'])
        summary[t['id']] = {k: r[k] for k in ('vds_pk', 'iL_pk', 'trip_t', 't_150', 'e_clamp', 'vH_end', 'wall')}
        print(f"  {t['id']:9s} Vds {r['vds_pk']:7.1f} V  |iL| {r['iL_pk']:6.1f} A  "
              + ' '.join(f"{x['id'].split('.')[1]}:{x['verdict']}" for x in rows if x['verdict'] != 'INFO'), flush=True)
    (camp / 'sim.log').write_text('\n'.join(log) + '\n')
    (camp / 'summary.json').write_text(json.dumps({'snapshot': snapshot, 'cases': summary}, indent=1))
    (camp / 'record.md').write_text(record_md(cat, camp, rows_by, snapshot))
    (camp / 'report.html').write_text(report(cat, camp, results, rows_by, snapshot), encoding='utf-8')
    import control_center
    print(control_center.write(OUT))
    print(camp / 'report.html')
    return 0


import numpy as np  # noqa: E402

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
