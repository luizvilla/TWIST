# Device limits for the protection thresholds

Research note for luizvilla/TWIST#5 (map #10). Question: what limits must the protection thresholds respect for the IPD200N15N3, L201, the UCC21222 and the ACS730, and what do the board's sensing paths look like?

How to read this note:

- Every value comes from a manufacturer datasheet. The **source** column gives the document, its revision and the page/table or figure.
- **Read off a chart**: the value comes from a datasheet graph, not a table. Expect about ±10–20 %.
- **Derived**: computed here from datasheet values and the schematic. The arithmetic is shown. It is not a manufacturer number.
- **UNCONFIRMED**: no primary source found.
- Schematic facts come from a netlist exported with KiCad 10 (`kicad-cli sch export netlist`) from `KiCAD_files/Power.kicad_sch` at `vhigh-investigation` dccb12c. Leg 1 references are given. Leg 2 is the same sheet (L301, Q301/Q302, U302, U303, …).

## Sources

| Ref | Document | Where |
|---|---|---|
| [IFX] | Infineon IPB/IPD/IPI/IPP200N15N3 G datasheet, Rev. 2.07, 2014-01-09 | local `KiCAD_files/datasheet/Infineon_IPD_BIP_200N15N3_DS_v02_07_en-3164333.pdf`. Product page: https://www.infineon.com/part/IPD200N15N3-G. The direct PDF URL was not re-checked. |
| [SRP] | Bourns SRP1510CA Series datasheet, REV. 07/26 (current) | https://www.bourns.com/docs/product-datasheets/srp1510ca.pdf. Local copy `Bourns_02182021_SRP1510CA-2025109.pdf` is older (02/2021). Same electrical table; it gives rated voltage as "40 V Typ." where the current revision says 50 V. |
| [UCC] | TI UCC21222 datasheet, SLUSCX6C, revised November 2024 (current) | https://www.ti.com/lit/ds/symlink/ucc21222.pdf. Local copy `ucc21222.pdf` is SLUSCX6A (April 2018). **Several numbers changed in rev C.** The rev C values are used below and the rev A values given where they differ. |
| [ACS] | Allegro ACS730 datasheet, ACS730-DS Rev. 14, 2025-08-28 (current) | https://www.allegromicro.com/-/media/files/datasheets/acs730-datasheet.pdf. Local copy is Rev. 12 (2022-05-17), same values for the items below. |
| [AMC1311] | TI AMC1311 datasheet, SBAS786C, June 2022 | https://www.ti.com/lit/ds/symlink/amc1311.pdf (local `amc1311.pdf`, same revision) |
| [MCP] | Microchip MCP6486 family datasheet, DS20006679A | local `MCP6486_Family_Data_Sheet_DS20006679A-2949415.pdf` (Microchip URL refused automated download) |
| [PU3] | Taiwan Semiconductor PU3BBH–PU3DBH datasheet | local `PU3BBH SERIES_B2109.pdf` |
| [ADR9] | Core2 ADR 0009, safety API / hardware protection | `~/code/Core2/docs/adr/0009-safety-api-hardware-protection.md` (context only, measured latencies) |

---

## 1. Infineon IPD200N15N3 G (Q201 high side, Q202 low side)

Schematic: Q201 drain on /V_High, source on SW_Node. Q202 drain on SW_Node, source on PGND. Gate resistors R215/R216 are 2.2 Ω, with turn-off diodes D202/D203 (PMEG3010CEJ) and gate–source resistors R219/R220 of 4.7 kΩ.

