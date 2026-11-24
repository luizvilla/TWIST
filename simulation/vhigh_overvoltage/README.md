# VHigh overvoltage: why high-side MOSFETs die when VHigh is disconnected

Investigation record, 2026-11-23. Board: TWIST V1.4.3 (also applies to the Ownverter, which shares the power-leg topology).

- **Diagnosis synthesis** (hypotheses, tests, evidence, conclusions, open gaps): [`DIAGNOSIS.md`](DIAGNOSIS.md).
- **Map of where this is going:** wayfinder issue [luizvilla/TWIST#10](https://github.com/luizvilla/TWIST/issues/10), with a Mermaid map of done, open and blocked tickets (#1–#9).
- **Results:** [`results/control-center.html`](results/control-center.html). Every case has interactive figures and links to its campaign.
- **Simulation code:** [`model/`](model/). Its `README.md` explains how to run a campaign and add a case.

## 1. The problem

Several converters have failed when VHigh was disconnected or its supply was switched off. Usually one high-side MOSFET died, sometimes both. The working assumption was that disconnecting VHigh creates a voltage spike that destroys the high-side switch. An active clamp was proposed and drawn on the schematic: a zener plus a blocking diode from Q201's drain (VHigh) to its gate.

### Reported field failures

| # | What happened | What died |
|---|---|---|
| 1 | Ownverter on a skateboard, lab supply on VHigh. A very heavy pilot rode it (after lighter ones), drove away from the supply, and the cable pulled out. | High-side MOSFETs |
| 2 | TWIST feeding a load; the users switched the supply off. | MOSFETs |
| 3 | Ownverter: the supply was disconnected before the low side was powered down. | High-side MOSFETs |
| 4 | Too large a duty-cycle step. | High-side MOSFET |
| 5 | Low-side MOSFETs died on some occasions (circumstances not recorded). When the low side failed, it was probably both low-side MOSFETs, depending on whether one or two legs were in use. | Low-side MOSFETs |

Common factors:
- There was always a lab supply on VHigh.
- The firmware had no protection at all. The Core2 safety API (`~/code/Core2`, ADR 0009) is being written now.

## 2. What the schematic says

| Fact | Consequence |
|---|---|
| Q201/Q202 IPD200N15N3: 150 V rating. Board rating 12–100 V on VHigh, 110 V absolute maximum. | Only 40 V of margin between the absolute maximum and the FET rating. |
| On each leg, VHigh has about 138 µF: C230/C231 (33 µF, 160 V), C224–C229 (4.7 µF X7R, in series pairs), C222/C223. | Once the supply is gone, this is the only thing that can absorb energy pushed into VHigh. |
| There is no TVS on V_High. | Nothing limits the bus voltage. |
| The Feeder (gate drive and control supply) is powered from V_High through JP5001. It starts at 9.7 V and runs down to 8.9 V. | If the converter itself pushes energy into VHigh, it keeps powering itself and keeps switching. Losing the external supply does not stop it. |
| Gate drive: UCC21222 with a bootstrap supply, R215/R216 = 2.2 Ω, D202/D203 gate-sink diodes, R219/R220 = 4.7 kΩ pull-downs. | This is a strong gate driver. A drain-to-gate clamp would have to fight it, and could only turn Q201 on partially. |
| Lab supplies cannot sink current. | Even with the cable still connected, energy flowing back into VHigh has nowhere to go. |

## 3. Hypotheses

The original guess was a fast inductive spike when the cable comes out. The field reports and the schematic point to something slower: **energy flows back into VHigh and has nowhere to go**.

1. **Returned energy with no sink: a slow overvoltage over milliseconds** *(main suspect; matches failures 1 and 3, and possibly 2)*.
   - A synchronous leg running at a fixed duty d behaves like a DC transformer, so VHigh = V_low / d.
   - Anything that pushes current back into VHigh charges the ~138 µF, because neither the supply nor anything else absorbs it. This includes braking, a regenerating motor, a battery, or a closed loop asking for negative current.
   - The bus then ramps by a few to tens of volts per millisecond until a MOSFET avalanches.
   - Fit with failure 1: a heavier pilot means more braking current for the same deceleration, so a faster ramp. The skateboard carries roughly 1 kJ of kinetic energy, while 1 J is enough to take 138 µF from 100 V to about 145 V.
2. **No overvoltage protection** *(certain: the firmware has none)*. This is why hypothesis 1 runs all the way to destruction.
3. **Duty step: the inductor current rings, then an overvoltage follows** *(matches failure 4)*.
   - L201 (33 µH) and the low-side capacitance form a resonant tank at about 3.6 kHz with an impedance of about 0.74 Ω.
   - A 0.2 to 0.8 step at 100 V puts a 60 V step across it, giving tens of amps of current peak.
   - L201 can saturate, and Q201 is switching that current off in buck mode.
   - A step down returns the low-side energy to VHigh.
4. **VHigh collapses, the duty goes to 100%, and the high-side gate drive starves** *(possible for failure 2 if a voltage loop was running)*.
   - At 100% duty the bootstrap capacitor never recharges, and R219 slowly drains it.
   - Q201's gate voltage sags, so it conducts load current only partly on and overheats. This kills the high side only.
   - Not modelled yet (case D-UV-01).
5. **Fast inductive spike from the cable inductance at disconnect** *(the original guess)*.
   - The cable current stops at the plug, not inside the converter.
   - The local ceramic capacitors and C230/C231 sit between the cable and Q201.
   - This mechanism is unlikely to be the main one.

**Why the active clamp doesn't fit.** In hypotheses 1 and 3 the energy keeps arriving for as long as the converter keeps switching. A drain-to-gate clamp holds the voltage by running Q201 in its linear region, so Q201 has to burn all the returned power. In the simulation that is about 1.1 kW continuously at 25 A of braking. Q201 dies in the clamp instead of in avalanche. The clamp also protects only Q201, and it fights the 2.2 Ω / D202 gate drive.

## 4. Simulation

**Model.** Averaged model of one leg ([`model/model.py`](model/model.py)):
- Q201/Q202, L201 with its resistance, about 138 µF on VHigh, and a lab supply with cable inductance and resistance (optionally unable to sink, optionally disconnected).
- Low side: a battery, a passive load (capacitor in parallel with a resistor), or a motor plus rider modelled as a 3 F equivalent capacitor.
- Control: a PI current loop or an open-loop duty.
- Optional protections: overvoltage trip with a latency, duty slew limit, cycle-by-cycle current limit, active clamp.
- The Feeder keeps the PWM running while VHigh is above 8.9 V.

**Limits of the model.** It is averaged over one switching period: no ripple, no parasitic ringing, no device heating, no inductor saturation. It shows where the energy goes, not what the scope will show. Its results are evidence for a hypothesis, never a verdict on the board.

**Pass criteria** for each case:
- Peak Vds(Q201) ≤ 150 V.
- Peak |iL| ≤ 40 A.
- For the clamp cases, the energy dissipated in Q201 ≤ 0.15 J. This figure is an assumed order of magnitude for the single-pulse avalanche rating and still needs checking against the IPD200N15N3 datasheet.

### Results

All cases run for 10 ms with a 100 V supply and 48 V on the low side, unless stated otherwise. Source: campaign `2026-11-23_122549_sim`.

| Case | Scenario | Peak Vds (V) | Peak \|iL\| (A) | Result |
|---|---|---|---|---|
| D-DIS-01 | Boost 8 A, supply that can sink, cable pulled at 2 ms | 173 (150 V crossed at 7.6 ms) | 8 | ✗ reproduces failure 3 |
| D-DIS-02 | Boost 8 A, lab supply connected (cannot sink) | 192 | 8 | ✗ no disconnect needed |
| D-DIS-03 | Boost 2 A, lab supply connected | 120, still rising at +2 V/ms | 2 | ✓ only because the run ends |
| D-SKT-01 | Skateboard braking 8 A, supply connected | 192 | 8 | ✗ |
| D-SKT-02 | Skateboard braking 25 A (heavy pilot) | 367 (150 V at 1.4 ms) | 25 | ✗ reproduces failure 1 |
| D-STP-01 | Duty step 0.2 → 0.8 | 119 | **81** | ✗ reproduces failure 4 |
| D-STP-02 | Duty step 0.8 → 0.2 | 114 | **67** | ✗ |
| D-BEN-01…05 | Buck with disconnect; fixed duty with the supply off (battery, resistive load, motor coasting); step 0.4 → 0.6 | 105–107 | 8–33 | ✓ harmless |
| D-FIX-01 | D-DIS-01 + overvoltage trip at 110 V, 1 ms latency | 117.5 | 8 | ✓ |
| D-FIX-02 | … 100 µs latency | 110.7 | 8 | ✓ |
| D-FIX-03 | … 5 µs (hardware comparator) | 110.0 | 8 | ✓ |
| D-FIX-04 | D-SKT-02 + hardware overvoltage trip, 5 µs | 111.0 | 25 | ✓ |
| D-FIX-05 | D-SKT-02 + firmware overvoltage trip, 1 ms | 143.2 | 25 | ✓ but only 7 V of margin |
| D-FIX-06 | D-STP-01 + duty slew limited to 0.1 per ms | 105 | 13.8 | ✓ |
| D-FIX-07 | D-STP-01 + 20 A cycle-by-cycle current limit | 105 | 20 | ✓ |
| D-FIX-08 | Proposed active clamp at 130 V on D-SKT-02 | 130 | 25 | ✗ Q201 dissipates about 1.1 kW, 9.9 J in 10 ms |
| D-FIX-09 | Proposed active clamp at 130 V on D-DIS-01 | 130 | 8 | ✗ 1.6 J in 8 ms |

The 105 V peaks in the safe cases are the 100 V bus plus the 5 V turn-off spike the model adds (10 nH × 0.5 A/ns).

### Conclusions

1. **Hypothesis 1 explains failures 1 and 3 without any fast spike.** With a lab supply, *any* power flowing into VHigh is dangerous, even with the cable connected. Disconnecting removes the last sink and makes it worse.
2. **Switching the supply off is harmless on its own.** It becomes dangerous only if the low side can return energy (battery, electronic load, motor) or if a control loop pushes current back. Failure 2 needs these details before it can be explained (see open questions).
3. **The duty-step failure (4) is an overcurrent, not an overvoltage.** A duty slew limit or a cycle-by-cycle current limit removes it.
4. **A VHigh overvoltage trip that stops the PWM fixes every overvoltage case.**
   - At high braking current the bus rises tens of volts per millisecond, so the trip has to act within microseconds: a comparator into the HRTIM fault input (the ADR 0009 path).
   - A 1 ms software trip is marginal.
5. **The drain-to-gate active clamp should not be built.** It turns an overvoltage into a thermal failure of the same MOSFET.

## 5. Next steps

### Bench confirmations (catalogue tab "Bench (L2)"), safest first

They run in the bench app ([`bench/app.py`](bench/app.py), one tab per test, one button per phase; it replaced `bench/bench_wizard.sh` on 2026-11-24), together with L2-OV-03 (#11) and L2-DIS-01 (#12). The setup, the code and the reasons behind them are in [`bench/README.md`](bench/README.md).

- **Firmware:** `~/code/examples`, branch `vhigh-investigation`, `TWIST/DC_DC/vhigh_investigation/`, built with Core `main`. The Core2 safety API is not used because it is still experimental.
- **Bench guard:** the firmware opens the leg at 45 V, 2.5 A, or LOW1 above 20 V. It checks every 100 µs and stays latched.
- **Bleed resistor:** a 100 Ω resistor across VHigh makes every overvoltage test limit itself.
- **Supply diode:** a Schottky in series with the VHigh supply keeps the rising VHigh off the supply's output; the set point at the board is one diode drop lower.
- **Voltages:** 32 V on VHigh and 12 V on LOW1, the supplies available (first planned at 60 V and 24 V).

Each result is compared with a model prediction of the exact bench setup (cases D-L2P-01..06):

- [ ] **L2-OV-01: confirm hypothesis 1 without any disconnect.**
  - Setup: lab supply at 32 V on VHigh, 12 V supply (3 A limit) on LOW1.
  - Push 0.5, 1.0, 1.25 and 1.5 A into VHigh.
  - Predicted: VHigh settles at 32.0, 34.5, 38.6 and 42.2 V.
  - Confirmed if VHigh rises above 35 V at 1.25 A.
- [ ] **L2-OV-02: the guard stops a rising VHigh at 45 V.**
  - 2.0 A would settle at about 48.7 V.
  - Predicted: the guard opens the leg at 45 V, and the bleed brings VHigh back to 32 V.
- [ ] **L2-STP-01: confirm hypothesis 3 at low energy.**
  - VHigh at 30 V, 10 Ω on LOW1, duty step 0.4 → 0.5, current probe on L201.
  - Predicted peak: 5.2 A.
  - The ringing frequency gives the real low-side capacitance; 60 µF is assumed.
- [ ] **Later, once the hardware overvoltage trip exists:** measure its trip voltage and reaction time the same way.

### First bench session, 2026-11-23 ([report](results/bench_2026-11-23_143232/report.html))

Setup: VHigh supply 32 V through an IN4007 (31.16 V at the board), 100 Ω bleed, LOW1 supply 12 V, no oscilloscope (firmware scope only).

- **F-1 is confirmed on the board.** With the supply still connected, VHigh settled at 32.98 V with 1.0 A pushed into it, 1.8 V above the supply. At 1.25 A it reached 36.8 V (the model predicted 38.6 V; the difference is the converter's losses, which the model ignores).
- **The bench guard tripped falsely on current**, at 1.25 A and at 2 A. Each trip was a single sample above the 2.5 A limit, at the moment a new reference was written. The limit did not leave room for the inductor ripple (about 1.2 A peak to peak). The wizard now sets 4 A. Still to run: the 1.5 A step of L2-OV-01, and L2-OV-02's stop on VHigh at 45 V.
- **L2-STP-01** ran without the oscilloscope, so it is INFO only (2.5 A seen at 100 µs per sample). Redo it with the MSO54.

### Second bench session, 2026-11-23 ([report](results/bench_2026-11-23_162247/report.html))

Same setup (31.14 V at the board, 12 V LOW1 supply, 100 Ω bleed, no oscilloscope), current guard at 4 A.

- **F-1 is confirmed through the whole range.** With the supply still connected, VHigh settled at 31.29 / 32.77 / 35.93 / 40.06 V with 0.5 / 1.0 / 1.25 / 1.5 A pushed into it, up to 8.9 V above the supply. At about 1.9 A it rose from 30.7 to 45.0 V in 102 ms.
- **The bench guard (L2-OV-02) works.** It stopped the leg on V_HIGH at 45.03 V and latched, and the bleed brought VHigh back to 31.08 V.
- **The model reads 5 to 7 % high above the set point.** It has no converter losses. The power balance shows that 74 to 81 % of the power taken from LOW1 reaches the bleed; the rest is switching and conduction losses plus the Feeder, which is powered from VHigh. A loss term calibrated on this session would close the gap.
- **The two sensor checks failed for procedural reasons.** The V_HIGH reading (29.20 V) was taken before the supply was moved from 30 V to 32 V; the wizard now asks for the meter readings first and reads the sensors right after. LOW1 reads 4 % above "12.00" in both sessions: check whether that value was a meter reading or the supply's set point.
- **L2-STP-01** is still INFO only: it needs the MSO54.

### Third bench session, 2026-11-23 ([report](results/bench_2026-11-23_170833/report.html)): not usable

- **The MSO54 captured nothing.** Its USB link was out of step (a stale reply in its queue, then refused USB writes after an acquisition was stopped mid-run), so the wizard fell back to the firmware scope. The helper now arms the scope in single sequence on each test's edge, reads it only once it has stopped, and resets the USB link when the scope does not answer.
- **Scope channels on this bench:** CH1 LOW1, CH2 VHigh, CH3 bleed current (current probe), CH4 TP203 (inductor current). These are the wizard's defaults.
- **The leg tripped on LOW1 > 20 V at the direction check:** current flowed into the 12 V supply, with the duty following the feedforward V1_low / V_high up to 0.643. The same firmware had the direction right in the previous session. The trip happened while the current was being observed with a probe on TP203, the ADC input of I1_LOW: an offset there makes the closed loop regulate a wrong current, and with a LOW1 supply that cannot sink, any real current into LOW1 raises it until the guard. The TP203 probe now goes on only for the open-loop duty step. The wizard also records the start-up with the firmware scope and stops when the direction check trips.
  - Lesson for the safety work: a current loop that pushes power into a source that cannot sink is only as good as its current measurement. The LOW1 overvoltage guard is what caught it.

### Fourth and fifth attempts, 2026-11-23 (sessions 173344 and 173944): the bench firmware's current loop

Both stopped at the direction check with LOW1 above 20 V, the second one without any probe on TP203. The firmware scope recorded the start-up: the current jumped to +0.3 A (into LOW1) and stayed there while the duty followed V1_low / V_high from 0.395 to 0.645 in 12 ms.

- **Cause: the bench firmware.** Its feedforward took V1_low live. The V1_LOW sensor of this board reads 4 % high (every sensor check: 12.47 V against 11.98 V), so the leg applied 4 % more than LOW1's real voltage. Current flowed into LOW1, the 12 V supply could not take it, LOW1 rose, and the feedforward followed: a loop gain of 1.04, a runaway. The PI (about 150 Hz, 1e-3 duty per A) was far too weak to stop it. Reproduced in simulation (`/data/tmp/loop_check.py` variant): with a 1.04 gain the old firmware drifts LOW1 towards 20 V, with 1.08 it trips in 5 ms.
- **Fix** (examples `vhigh-investigation`, commit "freeze V1 in the feedforward"): V1 is taken once when the mode starts, so a rising LOW1 now drives the current back down; the PI goes to about 500 Hz. In simulation it reaches the −0.2 A reference with LOW1 sensor gains of 1.00, 1.04 and 1.08, LOW1 peaking at 12.6 V on this board's 4 %.
- **Lesson for the safety work:** this is the field failure's mechanism on the low side. Power control into a source that cannot sink, with a voltage feedforward, depends on sensor gains. The LOW1 overvoltage guard is what stopped it.

### Sixth session, 2026-11-23 ([report](results/bench_2026-11-23_174906/report.html)): fixed firmware, supply limit

Firmware with the frozen-V1 feedforward (examples `6290f81`), MSO54 armed by the wizard.

- **The fix works:** the direction check held −0.19 A at −0.2 A with LOW1 at 12.3 V, on the same supply that ran away before.
- **The 12 V supply was left at a 1 A current limit** for part of the run (operator note). At 1.0 A and 1.25 A LOW1 sagged to 8.1 and 10.5 V, so those steps are not judged. At 1.5 A, with the limit corrected, VHigh settled at 39.79 V (session 2: 40.06 V), and the MSO54 confirms it independently: 0.378 A through the bleed while VHigh read 39.5 V.
- **L2-OV-02 did not reach the guard,** again because of the supply limit, but the scope caught the rise on its 43 V trigger: VHigh from 37.6 to 43.2 V, then back down as LOW1 sagged from 11.7 to 9.9 V.
- **L2-STP-01 missed the step:** a horizontal delay left on the scope put the window 13.8 ms after the trigger. The wizard now switches the delay off.
- Still to do: L2-OV-02's stop at 45 V and L2-STP-01's peak, with the supply limit at 3 A.

### Seventh session, 2026-11-23 ([report](results/bench_2026-11-23_180658/report.html)): F-1 and the guard, end to end

- **L2-OV-01, all four steps valid:** VHigh settled at 29.29 / 31.79 / 35.95 / 39.67 V for 0.5 / 1.0 / 1.25 / 1.5 A pushed into it, with the supply connected; 85 to 86 % of the power from LOW1 reached the bleed. The VHigh supply was still at 30 V from the previous duty step (the board read 29.3 V against the 32 V typed), so the model comparisons and L2-SEN-01 read low; the rise above the set point does not depend on it.
- **L2-OV-02 passed:** VHigh rose from 28.8 V, the guard opened the leg at 45.06 V on V_HIGH, and the bleed brought VHigh back to 29.2 V. The MSO54 caught it on its 43 V trigger.
- **L2-STP-01 did not run:** entering STEP mode jumped to duty 0.4 into a LOW1 discharged by its 10 Ω load, which rang the tank to the 6.5 A current guard before any step. Fixed in the firmware (examples `504bf68`: soft start to duty_0 in about 100 ms; the step stays a step); the wizard now stops if the guard has tripped before the step, and can skip the VHigh tests.

### Eighth session, 2026-11-23 ([report](results/bench_2026-11-23_182042/report.html)): F-2 on the board, and the real LOW1 tank

Firmware with the STEP soft start (examples `504bf68`), VHigh tests skipped, duty step 0.4 → 0.5 at VHigh 28.8 V into 10 Ω, MSO54 triggered on TP203 at 3.5 A.

- **F-2 is confirmed:** the inductor current went from 1.23 A to a 2.98 A peak (period-averaged; 3.55 A with the ripple) within about 35 µs of the step, then settled at 1.50 A within about 100 µs. LOW1 overshot from 10.5 to 14.1 V before settling at 13.4 V. A 0.1 duty step gave an overshoot about 6.5 times the change in steady state.
- **The tank is not the one assumed.** The response fits L201 against the three 4.7 µF ceramics (14.1 µF, about 7 kHz, Z0 = 1.54 Ω), with the 47 µF electrolytic C203 only damping it through 2 to 4 Ω of ESR; the first model assumed an ideal 60 µF (3.6 kHz, 5.2 A). The firmware does connect C203 (`connectCapacitor()` drives pin 7 low; through optocoupler U206 that holds Q203's gate at +12 V); to confirm on the board, Q203's gate should read about 12 V to PGND while the firmware runs.
- **The model now uses the calibrated tank** (14.1 µF + 47 µF / 3 Ω), and the bench prediction becomes 3.4 A against 3.55 A measured. The field case is revised: a 0.2 → 0.8 step at 100 V peaks at 48 A instead of 81 A, still above the 40 A limit, so F-2 stands; the step down 0.8 → 0.2 drops to 33 A (was 67 A). Duty slew limiting and a cycle-by-cycle current limit still remove it.
- **Bench status: L2-SEN-01, L2-OV-01, L2-OV-02 and L2-STP-01 have all run.** The mechanisms behind the field failures are confirmed on the board.

### Firmware: Core2 safety API

- [ ] Overvoltage limit on VHigh on the hardware path: comparator into the HRTIM fault input, latched, both legs off, set at about 110 V. Software and ADC-watchdog checks only as backup.
- [ ] Cycle-by-cycle current limit on the inductor current, plus an absolute overcurrent trip.
- [ ] Slew-rate limit on the duty command, and a maximum duty (for example 95%) so the bootstrap capacitor always recharges.
- [ ] Undervoltage on VHigh: stop switching when VHigh drops below the operating range, so the converter doesn't run itself from the low side.
- [ ] A reverse-power or reverse-current policy for when VHigh's source cannot sink, for example disabling boost-direction power flow unless explicitly allowed.

### Hardware: next TWIST and Ownverter revisions

- [ ] Overvoltage comparator on V_High wired to the HRTIM fault input, working independently of the CPU.
- [ ] TVS on V_High, per leg or per board, sized for the energy left in the inductor after the PWM stops (½·L·I² ≈ 1 mJ at 8 A). It is not meant to absorb continuous regeneration.
- [ ] Review whether the Feeder should keep running from V_High after the external supply is lost (JP5001). An undervoltage lockout or a "supply present" signal would stop a converter that is powering itself.
- [ ] Do **not** fit the drain-to-gate active clamp.
- [ ] For regenerative loads: a brake chopper or a sinking supply on VHigh (documentation and application notes for users).

### Simulation

- [ ] D-UV-01: model the bootstrap and gate drive to test hypothesis 4 (100% duty, gate starvation).
- [ ] Two legs in parallel or interleaved, to explain why one or both high-side MOSFETs die.
- [ ] Replace the 0.15 J clamp limit with the datasheet value for the IPD200N15N3.
- [ ] Calibrate against the scope captures from L2-OV-01 and L2-STP-01.

### Open questions for the people involved

- [ ] Failure 2 (TWIST, supply switched off): what was on the low side (resistive load, electronic load, battery, motor)? Was the board in open-loop duty or in a voltage or current loop?
- [ ] Failure 5 (low-side MOSFETs): operating point, direction of power flow, one or two legs.
- [ ] Skateboard: was the Ownverter braking or regenerating when the cable came out, and at what current?

## 6. Reproducing

```bash
cd simulation/vhigh_overvoltage/model
python3 -I run_campaign.py            # every case, about 5 s; writes a new campaign into results/
python3 -I run_campaign.py D-SKT-02   # one case
```

Then open `results/control-center.html`. Cases are defined in [`model/catalogue.json`](model/catalogue.json). `TWIST_SIM_OUT` redirects the output.
