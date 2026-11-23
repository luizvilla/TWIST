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
  bench_ctl.py mso-check                         empty the MSO54 output queue and check it answers in step
  bench_ctl.py mso-arm --session DIR --preset ov|stp [--auto | --source vhigh|il --level V] [--hscale s] [--hpos %]
                                                 set the channels (roles from session.env), the edge trigger, arm single
  bench_ctl.py mso-wait [--timeout S]            wait until the single acquisition has triggered and stopped
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
    ser = serial.Serial(port, 115200, timeout=0.2, write_timeout=2)  # a board that stops reading must not block us
    ts = ThingSetShell(ser)
    if not ts.enter_thingset():
        raise SystemExit(f'{port}: no ThingSet shell answered')
    return ts


def get(ts, path: str):
    ok, v = ts.get_value(path)
    if not ok or (isinstance(v, str) and 'Invalid' in v):  # the shell answers errors as a quoted string
        raise SystemExit(f'ThingSet read failed: {path} ({v})')
    from thingset import parse_scalar
    if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1]  # ThingSet strings come back quoted
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
    links = glob.glob('/dev/serial/by-id/usb-OwnTech*-if02')  # ThingSet shell: the second USB serial port
    for link in sorted(links, key=lambda l: ('TWIST' not in l, l)):  # TWIST boards first
        found.append(str(Path(link).resolve()))
    return found or sorted(glob.glob('/dev/ttyACM*'))


def cmd_list(_a) -> None:
    """@brief Every OwnTech serial port: board name, serial number, USB interface."""
    for link in sorted(glob.glob('/dev/serial/by-id/usb-OwnTech*')):
        name = Path(link).name.replace('usb-OwnTech_Technologies_', '')
        print(f'{Path(link).resolve()}  {name}')


def probe(port: str) -> None:
    """@brief Exit 0 if `port` runs the bench firmware (answers Converter/wOvLimit_V with a number)."""
    ts = shell(port)
    ok, v = ts.get_value('Converter/wOvLimit_V')
    ts.ser.close()
    float(v)  # the bench firmware answers a number; another firmware answers "Invalid endpoint"


def cmd_find(_a) -> None:
    import subprocess
    for port in ports():
        # Each port in its own process with a time limit: opening the port of a hung board blocks in the kernel.
        try:
            r = subprocess.run([sys.executable, __file__, 'probe', port], capture_output=True, timeout=8)
        except subprocess.TimeoutExpired:
            print(f'{port}: no answer within 8 s (board hung or busy)', file=sys.stderr)
            continue
        if r.returncode == 0:
            print(port)
            return
        print(f'{port}: not the bench firmware', file=sys.stderr)
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
# The MSO54 is used in single-sequence mode only: set up, armed on an edge, read once it has triggered and
# stopped. Stopping a running acquisition and querying right after made the scope refuse USB writes
# (session 2026-11-23_170833), and one stale reply in its output queue shifts every later answer.
TEK_RESOURCE = 'USB0::1689::1314::C017217::0::INSTR'

PRESETS = {  # role: (scale per div, centre offset), plus the timebase
    'ov':  {'vhigh': (5.0, 37.0), 'vlow': (5.0, 12.0), 'il': (0.2, 1.0), 'ibleed': (0.1, 0.35), 'hscale': 0.05, 'hpos': 30.0},
    'stp': {'vhigh': (2.0, 30.0), 'vlow': (2.0, 13.0), 'il': (0.1, 1.3), 'ibleed': (0.05, 0.30), 'hscale': 2e-4, 'hpos': 20.0},
}


def roles(session: str | None) -> dict:
    env = parse_env(Path(session) / 'session.env') if session else {}
    r = {'vhigh': env.get('CH_VHIGH', 'CH2'), 'vlow': env.get('CH_VLOW', 'CH1'), 'il': env.get('IL_CHANNEL', 'CH4'),
         'ibleed': env.get('CH_IBLEED', 'CH3')}
    return {k: v for k, v in r.items() if v and v != 'none'}