| Parameter | Value | Condition | Source |
|---|---|---|---|
| V(BR)DSS (min) | **150 V** | VGS = 0 V, ID = 1 mA, Tj = 25 °C | [IFX] p.2, static characteristics |
| V(BR)DSS vs Tj (typ) | ≈ 140 V @ −60 °C, ≈ 150 V @ 25 °C, ≈ 158 V @ 100 °C, ≈ 165 V @ 175 °C | ID = 1 mA | [IFX] p.7, Fig. 15 (read off a chart) |
| ID continuous | **50 A** @ TC = 25 °C; **40 A** @ TC = 100 °C | VGS ≥ 10 V | [IFX] p.1, max. ratings; p.4 Fig. 2 |
| ID,pulse | **200 A** | TC = 25 °C (limit shown in Fig. 3) | [IFX] p.1 |
| EAS single pulse | **170 mJ** | ID = 50 A, RGS = 25 Ω. Table header: Tj = 25 °C unless stated. **No starting Tj, L or VDD is given.** | [IFX] p.1, max. ratings |
| Avalanche current vs time in avalanche | IAS = 50 A is allowed for tAV up to ≈ 30 µs (Tj,start 25 °C), ≈ 8 µs (100 °C), ≈ 4 µs (125 °C), then it falls as 1/tAV (≈ 9 A at 1 ms from 25 °C) | RGS = 25 Ω, single pulse | [IFX] p.7, Fig. 13 (read off a chart) |
| Repetitive avalanche (EAR / IAR) | **Not specified** in this datasheet | – | [IFX] p.1 (absent) |
| SOA, single pulse, at VDS = 150 V | 1 µs: ≈ 200 A (ID,pulse limit); 10 µs: ≈ 45 A; 100 µs: ≈ 13 A; 1 ms: ≈ 2 A; 10 ms: ≈ 0.4 A; DC: ≈ 0.25 A | TC = 25 °C, D = 0 | [IFX] p.4, Fig. 3 (read off a log chart, ±20 %) |
| RDS(on) | 16 mΩ typ / **20 mΩ max** | VGS = 10 V, ID = 50 A, Tj = 25 °C | [IFX] p.2 |
| VGS(th) | 2 / 3 / 4 V | VDS = VGS, ID = 90 µA | [IFX] p.2 |
| VGS max | ±20 V | – | [IFX] p.1 |
| Ptot | 150 W | TC = 25 °C | [IFX] p.1 |
| RthJC | **1 K/W max** | – | [IFX] p.2, thermal |
| RthJA | 75 K/W (minimal footprint); 50 K/W (6 cm² cooling area) | 40×40×1.5 mm FR4, 70 µm Cu, vertical, still air | [IFX] p.2, footnote 3 |
| ZthJC single pulse | ≈ 0.02 K/W @ 10 µs, ≈ 0.1 K/W @ 100 µs, ≈ 0.5 K/W @ 1 ms, ≈ 1 K/W ≥ 50 ms | – | [IFX] p.4, Fig. 4 (read off a chart) |
| Tj max / Tstg | **175 °C**; −55 … 175 °C | – | [IFX] p.1 |
| Reverse diode | IS 50 A, IS,pulse 220 A; VSD 1.0 / 1.2 V @ 50 A; trr 106 ns, Qrr 332 nC (VR = 75 V, dIF/dt = 100 A/µs) | Tj = 25 °C | [IFX] p.3 |
| Qg total | 23 nC typ / 31 nC max | VDD = 75 V, ID = 50 A, VGS 0–10 V | [IFX] p.3 |
| Switching | td(on) 14, tr 11, td(off) 23, tf 6 ns (typ) | VDD = 75 V, VGS = 10 V, ID = 50 A, RG,ext = 1.6 Ω | [IFX] p.3 |

**Derived:**

- If the EAS test used the usual unclamped-inductive set-up and the VDD term is ignored, 170 mJ at 50 A implies L ≈ 2·E/I² ≈ **136 µH**. The datasheet does not state L, so this is **UNCONFIRMED**.
- Fig. 13 at 25 °C allows ≈ 30 µs at 50 A. With E ≈ ½·V(BR)·IAS·tAV and V(BR) ≈ 160 V, that is ≈ 0.12 J, the same order as the 170 mJ table value. The same estimate at Tj,start = 100 °C (≈ 8 µs) gives ≈ 0.03 J, and at 125 °C (≈ 4 µs) ≈ 0.016 J. These are rough derived figures. The datasheet gives no EAS at hot start.

## 2. L201 — Bourns SRP1510CA-330M

