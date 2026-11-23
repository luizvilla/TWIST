---
campaign: 2026-11-23_150526_sim
model_sha1: f1b740668a94655cfe04c5f0f3a8984b5747fad6
cases: 5
pass: 10
fail: 0
info: 10
new_failures: 0
reviewed: 
---

# TWIST power leg: VHigh overvoltage and overcurrent

| Criterion | Verdict | Limit | Measured |
|---|---|---|---|
| D-L2P-01.a | PASS | <= 150 V | 32.0 V |
| D-L2P-01.b | PASS | <= 40 A | 0.5 A |
| D-L2P-02.a | PASS | <= 150 V | 34.5 V |
| D-L2P-02.b | PASS | <= 40 A | 1.0 A |
| D-L2P-03.a | PASS | <= 150 V | 38.6 V |
| D-L2P-03.b | PASS | <= 40 A | 1.2 A |
| D-L2P-04.a | PASS | <= 150 V | 42.2 V |
| D-L2P-04.b | PASS | <= 40 A | 1.5 A |
| D-L2P-05.a | PASS | <= 150 V | 45.0 V |
| D-L2P-05.b | PASS | <= 40 A | 2.0 A |
| D-L2P-01.c | INFO |  | -78.0 V |
| D-L2P-01.d | INFO |  | VHigh 32.0 V at the end, +0.0 V/ms over the last 10 % |
| D-L2P-02.c | INFO |  | -75.5 V |
| D-L2P-02.d | INFO |  | VHigh 34.5 V at the end, +0.0 V/ms over the last 10 % |
| D-L2P-03.c | INFO |  | -71.4 V |
| D-L2P-03.d | INFO |  | VHigh 38.6 V at the end, +0.0 V/ms over the last 10 % |
| D-L2P-04.c | INFO |  | -67.8 V |
| D-L2P-04.d | INFO |  | VHigh 42.2 V at the end, +0.0 V/ms over the last 10 % |
| D-L2P-05.c | INFO |  | -65.0 V |
| D-L2P-05.d | INFO |  | OV trip at 28.379 ms; VHigh 32.0 V at the end, +0.0 V/ms over the last 10 % |
