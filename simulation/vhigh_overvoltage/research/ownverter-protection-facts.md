# Ownverter 1.1: facts for the protection limits

Collected 2026-11-25 for [Protection architecture](https://github.com/luizvilla/TWIST/issues/6), read-only. Sources: OWNVERTER KiCad repo at `6b4b9be` ("V1.1.1 as ordered 8Nov25"; sensing as v1.1.0), datasheets in `OWNVERTER/KiCAD_files/datasheet/`, Core2 `zephyr/boards/shields/ownverter/ownverter_v1_1_0.overlay` and `docs/safety/boards/ownverter_v1_1_0.md`. Refdes are for leg 1 (6xx); legs 2 and 3 are 7xx and 8xx. ADC reference 2.048 V.

**Uncertain** values are marked *(u)*; chart readings *(chart)*; derived numbers *(derived)*.

## Bus (V_IHigh)

| Item | Value |
|---|---|
| Rating | 12–100 VDC (absolute max table 8–100 V), 1.3 kW, 200 kHz |
| Lowest-rated parts on the bus | NCP12700ADNR2G feeder controller, VIN max **120 V** (U501, via JP501 and L501); MOSFETs 150 V; electrolytics 160 V; fuse F201 125 VDC |
| Capacitance per leg | C620, C621 33 µF Nichicon ULT 160 V (66 µF); C622–C627 4.7 µF X7R 100 V, three series pairs (7.05 µF nominal, less under DC bias) |
| Total | ≈ 219 µF on the bus + ≈ 4.8 µF behind L501 ≈ **224 µF nominal** (≈ 200 µF with ceramic derating, estimate) |
| Sensing | R201 330 k / R202 5.6 k (0.016687) → AMC1311BDWVR (1.6–2.1 µs, 220–275 kHz) → MCP6486 difference amp, 295 kHz pole → PC2 (ADC ch8) |
| Reading saturates | ADC full scale **122.7 V**; AMC1311 linear to 119.9 V, clips ≈ 150.8 V |
| Fail-low | If AMC1311 VDD1 (+5V_PGND from the bus via the feeder) is missing, V_HIGH reads 0 V |

## Switches

IPD200N15N3 G (Rev 2.07): 150 V, ID,pulse 200 A, EAS 170 mJ (50 A, 25 °C). SOA *(chart)*: 10 µs ≈ 45 A at 150 V, 100 µs ≈ 13 A at 150 V, 1 ms ≈ 4–5 A at 100 V.

## Leg current sensors

- Fitted part *(u)*: `manf#` says ACS730KLCTR-20AB, Value says ACS724LLCTR-50AB; the #28 calibration (52.6 mV/A at the pin) and `spoc_bench.md` point to **ACS724-50AB**.
- Path: divider R618/R624 (0.8987) → MCP6486 gain 1.433 with −2.165 V offset → Vout = 1.055 V + 51.5 mV/A. JP904/JP901 (open by default) switch to the ±50 A setting (≈ 20 mV/A).
- **Measurable range (jumpers open): about −19.9 A to +19.1 A**, both signs inside the ADC (no one-sided clip as on TWIST). Past +19 A the op-amp output rises to ≈ 3.6 V at +50 A, above VDDA, into the MCU pin *(derived)*.
- Pins: I1 PC1 (COMP3 → FLT5), I2 PA1 (COMP1 → FLT4), I3 PB11 (COMP6 → FLT3).
- I_HIGH sensor U202 *(u)*: 20AB vs 50AB, PC3, no limit.

## Fuses

| Ref | Part | Rating | Rail |
|---|---|---|---|
| F201 | Bel 0678H9300-02 | 30 A, I²t 2000 A²s | DC input → bus |
| F601/F701/F801 | Bel 0678H9250-02 | 25 A, I²t 660 A²s | each phase output *(u: docs say 15 A for ±20 A, 30 A for ±50 A)* |
| F401/F402 | 0ZCH0035FF2G | 350 mA polyfuse | +6 V aux input |

## Gate drivers

- UCC21222DR per leg, **DIS tied to DGND**, DT 20 k ≈ 200 ns. Low side VDDB = +12V_PGND from PS501, not switchable.
- High side bootstrap: +12V_PGND → Q699 DMP3099L P-MOS → R614 2.2 Ω → D605 *(u: STTH4R02U vs PU3DBH)* → VDDA (1.1 µF).
- **~STBY cut**: FODM217A U602 gates Q699. ~STBY1 PC12, ~STBY2 PC13, ~STBY3 PB7. High = bootstrap on; low or floating = off (reset-safe). LED resistor R610 **51 Ω** → ≈ 40 mA from the GPIO, above the STM32 pin rating *(derived, VF ≈ 1.2 V assumed; to check on the bench)*.

## Core2 overlay (v1.1.0)

- 200 kHz, all legs `open`, **no safety-outputs node**.
- Limits: V_HIGH 10 / 100 V (high on ADC1 AWD2 → FLT2, low software); I1_LOW ±7 A (ADC2 AWD3 → FLT6 / COMP3 → FLT5); I2_LOW ±7 A (low software, exception / COMP1 → FLT4); I3_LOW ±7 A (ADC1 AWD1 → FLT1 / COMP6 → FLT3); V1–V3_LOW −10 / 70 V software (the −10 V bound is out of the sensor range and can never trip). All six fault inputs used.
- ADC sequences: ADC1 = V1_LOW, V2_LOW, I3_LOW, V_HIGH, V_NEUTR (5); ADC2 = I1_LOW, I2_LOW, V3_LOW, I_HIGH, TEMP (5). Worst watchdog revisit **5 × 5 µs = 25 µs** (+2 µs AMC1311 for V_HIGH). LEG3 default ADC is "UNKNOWN_ADC".

## Inductors

None on the legs; the motor inductance is external.

## Bus overvoltage sizing (computed in #6)

C ≈ 200 µF, trip 100 V, ceiling 120 V (NCP12700): ADC-watchdog path (27 µs) holds up to **148 A** returned; 25 A braking overshoots 3.4 V; three legs at 50 A overshoot ≈ 20 V, at the edge of the margin. The software path (250 µs) holds only 16 A.
