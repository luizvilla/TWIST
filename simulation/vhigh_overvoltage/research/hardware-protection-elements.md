# Hardware protection elements: snubbers, TVS, brake chopper, crowbar

Research note for luizvilla/TWIST#16 (map #10, feeds #9). Question: which hardware elements outside the MCU should the next TWIST, Ownverter and micro-verter revisions consider against returned energy and switching overshoot? For each one: what it absorbs, how it is sized, cost and area, failure mode, and what it gives per board.

Facts and trade-offs only. The decision belongs to #9.

## Frame

- **Firmware is the primary protection** (#6 resolution). The ADC-watchdog trip reacts in ≤ 16 µs on TWIST and ≤ 27 µs on the Ownverter. Every element below is a **safeguard**: it backs up that trip and never latches.
- **F-1, returned power.** Power flows back into VHigh against a lab supply that cannot sink. The rise is slow (ms) and the energy keeps coming as long as the source drives it: 25 A of braking reaches 367 V without protection.
- **F-2, duty-step overshoot.** A duty step overshoots the inductor current. The energy is bounded by ½·L·I².
- **F-3 is rejected.** The drain-gate active clamp would burn the returned power in Q201.

Board facts come from the sibling notes [`device-limits.md`](device-limits.md), [`ownverter-protection-facts.md`](ownverter-protection-facts.md) and [`micro-verter-protection-facts.md`](micro-verter-protection-facts.md).

| Board | Bus C | Trip → ceiling (lowest-rated part) | Switches | Worst returned current |
|---|---|---|---|---|
| TWIST 1.4 | 147 µF | 100 → 135 V | IPD200N15N3 150 V, Coss 214 pF @ 75 V | 25 A (F-1 bench case) |
| Ownverter 1.1 | ≈ 200 µF | 100 → 120 V (NCP12700 feeder) | IPD200N15N3 150 V, three legs | 25–50 A per leg, ≈ 150 A for three legs at 50 A |
| micro-verter 0.9 | 122 µF film | 450 → 500 V (film caps) | GaN CID12N65D 650 V (750 V < 1 µs), no avalanche rating | ≈ 1.4 A at 550 W |

How to read this note:

- **[ref]** marks a primary source (see [Sources](#sources)).
- **Derived** means computed here, with the arithmetic shown.
- **NOT PRIMARY** means it comes from a secondary source or from engineering judgement. Check it before relying on it.

## Two numbers that frame everything

1. **The bus capacitors already absorb F-2.** The L201 energy at 25 A is ½·33 µH·25² = **10.3 mJ** (5.8 mJ at Isat 18.7 A). Dumped into the bus, it raises it by √(V0² + 2E/C) − V0:
   - TWIST, 147 µF from 100 V: **+0.70 V**
   - Ownverter, 200 µF: **+0.51 V**

   *Derived.* No hardware element is needed to absorb the F-2 inductor energy at the bus. F-2 is a switch-current and inductor-saturation problem, and the firmware's comparator trip handles it.
2. **F-1 is a power problem, not an energy problem.** At 25 A and ≈ 110–130 V the returned power is **2.75–3.25 kW** for as long as the source drives it. The bus capacitors only buy time: 25 A / 147 µF = 0.17 V/µs, so ≈ 200 µs from 100 V to 135 V *(derived)*. An element that has to *hold* the bus against F-1 must dissipate kilowatts, or the source must be stopped. On TWIST, once the trip has opened both switches, no path returns power to VHigh. The only path would be VLow > VHigh through the body diode, which cannot happen in normal use. On the Ownverter, a spinning motor keeps rectifying through the body diodes only while its line-to-line back-EMF is above the bus.

---

## 1. RC snubber on the switch node

**What it absorbs.** It damps the parasitic LC ring at each switching edge: loop inductance against Coss. It absorbs none of the F-1 or F-2 load energy.

- Todd [SEM900]: *"The basic function of a snubber is to absorb energy from the reactances in the power circuit."*
- Taylor [SLYT465]: the snubber damps *"the parasitic inductances and capacitances during the switching transitions"*.

**Sizing [SEM900 pp. 2-3 to 2-5; SLYT465 p. 2].**

1. Measure the ring frequency.
2. Add C across the switch until the frequency halves. The added C is then 3 × the parasitic C ([SEM900]: *"a near optimum value … damping very near Q = 1"*).
3. Compute L from f = 1/(2π√LC). Set R = √(L/C_parasitic).

As a first estimate, the snubber C is "two to four times" the switch Coss [SEM900 p. 2-4].

**Loss.** P = C·V²·f, *"independent of the value of the resistor"* [SEM900 p. 2-5]. TI's example: 1 nF, 78 Ω, 400 V, 100 kHz → 16 W.

**Cost and area.** Two parts, an 0805/1206 C0G capacitor and a 1206/2512 resistor, placed at the switch-node-to-PGND pins [SLUA851 via search summary]. Cents and a few mm². The resistor must be non-inductive; even non-inductive wirewound has too much inductance [SEM900 p. 2-5].

**Failure mode.** The resistor overheats if C or f is raised. Light-load efficiency drops [SLYT465 p. 2]. Overshoot reduction is modest: 23.4 → 19.1 V at 12 V in TI's test, against 19.8 V for a boot resistor [SLYT465 Table 1].

**Per board** *(derived; Coss 214 pF @ 75 V from [IFX], so C_snub ≈ 3 × 214 ≈ 680 pF; Coss is non-linear, so the number moves with voltage)*:

| Board | Loss per leg | Legs | Board total |
|---|---|---|---|
| TWIST | 680 pF·100²·200 kHz = **1.36 W** at 100 V; 0.49 W at 60 V | 2 | ≈ 2.7 W at 100 V |
| Ownverter | 1.36 W at 100 V | 3 | ≈ 4.1 W |
| micro-verter, HV GaN legs, 50 kHz | Coss of CID12N65D **not in the facts note: UNCONFIRMED** | 2 | – |

For the micro-verter, a 100 pF snubber at 400 V and 50 kHz would lose 0.8 W per leg (illustrative only). The GaN part is driver-integrated and rated 750 V only for < 1 µs, so switch-node overshoot matters more there than on the 150 V Si boards.

---

## 2. RCD snubber, or RCD clamp across the leg

**What it absorbs.** RCD **clamp mode**: only the energy of the commutation-loop inductance above the clamp level. Below the clamp it is passive. RCD **rate-of-rise mode**: C is charged to the rail on every transition and the whole of ½CV² is dissipated, P = ½·C·V²·f [SEM900 p. 2-5]. In both modes it absorbs no F-1 power. A clamp across the leg returns or burns only the commutation-loop energy.

**Sizing [SEM900 pp. 2-5 to 2-6].** Rate-of-rise mode: C = I·Δt/ΔV for the chosen rise time. R is set so that RC is short against the switching period. Clamp mode: the energy balance W_L + W_C1 = W_C2. The clamp C is large, so the clamp voltage stays near the bus.

**Loss in clamp mode** ≈ ½·Lσ·I²·f. With Lσ = 5 nH, an **assumption, NOT PRIMARY, to be measured**, at 25 A and 200 kHz: **≈ 0.31 W** per leg *(derived)*.

**Cost and area.** Three parts: an ultrafast or SiC diode rated above the bus (150–200 V for TWIST and Ownverter, 650 V for the micro-verter), a ceramic C and a resistor. Below a euro, ≈ 20–40 mm² *(NOT PRIMARY, estimate)*.

**Failure mode.** In rate-of-rise mode the discharge current adds to the switch turn-on spike. Narrow pulses leave C charged, so *"the peak stress on the switch will go way up"* during an overcurrent [SEM900 p. 2-6]. A diode that fails short becomes an RC across the bus, which is benign. A diode that fails open removes the clamp silently.

**Per board.**

- **TWIST, Ownverter.** Low value. These are synchronous half-bridges with 150 V FETs on a ≤ 100 V bus. A 2–4 µF X7R decoupling C at the leg already does most of the clamping.
- **Micro-verter.** More relevant: the GaN has no avalanche rating, and the 750 V figure holds only below 1 µs.

---

## 3. TVS on the bus

**What it absorbs.** Transient energy: single pulses defined on 10/1000 µs. It is **not** a continuous regulator.

- The Vishay SMCJ series is 1500 W peak on 10/1000 µs, **6.5 W** steady-state on an infinite heatsink at 50 °C [SMCJ p. 1].
- The 10/1000 µs waveform is *"an accepted industry test impulse … representative of"* inductive-energy surges [AN9772 p. 10-135].
- A 10/1000 µs pulse at 1500 W carries ≈ 1500 W × 1 ms / ln 2 ≈ **2.2 J** *(derived from the exponential tail)*. Fig. 1 of [SMCJ] gives the peak power against pulse width.
- TI uses a TVS on a motor supply as *"dynamic braking"*: a 27 V TVS held a 24 V rail at 29.6 V during deceleration [SSZTCH8]. That case is a small motor driver, with energy of the order of joules.

**Sizing.**

- VWM must be ≥ the highest normal bus voltage.
- VC at the expected peak current must be ≤ the lowest-rated part.
- Energy and pulse width are set against Fig. 1 and the temperature derating (Fig. 2) [SMCJ].
- The clamping ratio VC/VWM of a standard silicon TVS is ≈ 1.6–1.75 at IPPM: SMCJ100A 162/100, SMCJ188A 328/188 [SMCJ p. 2].
- Snapback parts such as Vishay XClampR lower that ratio, but the parts released are 24 V types only [XCLAMP].

**What energy should it be sized for?**

- **(a) F-2 inductor energy, 10 mJ.** An SMC part covers it easily, but the bus capacitors already take it at +0.7 V. A TVS is not needed for this.
- **(b) Cable or lead inductance on hot-plug or fuse-blow.** For example 1 µH (*assumed, NOT PRIMARY*) at 25 A gives **0.3 mJ**. Easily covered.
- **(c) F-1 returned power, 2.75–3.25 kW continuous.** **No SMC TVS survives it.** The power is above the 1 ms rating of 1500 W, and the steady-state rating is 6.5 W *(derived from [SMCJ])*.

**Failure mode.** TVS diodes, like varistors, fail short when overstressed. A shorted clamp then passes current *"limited mainly by the source impedance"*, and Littelfuse recommends fusing it [AN9772 p. 10-135, varistor section; NOT PRIMARY for silicon TVS specifically, though it is the usual behaviour]. On a board bus, a TVS overloaded by F-1 therefore turns into an uncontrolled crowbar.

**Per board** *(derived from the [SMCJ] table)*:

| Board | Window, normal max → ceiling | Candidate | Fit |
|---|---|---|---|
| TWIST | 100 → 135 V (150 V FETs) | SMCJ100A: VBR 111–123 V, VC **162 V** @ 9.3 A. SMCJ90A: VWM 90 V, VBR 100–111 V, VC 146 V @ 10.3 A. | **Does not fit.** A ratio of 1.35, or 1.5 to the FETs, is below the TVS clamping ratio. SMCJ90A starts conducting inside the operating range. SMCJ100A exceeds 150 V at rated current. |
| Ownverter | 100 → **120 V** (NCP12700) | same parts | **Does not fit** the feeder ceiling (ratio 1.2). It could protect only the 150 V FETs if the feeder were isolated. |
| micro-verter | 440 V burst level → 500 V film / 650 V GaN | VWM ≥ 440 V → VC ≈ 1.6 × 440 ≈ **700 V** | **Does not fit**: above the film rating and the GaN rating. No > 188 V datasheet was fetched; this uses the SMCJ ratio, so **UNCONFIRMED**. |

Cost and area of an SMC TVS: ≈ €0.2–0.5, 8 × 6 mm with the 8 × 8 mm pads the rating assumes [SMCJ note 2]. The price is *NOT PRIMARY*.

---

## 4. Brake chopper (dynamic braking resistor)

**What it absorbs.** The returned power, continuously, as heat. A semiconductor switches a resistor across the DC link when the link exceeds a threshold and disconnects it when the link falls back below. The current is pulsed, hence "chopper" [SIEMENS §1.2.3, p. 7].

- Siemens sets the switch-on level at 1.13·√2·V_line, or 0.98 × the Vdc_max threshold. The chopper therefore sits **just below the drive's own overvoltage trip**, and the drive keeps running while braking.
- The resistor must have *"the correct value (ohms and watts)"*. Thermal and wiring needs are called out [SIEMENS p. 7].
- Alternatives listed in the same FAQ: a longer ramp-down, a Vdc_max controller (firmware reduces the braking), compound braking, DC braking [SIEMENS §1.2].

**Sizing** *(derived)*:

- R ≤ V_on / I_return, so the resistor can take the whole returned current at the threshold.
- Peak power is V_on² / R.
- The average power and the energy per event set the resistor's pulse and thermal rating: E = P × braking time.

**MCU-independent form** (as #16 asks; *architecture, NOT PRIMARY*):

- a resistive divider straight off the bus, separate from the ADC divider;
- a comparator with hysteresis, for example on at V_on and off 3–5 V lower;
- a low-side MOSFET with a gate driver supplied from the bus side;
- a resistor, with a thermal fuse or PTC in series so that a stuck-on chopper fails open.

It never latches, so it is a safeguard in the #6 vocabulary.

**Failure mode.**

- MOSFET fails short: the resistor sits across the bus permanently. It drains the supply at V²/R (2.75 kW at 110 V, 4.4 Ω) until a fuse or the resistor opens. This is why the series thermal or fusible link is there.
- MOSFET fails open: the safeguard is silently gone. Periodic self-test needed.
- Resistor overheats on a long event.

**Per board** *(derived; V_on between trip and ceiling)*:

| Board | V_on (example) | I to absorb | R ≤ | Peak power | Remark |
|---|---|---|---|---|---|
| TWIST | 110 V | 25 A (F-1 case) | **4.4 Ω** | **2.75 kW** | After the trip, TWIST returns nothing more (inductor energy only). The chopper would back up a **failed trip path** (sensor, ADC, HRTIM), or let a regenerating LOW-side source keep running without a trip, which is a feature, not protection. 2.75 kW for 1 s = 2.75 kJ: a large resistor plus heatsink, outside a 100 × 100 mm board. |
| Ownverter | 110 V (< 120 V feeder) | 25 / 50 A per leg; ≈ 150 A for three legs at 50 A | 4.4 / 2.2 / **0.73 Ω** | 2.75 / 5.5 / **16.5 kW** | This is the textbook motor-drive case [SIEMENS]. Each braking stop returns E = kinetic energy of the load, **unknown: depends on motor and inertia**. Board-level for 25 A; an external resistor on terminals beyond that, the same pattern as the external chopper terminals in [SIEMENS p. 7]. |
| micro-verter | 460 V (between 450 V trip and 500 V film) | ≈ 1.4 A | **≈ 330 Ω** | ≈ 640 W | Small. The comparator divider would also give a bus reading independent of the ≈ 454 V ADC saturation. The comparator and the switch must be 650 V class. |

Cost and area: the comparator, driver and MOSFET are ≈ €2–4 and ≈ 2–4 cm². The resistor dominates: a 2.75 kW peak, kJ-class part is chassis-mounted aluminium-housed or wirewound, ≈ €5–30, off-board. *NOT PRIMARY, estimates, no resistor datasheet fetched.*

---

## 5. Bus crowbar (SCR) and fuse

**What it absorbs.** Nothing continuously. It **shorts** the bus and relies on a fuse or the source's current limit to remove the source. Littelfuse: *"A simple safeguard is to crowbar or short circuit the supply with an SCR"*. Once fired, *"the SCR remains on"* while the voltage does not drop to zero [AN9772 p. 10-134/135]. The SCR discharges the bus capacitors at turn-on, then carries the source current until a fuse blows.

**Sizing.**

- SCR: ITSM and I²t above the capacitor discharge plus the source's fault current; di/dt rating against the capacitor discharge.
- Fuse: I²t below the SCR's I²t, so the fuse clears first.
- Trigger: a TVS, varistor or comparator into the gate. SCR gate sensitivity *"is sensitive to junction temperatures"* [AN9772 p. 10-135].
- SCRs are slow and have a high on-state voltage. In ADI's bench test an SCR crowbar let a 1.0 V rail reach 1.6 V, against 116 % with a MOSFET crowbar [ADI, search summary; the article timed out on fetch, **NOT VERIFIED**]. That matters little on a 100–400 V bus.

**Failure mode.** It is **destructive by design**: a fuse to replace, and a nuisance trip ends the run. The SCR latches until the source current stops. An SCR that fails short is a permanent bus short.

**Per board** *(derived)*:

| Board | Bus energy dumped into the SCR | What clears the source | Remark |
|---|---|---|---|
| TWIST | ½·147 µF·120² = **1.06 J** (1.34 J at 135 V) | Lab supply: its current limit. A LOW-side source feeding through L201 and the Q201 body diode into the short: the LOW fuse (8 A 0154008 fitted per #6; schematic F102 rated 10 A, see device-limits). No VHigh-side fuse is recorded in the facts notes (**UNCONFIRMED**). | Fuse coordination exists on the LOW side. It is a last resort against the 150 V FET rating. |
| Ownverter | ½·200 µF·120² = **1.44 J** | F201 30 A input fuse (I²t 2000 A²s). A spinning motor drives a three-phase short through the high-side body diodes, limited by the motor impedance; phase fuses F601–F801 25 A (I²t 660 A²s). | It protects the 120 V feeder. It also brakes the motor hard, which can be mechanically undesirable. |
| micro-verter | ½·122 µF·460² = **12.9 J** | **No bus fuse and no PV fuse.** PV current is self-limited (≈ 11 A), so the SCR would hold the PV short indefinitely, ≈ 11 A × 1.5 V ≈ 16 W. | Needs a fuse or a timed PV disconnect to be complete. 12.9 J is a large di/dt and ITSM event for a small SCR. |

Cost and area: an SCR in TO-220 or DPAK, a trigger and a fuse: ≈ €1–3, ≈ 1–2 cm² *(NOT PRIMARY)*.

---

## 6. Schottky diode across the high side

**What it does.** It takes the freewheeling current from the MOSFET body diode during dead time. That removes the body-diode reverse recovery: IPD200N15N3 Qrr 332 nC, trr 106 ns at 75 V and 100 A/µs [IFX p. 3]. It **does not absorb** any F-1 or F-2 energy. The current still goes to the bus, just through another diode.

**What it gives.**

- Less recovery-driven ringing and overshoot at the switch node.
- Lower recovery loss. Upper bound Qrr·V·f = 332 nC × 100 V × 200 kHz ≈ **6.6 W per leg** *(derived, upper bound; Qrr grows with di/dt and temperature)*.

**Caveats.**

- With package and trace inductance, the current may still commutate through the body diode first. *Source: unattributed document on Scribd, NOT PRIMARY.*
- Schottkys at 80–100 V and above lose their forward-drop advantage. *Source: a patent, NOT PRIMARY.*
- It needs a 150–200 V Schottky able to carry the inductor current (up to 25 A) for ≈ 185 ns of dead time. The 150 V Schottky already in the TWIST library, ROHM RB168MM150, is 1 A / IFSM 35 A, too small for this.

**Failure mode.** A short Schottky shorts the high-side switch, which turns into a shoot-through at the next low-side turn-on. Reverse leakage rises with temperature.

**Per board.**

- **TWIST, Ownverter.** Possible efficiency and EMI value. No protection value against F-1 or F-2.
- **Micro-verter.** The GaN HV legs have no body-diode recovery, so not relevant there. The LV legs use 120 V Si FETs.

---

## 7. Bidirectional or sinking supply (bench recommendation)

**What it absorbs.** All of F-1, at the source: the supply sinks the returned power. It costs nothing on the board.

**Keysight [KS-5992-3174]:**

- *"A single-quadrant supply uses an internal resistor to load the output capacitor, converting the stored energy to heat."*
- *"Connecting a single-quadrant power supply directly to a battery or large capacitor can damage the power supply."* The external current damages the down-programming resistor.
- *"A typical two-quadrant power supply combines a single-quadrant power supply with a power dissipator"*, which is suited to charging and discharging capacitors and batteries.
- Separate source plus electronic load is *"the most common approach"* to source and sink, with compromises because the two are independent [KS-5991-2873].
- Active down-programmers are often limited to ≈ 10 % of rated current. *Source: Electronic Design article by a Keysight engineer, NOT PRIMARY.*

**Per board.**

- **TWIST, Ownverter.** The lab supply is the F-1 scenario itself. A two-quadrant, regenerative or source-plus-load bench setup removes F-1 at the root, or a battery bus with its own protection. It relies on the user's equipment, so it can only be a recommendation in the docs, never a guarantee.
- **Micro-verter.** Not applicable: PV in, grid out.

**Failure mode.** The user does not have one, or wires a single-quadrant supply anyway. Hence it does not replace the firmware trip.

---

## Comparison

What each element covers. Legend:

- **yes**: covers the failure mechanism;
- **partial**: helps but does not hold it;
- **no**: does nothing for it;
- **n/a**: not applicable to this board.

| Element | F-1 (returned power, kW, ms) | F-2 (inductor energy, ≤ 15 mJ) | Switch-node overshoot | TWIST | Ownverter | micro-verter | Board cost / area (est.) | Failure mode |
|---|---|---|---|---|---|---|---|---|
| RC snubber | no | no | yes (damps) | 1.4 W/leg at 100 V | 1.4 W/leg × 3 | Coss unknown; GaN overshoot matters most here | cents, mm² | resistor overheats; efficiency loss |
| RCD clamp | no | no (caps already take it) | yes (clamps) | low value | low value | relevant (no GaN avalanche) | < €1, ≈ 0.3 cm² | diode open = silent loss |
| TVS on the bus | **no** (fails short) | yes, but the caps already take it at +0.7 V | partial | **window 100 → 135 V too narrow** for VC/VWM ≈ 1.6 | **window 100 → 120 V does not fit** | **VC ≈ 700 V > 500/650 V** | €0.2–0.5, SMC | short → uncontrolled crowbar |
| Brake chopper | **yes** | yes | no | 4.4 Ω, 2.75 kW peak; backs up a failed trip | 4.4 → 0.73 Ω, 2.75 → 16.5 kW; the standard motor-drive answer | 330 Ω, 640 W; also an independent bus sense | €2–4 + resistor €5–30 (off-board at kW) | short = permanent load (needs a thermal link); open = silent |
| SCR crowbar + fuse | yes, destructively | yes | no | 1.1–1.3 J; LOW fuse coordinates | 1.4 J; brakes the motor through the diodes | 12.9 J; **no bus/PV fuse to clear** | €1–3, 1–2 cm² | blows a fuse on every fire; short SCR = dead bus |
| Schottky across high side | no | no | partial (Qrr) | ≤ 6.6 W/leg recovery saved (bound) | same | n/a (GaN) | €0.5–1 | short = shoot-through |
| Sinking supply (bench) | **yes, at the root** | n/a | no | recommend | recommend | n/a | none on board | user may not have it |

## Uncertain items

1. **Micro-verter GaN Coss** and the snubber loss there: not in the facts note.
2. **Clamping ratio for TVS above 188 V.** No > 188 V TVS datasheet was fetched. The 700 V figure uses the SMCJ ratio.
3. **Silicon TVS short-circuit failure.** The primary source here (AN9772) is about varistors.
4. **Commutation-loop inductance** (5 nH) and **lead inductance** (1 µH) are assumptions. Measure both.
5. **Schottky body-diode bypass effectiveness** and the high-voltage Schottky caveats: secondary sources.
6. **ADI SCR-versus-MOSFET crowbar numbers**: taken from a search summary; the page timed out.
7. **All prices and areas** are estimates, not distributor quotes.
8. **Ownverter braking energy per stop** depends on motor and load inertia: unknown.
9. **TWIST VHigh-side fuse**: none recorded in the facts notes. Check the schematic.
10. **Qrr recovery-loss bound**: Qrr is specified at 100 A/µs and 25 °C. The real value depends on di/dt and temperature.

## Sources

| Ref | Document | Where |
|---|---|---|
| [SEM900] | P. C. Todd, "Snubber Circuits: Theory, Design and Application", Unitrode Power Supply Design Seminar SEM-900, May 1993 (TI SLUP100) | https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/SEM_5F00_900.pdf (TI's own `ti.com/lit/ml/slup100` link requires login) |
| [SLYT465] | R. Taylor, "Controlling switch-node ringing in synchronous buck converters", TI Analog Applications Journal 2Q 2012, SLYT465 | https://www.ti.com/lit/pdf/slyt465 |
| [SLUA851] | TI SLUA851, TPS53355 switch-node ringing and snubber (search summary only, not opened) | https://edgeworker.ti.com/lit/pdf/slua851 |
| [SMCJ] | Vishay SMCJ5.0 thru SMCJ188CA TRANSZORB datasheet, doc 88394, rev. 04-Sep-07 | copy at https://docs.rs-online.com/86d5/0900766b80a93b01.pdf; product page https://www.vishay.com/en/product/88394/ |
| [XCLAMP] | Vishay, XClampR TVS Application Note, doc 98386 | https://www.vishay.com/docs/98386/xclampr_tvs_applicationnote.pdf |
| [AN9772] | Littelfuse (Harris), "Littelfuse Varistor Design Examples", AN9772, January 1998 | copy at https://docs.rs-online.com/b9ec/0900766b800a9c32.pdf |
| [SSZTCH8] | W. Zuo, TI technical article SSZTCH8, July 2015 (motor drive supply pumping, DRV8840) | https://www.ti.com/document-viewer/lit/html/SSZTCH8/GUID-DE5BCF99-20E7-4AEE-9B5E-6868089AF0F8 |
| [SIEMENS] | Siemens, FAQ "DC Link Overvoltage F0002", MICROMASTER 4, Item-ID 22445905, Version 1.3, 2008-09-08 | https://support.industry.siemens.com/cs/attachments/22445905/pdf_additional_text_dc_link_overvoltage_en_v1_3.pdf |
| [KS-5992-3174] | Keysight white paper 5992-3174, "Save Energy in Your High-Power Test Applications" | https://www.keysight.com/br/pt/assets/7018-06264/white-papers/5992-3174.pdf |
| [KS-5991-2873] | Keysight application note 5991-2873, "Conquering the Multi-Kilowatt Source/Sink Test Challenge" (summary page only) | https://www.keysight.com/us/en/assets/7018-04050/application-notes/5991-2873.pdf |
| [IFX] | Infineon IPD200N15N3 G datasheet Rev. 2.07: Coss 214 pF (VDS 75 V, 1 MHz), Qrr 332 nC, trr 106 ns | local `KiCAD_files/datasheet/Infineon_IPD_BIP_200N15N3_DS_v02_07_en-3164333.pdf` |
| [ADI] | Analog Devices technical article, "Bench Comparison of Two Overvoltage Protection (Crowbar) Methods: MOSFET vs. SCR" (search summary only) | https://www.analog.com/en/resources/technical-articles/bench-comparison-of-two-overvoltage-protection-crowbar-methods-mosfet-vs-silicon-controlled.html |

Not reached: the Eaton dynamic-braking note AP040010EN (HTTP 403), ON Semi AN004 (portal page), the ADI LTC1696 page (timeout) and the Littelfuse SMCJ datasheet (403).
