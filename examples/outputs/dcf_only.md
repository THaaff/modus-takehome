# VC Audit Report — Meridian Industrial Holdings

**As-of date:** 2026-03-31
**Generated:** 2026-05-07T04:52:54.714161+00:00

## Headline

_Money values are in $M (millions of US dollars). Confidence and weights are in [0, 1]. Dispersion is a unitless ratio._

- **Point estimate:** $259.74M
- **Range:** $214.33M – $305.15M
- **Dispersion:** 0.3497 (within tolerance)

## Method breakdown

| Method | Point ($M) | Low ($M) | High ($M) | Confidence | Weight | Overridden | Outlier |
|---|---|---|---|---|---|---|---|
| dcf | $259.74M | $214.33M | $305.15M | 100.00% | 100.00% | no |  |

### dcf

_3x3 sensitivity grid (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) over 5 projection years; range = min/max across 9 valid cells, point = midpoint._

**Assumptions:**
- **Discount rate:** 11.00% — Auditor-supplied WACC proxy.
- **Terminal growth rate:** 2.50% — Long-run nominal growth; must be < discount rate (Gordon stability).
- **Tax rate:** 21.00% — default; auditor can override
- **FCF formula:** EBITDA × (1 − tax) − capex − ΔNWC — No D&A tax shield modeled — slightly conservative.
- **Sensitivity grid:** 3x3 (discount_rate +/- 1pp x terminal_growth +/- 0.5pp) — Range = min/max across 9 valid cells; point = midpoint. 0 cell(s) skipped (Gordon stability: g >= r).
- **Confidence formula:** min(1, 5/5) × completeness_ratio — Saturates at 5 projection years; completeness counts non-zero revenue/ebitda/capex across years (ΔNWC excluded — default is 0).

**Citations:**
- ValuationRequest:projections — DCF on 5 projection years; discount=0.11, terminal_growth=0.025, tax=0.21 (retrieved 2026-05-07T04:52:54.714026+00:00)

## Request (echoed)

```json
{
  "company": {
    "name": "Meridian Industrial Holdings",
    "sector": null
  },
  "revenue": null,
  "ebitda": null,
  "last_post_money_valuation": null,
  "last_round_date": null,
  "reference_index": "NASDAQ",
  "projections": [
    {
      "year": 1,
      "revenue": "150.0",
      "ebitda": "28.0",
      "capex": "8.0",
      "change_in_nwc": "2.0"
    },
    {
      "year": 2,
      "revenue": "168.0",
      "ebitda": "33.0",
      "capex": "9.0",
      "change_in_nwc": "2.5"
    },
    {
      "year": 3,
      "revenue": "186.0",
      "ebitda": "38.0",
      "capex": "9.5",
      "change_in_nwc": "2.5"
    },
    {
      "year": 4,
      "revenue": "204.0",
      "ebitda": "44.0",
      "capex": "10.0",
      "change_in_nwc": "3.0"
    },
    {
      "year": 5,
      "revenue": "222.0",
      "ebitda": "50.0",
      "capex": "10.5",
      "change_in_nwc": "3.0"
    }
  ],
  "discount_rate": "0.11",
  "terminal_growth_rate": "0.025",
  "tax_rate": "0.21",
  "method_weights": null,
  "as_of_date": "2026-03-31"
}
```

