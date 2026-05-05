import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import io

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SEC EDGAR XBRL Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0a0e1a;
    color: #c9d1e0;
}
.stApp { background-color: #0a0e1a; }

h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #00d4ff; }

.metric-card {
    background: #111827;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 16px 20px;
    text-align: center;
}
.metric-label { font-size: 11px; color: #6b7a99; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 28px; font-weight: 600; color: #00d4ff; font-family: 'IBM Plex Mono', monospace; }

.stButton > button {
    background: linear-gradient(135deg, #0077ff, #00d4ff);
    color: #0a0e1a;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    font-size: 15px;
    border: none;
    border-radius: 6px;
    padding: 12px 32px;
    width: 100%;
    cursor: pointer;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }

.stDataFrame { background: #111827; border-radius: 8px; }

.status-box {
    background: #111827;
    border-left: 3px solid #00d4ff;
    padding: 10px 16px;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    color: #a0aec0;
    margin: 6px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
EDGAR_BASE = "https://data.sec.gov"
HEADERS = {"User-Agent": "SEC-EDGAR-Dashboard contact@example.com"}  # SEC requires a user-agent


# ── Helper functions ──────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def get_all_companies():
    """Fetch the full list of companies from SEC EDGAR."""
    url = f"{EDGAR_BASE}/submissions/CIK0000000001.json"
    # Use the company_tickers endpoint instead
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    companies = []
    for _, v in data.items():
        companies.append({
            "cik": str(v["cik_str"]).zfill(10),
            "ticker": v["ticker"],
            "name": v["title"],
        })
    return companies


def get_company_facts(cik: str):
    """Fetch all XBRL facts for a given CIK."""
    url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_latest_value(facts, taxonomy, concept):
    """Extract the most recent annual value for a given XBRL concept."""
    try:
        units = facts["facts"][taxonomy][concept]["units"]
        # Prefer USD units, fallback to shares
        unit_key = "USD" if "USD" in units else list(units.keys())[0]
        entries = units[unit_key]
        # Filter 10-K filings only
        annual = [e for e in entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
        if not annual:
            return None
        # Sort by end date and return most recent
        annual.sort(key=lambda x: x["end"], reverse=True)
        return annual[0]["val"], annual[0]["end"]
    except (KeyError, IndexError, TypeError):
        return None


def get_filing_metadata(cik: str):
    """Get filing status (404a/404b), filer category, and IPO date from submissions."""
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        data = r.json()

        result = {}

        # Filing category (accelerated filer status)
        result["filer_category"] = data.get("category", "N/A")

        # SIC code and description
        result["sic"] = data.get("sic", "N/A")
        result["sic_description"] = data.get("sicDescription", "N/A")
        result["state_of_incorporation"] = data.get("stateOfIncorporation", "N/A")

        # IPO date: earliest filing date
        filings = data.get("filings", {}).get("recent", {})
        filing_dates = filings.get("filingDate", [])
        forms = filings.get("form", [])

        # Find oldest 10-K or S-1 as proxy for IPO date
        ipo_candidates = []
        for date, form in zip(filing_dates, forms):
            if form in ("S-1", "S-11", "S-1/A", "424B4", "IPO"):
                ipo_candidates.append(date)

        if ipo_candidates:
            result["ipo_date"] = min(ipo_candidates)
        else:
            # Fallback: earliest 10-K date
            ten_k_dates = [d for d, f in zip(filing_dates, forms) if f in ("10-K", "10-K/A")]
            result["ipo_date"] = min(ten_k_dates) if ten_k_dates else "N/A"

        exchanges = data.get("exchanges", [])
        result["exchanges"] = ", ".join(exchanges) if exchanges else "N/A"

        # 404a/404b: derived from filer category (XBRL dei:EntityFilerCategory)
        # 404b exempts non-accelerated filers and smaller reporting companies
        # 404a applies to accelerated and large accelerated filers
        cat = result["filer_category"].lower()
        if "non-accelerated" in cat:
            result["filing_status"] = "404b Exempt (Non-Accelerated Filer)"
        elif "smaller reporting" in cat:
            result["filing_status"] = "404b Exempt (Smaller Reporting Company)"
        elif "large accelerated" in cat:
            result["filing_status"] = "404a (Large Accelerated Filer)"
        elif "accelerated" in cat:
            result["filing_status"] = "404a (Accelerated Filer)"
        elif "emerging growth" in cat:
            result["filing_status"] = "404b Exempt (Emerging Growth Company)"
        else:
            result["filing_status"] = "N/A"

        return result

    except Exception:
        return {}


def format_large_number(n):
    """Format large numbers to readable format (e.g. 1.2B, 500M)."""
    if n is None:
        return "N/A"
    try:
        n = float(n)
        if abs(n) >= 1e12:
            return f"${n/1e12:.2f}T"
        elif abs(n) >= 1e9:
            return f"${n/1e9:.2f}B"
        elif abs(n) >= 1e6:
            return f"${n/1e6:.2f}M"
        else:
            return f"${n:,.0f}"
    except Exception:
        return "N/A"


def process_company(company):
    """Process a single company and return its row of data."""
    cik = company["cik"]
    ticker = company["ticker"]
    name = company["name"]

    facts = get_company_facts(cik)
    meta = get_filing_metadata(cik)

    row = {
        "Ticker": ticker,
        "Company": name,
        "CIK": cik,
        "Filing Status (404a/404b)": meta.get("filing_status", "N/A"),
        "Filer Category": meta.get("filer_category", "N/A"),
        "Exchange": meta.get("exchanges", "N/A"),
        "IPO Date": meta.get("ipo_date", "N/A"),
        "SIC Description": meta.get("sic_description", "N/A"),
        "Revenue (Latest)": None,
        "Revenue Period": None,
        "Revenue Prior Year": None,
        "YOY Revenue Growth (%)": None,
        "Public Float (USD)": None,
        "Public Float (Shares)": None,
        "Public Float Period": None,
        "Public Float (Approx)": None,
    }

    if facts:
        # ── Revenue ──────────────────────────────────────────────────────────
        revenue_concepts = [
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "Revenues"),
            ("us-gaap", "SalesRevenueNet"),
            ("us-gaap", "SalesRevenueGoodsNet"),
            ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
        ]
        rev_result = None
        for tax, concept in revenue_concepts:
            rev_result = get_latest_value(facts, tax, concept)
            if rev_result:
                break

        if rev_result:
            rev_val, rev_period = rev_result
            row["Revenue (Latest)"] = rev_val
            row["Revenue Period"] = rev_period

            try:
                for tax, concept in revenue_concepts:
                    try:
                        units = facts["facts"][tax][concept]["units"]
                        unit_key = "USD" if "USD" in units else list(units.keys())[0]
                        entries = units[unit_key]
                        annual = [e for e in entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
                        annual.sort(key=lambda x: x["end"], reverse=True)
                        if len(annual) >= 2:
                            prior_val = annual[1]["val"]
                            row["Revenue Prior Year"] = prior_val
                            if prior_val and prior_val != 0:
                                growth = ((rev_val - prior_val) / abs(prior_val)) * 100
                                row["YOY Revenue Growth (%)"] = round(growth, 2)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        # ── Public Float ─────────────────────────────────────────────────────
        # Primary: EntityPublicFloat in USD (as reported in 10-K cover page)
        float_result = get_latest_value(facts, "dei", "EntityPublicFloat")
        if float_result:
            row["Public Float (USD)"] = float_result[0]
            row["Public Float Period"] = float_result[1]
            row["Public Float (Approx)"] = False

        # Always try to get shares float separately
        try:
            shares_entries = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
            annual_shares = [e for e in shares_entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
            if annual_shares:
                annual_shares.sort(key=lambda x: x["end"], reverse=True)
                row["Public Float (Shares)"] = annual_shares[0]["val"]
        except Exception:
            pass

        if not float_result:
            row["Public Float (Approx)"] = True

    return row


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown("# 📊 SEC EDGAR XBRL Dashboard")
st.markdown("**Pull latest 10-K data for all public companies directly from SEC EDGAR**")
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    max_companies = st.slider(
        "Max companies to pull",
        min_value=10,
        max_value=5000,
        value=100,
        step=10,
        help="Start with 100 to test, set to 5000 for full run (takes ~15-20 min)"
    )
    filter_exchange = st.multiselect(
        "Filter by Exchange",
        options=["NYSE", "NASDAQ", "OTC", "All"],
        default=["All"]
    )
    st.markdown("---")
    st.markdown("**Data Sources**")
    st.markdown("- 🏛️ SEC EDGAR Company Facts API")
    st.markdown("- 🏛️ SEC EDGAR Submissions API")
    st.markdown("- 📋 XBRL Taxonomy: us-gaap & dei")
    st.markdown("---")
    st.markdown("*Run quarterly for point-in-time snapshots*")

# Main content
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    pull_button = st.button("🔄 Pull Latest Data from SEC EDGAR", use_container_width=True)

with col2:
    if "df" in st.session_state and st.session_state.df is not None:
        df_export = st.session_state.df.copy()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="SEC Data")
        st.download_button(
            label="📥 Download Excel",
            data=buffer.getvalue(),
            file_name=f"sec_edgar_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with col3:
    if "last_updated" in st.session_state:
        st.markdown(f"<div class='status-box'>Last updated:<br>{st.session_state.last_updated}</div>", unsafe_allow_html=True)

st.markdown("")

# ── Pull data ─────────────────────────────────────────────────────────────────
if pull_button:
    st.session_state.df = None

    with st.spinner("Fetching company list from SEC EDGAR..."):
        try:
            companies = get_all_companies()
        except Exception as e:
            st.error(f"Failed to fetch company list: {e}")
            st.stop()

    companies = companies[:max_companies]
    total = len(companies)

    st.markdown(f"**Processing {total} companies...**")
    progress_bar = st.progress(0)
    status_text = st.empty()
    metrics_placeholder = st.empty()

    rows = []
    errors = 0

    for i, company in enumerate(companies):
        status_text.markdown(
            f"<div class='status-box'>⏳ [{i+1}/{total}] Processing: <b>{company['ticker']}</b> — {company['name'][:50]}</div>",
            unsafe_allow_html=True
        )
        try:
            row = process_company(company)
            rows.append(row)
        except Exception:
            errors += 1

        progress_bar.progress((i + 1) / total)

        # SEC rate limit: be polite
        time.sleep(0.1)

    # Build DataFrame
    df = pd.DataFrame(rows)

    # Format display columns
    df["Revenue (Display)"] = df["Revenue (Latest)"].apply(format_large_number)
    df["Prior Revenue (Display)"] = df["Revenue Prior Year"].apply(format_large_number)
    df["Public Float USD (Display)"] = df.apply(
        lambda r: (format_large_number(r["Public Float (USD)"]) + (" ⚠️ approx" if r.get("Public Float (Approx)") else ""))
        if r["Public Float (USD)"] is not None else "N/A",
        axis=1
    )
    df["Public Float Shares (Display)"] = df["Public Float (Shares)"].apply(
        lambda x: f"{x/1e9:.2f}B shares" if x is not None and x >= 1e9
        else (f"{x/1e6:.2f}M shares" if x is not None and x >= 1e6 else "N/A")
    )

    st.session_state.df = df
    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_text.markdown(
        f"<div class='status-box'>✅ Done! {len(rows)} companies processed. {errors} errors.</div>",
        unsafe_allow_html=True
    )

# ── Display results ───────────────────────────────────────────────────────────
if "df" in st.session_state and st.session_state.df is not None:
    df = st.session_state.df

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>Companies</div>
            <div class='metric-value'>{len(df):,}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        has_revenue = df["Revenue (Latest)"].notna().sum()
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>With Revenue Data</div>
            <div class='metric-value'>{has_revenue:,}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        has_float = df["Public Float (USD)"].notna().sum()
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>With Public Float</div>
            <div class='metric-value'>{has_float:,}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        has_growth = df["YOY Revenue Growth (%)"].notna().sum()
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>With YOY Growth</div>
            <div class='metric-value'>{has_growth:,}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # Filters
    with st.expander("🔍 Filter Results", expanded=False):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            search = st.text_input("Search by ticker or company name", "")
        with col_b:
            filer_filter = st.multiselect(
                "Filer Category",
                options=df["Filer Category"].dropna().unique().tolist(),
                default=[]
            )
        with col_c:
            growth_min, growth_max = st.slider(
                "YOY Revenue Growth (%)",
                min_value=-200.0,
                max_value=500.0,
                value=(-200.0, 500.0),
                step=1.0
            )

    # Apply filters
    filtered = df.copy()
    if search:
        filtered = filtered[
            filtered["Ticker"].str.contains(search, case=False, na=False) |
            filtered["Company"].str.contains(search, case=False, na=False)
        ]
    if filer_filter:
        filtered = filtered[filtered["Filer Category"].isin(filer_filter)]

    growth_mask = (
        filtered["YOY Revenue Growth (%)"].isna() |
        (
            (filtered["YOY Revenue Growth (%)"] >= growth_min) &
            (filtered["YOY Revenue Growth (%)"] <= growth_max)
        )
    )
    filtered = filtered[growth_mask]

    # Display columns
    display_cols = [
        "Ticker", "Company", "Filing Status (404a/404b)", "Filer Category",
        "Exchange", "IPO Date", "Revenue (Display)", "Prior Revenue (Display)",
        "YOY Revenue Growth (%)", "Public Float USD (Display)", "Public Float Shares (Display)", "Revenue Period", "SIC Description"
    ]

    st.markdown(f"**Showing {len(filtered):,} companies**")
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    # Note about approximations
    approx_count = df["Public Float (Approx)"].sum() if "Public Float (Approx)" in df.columns else 0
    if approx_count > 0:
        st.caption(f"⚠️ {int(approx_count)} companies have approximate public float (EntityPublicFloat not available in EDGAR XBRL). These are flagged in the table.")
