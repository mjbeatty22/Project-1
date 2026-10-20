# Locked Changed-Input Record — WMT

**Locked timestamp:** 2026-09-29T17:10:41.4343573-04:00

**Status:** Locked before model edit or run. Do not revise this prediction after
seeing the scenario output.

## Single independent input

| Field | Locked value |
|---|---|
| Input | Capital spending as a percent of revenue (`CAPEX_AS_PERCENT_OF_REVENUE`) |
| Old → new | **3.8% → 3.5%** of revenue in each forecast year |
| Unit | Percentage of annual revenue; a **0.3 percentage-point decrease**, not a 0.3% relative decrease |
| Forecast years | FY2027–FY2031 |
| Other inputs | Unchanged: revenue growth, gross margin, SG&A ÷ gross profit, working-capital days, tax rate, WACC, terminal growth, capital returns, and financing assumptions |

## Prediction before run

| Output | Expected direction | Rough expected size | Why |
|---|---|---:|---|
| FY2031 operating profit (EBIT) | No material change | ~$0 | In this model, capex is not an income-statement expense. |
| FY2031 FCFF | Increase | about **$2.5bn** | A 0.3 percentage-point lower capex rate saves roughly 0.3% × FY2031 revenue; capex reduces FCFF dollar-for-dollar in this model. |
| Value per share | **Unavailable for this test** | N/A | The current DCF subtracts opening net debt but does not bridge the forecast revolver build, and it holds shares constant despite modeled buybacks. Until repaired, its terminal-value-based per-share output is not defensible. |

## Range rationale

FY2026 filing capex was 3.7% of revenue. The 3.5% case is a labeled judgment:
it tests modest capital efficiency while remaining close to recent history. It does
not assert that management has guided to 3.5%.

## Partner check required before run

- [ ] The 3.8% → 3.5% change is correctly read as a **0.3 percentage-point** reduction in capex as a share of revenue.
- [ ] Capital spending is the only independent input changed.
- [ ] FY2031 EBIT and FY2031 **FCFF** will be used as the comparable outputs.
- [ ] No value-per-share conclusion will be reported until the net-debt and share-count bridge is repaired.