def tek_open(resource: str | None):
    """@brief Open the MSO54, empty its output queue, and check it answers *IDN? in step. @return the Core2 Scope."""
    import scope as tek  # Core2 tests/common/scope.py
    from pyvisa.errors import VisaIOError
    idn = None
    for attempt in range(2):
        try:
            sc = tek.Scope(resource or TEK_RESOURCE, timeout_s=10)
            for _ in range(3):
                sc.drain()
                idn = sc.q('*IDN?', timeout_s=3)
                if idn and idn.upper().startswith('TEKTRONIX'):
                    return sc
        except Exception as ex:  # pyvisa-py raises ValueError on a USB write timeout
            idn = f'{type(ex).__name__}: {ex}'
        if attempt == 0:
            # pyvisa-py has no USBTMC device clear: a USB reset (same as a replug) unwedges the link
            print(f'MSO54 not answering in step ({idn!r}): resetting its USB link', file=sys.stderr)
            try:
                import usb.core
                dev = usb.core.find(idVendor=0x0699, idProduct=0x0522)
                if dev is not None:
                    try:
                        dev.reset()
                    except Exception:
                        pass  # the device re-enumerates during the reset: "Entity not found" is expected
            except Exception as ex:
                print(f'USB reset failed: {ex}', file=sys.stderr)
            time.sleep(4)
    raise SystemExit(f'MSO54 does not answer *IDN? in step (last answer: {idn!r}); unplug and replug its USB cable')


def scope_errors(sc) -> str:
    ev = sc.q('ALLEv?', timeout_s=3) or ''
    return '' if ev.startswith('0,') or 'No events' in ev else ev


def cmd_mso_check(a) -> None:
    sc = tek_open(a.resource)
    print(sc.q('*IDN?'), '| acquisition', 'running' if sc.running() else 'stopped', '| trigger', sc.q('TRIGger:A:MODe?'))


def cmd_mso_arm(a) -> None:
    sc = tek_open(a.resource)
    p = PRESETS[a.preset]
    r = roles(a.session)
    sc.inst.write('ACQuire:STATE STOP')
    sc.q('*OPC?', timeout_s=10)
    for role, ch in r.items():
        scale, offset = p[role]
        sc.inst.write(f'DISplay:GLObal:{ch}:STATE ON')
        sc.inst.write(f'{ch}:POSition 0')
        sc.inst.write(f'{ch}:SCAle {scale}')
        sc.inst.write(f'{ch}:OFFSet {offset}')
    sc.inst.write('HORizontal:MODe AUTO')
    sc.inst.write(f'HORizontal:SCAle {a.hscale if a.hscale else p["hscale"]}')
    sc.inst.write(f'HORizontal:POSition {a.hpos if a.hpos is not None else p["hpos"]}')
    sc.inst.write('HORizontal:RECOrdlength 125000')
    sc.inst.write('HORizontal:MODe:RECOrdlength 125000')  # the form the MSO5 series takes in AUTO mode
    if a.auto:
        sc.inst.write('TRIGger:A:MODe AUTO')
    else:
        src = r[a.source]
        sc.inst.write('TRIGger:A:TYPe EDGE')
        sc.inst.write(f'TRIGger:A:EDGE:SOUrce {src}')
        sc.inst.write(f'TRIGger:A:EDGE:SLOpe {a.slope}')
        sc.inst.write(f'TRIGger:A:LEVel:{src} {a.level}')
        sc.inst.write('TRIGger:A:MODe NORMal')
    sc.q('*OPC?', timeout_s=10)
    err = scope_errors(sc)
    sc.arm_single()
    time.sleep(0.3)
    state = sc.q('TRIGger:STATE?', timeout_s=3)
    what = 'auto trigger' if a.auto else f'{a.source} ({r[a.source]}) {a.slope} at {a.level}'
    print(f'MSO54 armed, single sequence, {what}; {sc.num("HORizontal:SCAle?")} s/div, '
          f'{sc.num("HORizontal:RECOrdlength?")} points; trigger state {state}' + (f'; scope errors: {err}' if err else ''))


def cmd_mso_wait(a) -> None:
    sc = tek_open(a.resource)
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        if sc.q('ACQuire:STATE?', timeout_s=3) in ('0', 'OFF', 'STOP'):
            print(f'MSO54 triggered and stopped after {time.time() - t0:.1f} s')
            return
        time.sleep(0.2)
    print(f'MSO54 did not trigger within {a.timeout:g} s (trigger state {sc.q("TRIGger:STATE?", timeout_s=3)})')
    raise SystemExit(2)