Schematic: L201 (and L301) value "33uH", footprint `Footprints:SRP1510CA-330M`, field `manf#` = **SRP1510CA-330M**, datasheet field pointing to the Bourns SRP1510CA PDF (`KiCAD_files/PowerLeg.kicad_sch`, symbol L201). The repo has no separate BOM file.

| Parameter | Value | Condition | Source |
|---|---|---|---|
| L | **33 µH ±20 %** | 100 kHz, 0.1 V, 25 °C | [SRP] p.1, Electrical Specifications |
| Isat (typ) | **18.7 A** | "Inductance drops 30 % at Isat" (rated-current definition). The value is typical only, with no min. | [SRP] p.1 table + General Specifications |
| L vs I | ≈ 33 µH flat to ≈ 5 A; ≈ 23 µH at 18 A; **≈ 18 µH at 22.5 A** (end of the chart) | DC current, 25 °C | [SRP] p.2, "L vs. I Charts", SRP1510CA-330M (read off a chart) |
| L above 22.5 A | **Not characterised** (the chart stops at 22.5 A) | – | **UNCONFIRMED** |
| Irms (typ) | **9 A** (20 °C rise); **13 A** (40 °C rise) | – | [SRP] p.1 |
| DCR | **18.7 mΩ typ / 20 mΩ max** | 25 °C | [SRP] p.1 |
| SRF | 4 MHz typ | – | [SRP] p.1 |
| Rated voltage | **50 V** (REV. 07/26); the 2021 copy said "40 V Typ." | not defined further | [SRP] p.1, General Specifications |
| Operating temperature | −55 … +155 °C (temperature rise included) | – | [SRP] p.1 |

## 3. TI UCC21222 (U203 / U303), with the board's bootstrap

Schematic, leg 1:

- VCCI (pins 3, 8) = +5V. GND = DGND. VDDB (pin 11) = +12V, VSSB = PGND.
- VDDA (pin 16) = VDD_SWN, VSSA = SW_Node.
- **DIS (pin 5) is tied to DGND**: the hardware disable is not available to the MCU on this board.
- DT (pin 6): R207 = 20 kΩ to DGND, C211 = 100 nF.
- INA/INB: 51 Ω + 20 pF.
- Bootstrap: +12V → **Q204 (DMP3099 P-MOS)** → R214 2.2 Ω → **D201 PU3DBH** (200 V, 3 A ultrafast) → VDD_SWN.
- Bootstrap capacitors: **C219 1 µF (UMK212B7105KGHT)** ‖ **C217 100 nF (C1206C104K5RAC7867)**.
- Q204's gate is pulled to +12V by R211 (12 kΩ) and pulled low through optocoupler U207 (FODM217A), whose LED is driven by /~{STBY1} (JP413 → MCU PC12). The bootstrap charging path is therefore switchable from the MCU.
- High-side gate–source resistor R219 = 4.7 kΩ.

