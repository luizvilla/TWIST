# Diagnosis synthesis: why TWIST and Ownverter MOSFETs died

Status on 2026-11-24, at the end of the diagnosis phase. This document ties each hypothesis to the tests that were run, the evidence they gave, and what is concluded. It also lists what is **not** established, so that gaps are visible before the protections are designed.

- Raw data: [`results/control-center.html`](results/control-center.html) (model campaigns and bench sessions).
- Day-by-day record: [`README.md`](README.md).
- Map of the work ahead: [luizvilla/TWIST#10](https://github.com/luizvilla/TWIST/issues/10).

## 1. What was observed in the field

| # | Situation | What died |
|---|---|---|
| FF1 | Ownverter on a skateboard, lab supply on VHigh, heavy pilot; drove away from the supply and the cable pulled out | High-side MOSFETs |
| FF2 | TWIST feeding a load; the supply was switched off | MOSFETs |
| FF3 | Ownverter; the supply was disconnected before the low side was powered down | High-side MOSFETs |
| FF4 | Too large a duty-cycle step | High-side MOSFET |
| FF5 | Low-side MOSFETs, circumstances not recorded | Low-side MOSFETs |

In every case there was a lab supply on VHigh, and the firmware had no protection.

## 2. Hypotheses

| | Hypothesis | Mechanism |
|---|---|---|
| **H1** | Energy returned to VHigh has no sink: slow overvoltage | A lab supply cannot absorb current. When the leg pushes power into VHigh (braking, regeneration, a loop asking for negative current, or a low-side source at fixed duty), VHigh charges up within milliseconds, whether the cable is connected or not. The Feeder runs from VHigh, so the leg keeps switching. |
| **H2** | No overvoltage protection | Nothing stops the PWM when VHigh rises, so H1 runs until a MOSFET avalanches. |
| **H3** | A duty step makes the inductor current overshoot | L201 rings against the LOW-side capacitors: high peak current, and a step down returns energy to VHigh. |
| **H4** | VHigh collapses, the duty goes to 100 %, and the bootstrap starves | The high-side gate voltage sags and Q201 overheats while partly on. |
| **H5** | A fast inductive spike from the cable when it is pulled out | The originally suspected cause. |
| **F-3** | The proposed drain-to-gate active clamp would protect Q201 | It was a proposed fix, so it is tested as a hypothesis. |

## 3. Tests and evidence

### H1: energy returned to VHigh

| Test | Setup | Result |
|---|---|---|
| Model D-DIS, D-SKT | Averaged leg, 100 V supply that cannot sink, boost or braking | VHigh goes past 150 V: 192 V at 8 A, 367 V at 25 A of braking; 150 V is crossed 1.4 ms after the start at 25 A. Pulling the cable makes it worse but is **not needed**. |
| Bench L2-OV-01 (sessions 2 and 7) | 31 V supply through a diode, 12 V on LOW1, 100 Ω bleed, current pushed into VHigh | VHigh settled **above the connected supply**: 29.3 / 31.8 / 36.0 / 39.7 V at 0.5 / 1.0 / 1.25 / 1.5 A (up to +8.9 V in session 2). 85 % of the power from LOW1 reached the bleed. The bleed current probe agrees independently: 0.378 A against 39.5 V. |
| Bench L2-OV-02 (session 7) | Same setup, about 1.9 A | VHigh rose from 28.8 to 45.06 V within about 100 ms, with the supply connected. |
| Bench, by-product (session 3) | VHigh supply off, LOW1 at 12 V | VHigh sat at 11.4 V: LOW1 backfeeds VHigh through Q201's body diode. With LOW1 above 9.7 V, the Feeder can start and the board powers itself without any VHigh supply. |

**Conclusion: confirmed.** The mechanism happens on the board exactly as predicted: VHigh rises, with the supply connected, as soon as the leg returns more power than VHigh's loads absorb. The model and the bench agree within 5 to 7 %. The model reads high because it leaves out the converter losses.

### H2: no overvoltage protection

| Test | Result |
|---|---|
| Field statement | The firmware had no protection. |
| Model D-FIX | A trip that opens the leg within about 5 µs holds the worst case (25 A of braking) at 111 V. A 1 ms firmware trip reaches 143 V: 7 V of margin. |
| Bench L2-OV-02 | A software guard checked every 100 µs (bench firmware only) stopped the leg at 45.06 V and latched; the bleed then brought VHigh back to the supply. |

**Conclusion: confirmed.** H2 is what turns H1 into destruction. Stopping the PWM is enough to end H1: once the leg stops, VHigh stops rising.

### H3: duty step

| Test | Result |
|---|---|
| Model D-STP, first version (ideal 60 µF) | 81 A for 0.2 → 0.8 at 100 V |
| Bench L2-STP-01 (session 8) | Step 0.4 → 0.5 at 28.8 V, 10 Ω load: inductor current 1.23 → **2.98 A** (3.55 A with the ripple) within about 35 µs, settled at 1.50 A within about 100 µs. The overshoot is about 6.5 times the change in steady state. |
| Model recalibrated on the bench capture | The tank is the three 4.7 µF ceramics (14.1 µF, about 7 kHz) with C203 acting only as a damper through 2 to 4 Ω of ESR. The bench prediction becomes 3.4 A (measured 3.55 A). The field case 0.2 → 0.8 at 100 V becomes **48 A**, above the 40 A limit used. |

**Conclusion: the overshoot is confirmed; that it kills a MOSFET is not.** 48 A has to be compared with the MOSFET's SOA and with L201's saturation current, which are not known yet (#5). The step down (0.8 → 0.2) now predicts 33 A and Vds 109 V, so it no longer explains a failure on its own.

### H4: bootstrap starvation

**Not tested.** It needs a switching model of the gate driver, or a bench test at duty near 100 %.

### H5: fast spike at disconnect

**Not tested.** Ranked low by reasoning: the cable current is interrupted at the plug, and C230, C231 and the ceramics sit between the cable and Q201. No pull-out has been done on the bench with the scope on VHigh.

### F-3: active clamp

**Rejected, on the model only.** Holding VHigh at 130 V means Q201 dissipates all the returned power: about 1.1 kW, 9.9 J in 10 ms at 25 A of braking, against an assumed 0.15 J single-pulse capability. The 0.15 J is not checked against the datasheet (#5), but the margin is two orders of magnitude.

### Side finding: the bench firmware's runaway

The first bench firmware took V1_low live in its current loop's feedforward. With the board's V1_LOW sensor reading **+4 %**, the leg applied 4 % more than LOW1's real voltage and pushed current into a 12 V supply that could not sink. LOW1 ran away to the 20 V guard in 12 ms. This was reproduced in simulation and fixed by freezing V1 at mode entry. It is the same family as H1, on the low side: **control that pushes power into a source that cannot sink is only as safe as its sensors, and only a voltage limit on that rail stops it.**

## 4. Field failures explained

| Field failure | Explanation | Strength |
|---|---|---|
| FF1 skateboard | H1 + H2: braking returns power into VHigh against a lab supply; a heavier pilot means more braking current and a faster rise (model: 367 V at 25 A). | **Strong**: mechanism confirmed on the board; magnitude from the model. Not known whether the board was braking when the cable came out. |
| FF3 Ownverter, supply removed first | H1 + H2: with the low side still powered, any power flowing towards VHigh charges it; the board stays alive through the backfeed. | **Strong** if the low side could deliver power (source, regeneration, or a loop pushing current). The operating mode was not recorded. |
| FF4 duty step | H3: the overshoot is confirmed; a 0.2 → 0.8 step at 100 V predicts 48 A. | **Plausible**: lethality needs #5 (SOA, saturation). |
| FF2 supply switched off with a load | Not explained. In the model, switching off is harmless with a passive load, or at fixed duty with a battery or a coasting motor. It becomes H1 only if the load returned energy or a loop pushed current back. | **Open** (#4) |
| FF5 low-side failures | Not explained. | **Open** (#4) |

## 5. Incoherences and missing links

These are the places where the reasoning is not closed yet.

1. **Why the high side?** ([#11](https://github.com/luizvilla/TWIST/issues/11)) In H1 the overvoltage appears across whichever MOSFET is off, and Q201 and Q202 block VHigh in turn. Nothing so far explains why the high side dies more often. Candidates, untested:
   - in boost from a low LOW1, the duty is small, so Q201 blocks VHigh for most of the period;
   - Q201's body-diode reverse recovery in the boost direction (there is no Schottky across the high side);
   - the order in which the two devices reach avalanche.

   This matters for the protection: a VHigh trip protects both devices, but a high-side-only measure (the clamp, or a snubber on Q201) would not.
2. **"The board keeps switching" is assumed, not shown in the failure condition** ([#12](https://github.com/luizvilla/TWIST/issues/12)). The bench showed the backfeed (VHigh 11.4 V from LOW1). It has not shown the Feeder starting from it, or the leg switching on through a real supply disconnect.
3. **The real disconnect was never done on the bench** ([#12](https://github.com/luizvilla/TWIST/issues/12)). Every H1 test kept the supply connected, which is a worse case for the supply but not the same event. H5 (the spike) is untested for the same reason.
4. **Magnitudes at field power come from the model only.** The bench ran at 30 V and 20 W; the field ran at 100 V and hundreds of watts. The bench agrees with the model within 5 to 7 % at low power, but the model has no losses, no saturation and no switching detail.
5. **The LOW1 tank depends on C203.** If C203 is not connected on the bench board (#1), the calibration describes a board state the field boards did not have, and the 48 A field prediction changes.
6. **Sensor accuracy.** V1_LOW reads +4 % on the bench board (#2), and the mean I1_LOW reading in the current loop differed from its reference by +8 to +18 % in session 2 but by −6 to 0 % in session 7. These do not affect the H1 conclusion, which rests on VHigh and the bleed current, but they affect any protection based on these sensors.
7. **FF2 and FF5 have no hypothesis yet** (#4).
8. **H4 (bootstrap) is still open:** it could explain high-side-only deaths when VHigh collapses, and it has not been modelled.

## 6. Conclusions for the protection design

1. **The main cause is H1 with H2:** power returned into VHigh with no sink and nothing to stop the PWM. It needs a **VHigh overvoltage trip that opens the legs within microseconds**, independently of the CPU. A software check is not fast enough at field power.
2. **Every rail needs its own overvoltage limit**, not only VHigh: the bench firmware's runaway shows the same mechanism on LOW1.
3. **Duty steps need a slew limit or a cycle-by-cycle current limit.** The overshoot is real, and its lethality is pending #5.
4. **The drain-to-gate active clamp is rejected.** A TVS sized for the inductor energy only can back up the trip, but not replace it.
5. **Before the architecture is fixed (#6),** missing links 1 and 2 are worth closing. Both are cheap bench tests with the current rig:
   - which MOSFET sees the overvoltage first, measured with Vds on Q201 and Q202 during L2-OV-02;
   - whether the board keeps switching through a real VHigh disconnect while LOW1 stays powered.