def cmd_mso_capture(a) -> None:
    import scope as tek
    out = Path(a.session) / 'scope' / a.name
    try:
        sc = tek_open(a.resource)
        if sc.running():
            print('warning: the scope is still running (it did not trigger): capturing what it holds now')
        tek.capture(sc, out, label=a.name, waveforms=True)
    except Exception as ex:  # a USB timeout from pyvisa-py is a ValueError, not a VisaIOError
        raise SystemExit(f'MSO54 capture failed: {type(ex).__name__}: {ex}')
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


OV01_STEPS = [('ov01_0.50A', 'D-L2P-01'), ('ov01_1.00A', 'D-L2P-02'), ('ov01_1.25A', 'D-L2P-03'), ('ov01_1.50A', 'D-L2P-04')]


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
        last = steps[name].get('last', {})
        if str(last.get('rTripped')).lower() in ('true', '1'):
            row(f'L2-OV-01.{letter}', 'INFO', f'Step {name[5:]} not judged: the bench guard had stopped the leg', '',
                f'{last.get("rTripReason")} ({last.get("rTripValue")})')
            continue
        pv = pred.get(case, {}).get('vH_end')
        sp_meas = float(env['VHIGH_PSU_V']) if env.get('VHIGH_PSU_V') else None
        if pv and sp_meas and pv <= 32.0 + 0.1:
            pv = sp_meas  # the model says the supply holds VHigh: compare with the set point measured at the board (after the diode)
        if pv:
            ok = abs(v - pv) <= 0.05 * pv
            row(f'L2-OV-01.{letter}', 'PASS' if ok else 'FAIL', f'Settled VHigh at {name[5:]} into VHigh within 5 % of {case}',
                f'{pv:.1f} V +/- 5 %', f'{v:.2f} V ({(v - pv) / pv * 100:+.1f} %), I1 {steps[name]["mean"]["rI1Low_A"]:.3f} A')
    sp = float(env.get('VHIGH_PSU_V') or 32)
    done = [(name, steps[name]['mean']['rVHigh_V']) for name, _ in OV01_STEPS[1:]
            if name in steps and str(steps[name]['last'].get('rTripped')).lower() not in ('true', '1')]
    if done:
        name, v = max(done, key=lambda x: x[1])
        row('L2-OV-01.e', 'PASS' if v > sp + 1 else 'FAIL',
            'F-1 on the board: with 1 A or more pushed into VHigh, VHigh settles above the supply set point (supply still connected)',
            f'> {sp + 1:.2f} V (set point at the board + 1 V)', f'{v:.2f} V at {name[5:]} (+{v - sp:.2f} V)')
    bal = []
    rb = float(env.get('R_BLEED_OHM') or 100)
    for name, _ in OV01_STEPS[1:]:
        if name in steps and str(steps[name]['last'].get('rTripped')).lower() not in ('true', '1'):
            m = steps[name]['mean']; vh = m['rVHigh_V']
            if vh > sp + 0.5:  # above the set point the supply delivers nothing: all of the bleed power comes from the leg
                p_in = m['rV1Low_V'] * abs(m['rI1Low_A']); p_out = vh ** 2 / rb
                bal.append(f'{name[5:]}: {p_in:.1f} W in, {p_out:.1f} W in the bleed ({p_out / p_in * 100:.0f} %)')
    if bal:
        row('L2-OV-01.g', 'INFO', 'Power balance above the set point: LOW1 power taken by the leg against the power in the bleed. '
            'The difference is the converter losses and the Feeder load on VHigh, which the model leaves out', '', '; '.join(bal))
    cap = session / 'scope' / 'ov01_1.50A' / 'waveforms.npz'
    cb, cv = env.get('CH_IBLEED', 'none'), env.get('CH_VHIGH')
    if cap.exists() and cb != 'none' and cv:
        import numpy as np
        wv = np.load(cap)
        if f'{cb}_v' in wv and f'{cv}_v' in wv:
            ib, vh = float(wv[f'{cb}_v'].mean()), float(wv[f'{cv}_v'].mean())
            row('L2-OV-01.h', 'INFO', 'Bleed current probe at 1.5 A: the energy pushed into VHigh ends in the bleed', '',
                f'{ib:.3f} A x {rb:g} ohm = {ib * rb:.2f} V against VHigh {vh:.2f} V; {ib * vh:.1f} W in the bleed')
    fw2 = session / 'fwscope' / 'ov02.json'
    if fw2.exists():
        d = json.loads(fw2.read_text()); ch = d['channels']; pre = d['pretrigger']
        vh, ref = ch.get('rVHigh_V', []), ch.get('rCurrentApplied_A', [])
        if vh and ref and pre > 20:
            row('L2-OV-01.f', 'INFO', 'VHigh just before the L2-OV-02 stop, from the firmware scope (supply still connected)', '',
                f'{max(vh[:pre]):.2f} V with {ref[pre - 1]:+.2f} A applied (set point {sp:.2f} V)')
    if 'ov02_trip' in steps:
        t = steps['ov02_trip']['trip']
        val = float(t['rTripValue'])
        lim = float(t.get('wOvLimit_V') or 45)
        row('L2-OV-02.a', 'PASS' if t['rTripCode'] in (1, '1') and lim - 2 <= val <= lim + 2 else 'FAIL',
            f'The bench guard stops the leg on V_HIGH at its {lim:g} V limit', f'{lim - 2:g} to {lim + 2:g} V, reason V_HIGH', f'{val:.2f} V, "{t["rTripReason"]}"')
        if 'ov02_after' in steps:
            after = steps['ov02_after']['mean']['rVHigh_V']
            sp = float(env.get('VHIGH_PSU_V') or 32)
            row('L2-OV-02.b', 'PASS' if after < sp + 3 else 'FAIL', 'After the stop VHigh falls back to the supply through the bleed',
                f'< {sp + 3:.0f} V', f'{after:.2f} V')
    fw = session / 'fwscope' / 'ov02.json'
    if fw.exists():
        d = json.loads(fw.read_text()); vh = d['channels'].get('rVHigh_V', [])
        if vh:
            row('L2-OV-02.c', 'INFO', 'VHigh rise seen by the firmware scope', '', f'{min(vh):.1f} to {max(vh):.1f} V over {len(vh) * d["period_s"] * 1e3:.0f} ms')
    stp = session / 'scope' / 'stp01' / 'waveforms.npz'
    fw_stp = session / 'fwscope' / 'stp01.json'
    if not stp.exists() and fw_stp.exists():
        d = json.loads(fw_stp.read_text()); i1 = d['channels'].get('rI1Low_A', [])
        pp = pred.get('D-L2P-06', {}).get('iL_pk')
        if i1:
            row('L2-STP-01.a', 'INFO', 'Peak I1_LOW after the 0.4 to 0.5 step, firmware scope only (100 us per sample: the '
                '280 us ringing is undersampled, so the true peak is higher). Redo with the MSO54 for a verdict',
                f'model {pp:.2f} A' if pp else '', f'{max(i1):.2f} A seen at 100 us')
    if stp.exists():
        import numpy as np
        w = np.load(stp)
        ch = env.get('IL_CHANNEL', 'CH3')
        if f'{ch}_v' in w:
            v = w[f'{ch}_v']
            if env.get('IL_SOURCE') == 'TP203':  # ACS730 output after the level shift: volts to amps
                v = (v - float(env.get('IL_OFFSET_V', 1.0))) / float(env.get('IL_V_PER_A', 0.1))
            pk = float(v.max())
            if 'stp_before' in steps:
                n0 = max(1, len(v) // 10)
                row('L2-STP-01.b', 'INFO', 'TP203 scale check: scope current before the step against the board reading (ThingSet)', '',
                    f'{float(v[:n0].mean()):.2f} A on the scope, {steps["stp_before"]["mean"]["rI1Low_A"]:.2f} A from the board')
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
    seen = set()
    for r in rows:
        test = r['id'].split('.')[0]
        anchor = f' id="{e(test)}"' if test not in seen else ''
        seen.add(test)
        p.append(f'<tr{anchor}><td>{e(r["id"])}</td><td>{e(r["desc"])}</td><td>{rc.badge(r)}</td><td>{e(r["limit"])}</td><td>{e(r["measured"])}</td></tr>')
    p.append('</table><h3>3 · Figures</h3>')
    figs = 0
    for fw in sorted((session / 'fwscope').glob('*.json')) if (session / 'fwscope').exists() else []:
        d = json.loads(fw.read_text()); ch = d['channels']; n = len(next(iter(ch.values())))
        t = [(i - d['pretrigger']) * d['period_s'] * 1e3 for i in range(n)]
        f = ip.Figure('ms')
        c = f.chart('V', 220)
        if 'rVHigh_V' in ch:
            f.line(c, 'VHigh (firmware, V)', t, ch['rVHigh_V'], rc.BLUE, 2.5)
        c['hlines'] = [{'v': 45, 'color': rc.CRITICAL, 'dash': [6, 4]}] if fw.stem.startswith('ov') else []
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
                 'Red dashed (OV runs): the 45 V guard.</figcaption></figure>')
        figs += 1
    for wf in sorted((session / 'scope').glob('*/waveforms.npz')) if (session / 'scope').exists() else []:
        import numpy as np
        w = np.load(wf); name = wf.parent.name
        roles = {env.get('CH_VHIGH', 'CH1'): ('VHigh (V)', 'V'), env.get('CH_VLOW', 'CH2'): ('LOW1 (V)', 'V'),
                 env.get('IL_CHANNEL', 'CH3'): ('iL from TP203 (A)' if env.get('IL_SOURCE') == 'TP203' else 'iL (A)', 'A')}
        if env.get('CH_IBLEED', 'none') != 'none':
            roles[env['CH_IBLEED']] = ('bleed current (A)', 'A')
        w = dict(w)
        if env.get('IL_SOURCE') == 'TP203':
            ch_il = env.get('IL_CHANNEL', 'CH3')
            if f'{ch_il}_v' in w:
                w[f'{ch_il}_v'] = (w[f'{ch_il}_v'] - float(env.get('IL_OFFSET_V', 1.0))) / float(env.get('IL_V_PER_A', 0.1))
        f = ip.Figure('ms')
        for unit in ('V', 'A'):
            present = [ch for ch in ('CH1', 'CH2', 'CH3', 'CH4') if f'{ch}_v' in w and roles.get(ch, (ch, 'V'))[1] == unit]
            if not present:
                continue
            c = f.chart(unit, 200)
            for k, ch in enumerate(present):
                f.line(c, f'{ch}: ' + roles.get(ch, (ch + ' (V)', 'V'))[0], w[f'{ch}_t'] * 1e3, w[f'{ch}_v'], ip.SERIES[k % 4], 2 if k == 0 else 1.2)
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
    s = sub.add_parser('probe'); s.add_argument('probe_port')
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
    sub.add_parser('mso-check')
    s = sub.add_parser('mso-arm'); s.add_argument('--session'); s.add_argument('--preset', choices=list(PRESETS), default='ov')
    s.add_argument('--auto', action='store_true'); s.add_argument('--source', choices=['vhigh', 'vlow', 'il', 'ibleed'], default='vhigh')
    s.add_argument('--level', type=float, default=0.0); s.add_argument('--slope', default='RISe')
    s.add_argument('--hscale', type=float); s.add_argument('--hpos', type=float)
    s = sub.add_parser('mso-wait'); s.add_argument('--timeout', type=float, default=10.0)
    s = sub.add_parser('mso-capture'); s.add_argument('--session', required=True); s.add_argument('--name', required=True)
    sub.add_parser('predictions')
    s = sub.add_parser('record'); s.add_argument('--session', required=True)
    a = ap.parse_args()
    if a.cmd == 'find':
        return cmd_find(a)
    if a.cmd == 'list':
        return cmd_list(a)
    if a.cmd == 'probe':
        try:
            return probe(a.probe_port)
        except BaseException:
            raise SystemExit(1)
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
         'mso-check': cmd_mso_check, 'mso-arm': cmd_mso_arm, 'mso-wait': cmd_mso_wait, 'mso-capture': cmd_mso_capture, 'predictions': cmd_predictions, 'record': cmd_record}[a.cmd](a)


if __name__ == '__main__':
    main()