| Parameter | Value (rev C, current) | Condition | Rev A (local copy) if different | Source |
|---|---|---|---|---|
| VCCI UVLO rising | 2.55 / **2.7** / 2.85 V | – | same | [UCC] p.8, §5.8 |
| VCCI UVLO falling | 2.35 / **2.5** / 2.65 V | – | same | [UCC] p.8 |
| VCCI UVLO hysteresis | 0.2 V typ | – | same | [UCC] p.8 |
| VCCI UVLO off delay (VCC falls → outputs low) | 0.5 / 1.2 / 7 µs; deglitch 0.4 / 0.9 / 3.1 µs | – | rev A: "held low within 1 µs" | [UCC] p.8 |
| VCCI UVLO on delay | 18 … 80 µs | – | 40 µs typ | [UCC] p.8 |
| VDDA/VDDB UVLO rising (8-V option = UCC21222) | 7.7 / **8.5** / 8.9 V | – | 8 / 8.5 / 9 V | [UCC] p.8 |
| VDDA/VDDB UVLO falling | 7.2 / **7.9** / 8.4 V | – | 7.5 / 8 / 8.5 V | [UCC] p.8 |
| VDD UVLO hysteresis | 0.6 V typ | – | 0.5 V | [UCC] p.8 |
| VDD UVLO off delay | 0.1 / 0.5 / 2 µs; deglitch 0.1 / 0.17 µs | – | – | [UCC] p.8 |
| VDD UVLO on delay | ≤ 10 µs | – | 22 µs typ | [UCC] p.8 |
| VDDA/VDDB recommended range | **9.2 … 25 V** | 8-V UVLO version | 18 V max | [UCC] p.4, §5.3 |
| VDDx quiescent current | 1.2 / 2.0 mA (INx = 0); **1.4 / 2.2 mA (INx = VCC, i.e. output high)** | VDD = 12 V | 1.0 / 1.8 mA | [UCC] p.8 |
| Propagation delay tPDLH, tPDHL | 26 / **33** / 45 ns | 100 ns pulse, 500 kHz | 28 / 40 ns | [UCC] p.9, §5.9 |
| DIS response delay (HL and LH) | 27 / **48** / 80 ns | VDD ≥ VDD_ON + 0.2 V | Fig. 20, ≈ 36–49 ns typ | [UCC] p.9; §7.4.1 p.22 |
| DIS pin default | Open or high = **outputs disabled** (internal pull-up); low = enabled | – | rev A said pulled **low** if open (changed in rev C) | [UCC] p.3 pin table, §7.4.1 p.22, revision history p.40 |
| Min input pulse passed | 4 / 12 / 30 ns | – | 10 / 20 ns | [UCC] p.9 |
| Dead time, RDT = 20 kΩ | 167 / **185** / 203 ns (DT ≈ 8.6·RDT[kΩ] + 13) | – | 160 / 200 / 240 ns (DT = 10·RDT) | [UCC] p.8; p.30 |
| 100 % high-side duty | "a 100% duty cycle for the high side is not possible unless there is a dedicated power supply for the high side": the low side must conduct (or freewheel) every cycle to refresh CBOOT | bootstrap supply | – | [UCC] §8.2.3, p.33 (item 2) |
| Bootstrap capacitor guidance | QTotal = QG + IVDD/fsw; CBOOT ≥ QTotal / ΔVVDDA (example 170 nF min → 1 µF chosen, + 100 nF). VDD must not drop below the recommended minimum for the whole high-side on-time. If it drops below UVLO falling, the high-side output turns off ("uncontrolled hard-switching … may result in permanent damage"). Too large a CBOOT may not charge in the first cycles. | – | – | [UCC] §8.2.2.7.2, pp.29–30 |
| Bootstrap diode / resistor | Fast-recovery, voltage rating above the DC link with margin; RBOOT recommended (2.2 Ω in the example) | – | – | [UCC] §8.2.2.2, p.25 |

Bootstrap diode on the board ([PU3]): PU3DBH, VRRM 200 V, IF 3 A, VF 0.81 V typ @ 1.5 A / 0.93 V max @ 3 A (25 °C), trr 25 ns max.

**Derived (board hold-up at duty near 100 %):**

- During the high-side on-time C219 ‖ C217 (1.1 µF nominal, before X7R DC-bias derating, which is **UNCONFIRMED**) supplies two loads:
  - the driver's VDDA current with the output high: 1.4 mA typ / 2.2 mA max;
  - R219: ≈ 11 V / 4.7 kΩ ≈ 2.3 mA.
- Starting from ≈ 11.2 V (12 V minus ≈ 0.8 V for D201 and R214), the time until VDDA reaches:
  - the recommended minimum (9.2 V): ≈ 1.1 µF·2.0 V / 4.5 mA ≈ **0.5 ms** worst case;
  - UVLO falling, typical case (7.9 V, 3.7 mA): ≈ 1.1 µF·3.3 V / 3.7 mA ≈ **1.0 ms**;
  - UVLO falling, worst case (8.4 V, 4.5 mA): ≈ 1.1 µF·2.8 V / 4.5 mA ≈ **0.7 ms**.
- At 200 kHz this is about 100–200 periods with no low-side conduction before the high side drops out by itself.
- If /~{STBY1} turns Q204 off, the bootstrap stops recharging altogether.

