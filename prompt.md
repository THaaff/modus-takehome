# Take-Home Assignment: VC Audit Tool

**Timeline:** 24–48 hours
**Deliverables:** Working code in a public GitHub repo + short README (max 1 page), including instructions for running.
**Follow-up:** 30-minute walkthrough interview covering design, reasoning, and technical implementation.

---

## Problem Overview

Auditors reviewing venture capital portfolios need to estimate the fair value of private, illiquid portfolio companies. The goal of this exercise is **not to produce a "correct" valuation**, but to design and implement a **structured, auditable workflow** that helps auditors efficiently arrive at a consistent, well-documented fair value estimate.

This task is distinct from valuing publicly traded companies, which have a readily available market price. Private companies lack this price and often have sparse or non-standardized financial data. The challenge is to build a system that can value these private assets using the best available data, which might include:

- Internal company metrics
- Data from the last funding round
- Data from publicly-traded comparable companies

Your solution should demonstrate how you translate a business problem into a sound, maintainable backend system.

---

## Potential Methodologies (for inspiration)

A key part of this exercise is choosing a valuation methodology and building a structured workflow around it. Your system should be able to:

1. Ingest data
2. Apply a chosen model
3. Output the result

We are **not testing your financial modeling expertise**, but rather your ability to translate one of these business-logic workflows into code. You are free to choose your approach.

### 1. Comparable Company Analysis (Comps)

- **Logic:** The system identifies a set of comparable public companies (based on sector, size, etc.).
- **Data:** It would fetch their financial data (e.g., Revenue, EBITDA) and Enterprise Value.
- **Calculation:** It determines a relevant valuation multiple (e.g., Enterprise Value / Revenue).
- **Application:** It then applies this average multiple to the private portfolio company's own revenue.
  - *Example:* `8x EV/Revenue × $10M Revenue = $80M Fair Value`

### 2. Discounted Cash Flow (DCF)

- **Logic:** The system projects a company's future cash flows and discounts them back to their present value.
- **Data:** This approach assumes you are given a set of detailed financial projections for the portfolio company (e.g., 5-year forecasts for revenue, expenses, and capital expenditures).
- **Calculation:** The system would apply a discount rate (e.g., a WACC) to these future cash flows.
- **Application:** The sum of the discounted cash flows would be the estimated fair value.

### 3. Last Round (Market-Adjusted) Valuation

- **Logic:** A common "mark-to-market" approach. It starts with the valuation from the company's most recent funding round and adjusts it based on public market performance.
- **Data:** The inputs would be the company's `last_post_money_valuation`, the `date_of_last_round`, and a data source for a relevant public index (e.g., the Nasdaq Composite).
- **Calculation:** The system calculates the percentage change in the public index from the `date_of_last_round` to the present.
- **Application:** This percentage change is then applied to the `last_post_money_valuation` to produce a new, auditable fair value estimate.

---

## Requirements

### Inputs

- Portfolio company name (e.g., "Basis AI", "Inflo")
- Key data required by your chosen methodology. Examples:
  - **For Comps:** `sector`, `revenue`
  - **For DCF:** `financial_projections` (could be a path to a file or a JSON object)
  - **For Last Round:** `last_post_money_valuation`, `last_round_date`

### Outputs

- **Estimated fair value** (numeric or range)
- **Key inputs and assumptions used**
  - *e.g., "Used 8.2x EV/Revenue multiple", "Used 15% discount rate"*
- **Citations or data sources**
  - *e.g., "Public comp data from Yahoo Finance API [mocked]", "Internal projections dated Q3 2025"*
- **Explanation of how the estimate was derived** (structured or narrative)
  - *e.g., "Valuation based on peer-group median multiple of 8.2x applied to $10M LTM Revenue."*

### Core Expectations

- Backend service that takes an input and returns the valuation output.
- Strong code quality, organization, and documentation.
- Clear workflow from **data ingestion → valuation logic → output**.
- **Traceable, auditable process:** it should be easy to understand how the result was produced.

### Preferred

- Structured approach to problem solving (clear steps, modular design).
- If external data is used (e.g., public APIs, datasets), handle errors gracefully — **mocking is perfectly fine**.
- Thoughtful UX — CLI tool is fine, or simple web frontend. Whatever you need to communicate how auditors would use this in practice. Wireframes / sketches also acceptable.

### Not Required

- Extensive deployment setup
- Highly accurate financial modeling (**the logic is more important than the numbers**)

---

## Deliverables

1. **Source code** in a public GitHub repository.
2. **README** including:
   - Overview of the problem and your chosen approach / methodology.
   - Key design decisions and tradeoffs.
   - Setup instructions and usage example.
   - Notes on potential improvements if you had more time.
   - *(Optional)* Screenshot or diagram of UX / workflow.
3. **Set up time** with us to review live.
