# Walmart DCF inputs

All dollar figures are USD millions unless stated otherwise. Reported inputs are from the latest available Walmart filings as of September 10, 2026. Forecasts and placeholders are labelled rather than treated as facts.

> Educational use only: this is not financial advice. This model is a classroom exercise for learning DCF and reverse-DCF valuation.

## WMT peer-valuation source table

Comparison date: September 17, 2026. Only `use` or `qualified` candidates appear in `WMT_valuation.py`. A price is left unresolved unless it can be verified from Nasdaq for the matched trading date.

| Company | Role / decision | Price on comparison date | Annual reported diluted EPS | Fiscal year-end | Publication date | Source locator / reason |
|---|---|---:|---:|---|---|---|
| Walmart (WMT) | Target | Unresolved | $2.73 | January 31, 2026 | March 13, 2026 | FY26 Form 10-K, Consolidated Statements of Income and Note 9 Earnings Per Share: https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/wmt-20260131.htm |
| Costco (COST) | Use, qualified | Unresolved | $18.21 | August 31, 2025 | October 8, 2025 | FY25 Form 10-K, Item 1 Business and Consolidated Statements of Income: https://www.sec.gov/Archives/edgar/data/909832/000090983225000101/0000909832-25-000101-index.htm. Qualified because its membership-warehouse model differs from Walmart's multi-format retail model. |
| Kroger (KR) | Exclude | Unresolved | $1.54 | January 31, 2026 | March 31, 2026 | FY25 Form 10-K, Item 1 Business and Net Earnings per Diluted Common Share: https://www.sec.gov/Archives/edgar/data/56873/000110465926037723/0001104659-26-037723-index.htm. Excluded from the base GAAP P/E set because it is grocery-led and its FY25 GAAP EPS included a large fulfillment-network impairment. |

| Input | Value | Unit | As-of date | Exact locator / status |
|---|---:|---|---|---|
| Operating cash flow | 41,565 | USD mm | January 31, 2026 | FY26 Form 10-K, Item 7 MD&A, cash-flow reconciliation: “Net cash provided by operating activities.” |
| Interest paid | 2,793 | USD mm | January 31, 2026 | FY26 Form 10-K, Consolidated Statements of Cash Flows, supplemental cash-flow information: “Interest paid.” |
| Income-tax provision | 7,199 | USD mm | January 31, 2026 | FY26 Form 10-K, Note 8 “Taxes,” total provision for income taxes. |
| Income before income taxes | 29,469 | USD mm | January 31, 2026 | FY26 Form 10-K, Note 8 “Taxes,” total income before income taxes. |
| Effective tax rate | 24.42% | percent | January 31, 2026 | Derived: 7,199 / 29,469. |
| Capital expenditure | (26,642) | USD mm | January 31, 2026 | FY26 Form 10-K, Item 7 MD&A, cash-flow reconciliation: “Payments for property and equipment.” |
| Starting FCFF | 17,033.6963 | USD mm | January 31, 2026 | Derived: 41,565 + 2,793 × (1 − 24.42%) − 26,642. |
| FCFF growth: Years 1–5 | 8%, 7%, 6%, 5%, 4% | percent | Forecast | Analyst estimates. Anchored to FY27 management guidance of 4–5% constant-currency sales growth and 7–8.5% adjusted operating-income growth; not company guidance for FCFF. |
| WACC | 10.00% | percent | Placeholder | Training value retained. Needs a sourced risk-free rate, beta, equity-risk premium, cost of debt, tax rate, and market-value capital weights. |
| Terminal growth | 3.00% | percent | Placeholder | Training value retained. Needs a defensible long-run nominal-economic-growth assumption. |
| Cash and cash equivalents | 11,529 | USD mm | July 31, 2026 | Q2 FY27 Form 10-Q, Condensed Consolidated Balance Sheets, line “Cash and cash equivalents.” |
| Debt and finance-lease obligations | 57,243 | USD mm | July 31, 2026 | Q2 FY27 Form 10-Q balance sheet: short-term borrowings 10,479 + long-term debt due within one year 3,470 + finance lease due within one year 880 + long-term debt 36,462 + long-term finance leases 5,952. |
| Diluted weighted-average shares | 7,989 | million | Six months ended July 31, 2026 | Q2 FY27 Form 10-Q, Note 2 “Net Income Per Common Share,” denominator, diluted. |
| WMT share price | 105.83 | USD/share | September 10, 2026, 8:00 p.m. ET | Public.com after-hours quote; used as the reverse-DCF target. |

## Sources

- FY26 10-K: https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/wmt-20260131.htm
- Q2 FY27 10-Q: https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000154/wmt-20260731.htm
- Q2 FY27 earnings presentation: https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-26-000145/earningspresentationfy27.htm
- Share price: https://public.com/stocks/wmt/after-hours