## 4. Allegro ACS730KLCTR-20AB (U202 / U302) and the I1_LOW path to COMP1

Schematic: symbol value "ACS730xLCTR-20AB", `manf#` = **ACS730KLCTR-20AB**. There is no -S/-T suffix; Allegro says the -S and -T variants have identical performance ([ACS] p.2, notes 2–3).

- IP+ (pins 1, 2) = L201 pad 1. IP− (pins 3, 4) = /V_{1_Low_unfused}. L201 pad 2 is SW_Node.
- **Positive output = current flowing from the switch node through L201 into LOW1** (buck direction), per [ACS] p.1: "positive slope when an increasing current flows … from pins 1 and 2, to pins 3 and 4".
- VCC = +5V. VZCR has C210 = 1 nF to DGND (the allowed max is 1 nF). VIOUT drives only R217, with no capacitor on the output.

| Parameter | Value | Condition | Source |
|---|---|---|---|
| Optimised sensing range IPR | **±20 A** | – | [ACS] p.6, xKLCTR-20AB table; p.2 selection guide |
| Sensitivity | **100 mV/A** typ | VCC = 5 V | [ACS] p.6 |
| Zero-current output VIOUT(Q) | 2.5 V typ | IP = 0, TA = 25 °C | [ACS] p.6 |
| Output beyond IPR | "will continue to respond … until the high or low saturation voltage; nonlinearity … worse" | – | [ACS] p.5, note 2 |
| VOH (output high saturation) | **≥ VCC − 0.4 V** (typ VCC − 0.3 V) | TA = 25 °C | [ACS] p.5, common electrical characteristics |
| VOL (output low saturation) | 0.1 V typ / **0.2 V max** | TA = 25 °C | [ACS] p.5 |
| Internal bandwidth | **1 MHz** typ | small signal −3 dB, CL = 0.47 nF | [ACS] p.5 |
| Response time | **0.7 µs** typ | TA = 25 °C, CL = 0.47 nF | [ACS] p.5 |
| Propagation delay / rise time | 0.2 µs / 0.6 µs typ | same | [ACS] p.5 |
| Output slew rate | 2.67 V/µs typ (≈ 26.7 A/µs equivalent) | CL = 1 nF | [ACS] p.5 |
| Noise | 40 mA rms (input-referred) | TA = 25 °C, CL = 0.47 nF | [ACS] p.5 |
| Total output error | ±3 % typ / ±4 % max (25–125 °C); ±6.7 % incl. lifetime drift | IP = IPR(max) | [ACS] p.6 |
| Offset | ±50 typ / ±75 mV max (25–125 °C); ±118 mV incl. lifetime drift (≈ ±1.2 A) | IP = 0 | [ACS] p.6 |
| Primary resistance | 1.2 mΩ typ | – | [ACS] p.5 |
| Output load limits | CL ≤ 0.47 nF, RL ≥ 10 kΩ | – | [ACS] p.5 |
| TJ max | 165 °C (surges above the continuous limit are allowed if TJ max is respected) | – | [ACS] p.3 abs. max.; p.26 thermal section |

**Analog path, sensor → MCU pin (schematic):**

- VIOUT (/Power Leg 1/IILow) → R217 5.9 kΩ → U205 (+), with R222 20 kΩ to DGND.
- U205 (−): R218 20 kΩ from +5V, R223 5.9 kΩ to the output, C221 20 pF across R223.
- U205 is an MCP6486, powered from +5V.
- Output /I_{I1Low} → TP203, J1 pin 13 → **SPIN U401 pin 30 = PA1**. PA1 is COMP1+ per [ADR9].
- Transfer: V(PA1) = VIOUT·(20/25.9)·(1 + 5.9/20) − 5·(5.9/20) = **VIOUT − 1.475 V** (gain exactly 1). R217/R223 are RR1220P-5901-D (0.5 %), R218/R222 are RT0805DRD (0.5 %).
- Hence **V(PA1) = 1.025 V + 0.1 V/A · I**.
- Filter: C221 with R223 gives a pole at ≈ **1.35 MHz**. MCP6486 GBWP is 10 MHz (noise gain 1.295, closed-loop BW ≈ 7.7 MHz), slew rate 20 V/µs, output swing to within 3.5 mV typ / 10 mV max of the rails ([MCP] p.2–3).
- Any filter inside the SPIN module between its pin 30 and the STM32 PA1 is **UNCONFIRMED**: the SPIN schematic is not in this repo.

