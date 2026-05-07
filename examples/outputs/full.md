# VC Audit Report — Atlas Cloud Inc.

**As-of date:** 2026-03-31
**Generated:** 2026-05-07T21:30:21.409097+00:00
**Sector:** SaaS

## Headline

_Money values are in $M (millions of US dollars). Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._

- **Valuation point estimate:** $2,438.43M
- **Valuation range:** $764.68M – $6,882.13M
- **Dispersion:** 2.5088 (FLAG)
- **Outlier methods:** dcf

## Method breakdown

| Method | Point ($M) | Low ($M) | High ($M) | Confidence | Weight | Overridden | Outlier |
|---|---|---|---|---|---|---|---|
| comps | $5,483.17M | $4,170.55M | $6,803.47M | 50.00% | 33.33% | no |  |
| last_round | $5,984.46M | $5,086.79M | $6,882.13M | 0.00% | 0.00% | no |  |
| dcf | $916.07M | $764.68M | $1,067.46M | 100.00% | 66.67% | no | yes |

### comps

**Assumptions:**
- **Multiples used:** EV/Revenue and EV/EBITDA — EV/Revenue applied whenever target revenue and >=1 peer revenue are present; EV/EBITDA additionally applied when target EBITDA and >=2 peers' EBITDA are positive.
- **EV/Revenue median multiple:** 13.39x — Median across sector peers; 25/75 percentile drives low/high.
- **EV/EBITDA median multiple:** 56.94x — Median across sector peers with positive EBITDA.
- **Peer count:** 4 — Number of sector-matched peers found in the comps universe; drives confidence via min(1, n/8).

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **CompsProvider:** mock_universe_v1 — Peer set: CRM, DDOG, NOW, WDAY (sector=SaaS, n=4) (retrieved 2026-05-07T21:30:21.408864+00:00)

### last_round

**Assumptions:**
- **Reference index:** NASDAQ — Used as a public-market proxy for the period return between last round and as-of date.
- **Range factor:** +/-15% — Basis-risk haircut/expansion to reflect that the chosen index is an imperfect proxy for the company's specific industry beta.
- **Index lookup strategy:** nearest-prior date — Returns the closing level of the most recent entry on or before the requested date. Defensible heuristic in the absence of daily granularity; emit as a known approximation rather than interpolating.
- **Age decay:** 914 days; confidence = max(0, 1 - age/730) — Last-round signal degrades as the round becomes stale; zero confidence at 2 years.

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **MarketIndexProvider:** mock_nasdaq_v1 — NASDAQ 13219.32 on 2023-09-29 -> 17580.12 on 2026-03-31 (retrieved 2026-05-07T21:30:21.409010+00:00)

### dcf

_3x3 sensitivity grid (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) over 5 projection years; range = min/max across 9 valid cells, point = midpoint._

**Assumptions:**
- **Discount rate:** 12.00% — Auditor-supplied WACC proxy.
- **Terminal growth rate:** 3.00% — Long-run nominal growth; must be < discount rate (Gordon stability).
- **Tax rate:** 21.00% — default; auditor can override
- **FCF formula:** EBITDA × (1 − tax) − capex − ΔNWC — No D&A tax shield modeled — slightly conservative.
- **Sensitivity grid:** 3x3 (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) — Range = min/max across 9 valid cells; point = midpoint. 0 cell(s) skipped (Gordon stability: g >= r).
- **Confidence formula:** min(1, 5/5) × completeness_ratio — Saturates at 5 projection years; completeness counts non-zero revenue/ebitda/capex across years (ΔNWC excluded — default is 0).

**Citations:**
_Upstream data sources this method drew from. Format: `Source: identifier — description (retrieved timestamp)`._
- **ValuationRequest:** projections — DCF on 5 projection years; discount=0.12, terminal_growth=0.03, tax=0.21 (retrieved 2026-05-07T21:30:21.409075+00:00)

## Request (echoed)

```json
{
  "company": {
    "name": "Atlas Cloud Inc.",
    "sector": "SaaS"
  },
  "revenue": "500.0",
  "ebitda": "75.0",
  "last_post_money_valuation": "4500.0",
  "last_round_date": "2023-09-29",
  "reference_index": "NASDAQ",
  "projections": [
    {
      "year": 1,
      "revenue": "600.0",
      "ebitda": "100.0",
      "capex": "30.0",
      "change_in_nwc": "10.0"
    },
    {
      "year": 2,
      "revenue": "720.0",
      "ebitda": "130.0",
      "capex": "35.0",
      "change_in_nwc": "12.0"
    },
    {
      "year": 3,
      "revenue": "850.0",
      "ebitda": "160.0",
      "capex": "40.0",
      "change_in_nwc": "14.0"
    },
    {
      "year": 4,
      "revenue": "970.0",
      "ebitda": "185.0",
      "capex": "45.0",
      "change_in_nwc": "15.0"
    },
    {
      "year": 5,
      "revenue": "1080.0",
      "ebitda": "210.0",
      "capex": "50.0",
      "change_in_nwc": "16.0"
    }
  ],
  "discount_rate": "0.12",
  "terminal_growth_rate": "0.03",
  "tax_rate": "0.21",
  "method_weights": null,
  "as_of_date": "2026-03-31"
}
```

