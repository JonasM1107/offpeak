# Tariff calculator

`offpeak/tariffs/` turns a market price into what a business really pays per kWh, and adds up a bill. It implements section 9.1 of `PLAN.md`.

## How a price is built

| Part | Germany (dynamic) | Portugal BTE (indexed) |
|---|---|---|
| Energy | spot + supplier margin | (OMIE + margin) × (1 + loss factor) |
| Grid fee per kWh | flat, by voltage level and utilisation | by time period (ponta, cheias, vazio normal, super vazio) |
| Levies | concession fee, CHP levy, offshore levy, § 19 levy | — |
| Tax | electricity tax 2.05 ct (0.05 ct for manufacturing and farming) | IEC 0.1 ct |
| Demand charge | € per kW of the highest slot (Leistungspreis) | € per kW in peak hours, and per kW contracted |
| Fixed | metering or grid base price | — |
| Feed-in | EEG rate, nothing when the spot price is negative | 90 % of OMIE |

All values are net of VAT, which businesses deduct.

## Using it

```python
from offpeak.tariffs import germany_2026, slot_prices, bill

tariff = germany_2026(voltage="low", load_metered=True, reduced_electricity_tax=False)
priced = slot_prices(prices, tariff)  # prices: ts (UTC), eur_mwh
priced["import_ct"]                    # all-in ct/kWh per slot
b = bill(grid_kw, priced, tariff)      # grid_kw per slot, positive buys
b.lines, b.total, b.ct_per_kwh
```

`demo_site.apply_tariff()` and `demo_site.plan_day(inputs, tariff)` use it, so the site view and its plan compare full bills, including the demand charge.

## Where the numbers come from

| Value | Source |
|---|---|
| Grid fees Köln 2026 | [RheinNetz price sheet 2026](https://www.rheinnetz.de/netzentgelte-strom-ab-dem-01.01.2026.pdfx), sheets 1, 4, 9 |
| KWKG 0.446, offshore 0.941, § 19 1.559 ct/kWh | Transmission system operators, published October 2025 ([netztransparenz.de](https://www.netztransparenz.de/de-de/Umlagen)) |
| Concession fee 0.11 ct/kWh | § 2 KAV, special-contract customers |
| Electricity tax 2.05 / 0.05 ct/kWh | Stromsteuergesetz change in force since 1 Jan 2026 ([BMF](https://www.bundesfinanzministerium.de/Content/DE/Pressemitteilungen/Finanzpolitik/2025/09/2025-09-03-massnahmen-niedrigere-energiepreise.html)) |
| EEG feed-in 7.70 / 6.66 / 5.44 ct/kWh | Bundesnetzagentur, plants from 1 Aug 2026 |
| Portugal TAR 2026, BTE | [ERSE Directive 10/2025](https://www.erse.pt/media/lamnmp31/diretiva-erse-10-2025-tep-se-2026.pdf) |
| Portugal time periods | ERSE weekly cycle, valid until 31 Mar 2027 |

**Assumptions to replace with a real contract:** supplier margin, fixed energy price, Portuguese loss factor and export share.

**Not covered yet:**
- Grid areas other than Köln.
- The reduced § 19 levy above 1 GWh a year.
- Portugal's new time periods from April 2027.
- Live Portuguese prices: the OMIE adapter is next.