**Derived usable window at PA1:**

| Current | VIOUT | V(PA1) | Note |
|---|---|---|---|
| −10.25 A | 1.475 V | 0 V | **op-amp output at the 0 V rail: currents more negative than ≈ −10 A are clipped and invisible at PA1** |
| 0 A | 2.5 V | 1.025 V | |
| +20 A | 4.5 V | 3.025 V | end of IPR |
| +21 A (VOH min, 4.6 V) to +22 A (VOH typ, 4.7 V) | 4.6–4.7 V | 3.125–3.225 V | **sensor saturated; anything above reads the same** |

## 5. VHigh sensing and bulk capacitance (context for reaction times)

**VHigh sense** (one per board, sheet High_side):

- /V_High → R601 330 kΩ (CR0805-FX-3303ELF) / R602 5.6 kΩ (CR0805-FX-5601ELF) to PGND.
- Ratio 5.6/335.6 = **0.01669**.
- → U601 **AMC1311B** (isolated, gain 1) → U603 MCP6486 difference amplifier, 27 kΩ/27 kΩ (gain 1), with C605 20 pF across R606 (pole ≈ **295 kHz**).
- → /V_{IHigh_sense} → SPIN pin 27 = **PC3**.

| Parameter | Value | Source |
|---|---|---|
| AMC1311 linear input | −0.1 … **2.0 V** (→ VHigh ≈ 0 … **119.9 V**) | [AMC1311] §7.3, VFSR |
| AMC1311 input before output clipping | **2.516 V** (→ VHigh ≈ **150.8 V**; above this the reading is flat) | [AMC1311] §7.3, VClipping |
| AMC1311B output bandwidth | 220 min / **275 kHz** typ | [AMC1311] §7.9 |
| AMC1311B signal delay (unfiltered) | 50–10 %: 1.0 / 1.5 µs; 50–50 %: **1.6 / 2.1 µs**; 50–90 %: 2.5 / 3.0 µs (typ / max) | [AMC1311] §7.10 |
| AMC1311 rise / fall | 1.3 µs typ | [AMC1311] §7.10 |
| Input resistance | 1 GΩ typ | [AMC1311] §7.9 |

Per [ADR9], VHigh (and I_HIGH) are watched by the ADC-watchdog path. Its reaction time is N × switching period + one conversion (measured 0.68–15.16 µs on ADC2 at 200 kHz, three channels). The comparator path measured 258–310 ns, pin to outputs off.

**Capacitance on /V_High.** Both legs share the same net.

| Per leg | Parts | Nominal |
|---|---|---|
| Electrolytic | C230, C231: 33 µF 160 V, ULV2C330MNL1GS | 66 µF |
| Ceramic | C224–C229: 4.7 µF 100 V X7R 1210 (CL32B475KCVZNWE) in **three series pairs** (midpoint balanced by R201/R206 1 MΩ) | 3 × 2.35 = 7.05 µF |
| Small | C223 100 nF, C222 1 nF | 0.1 µF |
| **Per leg** | | **≈ 73.2 µF** |
| **Board (two legs on /V_High)** | + C5002 470 nF on the feeder via JP5001 | **≈ 147 µF nominal** |

The README states "on each leg, VHigh has about 138 µF". The netlist gives ≈ 73 µF per leg, ≈ 147 µF for the board. The DC-bias derating of the X7R parts is **UNCONFIRMED**.

**LOW1 side** (/V_{1_Low_unfused}, per leg):

- C206, C209, C212: 4.7 µF 100 V X7R 1210 (CL32B475KCVZNWE), 14.1 µF nominal.
- **C203**: 47 µF 100 V electrolytic (EEE-FN2A470UL), returned to PGND through **Q203 DMN10H220L** (switched by /LEG1_CAPA_DRIVE = PC6 via U206).
- Fuse F102 (10 A) sits between /V_{1_Low_unfused} and the LOW1 terminal.
- V1_LOW sense: R202 150 kΩ / R203 470 Ω (ratio 0.003124) → AMC1100.

