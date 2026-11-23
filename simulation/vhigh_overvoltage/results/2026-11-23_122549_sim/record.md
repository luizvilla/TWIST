---
campaign: 2026-11-23_122549_sim
model_sha1: b86445077bf73b03941e09c6785b93a64cef94e8
cases: 21
pass: 36
fail: 8
info: 42
new_failures: 0
reviewed: 
---

# TWIST power leg: VHigh overvoltage and overcurrent

| Criterion | Verdict | Limit | Measured |
|---|---|---|---|
| D-DIS-01.a | FAIL (known F-1) | <= 150 V | 172.7 V |
| D-DIS-02.a | FAIL (known F-1) | <= 150 V | 191.8 V |
| D-FIX-08.e | FAIL (known F-3) | <= 150 mJ | 9903 mJ, peak 1.1 kW |
| D-FIX-09.e | FAIL (known F-3) | <= 150 mJ | 1579 mJ, peak 0.4 kW |
| D-SKT-01.a | FAIL (known F-1) | <= 150 V | 192.1 V |
| D-SKT-02.a | FAIL (known F-1) | <= 150 V | 366.9 V |
| D-STP-01.b | FAIL (known F-2) | <= 40 A | 81.0 A |
| D-STP-02.b | FAIL (known F-2) | <= 40 A | 66.9 A |
| D-BEN-01.a | PASS | <= 150 V | 105.0 V |
| D-BEN-01.b | PASS | <= 40 A | 8.0 A |
| D-BEN-02.a | PASS | <= 150 V | 105.5 V |
| D-BEN-02.b | PASS | <= 40 A | 8.6 A |
| D-BEN-03.a | PASS | <= 150 V | 105.0 V |
| D-BEN-03.b | PASS | <= 40 A | 8.2 A |
| D-BEN-04.a | PASS | <= 150 V | 105.0 V |
| D-BEN-04.b | PASS | <= 40 A | 14.3 A |
| D-BEN-05.a | PASS | <= 150 V | 106.9 V |
| D-BEN-05.b | PASS | <= 40 A | 33.0 A |
| D-DIS-01.b | PASS | <= 40 A | 8.0 A |
| D-DIS-02.b | PASS | <= 40 A | 8.0 A |
| D-DIS-03.a | PASS | <= 150 V | 119.5 V |
| D-DIS-03.b | PASS | <= 40 A | 2.0 A |
| D-FIX-01.a | PASS | <= 150 V | 117.5 V |
| D-FIX-01.b | PASS | <= 40 A | 8.0 A |
| D-FIX-02.a | PASS | <= 150 V | 110.7 V |
| D-FIX-02.b | PASS | <= 40 A | 8.0 A |
| D-FIX-03.a | PASS | <= 150 V | 110.0 V |
| D-FIX-03.b | PASS | <= 40 A | 8.0 A |
| D-FIX-04.a | PASS | <= 150 V | 111.0 V |
| D-FIX-04.b | PASS | <= 40 A | 25.0 A |
| D-FIX-05.a | PASS | <= 150 V | 143.2 V |
| D-FIX-05.b | PASS | <= 40 A | 25.0 A |
| D-FIX-06.a | PASS | <= 150 V | 105.0 V |
| D-FIX-06.b | PASS | <= 40 A | 13.8 A |
| D-FIX-07.a | PASS | <= 150 V | 105.0 V |
| D-FIX-07.b | PASS | <= 40 A | 20.0 A |
| D-FIX-08.a | PASS | <= 150 V | 130.0 V |
| D-FIX-08.b | PASS | <= 40 A | 25.0 A |
| D-FIX-09.a | PASS | <= 150 V | 130.0 V |
| D-FIX-09.b | PASS | <= 40 A | 8.0 A |
| D-SKT-01.b | PASS | <= 40 A | 8.0 A |
| D-SKT-02.b | PASS | <= 40 A | 25.0 A |
| D-STP-01.a | PASS | <= 150 V | 119.2 V |
| D-STP-02.a | PASS | <= 150 V | 113.8 V |
| D-BEN-01.c | INFO |  | -5.0 V |
| D-BEN-01.d | INFO |  | VHigh 59.8 V at the end, -3.1 V/ms over the last 10 % |
| D-BEN-02.c | INFO |  | -4.5 V |
| D-BEN-02.d | INFO |  | VHigh 98.8 V at the end, -0.0 V/ms over the last 10 % |
| D-BEN-03.c | INFO |  | -5.0 V |
| D-BEN-03.d | INFO |  | VHigh 13.2 V at the end, -3.8 V/ms over the last 10 % |
| D-BEN-04.c | INFO |  | -5.0 V |
| D-BEN-04.d | INFO |  | VHigh 98.0 V at the end, -0.0 V/ms over the last 10 % |
| D-BEN-05.c | INFO |  | -3.1 V |
| D-BEN-05.d | INFO |  | VHigh 99.7 V at the end, -0.0 V/ms over the last 10 % |
| D-DIS-01.c | INFO |  | +62.7 V |
| D-DIS-01.d | INFO |  | 150 V crossed at 7.578 ms; VHigh 172.7 V at the end, +9.5 V/ms over the last 10 % (still rising: the run stops before the peak) |
| D-DIS-02.c | INFO |  | +81.8 V |
| D-DIS-02.d | INFO |  | 150 V crossed at 5.604 ms; VHigh 191.7 V at the end, +9.7 V/ms over the last 10 % (still rising: the run stops before the peak) |
| D-DIS-03.c | INFO |  | +9.5 V |
| D-DIS-03.d | INFO |  | VHigh 119.5 V at the end, +2.0 V/ms over the last 10 % (still rising: the run stops before the peak) |
| D-FIX-01.c | INFO |  | +7.5 V |
| D-FIX-01.d | INFO |  | OV trip at 3.737 ms; VHigh 117.5 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-02.c | INFO |  | +0.7 V |
| D-FIX-02.d | INFO |  | OV trip at 2.837 ms; VHigh 110.7 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-03.c | INFO |  | +0.0 V |
| D-FIX-03.d | INFO |  | OV trip at 2.742 ms; VHigh 110.0 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-04.c | INFO |  | +1.0 V |
| D-FIX-04.d | INFO |  | OV trip at 0.141 ms; VHigh 111.0 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-05.c | INFO |  | +33.2 V |
| D-FIX-05.d | INFO |  | OV trip at 1.136 ms; VHigh 143.2 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-06.c | INFO |  | -5.0 V |
| D-FIX-06.d | INFO |  | VHigh 99.5 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-07.c | INFO |  | -5.0 V |
| D-FIX-07.d | INFO |  | VHigh 99.5 V at the end, -0.0 V/ms over the last 10 % |
| D-FIX-08.c | INFO |  | +20.0 V |
| D-FIX-08.d | INFO |  | VHigh 130.0 V at the end, +0.0 V/ms over the last 10 % |
| D-FIX-09.c | INFO |  | +20.0 V |
| D-FIX-09.d | INFO |  | VHigh 130.0 V at the end, +0.0 V/ms over the last 10 % |
| D-SKT-01.c | INFO |  | +82.1 V |
| D-SKT-01.d | INFO |  | 150 V crossed at 5.550 ms; VHigh 192.1 V at the end, +9.6 V/ms over the last 10 % (still rising: the run stops before the peak) |
| D-SKT-02.c | INFO |  | +256.9 V |
| D-SKT-02.d | INFO |  | 150 V crossed at 1.396 ms; VHigh 366.8 V at the end, +21.4 V/ms over the last 10 % (still rising: the run stops before the peak) |
| D-STP-01.c | INFO |  | +9.2 V |
| D-STP-01.d | INFO |  | VHigh 99.5 V at the end, -0.0 V/ms over the last 10 % |
| D-STP-02.c | INFO |  | +3.8 V |
| D-STP-02.d | INFO |  | VHigh 100.0 V at the end, +0.0 V/ms over the last 10 % |
