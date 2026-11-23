# VHigh overvoltage: why high-side MOSFETs die when VHigh is disconnected

Investigation record, 2026-11-23. Board: TWIST V1.4.3 (also applies to the Ownverter, which shares the power-leg topology).

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

All three run in one session through [`bench/bench_wizard.sh`](bench/bench_wizard.sh). The setup, the code and the reasons behind them are in [`bench/README.md`](bench/README.md).

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
