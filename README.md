# SEC EDGAR Dashboard — XBRL Financial Data Explorer

![Status](https://img.shields.io/badge/Status-Live-brightgreen)
![Deploy](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel)
![Language](https://img.shields.io/badge/Built%20with-Python-blue?logo=python)
![Data](https://img.shields.io/badge/Data-SEC%20EDGAR%20API-red)
![Companies](https://img.shields.io/badge/Coverage-5000%2B%20Companies-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

> Pulls and analyzes **XBRL financial data** from the SEC EDGAR API for 5,000+ public US companies. Extracts structured financial statements — income, balance sheet, cash flows — and outputs clean, analysis-ready datasets. Built for investors, researchers, and fintech developers who need reliable fundamental data at scale.

---

## 🧠 What is SEC EDGAR XBRL?

The SEC (U.S. Securities and Exchange Commission) requires all public companies to file financial statements in **XBRL format** (eXtensible Business Reporting Language) — a structured, machine-readable standard. The EDGAR API provides free, programmatic access to this data.

This dashboard pulls that raw XBRL data, normalizes it across companies and filing periods, and delivers clean financial metrics ready for analysis.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **XBRL data extraction** | Pulls structured financials from SEC EDGAR API |
| **5,000+ companies** | Full coverage of US public equities |
| **Multi-statement** | Income statement, balance sheet, cash flows |
| **Key metrics** | Revenue, net income, EPS, assets, liabilities, FCF |
| **Clean CSV output** | Analysis-ready datasets, no manual cleaning |
| **Batch processing** | Handles large company lists efficiently |
| **Historical data** | Multi-period filings for trend analysis |

---

## 🏗️ Architecture

```
SEC EDGAR XBRL API (free, no auth required)
        │
        ▼
  Python Data Pipeline
  ┌──────────────────────────────────┐
  │  Fetch company facts (CIK)       │
  │  Parse XBRL taxonomy             │
  │  Extract target financial tags   │
  │  Normalize across periods        │
  │  Clean and validate data         │
  └──────────────────────────────────┘
        │
        ▼
  Structured Output
  - Clean CSV / DataFrame
  - Per-company financial summary
  - Multi-company comparison table
```

---

## 📊 Data Points Extracted

**Income Statement:**
Revenue · Gross Profit · Operating Income · Net Income · EPS (Basic & Diluted)

**Balance Sheet:**
Total Assets · Total Liabilities · Shareholders Equity · Cash & Equivalents · Long-term Debt

**Cash Flow Statement:**
Operating Cash Flow · Capital Expenditures · Free Cash Flow · Financing Activities

---

## 🚀 Quick Start

**Requirements:**
- Python 3.10+
- No API key required — SEC EDGAR is free and public

```bash
git clone https://github.com/cris-devtrading/sec-edgar-dashboard
cd sec-edgar-dashboard
pip install -r requirements.txt
python main.py
```

**Usage:**
1. Set your target tickers or CIK numbers in the config
2. Run the pipeline — data is fetched directly from EDGAR
3. Review the output CSV with clean financials per company
4. Use the dashboard to visualize key metrics

---

## 🛠️ Tech Stack

- **Python 3.10+** — core pipeline
- **requests / httpx** — SEC EDGAR API calls
- **pandas** — data normalization and processing
- **SEC EDGAR XBRL API** — `data.sec.gov/api/xbrl/`

---

## 💡 Use Cases

- **Fundamental analysts** screening 5,000+ companies for financial health
- **Quant developers** building factor models with clean SEC data
- **Fintech startups** needing a free alternative to Bloomberg/FactSet for US financials
- **Researchers** studying financial reporting patterns across sectors

---

## 👤 About the Author

Built by **Cristian Chaves** — Algorithmic Trading & Fintech Developer.

Specializing in automated trading systems, broker API integrations, options analytics, and real-time financial dashboards for retail traders, prop firms, and fintech startups.

🔗 [AlgoTrader Pro — IBKR Automated Bot](https://github.com/cris-devtrading/algotrader-pro)  
🔗 [OptionsGuru — Live Options Analyzer](https://option-guru.vercel.app)  
🔗 [CCL Radar v2 — Argentine ADR/CEDEAR Monitor](https://ccl-radar.vercel.app)  
📧 Open for freelance projects — [Upwork](https://www.upwork.com/freelancers/cristianchaves) | [Fiverr](https://www.fiverr.com/cristianchaves)
📧 Contacto: quantedgelatam@gmail.com
🌐 GitHub: github.com/cris-devtrading

---

## 📄 License

MIT — free to use, modify, and distribute with attribution.
