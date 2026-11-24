#!/usr/bin/env python3
"""Bench app of the VHigh investigation: a local web page with one tab per test and one button per phase.

Same approach as the micro-inverter bench app (Core2 branch apf_quadrature, tests/l2/app.py): a standard-library
HTTP server on 127.0.0.1, a JSON API and one page (web/index.html). It replaces bench_wizard.sh. The board and
scope logic is bench_ctl.py's (ThingSet over USB, MSO54 single sequences, record and report), so the command line
and the app write the same session files, and every phase regenerates the session's report and the control center.

Usage (Core2 venv: pyserial, pyvisa, pyvisa-py, numpy):
    ~/code/Core2/.venv/bin/python app.py                  # newest unfinished session, or a new one
    ~/code/Core2/.venv/bin/python app.py --new
    ~/code/Core2/.venv/bin/python app.py --session ../results/bench_2026-11-24_101500 --port 8770 --no-browser
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_ctl as bc  # noqa: E402

WEB = HERE / 'web'
RESULTS = bc.RESULTS

# ---------------------------------------------------------------- tests and phases (the page is built from this)
# kind: 'action' runs on the server; 'check' is an operator confirmation (with optional answer); inputs are written to
# session.env. 'confirm' asks before running (power-on, current steps).
GUARD_OV = {'wOvLimit_V': 45, 'wILimit_A': 4.0, 'wV1LowLimit_V': 20}

TESTS = [
    {'id': 'setup', 'test': 'L2-SEN-01', 'title': 'Setup and sensors',
     'purpose': 'Session, board, scope and the sensor check against a meter. Run it at the start of every session.',
     'phases': [
         {'id': 'session', 'label': 'Session', 'kind': 'check',
          'text': 'Who and what is on the bench.',
          'inputs': [('BOARD_ID', 'Board label / serial', ''), ('TWIST_HW', 'TWIST hardware version', '1.4.3'),
                     ('OPERATOR', 'Operator', ''), ('HV_DIODE', 'Diode in series with the VHigh supply', '1N4007'),
                     ('R_BLEED_OHM', 'Bleed resistor across VHigh, measured (ohm)', '100')]},
         {'id': 'board', 'label': 'Find the board', 'kind': 'action',
          'text': 'Only the Spin USB cable is needed. Finds the ThingSet port of the bench firmware and reads its identity.'},
         {'id': 'scope', 'label': 'Scope channels', 'kind': 'action',
          'text': 'Which channel carries which signal ("none" if absent), then checks the MSO54 USB link. '
                  'Probe grounds on the board ground only: the scope ground is earth.',
          'inputs': [('USE_MSO', 'MSO54 connected (yes / no)', 'yes'), ('CH_VLOW', 'LOW1', 'CH1'), ('CH_VHIGH', 'VHigh', 'CH2'),
                     ('CH_IBLEED', 'Bleed current probe (arrow from VHigh into the resistor)', 'CH3'),
                     ('IL_CHANNEL', 'TP203 inductor current (only for L2-STP-01)', 'CH4'), ('CH_SW', 'Switch node (only for L2-OV-03)', 'none')]},
         {'id': 'power', 'label': 'Wiring and power-up', 'kind': 'check',
          'text': 'VHigh: lab supply 32 V, 1 A limit, through the series diode (anode on the supply); 100 ohm bleed across VHigh on the '
                  'board side. LOW1: lab supply 12 V with a 3 A current limit. Nothing on LOW2. TP203 probe OFF (it disturbs the current loop). '
                  'Then both outputs ON.'},
         {'id': 'sensors', 'label': 'Sensor check', 'kind': 'action',
          'text': 'Measure VHigh (board side of the diode) and LOW1 at the board terminals with a meter, type them, then the board is read.',
          'inputs': [('VHIGH_PSU_V', 'VHigh at the board (V)', ''), ('VLOW_PSU_V', 'LOW1 at the board (V)', '')]},
     ]},
    {'id': 'ov01', 'test': 'L2-OV-01', 'title': 'L2-OV-01 VHigh rise',
     'purpose': 'F-1 on the board: current pushed into VHigh raises VHigh above the connected supply. '
                'Expected (model, 32 V supply): 32.0 / 34.5 / 38.6 / 42.2 V at 0.5 / 1.0 / 1.25 / 1.5 A.',
     'phases': [
         {'id': 'guard', 'label': 'Bench guard', 'kind': 'action', 'text': 'Leg off and latched if VHigh > 45 V, |I1| > 4 A or LOW1 > 20 V.'},
         {'id': 'direction', 'label': 'Direction check (-0.2 A)', 'kind': 'action', 'confirm': 'Start CURRENT mode at -0.2 A (power from LOW1 into VHigh)?',
          'text': 'I1 must read about -0.2 A and the 12 V supply must deliver current. The start-up is recorded by the firmware scope.'},
         {'id': 'i050', 'label': '0.50 A', 'kind': 'action', 'text': 'Reference -0.50 A, settle 2.5 s.'},
         {'id': 'i100', 'label': '1.00 A', 'kind': 'action', 'text': 'Reference -1.00 A, settle 2.5 s.'},
         {'id': 'i125', 'label': '1.25 A', 'kind': 'action', 'text': 'Reference -1.25 A, settle 2.5 s.'},
         {'id': 'i150', 'label': '1.50 A', 'kind': 'action', 'text': 'Reference -1.50 A, settle 2.5 s.'},
         {'id': 'snap', 'label': 'Scope snapshot', 'kind': 'action', 'text': 'MSO54 free-running snapshot at 1.5 A (VHigh, LOW1, bleed current).'},
         {'id': 'idle', 'label': 'Back to idle', 'kind': 'action', 'text': 'Reference 0, then the leg off.'},
     ]},
    {'id': 'ov02', 'test': 'L2-OV-02', 'title': 'L2-OV-02 Guard stop',
     'purpose': '2.0 A would settle VHigh near 48.7 V: the guard must open the leg at 45 V, and the bleed brings VHigh back to the supply.',
     'phases': [
         {'id': 'guard', 'label': 'Bench guard', 'kind': 'action', 'text': '45 V, 4 A, LOW1 20 V; clears any trip.'},
         {'id': 'start', 'label': 'Start at 1.25 A', 'kind': 'action', 'confirm': 'Start CURRENT mode at -1.25 A?', 'text': 'VHigh settles near 38 V.'},
         {'id': 'arm', 'label': 'Arm the scopes', 'kind': 'action', 'text': 'Firmware scope (triggers on the trip) and MSO54 on VHigh rising at 43 V.'},
         {'id': 'run', 'label': 'Step to 2.0 A', 'kind': 'action', 'confirm': 'Step to -2.0 A until the guard stops the leg?',
          'text': 'Waits for the trip, reads both scopes, records VHigh after the stop.'},
         {'id': 'idle', 'label': 'Back to idle', 'kind': 'action', 'text': 'Reference 0, clear the trip, leg off.'},
     ]},
    {'id': 'ov03', 'test': 'L2-OV-03', 'title': 'L2-OV-03 Which MOSFET (#11)',
     'purpose': 'During the rise, which MOSFET blocks VHigh, for how long, and with which peak? Vds(Q202) = switch node, '
                'Vds(Q201) = VHigh - switch node. Map ticket #11.',
     'phases': [
         {'id': 'rewire', 'label': 'Switch-node probe', 'kind': 'check',
          'text': 'Supplies may stay on, leg idle. Move a probe to the switch node of leg 1 (L201 side of Q201/Q202), ground on PGND, '
                  'and give its channel. VHigh stays on its own probe: Vds(Q201) = VHigh - switch node is computed from the two '
                  '(and shown on the scope as MATH1); no second VHigh probe is needed. TP203 is not needed here.',
          'inputs': [('CH_SW', 'Switch-node channel', 'CH4'), ('IL_CHANNEL', 'TP203 channel (none now)', 'none')]},
         {'id': 'guard', 'label': 'Bench guard', 'kind': 'action', 'text': '45 V, 4 A, LOW1 20 V; clears any trip.'},
         {'id': 'start', 'label': 'Start at 1.25 A', 'kind': 'action', 'confirm': 'Start CURRENT mode at -1.25 A?', 'text': ''},
         {'id': 'fast', 'label': 'Fast capture at 43 V', 'kind': 'action', 'confirm': 'Step to -2.0 A until the guard stops the leg?',
          'text': 'MSO54 at 1 us/div, trigger VHigh rising at 43 V: the switching edges of both MOSFETs near the top of the rise.'},
         {'id': 'restart', 'label': 'Restart at 1.25 A', 'kind': 'action', 'confirm': 'Clear the trip and start again at -1.25 A?', 'text': ''},
         {'id': 'long', 'label': 'Peak-detect capture', 'kind': 'action', 'confirm': 'Step to -2.0 A until the guard stops the leg?',
          'text': 'MSO54 at 40 ms/div in peak detect, trigger VHigh rising at 43 V: the highest Vds of each MOSFET over the whole rise.'},
         {'id': 'idle', 'label': 'Back to idle', 'kind': 'action', 'text': 'Reference 0, clear the trip, leg off.'},
     ]},
    {'id': 'dis01', 'test': 'L2-DIS-01', 'title': 'L2-DIS-01 Real disconnect (#12)',
     'purpose': 'Does the board power itself from LOW1, and does the leg keep switching when the VHigh supply lead is opened? '
                'Also the first look at the pull-out itself (H5). Map ticket #12.',
     'phases': [
         {'id': 'selfpower', 'label': 'Self-powering from LOW1', 'kind': 'check', 'answer': 'dis_selfpower',
          'text': 'Unplug the Spin USB. VHigh supply OFF (leave it connected), LOW1 at 12 V ON. Does the board come up from LOW1 alone '
                  '(Spin LED, +12 V of the Feeder, VHigh around 11 V through the body diode)? Answer, then plug USB back in and switch the '
                  'VHigh supply back ON.'},
         {'id': 'board', 'label': 'Find the board again', 'kind': 'action', 'text': 'USB is back: the port may have changed.'},
         {'id': 'guard', 'label': 'Bench guard', 'kind': 'action', 'text': '45 V, 4 A, LOW1 20 V; clears any trip.'},
         {'id': 'start', 'label': 'Start at 0.5 A', 'kind': 'action', 'confirm': 'Start CURRENT mode at -0.5 A?',
          'text': 'At 0.5 A the supply still delivers part of the power: opening its lead makes VHigh drop to the bleed level (about 23 V).'},
         {'id': 'arm', 'label': 'Arm the scope', 'kind': 'action', 'text': 'MSO54 at 40 ms/div, peak detect, trigger VHigh falling at 29 V.'},
         {'id': 'pull', 'label': 'Open the VHigh lead', 'kind': 'action',
          'confirm': 'Open the VHigh supply lead now (pull it at the board side of the diode), then press OK.',
          'text': 'Waits for the trigger, captures, and reads the board: the current should stay at -0.5 A.'},
         {'id': 'switching', 'label': 'Still switching?', 'kind': 'check', 'answer': 'dis_switching',
          'text': 'Did the leg keep switching after the pull-out (readings, switch node, sound)?'},
         {'id': 'idle', 'label': 'Reconnect, back to idle', 'kind': 'action', 'text': 'Leg off. Then reconnect the VHigh lead.'},
     ]},
    {'id': 'stp01', 'test': 'L2-STP-01', 'title': 'L2-STP-01 Duty step',
     'purpose': 'F-2 on the board: open-loop duty step 0.4 -> 0.5 at 30 V into 10 ohm. Model (calibrated tank): peak 3.4 A.',
     'phases': [
         {'id': 'rewire', 'label': 'Rewire', 'kind': 'check',
          'text': 'Both supplies OFF, wait for VHigh and LOW1 below 5 V. Disconnect the LOW1 supply; 10 ohm / 50 W load across LOW1. '
                  'VHigh supply to 30 V (keep the bleed and the diode). Now clip the TP203 probe (ground on DGND). VHigh supply ON.',
          'inputs': [('R_LOAD_OHM', 'LOW1 load, measured (ohm)', '10'), ('IL_CHANNEL', 'TP203 channel', 'CH4'), ('CH_SW', 'Switch-node channel', 'none')]},
         {'id': 'guard', 'label': 'Guard and duties', 'kind': 'action', 'text': '40 V, 6.5 A, LOW1 20 V; duty 0.4 then 0.5.'},
         {'id': 'start', 'label': 'Start STEP mode', 'kind': 'action', 'confirm': 'Start STEP mode (soft start to duty 0.4)?',
          'text': 'Soft start to duty 0.4 in about 100 ms; checks the guard did not trip.'},
         {'id': 'arm', 'label': 'Arm the scopes', 'kind': 'action', 'text': 'Firmware scope and MSO54 on TP203 rising at 1.35 V (3.5 A), 200 us/div.'},
         {'id': 'step', 'label': 'Duty step 0.4 -> 0.5', 'kind': 'action', 'confirm': 'Step the duty to 0.5?',
          'text': 'Waits for the MSO54, captures both scopes, records the settled point.'},
         {'id': 'idle', 'label': 'Back to idle', 'kind': 'action', 'text': 'Duty back to 0.4, leg off.'},
     ]},
]
BY_ID = {t['id']: t for t in TESTS}


# ---------------------------------------------------------------- board connection
class Board:
    """@brief One persistent ThingSet connection, shared by the actions and the live readings."""

    def __init__(self):
        self.lock = threading.Lock()
        self.ts = None
        self.port = None

    def connect(self, port: str) -> None:
        self.close()
        self.ts = bc.shell(port)
        self.port = port

    def close(self) -> None:
        if self.ts is not None:
            try:
                self.ts.ser.close()
            except Exception:  # noqa: BLE001
                pass
        self.ts = None

    def need(self):
        if self.ts is None:
            raise bc.BenchError('no board connected: Setup -> Find the board')
        return self.ts


# ---------------------------------------------------------------- server state
class App:
    def __init__(self, session: Path):
        self.board = Board()
        self.job = {'busy': False, 'label': '', 'error': '', 'done': ''}
        self.log: list[str] = []
        self.live: dict = {}
        self.live_time = 0.0
        self.open(session)
        threading.Thread(target=self._poll, daemon=True).start()

    # -- session
    def open(self, session: Path) -> None:
        self.session = session
        session.mkdir(parents=True, exist_ok=True)
        self.env_file = session / 'session.env'
        if not self.env_file.exists():
            self.set_env({'SESSION_STARTED': dt.datetime.now().isoformat(timespec='seconds')})
        port = self.env().get('TS_PORT')
        if port and self.board.ts is None:
            try:
                self.board.connect(port)
            except BaseException:  # noqa: BLE001  (shown as not connected)
                self.board.close()

    def env(self) -> dict:
        return bc.parse_env(self.env_file)

    def set_env(self, values: dict) -> None:
        env = self.env() if self.env_file.exists() else {}
        for k, v in values.items():
            v = str(v).strip()
            if v.count(',') == 1 and v.replace(',', '', 1).replace('.', '', 1).lstrip('-').isdigit():
                v = v.replace(',', '.')
            env[k] = v
        self.env_file.write_text(''.join(f"{k}='{str(v).replace(chr(39), chr(34))}'\n" for k, v in env.items()))

    def phases(self) -> dict:
        f = self.session / 'phases.json'
        return json.loads(f.read_text()) if f.exists() else {}

    def mark(self, test: str, phase: str, state: str, text: str) -> None:
        ph = self.phases()
        ph.setdefault(test, {})[phase] = {'state': state, 'time': dt.datetime.now().isoformat(timespec='seconds'), 'text': text}
        (self.session / 'phases.json').write_text(json.dumps(ph, indent=1))

    def say(self, text: str) -> None:
        line = f'{dt.datetime.now().strftime("%H:%M:%S")}  {text}'
        print(line, flush=True)
        self.log.append(line)
        self.log = self.log[-300:]
        with open(self.session / 'app_log.txt', 'a') as f:
            f.write(line + '\n')

    # -- live readings (every second when no action holds the board)
    def _poll(self) -> None:
        while True:
            time.sleep(1.0)
            if self.board.ts is None or not self.board.lock.acquire(blocking=False):
                continue
            try:
                ts = self.board.ts
                self.live = {k: bc.get(ts, p) for k, p in (('VHigh', 'Measurements/rVHigh_V'), ('V1Low', 'Measurements/rV1Low_V'),
                                                           ('I1Low', 'Measurements/rI1Low_A'), ('duty', 'Measurements/rDuty'),
                                                           ('Mode', 'Converter/Mode'), ('ref', 'Converter/wCurrentRef_A'),
                                                           ('tripped', 'Converter/rTripped'), ('reason', 'Converter/rTripReason'))}
                self.live_time = time.time()
            except BaseException:  # noqa: BLE001
                self.live = {}
            finally:
                self.board.lock.release()

    # -- jobs
    def run(self, label: str, fn) -> None:
        if self.job['busy']:
            raise bc.BenchError(f'busy: {self.job["label"]}')
        self.job = {'busy': True, 'label': label, 'error': '', 'done': ''}

        def work():
            try:
                with self.board.lock:
                    self.job['done'] = fn() or 'done'
            except BaseException as ex:  # noqa: BLE001  (SystemExit from bench_ctl included)
                self.job['error'] = f'{ex}'
                self.say(f'ERROR {label}: {ex}')
                traceback.print_exc()
            finally:
                self.job['busy'] = False
        threading.Thread(target=work, daemon=True).start()

    def record(self) -> list[dict]:
        rows = bc.criteria(self.session)
        (self.session / 'sim.log').write_text(''.join('\t'.join(['@@', r['id'], r['verdict'], r['desc'], r['limit'], r['measured']]) + '\n' for r in rows))
        (self.session / 'summary.json').write_text(json.dumps({'kind': 'bench', 'cases': {}}, indent=1))
        (self.session / 'report.html').write_text(bc.report(self.session, rows), encoding='utf-8')
        import control_center
        control_center.write(RESULTS)
        return rows

    # -- actions
    def stop(self) -> str:
        """@brief The STOP button: leg off whatever runs (does not wait for a running action)."""
        ts = self.board.need()
        for path, v in (('Converter/Mode', 0), ('Converter/wCurrentRef_A', 0), ('Converter/wStep', 0)):
            try:
                bc.put(ts, path, v)
            except BaseException:  # noqa: BLE001
                pass
        self.say('STOP: Mode 0, reference 0, step 0')
        return 'leg off'

    def phase(self, tid: str, pid: str, inputs: dict, answer: dict | None) -> None:
        t = BY_ID[tid]
        p = next(x for x in t['phases'] if x['id'] == pid)
        if inputs:
            self.set_env(inputs)
        if answer is not None and p.get('answer'):
            f = self.session / 'operator.json'
            op = json.loads(f.read_text()) if f.exists() else {}
            op[p['answer']] = {'answer': answer.get('answer', ''), 'text': answer.get('text', ''), 'time': dt.datetime.now().isoformat(timespec='seconds')}
            f.write_text(json.dumps(op, indent=1))
        if p['kind'] == 'check':
            self.mark(tid, pid, 'done', 'confirmed' + (f': {answer.get("answer", "")}' if answer else ''))
            self.say(f'{t["test"]} {p["label"]}: confirmed')
            self.record()
            return
        fn = getattr(self, f'do_{tid}_{pid}', None) or getattr(self, f'do_any_{pid}')

        def go():
            self.say(f'{t["test"]} {p["label"]} ...')
            try:
                text = fn()
            except BaseException as ex:
                self.mark(tid, pid, 'failed', str(ex))
                try:
                    self.record()
                except BaseException:  # noqa: BLE001
                    pass
                raise
            self.mark(tid, pid, 'done', text or 'done')
            self.say(f'{t["test"]} {p["label"]}: {text}')
            self.record()
            return text
        self.run(f'{t["test"]} {p["label"]}', go)

    # helpers
    def _ts(self):
        return self.board.need()

    def _s(self) -> str:
        return str(self.session)

    def _settle(self, name: str, seconds: float = 2.5) -> dict:
        out = bc.settle(self._ts(), name, self._s(), seconds)
        s = bc.settle_summary(out)
        if str(s['tripped']).lower() in ('true', '1'):
            bc.put(self._ts(), 'Converter/Mode', 0)
            raise bc.BenchError(f'guard tripped: {s["reason"]} (VHigh {s["VHigh_V"]} V, I1 {s["I1Low_A"]} A, LOW1 {s["V1Low_V"]} V)')
        return s

    def _guard(self, ov=45, il=4.0, v1=20) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/Mode', 0)
        for path, v in (('Converter/wOvLimit_V', ov), ('Converter/wILimit_A', il), ('Converter/wV1LowLimit_V', v1), ('Converter/wClear', 1)):
            bc.put(ts, path, v)
        return f'guard {ov} V, {il} A, LOW1 {v1} V; trip cleared'

    def _start(self, ref: float, name: str | None = None) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/wClear', 1)
        bc.put(ts, 'Converter/wCurrentRef_A', ref)
        bc.put(ts, 'Converter/Mode', 1)
        if name:
            s = self._settle(name, 2.5)
            return f'VHigh {s["VHigh_V"]} V, I1 {s["I1Low_A"]} A, LOW1 {s["V1Low_V"]} V'
        time.sleep(2.0)
        d = bc.read_all(ts)
        if str(d['rTripped']).lower() in ('true', '1'):
            raise bc.BenchError(f'guard tripped: {d["rTripReason"]}')
        return f'VHigh {float(d["rVHigh_V"]):.2f} V, I1 {float(d["rI1Low_A"]):.3f} A'

    def _idle(self, clear=False) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/wCurrentRef_A', 0)
        time.sleep(0.5)
        bc.put(ts, 'Converter/Mode', 0)
        bc.put(ts, 'Converter/wStep', 0)
        if clear:
            bc.put(ts, 'Converter/wClear', 1)
        return 'leg off'

    def _mso(self) -> bool:
        return self.env().get('USE_MSO', 'yes').lower().startswith('y')

    def _step_to_trip(self, ref: float, trip_name: str, mso_name: str | None, fw_name: str | None) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/wCurrentRef_A', ref)
        d = bc.wait_trip(ts, self._s(), trip_name, 5.0)
        out = []
        if d is None:
            self._idle()
            out.append('no trip within 5 s: leg stopped by the app')
        else:
            out.append(f'guard stopped the leg at {float(d["rTripValue"]):.2f} ({d["rTripReason"]}) after {d["seconds_waited"]} s')
        if fw_name:
            try:
                out.append(bc.fwscope_read(ts, self._s(), fw_name))
            except BaseException as ex:  # noqa: BLE001
                out.append(f'firmware scope: {ex}')
        if mso_name and self._mso():
            out.append('MSO54 triggered' if bc.mso_wait(5.0) else 'MSO54 did not trigger')
            out.append(bc.mso_capture(self._s(), mso_name))
        return '; '.join(out)

    # setup
    def do_setup_board(self) -> str:
        return self.do_any_board()

    def do_any_board(self) -> str:
        r = subprocess.run([sys.executable, str(HERE / 'bench_ctl.py'), 'find'], capture_output=True, text=True, timeout=120)
        port = r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip() else ''
        if not port:
            raise bc.BenchError('no board answers with the bench firmware (replug its USB after a flash). ' + r.stderr.strip()[-300:])
        self.board.connect(port)
        ts = self._ts()
        ident = {k: bc.get(ts, f'Build/{k}') for k in ('rCommit', 'rDirty')}
        ex = Path.home() / 'code' / 'examples'
        commit = subprocess.run(['git', '-C', str(ex), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        self.set_env({'TS_PORT': port, 'FW_EXAMPLES_COMMIT': commit, 'FW_BUILD_COMMIT': ident['rCommit']})
        return f'bench firmware on {port} (examples {commit[:7]})'

    def do_setup_scope(self) -> str:
        if not self._mso():
            return 'no MSO54 in this session: firmware scope only (L2-STP-01 becomes INFO)'
        return bc.mso_check()

    def do_setup_sensors(self) -> str:
        s = self._settle('sensor_check', 0.5)
        env = self.env()
        msg = [f'board VHigh {s["VHigh_V"]} V (meter {env.get("VHIGH_PSU_V")}), LOW1 {s["V1Low_V"]} V (meter {env.get("VLOW_PSU_V")}), '
               f'I1 {s["I1Low_A"]} A with the PWM off']
        if abs(float(s['I1Low_A'])) > 0.1:
            msg.append('WARNING: I1_LOW is not about 0 A: the current loop would act on a wrong current')
        return '; '.join(msg)

    # L2-OV-01
    def do_any_guard(self) -> str:
        return self._guard()

    def do_ov01_direction(self) -> str:
        ts = self._ts()
        bc.put(ts, 'Scope/wArm', 1)
        r = self._start(-0.2, 'direction_check')
        return r + ' (expected about -0.2 A, and the 12 V supply delivering current)'

    def _ov01_step(self, amps: float) -> str:
        bc.put(self._ts(), 'Converter/wCurrentRef_A', -amps)
        s = self._settle(f'ov01_{amps:.2f}A', 2.5)
        return f'VHigh {s["VHigh_V"]} V, I1 {s["I1Low_A"]} A, LOW1 {s["V1Low_V"]} V'

    def do_ov01_i050(self): return self._ov01_step(0.50)
    def do_ov01_i100(self): return self._ov01_step(1.00)
    def do_ov01_i125(self): return self._ov01_step(1.25)
    def do_ov01_i150(self): return self._ov01_step(1.50)

    def do_ov01_snap(self) -> str:
        if not self._mso():
            return 'no MSO54 in this session'
        a = bc.mso_arm(self._s(), 'ov', auto=True)
        ok = bc.mso_wait(15)
        return f'{a}; {"stopped" if ok else "no stop"}; {bc.mso_capture(self._s(), "ov01_1.50A")}'

    def do_any_idle(self) -> str:
        return self._idle(clear=True)

    # L2-OV-02
    def do_ov02_start(self): return self._start(-1.25)

    def do_ov02_arm(self) -> str:
        bc.put(self._ts(), 'Scope/wArm', 1)
        return 'firmware scope armed; ' + (bc.mso_arm(self._s(), 'ov', source='vhigh', level=43, hscale=0.05, hpos=30) if self._mso() else 'no MSO54')

    def do_ov02_run(self) -> str:
        r = self._step_to_trip(-2.0, 'ov02_trip', 'ov02', 'ov02')
        s = bc.settle_summary(bc.settle(self._ts(), 'ov02_after', self._s(), 2.0))  # the leg is stopped and latched here
        return f'{r}; VHigh after {s["VHigh_V"]} V'

    # L2-OV-03 (#11)
    def do_ov03_start(self): return self._start(-1.25)
    do_ov03_restart = do_ov03_start

    def do_ov03_fast(self) -> str:
        if not self._mso():
            raise bc.BenchError('L2-OV-03 needs the MSO54')
        a = bc.mso_arm(self._s(), 'sw', source='vhigh', level=43, hscale=1e-6, hpos=50)
        return a + '; ' + self._step_to_trip(-2.0, 'ov03_trip', 'ov03_fast', None)

    def do_ov03_long(self) -> str:
        if not self._mso():
            raise bc.BenchError('L2-OV-03 needs the MSO54')
        a = bc.mso_arm(self._s(), 'ov', source='vhigh', level=43, hscale=0.04, hpos=30, peak=True)
        return a + '; ' + self._step_to_trip(-2.0, 'ov03_trip_long', 'ov03_long', None)

    # L2-DIS-01 (#12)
    def do_dis01_start(self): return self._start(-0.5, 'dis_before')

    def do_dis01_arm(self) -> str:
        if not self._mso():
            return 'no MSO54: the pull-out is judged on the board readings only'
        return bc.mso_arm(self._s(), 'dis', source='vhigh', level=29, slope='FALL', hscale=0.04, hpos=30, peak=True)

    def do_dis01_pull(self) -> str:
        out = []
        if self._mso():
            out.append('MSO54 triggered' if bc.mso_wait(10) else 'MSO54 did not trigger (VHigh did not fall below 29 V)')
            out.append(bc.mso_capture(self._s(), 'dis01'))
        s = bc.settle_summary(bc.settle(self._ts(), 'dis_after', self._s(), 1.0))
        out.append(f'after the pull-out: VHigh {s["VHigh_V"]} V, I1 {s["I1Low_A"]} A, tripped {s["tripped"]}')
        return '; '.join(out)

    # L2-STP-01
    def do_stp01_guard(self) -> str:
        r = self._guard(40, 6.5, 20)
        ts = self._ts()
        for path, v in (('Converter/wDuty0', 0.4), ('Converter/wDuty1', 0.5), ('Converter/wStep', 0)):
            bc.put(ts, path, v)
        return r + '; duty 0.4 -> 0.5'

    def do_stp01_start(self) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/Mode', 2)
        s = self._settle('stp_before', 1.5)
        return f'duty {s["duty"]}, LOW1 {s["V1Low_V"]} V, I1 {s["I1Low_A"]} A'

    def do_stp01_arm(self) -> str:
        bc.put(self._ts(), 'Scope/wArm', 1)
        return 'firmware scope armed; ' + (bc.mso_arm(self._s(), 'stp', source='il', level=1.35) if self._mso() else 'no MSO54')

    def do_stp01_step(self) -> str:
        ts = self._ts()
        bc.put(ts, 'Converter/wStep', 1)
        time.sleep(1.0)
        out = []
        if self._mso():
            out.append('MSO54 triggered' if bc.mso_wait(3) else 'MSO54 did not trigger')
            out.append(bc.mso_capture(self._s(), 'stp01'))
        try:
            out.append(bc.fwscope_read(ts, self._s(), 'stp01'))
        except BaseException as ex:  # noqa: BLE001
            out.append(f'firmware scope: {ex}')
        s = bc.settle_summary(bc.settle(ts, 'stp_after', self._s(), 0.5))
        out.append(f'after: duty {s["duty"]}, I1 {s["I1Low_A"]} A, LOW1 {s["V1Low_V"]} V')
        return '; '.join(out)

    # -- view
    def state(self) -> dict:
        rows = []
        try:
            rows = bc.criteria(self.session)
        except BaseException as ex:  # noqa: BLE001
            rows = [{'id': '-', 'verdict': 'INFO', 'desc': 'criteria failed', 'limit': '', 'measured': str(ex)}]
        caps = sorted(str(p.parent.relative_to(self.session)) for p in (self.session / 'scope').glob('*/screen.png')) \
            if (self.session / 'scope').exists() else []
        return {'session': self.session.name, 'env': self.env(), 'phases': self.phases(), 'tests': TESTS,
                'live': self.live, 'live_age': round(time.time() - self.live_time, 1) if self.live_time else None,
                'connected': self.board.ts is not None, 'port': self.board.port, 'job': self.job, 'log': self.log[-40:],
                'rows': rows, 'captures': caps}


# ---------------------------------------------------------------- HTTP
def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str = 'application/json') -> None:
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path in ('/', '/index.html'):
                return self._send(200, (WEB / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/state':
                return self._json(app.state())
            if path.startswith('/results/'):  # the control center, reports, captures
                f = (RESULTS / path[len('/results/'):]).resolve()
                if RESULTS.resolve() in f.parents and f.is_file():
                    return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
            return self._send(404, b'not found', 'text/plain')

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                if path == '/api/phase':
                    app.phase(body['test'], body['phase'], body.get('inputs') or {}, body.get('answer'))
                elif path == '/api/stop':
                    app.stop()
                elif path == '/api/record':
                    app.record()
                    app.say('record written: report.html and the control center')
                elif path == '/api/note':
                    app.set_env({'NOTES': (app.env().get('NOTES', '') + ' | ' if app.env().get('NOTES') else '') + body['text']})
                    app.say(f'note: {body["text"]}')
                elif path == '/api/new':
                    app.board.close()
                    app.open(RESULTS / f'bench_{dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")}')
                    app.say(f'new session {app.session.name}')
                elif path == '/api/end':
                    app.set_env({'SESSION_ENDED': dt.datetime.now().isoformat(timespec='seconds')})
                    app.record()
                    app.say('session ended')
                else:
                    return self._json({'error': 'unknown'}, 404)
                return self._json({'ok': True})
            except BaseException as ex:  # noqa: BLE001
                return self._json({'error': str(ex)}, 400)
    return H


def newest_open_session(max_age_h: float = 12.0) -> Path | None:
    """@brief The newest session never ended and started less than max_age_h ago (an aborted older one is left alone)."""
    for d in sorted(RESULTS.glob('bench_*'), reverse=True):
        env = bc.parse_env(d / 'session.env')
        if not env or env.get('SESSION_ENDED'):
            continue
        try:
            started = dt.datetime.fromisoformat(env.get('SESSION_STARTED', ''))
        except ValueError:
            continue
        if (dt.datetime.now(started.tzinfo) - started).total_seconds() < max_age_h * 3600:
            return d
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--new', action='store_true', help='start a new session')
    ap.add_argument('--session', type=Path, help='open this session folder')
    ap.add_argument('--port', type=int, default=8770)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    sess = a.session.resolve() if a.session else (None if a.new else newest_open_session())
    sess = sess or RESULTS / f'bench_{dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")}'
    app = App(sess)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(app))
    url = f'http://127.0.0.1:{a.port}/'
    print(f'bench app on {url}  (session {sess.name}); Ctrl-C to stop', flush=True)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
