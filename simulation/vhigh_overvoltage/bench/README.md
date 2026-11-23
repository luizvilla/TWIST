# Bench sessions (level L2)

These sessions confirm on a real TWIST what the model predicts (finding F-1, and finding F-2 at low energy). They run before any protection is built. Every bench number is compared with the model prediction of the same setup: cases D-L2P-01..06 in [`../model/catalogue.json`](../model/catalogue.json).

Run a session:

```bash
cd simulation/vhigh_overvoltage/bench
./bench_wizard.sh                                    # a new session in ../results/bench_<date>_<time>/
SESSION=../results/bench_<...> ./bench_wizard.sh     # resume one (values already entered are offered again)
```

The wizard walks through 12 stages, asks before every power-on and every step, and finishes by writing the session's `report.html` and refreshing [`../results/control-center.html`](../results/control-center.html) (Bench tab).

## Code

| Part | Where | Notes |
|---|---|---|
| Firmware | `~/code/examples`, branch `vhigh-investigation`, `TWIST/DC_DC/vhigh_investigation/` | Same structure as `buck_voltage_mode` on `ownstudio/buck-extras` (ThingSet on the second USB serial port, firmware scope, build identity). Leg 1 only. |
| Core | `~/code/Core` `main`, as a worktree in `~/code/Core-vhigh` | Keeps the working Core checkout untouched. The Core2 safety API is not used: it is experimental. |
| Bench helper | [`bench_ctl.py`](bench_ctl.py) | ThingSet client (Core2 `tests/common/spoc/thingset.py`), MSO54 (Core2 `tests/common/scope.py`), record and report. Run with `~/code/Core2/.venv/bin/python`. |
| Wizard | [`bench_wizard.sh`](bench_wizard.sh) | Generated with the `/wizard` skill; the library above the STAGES marker is the skill's template. |

Firmware commands, over ThingSet (`Converter/...`):

| Object | Use |
|---|---|
| `Mode` | 0 idle, 1 CURRENT (average-current loop on I1_LOW, feedforward V1/VHigh plus a PI at about 300 Hz), 2 STEP (open-loop duty) |
| `wCurrentRef_A` | Current reference; negative pushes power from LOW1 into VHigh. Ramped at 2 A/s (`rCurrentApplied_A`). |
| `wDuty0`, `wDuty1`, `wStep` | STEP mode: duty_0, or duty_1 while `wStep` = 1 |
| `wOvLimit_V`, `wILimit_A`, `wV1LowLimit_V` | Bench guard: the leg opens and stays off when VHigh, \|I1_LOW\| or LOW1 exceed them (checked every 100 us) |
| `rTripped`, `rTripReason`, `rTripValue`, `wClear` | Guard state; `wClear` = 1 clears a trip in idle |
| `Scope/...` | Firmware scope (100 us per sample, 1024 samples): armed by `wArm`, triggered by a change of `Mode`, `wStep` or a guard trip |

The guard protects the test. It is not the fix: at 100 us it is far too slow for the fast cases the investigation is about.

## Setup

| Test | VHigh | LOW1 | Other | Expected (model) |
|---|---|---|---|---|
| L2-OV-01 | Lab supply 60 V, 1 A limit, plus a 200 ohm / 30 W bleed | Lab supply 24 V, 2 A limit | MSO54 CH1 VHigh, CH2 LOW1, CH3 iL, CH4 SW | VHigh settles at 60 / 60 / 69.2 / 74.2 V for 0.5 / 0.75 / 1.0 / 1.15 A into VHigh |
| L2-OV-02 | Same | Same | MSO54 triggered at 76 V | 1.5 A would settle at about 85 V: the guard opens the leg at 80 V, and the bleed brings VHigh back to 60 V |
| L2-STP-01 | Lab supply 30 V, plus the bleed | 10 ohm / 50 W load, no supply | MSO54 CH3 trigger at 3.5 A, 200 us/div | Duty step 0.4 → 0.5: iL peaks at about 5.2 A |

Why a bleed resistor: a lab supply cannot sink current, so the energy pushed into VHigh has to go somewhere. Through the resistor, VHigh settles at about the square root of P·R instead of running away, so the test limits itself even if the guard failed. It is also what discharges VHigh after the test. Keep it connected at all times.

Design choices behind the setup:

- L2-OV-01 confirms the main mechanism with no disconnect at all: if VHigh rises above the supply's set point while the supply is still connected, F-1 is on the board.
- L2-OV-02 keeps the bleed (rather than removing it) so that no capacitor is left charged at 80 V after the stop.
- L2-STP-01 runs at 30 V and with a 0.1 duty step so that the overshoot stays at about 5 A, under the 7 A I1_LOW range.
- The low-side capacitance in D-L2P-06 (60 uF) is an assumption. The ringing frequency in the capture gives its real value.

## Results

Each session writes `../results/bench_<date>_<time>/`:
- `session.env`: board, operator, firmware commits, measured resistors;
- `steps/*.json`: averaged readings at each step;
- `fwscope/*.json` and `scope/<name>/`: MSO54 screen, measurements and waveforms;
- `sim.log` (`@@` result lines), `report.html`.
