#!/usr/bin/env python3
"""Bench helper of the VHigh investigation (level L2), called by bench_wizard.sh.

Talks to the examples firmware TWIST/DC_DC/vhigh_investigation over its ThingSet shell (second USB
serial port), drives the Tektronix MSO54 through Core2 tests/common/scope.py, and turns a bench session
folder into a campaign the control center reads (sim.log @@ lines, summary.json, report.html).

Needs pyserial, pyvisa, pyvisa-py, numpy: run it with the Core2 venv (~/code/Core2/.venv/bin/python).

  bench_ctl.py list                              every OwnTech serial port: board, serial number, interface
  bench_ctl.py find                              print the ThingSet port running the bench firmware
  bench_ctl.py --port P identity                 build commit of the firmware
  bench_ctl.py --port P read                     every measurement and the guard state, as JSON
  bench_ctl.py --port P set Converter/Mode 1     write one ThingSet value
  bench_ctl.py --port P settle NAME [--seconds S] [--n N] [--session DIR] [--expect JSON]
                                                 wait, average N reads, store steps/NAME.json
  bench_ctl.py --port P wait-trip [--timeout S] [--session DIR] [--name NAME]
  bench_ctl.py --port P fwscope-arm              arm the firmware scope (triggers on Mode/wStep/trip)
  bench_ctl.py --port P fwscope-read --session DIR --name NAME
  bench_ctl.py mso-arm                           MSO54 single acquisition
  bench_ctl.py mso-capture --session DIR --name NAME   screen, measurements, waveforms
  bench_ctl.py predictions                       the D-L2P predictions from the newest campaign
  bench_ctl.py record --session DIR              write sim.log, summary.json, report.html; refresh the control center
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
MODEL = STUDY / 'model'
RESULTS = STUDY / 'results'
CORE2 = Path.home() / 'code' / 'Core2'
sys.path.insert(0, str(CORE2 / 'tests' / 'common'))
sys.path.insert(0, str(CORE2 / 'tests' / 'common' / 'spoc'))
sys.path.insert(0, str(MODEL))
sys.path.insert(0, str(MODEL / 'common'))

MEAS = ['rVHigh_V', 'rV1Low_V', 'rI1Low_A', 'rV2Low_V', 'rI2Low_A', 'rIHigh_A', 'rDuty', 'rTemp1_degC', 'rTemp2_degC']
CONV = ['Mode', 'wCurrentRef_A', 'rCurrentApplied_A', 'wDuty0', 'wDuty1', 'wStep', 'wOvLimit_V', 'wILimit_A',
        'wV1LowLimit_V', 'rTripped', 'rTripCode', 'rTripReason', 'rTripValue']


# ---------------------------------------------------------------- ThingSet
def shell(port: str):
    import serial  # type: ignore
    from thingset import ThingSetShell  # Core2 tests/common/spoc/thingset.py
    ser = serial.Serial(port, 115200, timeout=0.2)
    ts = ThingSetShell(ser)
    if not ts.enter_thingset():
        raise SystemExit(f'{port}: no ThingSet shell answered')
    return ts


def get(ts, path: str):
    ok, v = ts.get_value(path)
    if not ok or (isinstance(v, str) and 'Invalid' in v):  # the shell answers errors as a quoted string
        raise SystemExit(f'ThingSet read failed: {path} ({v})')
    from thingset import parse_scalar
    return parse_scalar(v) if isinstance(v, str) else v


def put(ts, path: str, value) -> None:
    ok, resp = ts.set_value(path, str(value))
    if not ok:
        raise SystemExit(f'ThingSet write refused: {path} = {value}\n{resp}')


def read_all(ts) -> dict:
    d = {k: get(ts, f'Measurements/{k}') for k in MEAS}
    d.update({k: get(ts, f'Converter/{k}') for k in CONV})
    return d


def ports() -> list[str]:
    """@brief OwnTech USB serial ports only (never an ST-Link or another device), from /dev/serial/by-id."""
    found = []
    for link in sorted(glob.glob('/dev/serial/by-id/usb-OwnTech*-if02')):  # ThingSet shell: the second USB serial port
        found.append(str(Path(link).resolve()))
    return found or sorted(glob.glob('/dev/ttyACM*'))


def cmd_list(_a) -> None:
    """@brief Every OwnTech serial port: board name, serial number, USB interface."""
    for link in sorted(glob.glob('/dev/serial/by-id/usb-OwnTech*')):
        name = Path(link).name.replace('usb-OwnTech_Technologies_', '')
        print(f'{Path(link).resolve()}  {name}')


def cmd_find(_a) -> None:
    for port in ports():
        try:
            ts = shell(port)
            ok, v = ts.get_value('Converter/wOvLimit_V')
            ts.ser.close()
            float(v)  # the bench firmware answers a number; another firmware answers "Invalid endpoint"
            print(port)
            return
        except (SystemExit, Exception):
            continue
    raise SystemExit('no port with the vhigh_investigation firmware (Converter/wOvLimit_V) found')


def save_step(session: str | None, name: str, data: dict) -> None:
    if not session:
        return
    p = Path(session) / 'steps'
    p.mkdir(parents=True, exist_ok=True)
    (p / f'{name}.json').write_text(json.dumps(data, indent=1))


def cmd_settle(a) -> None:
    ts = shell(a.port)
    time.sleep(a.seconds)
    reads = []
    for _ in range(a.n):
        reads.append(read_all(ts))
        time.sleep(0.1)
    num = {k: statistics.fmean(float(r[k]) for r in reads) for k in ('rVHigh_V', 'rV1Low_V', 'rI1Low_A', 'rDuty')}
    num.update({k + '_sd': statistics.pstdev(float(r[k]) for r in reads) for k in ('rVHigh_V', 'rI1Low_A')})
    out = {'name': a.name, 'time': dt.datetime.now().isoformat(timespec='seconds'), 'mean': num, 'last': reads[-1],
           'expect': json.loads(a.expect) if a.expect else None}
    save_step(a.session, a.name, out)
    print(json.dumps({'VHigh_V': round(num['rVHigh_V'], 2), 'I1Low_A': round(num['rI1Low_A'], 3),
                      'V1Low_V': round(num['rV1Low_V'], 2), 'duty': round(num['rDuty'], 4),
                      'tripped': reads[-1]['rTripped'], 'reason': reads[-1]['rTripReason']}))


def cmd_wait_trip(a) -> None:
    ts = shell(a.port)
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        if str(get(ts, 'Converter/rTripped')).lower() in ('true', '1'):
            d = read_all(ts)
            d['seconds_waited'] = round(time.time() - t0, 2)
            save_step(a.session, a.name, {'name': a.name, 'trip': d})
            print(json.dumps({'tripped': True, 'reason': d['rTripReason'], 'value': d['rTripValue'],
                              'VHigh_now': d['rVHigh_V']}))
            return
        time.sleep(0.05)
    print(json.dumps({'tripped': False}))
    raise SystemExit(2)


def cmd_fwscope_arm(a) -> None:
    put(shell(a.port), 'Scope/wArm', 1)
    print('armed')


def cmd_fwscope_read(a) -> None:
    ts = shell(a.port)
    t0 = time.time()
    while str(get(ts, 'Scope/rState')) != '3':
        if time.time() - t0 > a.timeout:
            raise SystemExit('firmware scope not ready (rState != 3)')
        time.sleep(0.1)
    length = int(get(ts, 'Scope/rLength'))
    period = float(get(ts, 'Scope/rPeriod_s'))
    pre = int(get(ts, 'Scope/rPretrigger'))
    names = str(get(ts, 'Scope/rChannels')).split(',')
    vals = []
    for chunk in range((length * len(names) + 63) // 64):
        put(ts, 'Scope/wChunk', chunk)
        ok, v = ts.get_value('Scope/rData')
        vals += json.loads(v) if isinstance(v, str) else v
    vals = vals[:length * len(names)]
    data = {'period_s': period, 'pretrigger': pre, 'channels': {n: vals[i * length:(i + 1) * length] for i, n in enumerate(names)}}
    p = Path(a.session) / 'fwscope'
    p.mkdir(parents=True, exist_ok=True)
    (p / f'{a.name}.json').write_text(json.dumps(data))
    print(f'{len(names)} channels x {length} samples -> {p / (a.name + ".json")}')


# ---------------------------------------------------------------- MSO54
def cmd_mso_arm(a) -> None:
    import scope as tek  # Core2 tests/common/scope.py
    tek.Scope(a.resource).arm_single()
    print('MSO54 armed (single)')


def cmd_mso_capture(a) -> None:
    import scope as tek
    out = Path(a.session) / 'scope' / a.name
    tek.capture(tek.Scope(a.resource), out, label=a.name, waveforms=True)
    print(out)


# ---------------------------------------------------------------- predictions and record
def predictions() -> dict:
    """@return {case: summary} for the D-L2P cases, from the newest campaign that ran each."""
    found = {}
    for d in sorted(RESULTS.glob('*_sim'), reverse=True):
        s = json.loads((d / 'summary.json').read_text())['cases']
        for k, v in s.items():
            if k.startswith('D-L2P') and k not in found:
                v['campaign'] = d.name
                found[k] = v
    return found


def cmd_predictions(_a) -> None:
    print(json.dumps(predictions(), indent=1))


OV01_STEPS = [('ov01_0.50A', 'D-L2P-01'), ('ov01_0.75A', 'D-L2P-02'), ('ov01_1.00A', 'D-L2P-03'), ('ov01_1.15A', 'D-L2P-04')]


def criteria(session: Path) -> list[dict]:
    pred = predictions()
    steps = {p.stem: json.loads(p.read_text()) for p in (session / 'steps').glob('*.json')}
    rows = []

    def row(rid, verdict, desc, limit, measured):
        rows.append({'id': rid, 'verdict': verdict, 'desc': desc, 'limit': limit, 'measured': measured})

    env = parse_env(session / 'session.env')
    if 'sensor_check' in steps:
        m = steps['sensor_check']['mean']
        for key, psu, label in (('rVHigh_V', 'VHIGH_PSU_V', 'V_HIGH'), ('rV1Low_V', 'VLOW_PSU_V', 'V1_LOW')):
            if env.get(psu):
                ref = float(env[psu]); err = (m[key] - ref) / ref * 100
                row(f'L2-OV-01.s{label}', 'PASS' if abs(err) <= 3 else 'FAIL', f'{label} sensor against the supply display',
                    '|error| <= 3 %', f'{m[key]:.2f} V vs {ref:.2f} V ({err:+.1f} %)')
    letters = 'abcd'
    for (name, case), letter in zip(OV01_STEPS, letters):
        if name not in steps:
            continue
        v = steps[name]['mean']['rVHigh_V']
        pv = pred.get(case, {}).get('vH_end')
        if pv:
            ok = abs(v - pv) <= 0.05 * pv
            row(f'L2-OV-01.{letter}', 'PASS' if ok else 'FAIL', f'Settled VHigh at {name[5:]} into VHigh within 5 % of {case}',
                f'{pv:.1f} V +/- 5 %', f'{v:.2f} V ({(v - pv) / pv * 100:+.1f} %), I1 {steps[name]["mean"]["rI1Low_A"]:.3f} A')
    if 'ov01_1.00A' in steps:
        v = steps['ov01_1.00A']['mean']['rVHigh_V']
        sp = float(env.get('VHIGH_PSU_V') or 60)
        row('L2-OV-01.e', 'PASS' if v > sp + 3 else 'FAIL', 'F-1 on the board: with 1 A into VHigh, VHigh rises above the supply set point',
            f'> {sp + 3:.0f} V', f'{v:.2f} V')
    if 'ov02_trip' in steps:
        t = steps['ov02_trip']['trip']
        val = float(t['rTripValue'])
        row('L2-OV-02.a', 'PASS' if t['rTripCode'] in (1, '1') and 78 <= val <= 82 else 'FAIL',
            'The bench guard stops the leg on V_HIGH at its 80 V limit', '78 to 82 V, reason V_HIGH', f'{val:.2f} V, "{t["rTripReason"]}"')
        if 'ov02_after' in steps:
            after = steps['ov02_after']['mean']['rVHigh_V']
            row('L2-OV-02.b', 'PASS' if after < 65 else 'FAIL', 'After the stop VHigh falls back to the supply through the bleed',
                '< 65 V', f'{after:.2f} V')
    fw = session / 'fwscope' / 'ov02.json'
    if fw.exists():
        d = json.loads(fw.read_text()); vh = d['channels'].get('rVHigh_V', [])
        if vh:
            row('L2-OV-02.c', 'INFO', 'VHigh rise seen by the firmware scope', '', f'{min(vh):.1f} to {max(vh):.1f} V over {len(vh) * d["period_s"] * 1e3:.0f} ms')
    stp = session / 'scope' / 'stp01' / 'waveforms.npz'
    if stp.exists():
        import numpy as np
        w = np.load(stp)
        ch = env.get('IL_CHANNEL', 'CH3')
        if f'{ch}_v' in w:
            pk = float(w[f'{ch}_v'].max())
            pp = pred.get('D-L2P-06', {}).get('iL_pk')
            if pp:
                ok = abs(pk - pp) <= 0.3 * pp
                row('L2-STP-01.a', 'PASS' if ok else 'FAIL', 'Peak inductor current after the 0.4 to 0.5 step, against D-L2P-06',
                    f'{pp:.2f} A +/- 30 %', f'{pk:.2f} A ({(pk - pp) / pp * 100:+.0f} %)')
    return rows


def parse_env(p: Path) -> dict:
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip().strip("'")
    return out


def report(session: Path, rows: list[dict]) -> str:
    import run_campaign as rc  # model/run_campaign.py: the same page style
    import interactive_plot as ip
    e = html.escape
    env = parse_env(session / 'session.env')
    p = [rc.page_head(f'Bench {session.name}'),
         f'<h1>Bench session: {e(session.name)}</h1><div class="sub">Level L2 (on the board) · '
         '<a href="../control-center.html">control center</a> · investigation record <a href="../../README.md">README.md</a></div>']
    cnt = {v: sum(r['verdict'] == v for r in rows) for v in ('PASS', 'FAIL', 'INFO')}
    p.append(f'<div class="banner{" bad" if cnt["FAIL"] else ""}"><div class="counts"><span>✓ {cnt["PASS"]} PASS</span>'
             f'<span>✗ {cnt["FAIL"]} FAIL</span><span>i {cnt["INFO"]} INFO</span></div>'
             '<div class="sub">Each bench result is compared with the model prediction of the same setup (D-L2P cases).</div></div>')
    p.append('<h3>1 · Session and setup</h3><div class="wrap"><table class="kv">')
    for k, v in env.items():
        p.append(f'<tr><td>{e(k)}</td><td>{e(v)}</td></tr>')
    p.append('</table></div><h3>2 · Results</h3><table><tr><th>Criterion</th><th>What is checked</th><th>Verdict</th><th>Limit</th><th>Measured</th></tr>')
    for r in rows:
        p.append(f'<tr><td>{e(r["id"])}</td><td>{e(r["desc"])}</td><td>{rc.badge(r)}</td><td>{e(r["limit"])}</td><td>{e(r["measured"])}</td></tr>')
    p.append('</table><h3>3 · Figures</h3>')
    figs = 0
    for fw in sorted((session / 'fwscope').glob('*.json')) if (session / 'fwscope').exists() else []:
        d = json.loads(fw.read_text()); ch = d['channels']; n = len(next(iter(ch.values())))
        t = [(i - d['pretrigger']) * d['period_s'] * 1e3 for i in range(n)]
        f = ip.Figure('ms')
        c = f.chart('V', 220)
        if 'rVHigh_V' in ch:
            f.line(c, 'VHigh (firmware, V)', t, ch['rVHigh_V'], rc.BLUE, 2.5)
        c['hlines'] = [{'v': 80, 'color': rc.CRITICAL, 'dash': [6, 4]}]
        c['events'] = [{'t': 0, 'label': 'trigger'}]
        c2 = f.chart('A', 150)
        if 'rI1Low_A' in ch:
            f.line(c2, 'I1_LOW (firmware, A)', t, ch['rI1Low_A'], rc.BLUE, 2)
        if 'rCurrentApplied_A' in ch:
            f.line(c2, 'current reference after the ramp (A)', t, ch['rCurrentApplied_A'], rc.ORANGE, 1.2)
        c3 = f.chart('duty', 100)
        if 'rDuty' in ch:
            f.line(c3, 'duty', t, ch['rDuty'], rc.GREEN, 1.5)
        p.append(f'<figure><div><b>Firmware scope: {e(fw.stem)}</b></div>{f.html("fw_" + fw.stem, "firmware scope " + fw.stem)}'
                 '<figcaption>Sampled every control period (100 us) by the example firmware; time 0 is the trigger (mode change, step or guard trip). '
                 'Red dashed: the 80 V guard.</figcaption></figure>')
        figs += 1
    for wf in sorted((session / 'scope').glob('*/waveforms.npz')) if (session / 'scope').exists() else []:
        import numpy as np
        w = np.load(wf); name = wf.parent.name
        labels = {'CH1': 'VHigh (V)', 'CH2': 'V1_low (V)', 'CH3': 'iL (A)', 'CH4': 'SW node (V)'}
        f = ip.Figure('ms')
        for chs, unit in ((('CH1', 'CH2', 'CH4'), 'V'), (('CH3',), 'A')):
            present = [ch for ch in chs if f'{ch}_v' in w]
            if not present:
                continue
            c = f.chart(unit, 200)
            for k, ch in enumerate(present):
                f.line(c, labels[ch], w[f'{ch}_t'] * 1e3, w[f'{ch}_v'], ip.SERIES[k % 4], 2 if k == 0 else 1.2)
        png = wf.parent / 'screen.png'
        img = f'<p><a href="{e(str(png.relative_to(session)))}">MSO54 screenshot</a></p>' if png.exists() else ''
        p.append(f'<figure><div><b>MSO54: {e(name)}</b></div>{f.html("mso_" + name, "MSO54 " + name)}{img}'
                 '<figcaption>Waveforms read from the MSO54 at the end of the acquisition (Core2 tests/common/scope.py). '
                 'Long records are reduced to min/max per bucket, so peaks survive.</figcaption></figure>')
        figs += 1
    if not figs:
        p.append('<p class="sub">No figure recorded in this session.</p>')
    p.append(ip.assets() + '</main></body></html>')
    return '\n'.join(p)


def cmd_record(a) -> None:
    session = Path(a.session)
    rows = criteria(session)
    (session / 'sim.log').write_text(''.join('\t'.join(['@@', r['id'], r['verdict'], r['desc'], r['limit'], r['measured']]) + '\n' for r in rows))
    (session / 'summary.json').write_text(json.dumps({'kind': 'bench', 'cases': {}}, indent=1))
    (session / 'report.html').write_text(report(session, rows), encoding='utf-8')
    import control_center
    print(control_center.write(RESULTS))
    print(session / 'report.html')
    for r in rows:
        print(f"  {r['verdict']:5s} {r['id']:16s} {r['measured']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', help='ThingSet serial port of the bench firmware')
    ap.add_argument('--resource', help='MSO54 VISA resource (default: first Tektronix on USB)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('find')
    sub.add_parser('list')
    sub.add_parser('identity')
    sub.add_parser('read')
    s = sub.add_parser('set'); s.add_argument('path'); s.add_argument('value')
    s = sub.add_parser('settle'); s.add_argument('name'); s.add_argument('--seconds', type=float, default=2.0)
    s.add_argument('--n', type=int, default=10); s.add_argument('--session'); s.add_argument('--expect')
    s = sub.add_parser('wait-trip'); s.add_argument('--timeout', type=float, default=5.0); s.add_argument('--session'); s.add_argument('--name', default='trip')
    sub.add_parser('fwscope-arm')
    s = sub.add_parser('fwscope-read'); s.add_argument('--session', required=True); s.add_argument('--name', required=True)
    s.add_argument('--timeout', type=float, default=5.0)
    sub.add_parser('mso-arm')
    s = sub.add_parser('mso-capture'); s.add_argument('--session', required=True); s.add_argument('--name', required=True)
    sub.add_parser('predictions')
    s = sub.add_parser('record'); s.add_argument('--session', required=True)
    a = ap.parse_args()
    if a.cmd == 'find':
        return cmd_find(a)
    if a.cmd == 'list':
        return cmd_list(a)
    if a.cmd in ('identity', 'read', 'set', 'settle', 'wait-trip', 'fwscope-arm', 'fwscope-read') and not a.port:
        raise SystemExit('--port is required (bench_ctl.py find prints it)')
    if a.cmd == 'identity':
        ts = shell(a.port)
        print(json.dumps({k: get(ts, f'Build/{k}') for k in ('rCommit', 'rDirty', 'rSourceHash')}))
    elif a.cmd == 'read':
        print(json.dumps(read_all(shell(a.port)), indent=1))
    elif a.cmd == 'set':
        put(shell(a.port), a.path, a.value); print(f'{a.path} = {a.value}')
    else:
        {'settle': cmd_settle, 'wait-trip': cmd_wait_trip, 'fwscope-arm': cmd_fwscope_arm, 'fwscope-read': cmd_fwscope_read,
         'mso-arm': cmd_mso_arm, 'mso-capture': cmd_mso_capture, 'predictions': cmd_predictions, 'record': cmd_record}[a.cmd](a)


if __name__ == '__main__':
    main()
