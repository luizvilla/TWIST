# Micro-verter (uSolarVerter V0.9): facts for the protection limits

Collected 2026-11-25 for [Protection architecture](https://github.com/luizvilla/TWIST/issues/6), read-only. Sources: `HARDWARE/micro-inverter/KiCAD_Files` at `a4a4a2b` ("V0.9 as ordered 23/01/26"; `private_uverter` is an older identical copy), Core2 branch `apf_quadrature` (`4dd95e9d`) overlay `zephyr/boards/shields/uSolarVerter/uSolarVerter_v0_9_0.overlay` with `src/main.cpp` and `src/app/control_step.h`, boost firmware `code/core-micro-verter-boost` (`43e249e`). ADC reference 2.048 V.

**Uncertain** values are marked *(u)*; derived numbers *(derived)*. The micro-verter work is paused until the Core2 Safety API and its merge into Core are finished (Luiz, 2026-11-26).

## Key findings

1. **The bus overvoltage trip can never fire.** VDCBus gain 0.110840 V/count, so the reading tops out at ≈ 453.9 V (≈ 465 V by the design divider; the firmware gain is ≈ 2.4 % off). The trips (`boost_trip_voltage` and `VDC_max` = 460 V) are above that. The 440 V burst level is reachable.
2. **DIS_HV (PB9, Spin pin 21) is not reset-safe.** It drives the EN of U703 VPS8701B, which makes +12V_HV. EN is active-high with an internal pull-up and there is no external pull-down, so under MCU reset +12V_HV stays on. Pulled low, it removes every GaN gate supply (low side and the bootstrap rails) **and** +5V_HV, which powers the bus-voltage AMC1311: the bus then reads ≈ 0 V. Decay to the GaN UVLO (7.8 V) ≈ 2–5 ms *(derived)*. No firmware drives it.
3. **The PV current sensors look wired for the wrong sign *(u)*.** INA240 IN+ on the inductor side, IN− on V_ILow, REF grounded: forward PV current gives a negative differential and the output should clip at 0 V, yet the firmware uses +0.005 A/count and trips at +8 A. Bench check needed.
4. **The Safety API is not active**: `safety.initShield()` is never called; the overlay's thresholds are stale TWIST copies (bus 10–100 V, ±7 A); no safe outputs, no HRTIM fault input.

## Topology and ratings

PV 16–58 V → two interleaved isolated current-fed half-bridge DC/DC channels (LEG1_LOW, LEG2_LOW) → 400 V bus (`HV_BUS`, sensor `VDCBus`) → GaN full bridge → filter, fuses, relay → grid 220–250 VAC. 450 VA rated; PV input 11 A. Bus nominal 400 V, schedule 390–410 V, reference max 420 V, burst/OV hysteresis 440 V.

## Bus capacitance

| Parts | Value | Rating |
|---|---|---|
| C1–C3 film board (KNSCHA 228CB0046, PP) | 3 × 40 µF = 120 µF | **500 V, the lowest on the bus** |
| C121, C127 film | 2 × 1 µF | 630 V |
| C16, C17, C114, C115 X7R | 4 × 100 nF (much less at 400 V) | 630 V |
| Doubler pairs | ≈ 2 × 0.5 µF | 630 V |

Total ≈ 122–123 µF (9.8 J at 400 V; 400 → 460 V adds 3.2 J).

## Bus sensing

4 × 1.13 MΩ / 20 kΩ (1/227), C401 100 pF (≈ 80 kHz) → AMC1311BDWVR (linear 0–2 V ≈ 454 V) → MCP6486 difference amp, **33.9 kHz pole** → PC3 (ADC ch9). No comparator on PC3.

## Switches

- Q1–Q4 Tokmas CID12N65D e-mode GaN with integrated driver: 650 V (750 V transient < 1 µs), ID 11.5 A, ID,pulse 20.5 A (25 °C, 10 µs), VCC UVLO 8.4 / 7.8 V, PWM 200 k pull-down. No EAS, no SOA in the datasheet.
- Q5–Q10 JSCJ CJAC90SN12: 120 V, IDM 360 A, EAS 500 mJ.
- D1–D4 Tokmas CI04S65E3 SiC 650 V.

## Current sensors

| Sensor | Chain | Range | Pin |
|---|---|---|---|
| ILow1, ILow2 | 5 mΩ → INA240A1 (gain 20, unidirectional) → 0.1 V/A | 0 to +20.5 A, one sign only (sign doubt, finding 3) | PA1 (COMP1), PC1 (COMP3) |
| IAC | 30 mΩ → AMC1301 → diff amp 28 kHz → +1.024 V offset, 0.298 V/A | ≈ −3.4 / +3.4 A (firmware calibration −3.16 / +3.72 A); AMC1301 itself ±8.3 A | PC2, **no comparator** |
| VLow | ÷40, 6.4 kHz | ≈ 82 V | PA0 |
| VAC | AMC1301 | ≈ ±384 V | PC0 |

Free comparator / fault pins on this shield: PB1, PA3, PA7, PB0, PB11, PA15, PB10, PC7.

## Fuses

F1, F101 SETsafe SPT478T2.5A250V, 2.5 A time-lag, in L and N after FL1. **No fuse on the PV input or the 400 V bus.** MOVs RV101–103, RV1–3; GDT GD1.

## Gate drivers and reset state

- HV bridge: drivers integrated in the GaN; low side VCC from +12V_HV, high side bootstrap from +12V_HV. PWM through ISO7720F (defaults low).
- LV legs: UCC27282 U3, U4; **EN_I = PC12** (pin 19), active-high with internal 250 k pull-down → off under reset.
- Grid relay K1: PC13 (pin 22) via Q11, R13 10 k pull-down → open under reset.
- Under reset: relay open, LV drivers off, GaN PWM low, **+12V_HV on**.

## Firmware

LV legs 200 kHz, HV legs 50 kHz, control task 50 µs. ADC_1 = VLow, VAC, VDCBus (N = 3), trigger source *(u)*: PWMA 200 kHz → VDCBus every 15 µs, or PWMD 50 kHz → every 60 µs. ADC_2 = ILow1, (ILow2), IAC at 100 kHz.

## Inductors

L1, L3 grid side 250 µH, Isat 6.5 A *(LCSC listing)*; L5, L6 PV input 33 µH, Isat 16.7 A *(u: footprint named SRP1510CA-330M)*.

## Bus overvoltage sizing (computed in #6)

C ≈ 122 µF, trip ≈ 450 V (inside the ≈ 454 V reading), ceiling 500 V (film caps): ADC-watchdog path holds up to **277 A** at 200 kHz (91 A at 50 kHz); the DC/DC at 550 W returns ≈ 1.4 A, overshoot < 1 V. Any path is fast enough; the constraint is the sensing range against the threshold.
