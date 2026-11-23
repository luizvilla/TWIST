# TWIST VHigh overvoltage study (simulation, level D)

Core2-style campaign for the averaged model of one TWIST power leg. Investigation record: [`../README.md`](../README.md).

Requires Python 3 with numpy. uPlot (MIT, `common/vendor/uPlot-LICENSE`) is inlined into the pages so they work offline.

| File | Role |
|---|---|
| `model.py` | Averaged leg model (Q201/Q202, L201, VHigh caps, lab supply + cable, Feeder self-supply, OV trip, duty slew, current limit, active clamp) |
| `catalogue.json` | Every case defined once: tab, purpose, parameters; findings F-1..F-3; field failures mapped to cases |
| `run_campaign.py` | Runs the implemented D cases -> `../results/<date>_<time>_sim/` (override with `TWIST_SIM_OUT`) (sim.log `@@` lines, record.md, summary.json, traces/*.npz, report.html) and regenerates the control center |
| `control_center.py` | `../results/control-center.html`: overview, peak-stress chart, field failures, findings, one tab per stage, runs |
| `common/` | `interactive_plot.py` + uPlot copied from Core2 `tests/common` (offline figures) |

Run: `python3 -I run_campaign.py [ID ...]` then open `../results/control-center.html`.
Add a case: add it to `catalogue.json` (params override `model.BASE`), rerun.

