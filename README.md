# SEC EDGAR XBRL Dashboard

A Streamlit web app that pulls financial data for ~5,000 public companies directly from SEC EDGAR.

## Features
- Filing status (404a / 404b)
- Filer category (Large Accelerated, Accelerated, Smaller Reporting)
- Revenue (latest 10-K)
- YOY Revenue Growth
- IPO Date
- Public Float (from EntityPublicFloat XBRL tag; flagged if approximate)
- One-click Excel export
- Filterable table

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud (free)

1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io
3. Connect your GitHub repo
4. Set main file as `app.py`
5. Deploy — you get a public URL to share with the client

## Data Sources
- SEC EDGAR Company Tickers: https://www.sec.gov/files/company_tickers.json
- SEC EDGAR Company Facts API: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
- SEC EDGAR Submissions API: https://data.sec.gov/submissions/CIK{cik}.json

## Notes
- Public Float: pulled from `dei:EntityPublicFloat` XBRL tag (exact). If not available, flagged as approximate.
- Rate limiting: 0.1s delay between requests to respect SEC EDGAR guidelines.
- Full 5,000 company run takes ~15-20 minutes. Recommended to use quarterly.
