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
| `wOvLimit_V`, `wILimit_A`, `wV1LowLimit_V` | Bench guard: the leg opens and stays off when VHigh, \|I1_LOW\| or LOW1 exceed them (checked every 100 us). The wizard sets 45 V, 2.5 A, 20 V. |
| `rTripped`, `rTripReason`, `rTripValue`, `wClear` | Guard state; `wClear` = 1 clears a trip in idle |
| `Scope/...` | Firmware scope (100 us per sample, 1024 samples): armed by `wArm`, triggered by a change of `Mode`, `wStep` or a guard trip |

The guard protects the test. It is not the fix: at 100 us it is far too slow for the fast cases the investigation is about.

## Setup

| Test | VHigh | LOW1 | Other | Expected (model) |
|---|---|---|---|---|
| L2-OV-01 | Lab supply 32 V, 1 A limit, through a series Schottky diode, plus a 100 ohm / 30 W bleed on the board side | Lab supply 12 V, 3 A limit | MSO54 CH1 VHigh, CH2 LOW1, CH3 iL on TP203, CH4 SW | VHigh settles at 32.0 / 34.5 / 38.6 / 42.2 V for 0.5 / 1.0 / 1.25 / 1.5 A into VHigh |
| L2-OV-02 | Same | Same | MSO54 triggered at 43 V | 2.0 A would settle at about 48.7 V: the guard opens the leg at 45 V, and the bleed brings VHigh back to 32 V |
| L2-STP-01 | Lab supply 30 V, plus the bleed | 10 ohm / 50 W load, no supply | MSO54 CH3 (TP203) trigger at 1.35 V (3.5 A), 200 us/div | Duty step 0.4 → 0.5: iL peaks at about 5.2 A |

Why a bleed resistor: a lab supply cannot sink current, so the energy pushed into VHigh has to go somewhere. Through the resistor, VHigh settles at about the square root of P·R instead of running away, so the test limits itself even if the guard failed. It is also what discharges VHigh after the test. Keep it connected at all times.

Why a diode in series with the VHigh supply (anode on the supply, cathode on the board; Schottky, 40 V / 3 A or more):
- VHigh is meant to rise above the set point, up to 45 V. The diode keeps that voltage off the supply's output, which may be rated for only 30 to 32 V.
- If the supply has a crowbar over-voltage protection, its short cannot reach the board's charged VHigh capacitors.
- The test is unchanged, because a lab supply cannot sink current anyway. The set point at the board drops by one diode drop (about 0.4 V): stage 6 asks for VHigh measured on the board side, and the L2-OV-01 threshold uses that value. Settled voltages above the set point depend only on the injected power and the bleed, so the predictions hold.
- The diode carries only the bleed current (0.3 to 0.5 A). A diode on the low-side supply is optional: it only matters if the current sign is wrong, and it carries the full low-side current (about 1 W).

Design choices behind the setup:

- L2-OV-01 confirms the main mechanism with no disconnect at all: if VHigh rises above the supply's set point while the supply is still connected, F-1 is on the board.
- L2-OV-02 keeps the bleed (rather than removing it) so that no capacitor is left charged at 45 V after the stop.
- The voltages are scaled to the supplies at hand (32 V and 12 V; the model was first set up for 60 V and 24 V). The mechanism does not depend on the voltage: VHigh rises as soon as the injected power exceeds what the bleed draws at the set point (32² / 100 = 10.2 W, reached at 0.85 A from 12 V).
- L2-STP-01 runs at 30 V and with a 0.1 duty step so that the overshoot stays at about 5 A, under the 7 A I1_LOW range.
- The low-side capacitance in D-L2P-06 (60 uF) is an assumption. The ringing frequency in the capture gives its real value.

## Probes

Passive 10x voltage probes only, all referenced to the board ground; no current probe is needed.

| Channel | Point | Ground | Scale |
|---|---|---|---|
| CH1 | VHigh terminal | PGND (TP5001) | 5 V/div (2 V/div for the duty step) |
| CH2 | LOW1 terminal | PGND | 5 V/div |
| CH3 | TP203, `I_{I1Low}`: the on-board ACS730 after its level shift | DGND (TP202 or TP204) | 1.0 V at 0 A, +0.1 V per A |
| CH4 (optional) | Switch node of leg 1 | PGND | 10 V/div |

The ACS730 (U202) sits between L201 and the low-side capacitors (C203 47 uF switched by Q203, plus C206, C209 and C212 at 4.7 uF), so TP203 carries the true inductor current, with about 1 MHz of bandwidth. A current probe on the LOW1 wire would only see the load current, smoothed by those capacitors. The record converts CH3 to amps and checks the scale against the board's own reading before the step (L2-STP-01.b). The scope ground is earth: never clip a probe ground anywhere but the board ground.

## Without an oscilloscope

Stage 5 asks whether an MSO54 is connected. Without one, the session uses the board's own measurements (ThingSet) and its firmware scope (100 us per sample):

- L2-OV-01 and L2-OV-02 keep their verdicts: they are judged on settled ThingSet readings and on the guard's trip value.
- L2-STP-01 becomes INFO only. Its ringing has a period of about 280 us, so 100 us sampling misses the true peak. Redo it with the MSO54 for a verdict.

## Results

Each session writes `../results/bench_<date>_<time>/`:
- `session.env`: board, operator, firmware commits, measured resistors;
- `steps/*.json`: averaged readings at each step;
- `fwscope/*.json` and `scope/<name>/`: MSO54 screen, measurements and waveforms;
- `sim.log` (`@@` result lines), `report.html`.