---

## Implications for #6 (facts only)

1. **Inductor.**
   - The predicted 48 A duty-step peak is **2.57 × Isat (157 % above the 18.7 A typical Isat)**, and 2.1 × the highest current Bourns characterises (22.5 A, where L ≈ 18 µH, about −45 %).
   - L at 48 A is not given by any primary source.
   - A model with a constant 33 µH does not follow the datasheet L(I) above about 10 A.
2. **MOSFET current.**
   - 48 A is below ID,pulse (200 A) and just below the continuous rating at TC = 25 °C (50 A).
   - It is above the continuous rating at TC = 100 °C (40 A).
   - The device is not in linear mode during a duty step, so Fig. 3 SOA (linear-mode, single pulse) applies only to clamp or avalanche cases.
3. **MOSFET avalanche energy.**
   - The 0.15 J in the model is close to the datasheet EAS of **0.17 J**, which is specified only at ID = 50 A, RGS = 25 Ω, Tj = 25 °C, with no L or starting-Tj variants.
   - From Fig. 13 the time in avalanche at 50 A shrinks by about 4× at Tj,start = 100 °C and about 8× at 125 °C (derived energy ≈ 0.03 J and ≈ 0.016 J).
   - No repetitive avalanche rating exists.
   - The clamp case in DIAGNOSIS (9.9 J in 10 ms) is about 58× the datasheet EAS.
4. **MOSFET voltage.** V(BR)DSS is 150 V min at 25 °C and about 140 V typ at −60 °C. The step-down case (Vds 109 V) leaves 41 V to the 25 °C minimum.
5. **Current sensor range.**
   - The ACS730-20AB output saturates at about **+21 A** (VOH min) to +22 A (typ) and about −23 A (VOL max).
   - The board's level shift clips negative currents at about **−10.25 A** (PA1 at 0 V).
   - A 48 A event reads at most about +21–22 A. A boost-direction (negative) current beyond −10 A cannot be seen at PA1 at all.
6. **Current-limit latency (derived chain).**
   - Sensor response 0.7 µs typ + level shifter (pole 1.35 MHz, ≈ 0.1 µs) + COMP1→HRTIM fault 0.26–0.31 µs measured ([ADR9] L0-LAT-02) + driver 33–45 ns ≈ **1.1–1.2 µs** typ from current to gate off.
   - The SPIN-internal filter on PA1 is unconfirmed.
   - During that time, with 100 V across L, di/dt = V/L ≈ 3 A/µs at 33 µH and ≈ 5.6 A/µs at 18 µH, i.e. ≈ 3.3 … 6.5 A of further rise.
7. **VHigh measurement.**
   - The VHigh reading is linear only to **≈ 120 V** and is flat above **≈ 151 V** (AMC1311 clipping).
   - The AMC1311B alone adds 1.6 µs typ / 2.1 µs max of delay (50–50 %) and limits BW to 275 kHz typ, before the ADC-watchdog sampling delay.
8. **Gate driver.**
   - VDDA UVLO falling is 7.2 / 7.9 / 8.4 V. The recommended minimum is 9.2 V.
   - With the board's 1.1 µF bootstrap and 4.7 kΩ gate pull-down, the high side can be held on for about 0.5 ms (recommended-minimum limit, worst case) to about 1 ms (typical UVLO) with no low-side conduction (derived). After that the high-side output turns off by UVLO, which TI warns is uncontrolled hard switching.
   - DIS is tied to GND, so there is no driver-level hardware disable on this board. The HRTIM fault path is the only fast off path.
   - DIS response, if it were used: 48 ns typ, 80 ns max.
9. **Inductor rated voltage.** The current Bourns datasheet gives "Rated Voltage 50 V" for the SRP1510CA family without a definition. Whether it limits VHigh − V1_LOW across L201 is **UNCONFIRMED**.
