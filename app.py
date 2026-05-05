import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import io
import re

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
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #0a0e1a; color: #c9d1e0; }
.stApp { background-color: #0a0e1a; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #00d4ff; }
.metric-card { background: #111827; border: 1px solid #1e3a5f; border-radius: 8px; padding: 16px 20px; text-align: center; }
.metric-label { font-size: 11px; color: #6b7a99; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 28px; font-weight: 600; color: #00d4ff; font-family: 'IBM Plex Mono', monospace; }
.stButton > button { background: linear-gradient(135deg, #0077ff, #00d4ff); color: #0a0e1a; font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 15px; border: none; border-radius: 6px; padding: 12px 32px; width: 100%; cursor: pointer; transition: opacity 0.2s; }
.stButton > button:hover { opacity: 0.85; }
.stDataFrame { background: #111827; border-radius: 8px; }
.status-box { background: #111827; border-left: 3px solid #00d4ff; padding: 10px 16px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; font-size: 13px; color: #a0aec0; margin: 6px 0; }
</style>
""", unsafe_allow_html=True)

EDGAR_BASE = "https://data.sec.gov"
HEADERS = {"User-Agent": "SEC-EDGAR-Dashboard contact@example.com"}
FOREIGN_FORM_PATTERN = re.compile(r'^(20-F|40-F|10-F|20-F/A|40-F/A|10-F/A|6-K|6-K/A|F-1|F-3|F-4|F-6|F-10|F-1/A|F-3/A)$', re.IGNORECASE)

@st.cache_data(ttl=86400, show_spinner=False)
def get_all_companies():
    urls = [
        "https://www.sec.gov/files/company_tickers_exchange.json",
        "https://www.sec.gov/files/company_tickers.json",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            companies = []
            if "data" in data:
                for row in data["data"]:
                    companies.append({"cik": str(row[0]).zfill(10), "name": row[1], "ticker": row[2] if len(row) > 2 else "", "exchange": row[3] if len(row) > 3 else ""})
            else:
                for _, v in data.items():
                    companies.append({"cik": str(v["cik_str"]).zfill(10), "ticker": v["ticker"], "name": v["title"], "exchange": ""})
            return companies
        except Exception:
            continue
    return []

def get_company_facts(cik):
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
    try:
        units = facts["facts"][taxonomy][concept]["units"]
        unit_key = "USD" if "USD" in units else list(units.keys())[0]
        entries = units[unit_key]
        annual = [e for e in entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
        if not annual:
            return None
        annual.sort(key=lambda x: x["end"], reverse=True)
        return annual[0]["val"], annual[0]["end"]
    except (KeyError, IndexError, TypeError):
        return None

def get_filing_metadata(cik):
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        data = r.json()
        result = {}
        result["filer_category"] = data.get("category", "")
        result["sic_description"] = data.get("sicDescription", "N/A")
        filings = data.get("filings", {}).get("recent", {})
        filing_dates = filings.get("filingDate", [])
        forms = filings.get("form", [])

        ipo_candidates = [d for d, f in zip(filing_dates, forms) if f in ("S-1", "S-11", "S-1/A", "424B4")]
        result["ipo_date"] = min(ipo_candidates) if ipo_candidates else (min([d for d, f in zip(filing_dates, forms) if f in ("10-K", "10-K/A")]) if any(f in ("10-K", "10-K/A") for f in forms) else "N/A")

        exchanges = data.get("exchanges", [])
        result["exchanges"] = ", ".join(exchanges) if exchanges else "N/A"

        # Foreign filer: ANY form matching -F pattern overrides everything
        is_foreign = any(FOREIGN_FORM_PATTERN.match(str(f)) for f in forms)
        result["is_foreign_filer"] = is_foreign

        cat = result["filer_category"].lower()
        result["is_egc"] = "emerging growth" in cat

        # SRC: disclosure category only, NOT a 404(b) exemption proxy
        result["is_src"] = "smaller reporting" in cat

        # SOX 404(b): based STRICTLY on filer status, not SRC
        if is_foreign:
            result["filing_status"] = "Not Applicable (Foreign Filer)"
        elif "large accelerated" in cat:
            result["filing_status"] = "404(b) Required (Large Accelerated Filer)"
        elif "accelerated" in cat and "non-accelerated" not in cat:
            result["filing_status"] = "404(b) Required (Accelerated Filer)"
        elif "non-accelerated" in cat:
            result["filing_status"] = "404(b) Exempt (Non-Accelerated Filer)"
        else:
            result["filing_status"] = "Unknown / No Category Data"

        return result
    except Exception:
        return {}

def format_large_number(n):
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
    cik = company["cik"]
    facts = get_company_facts(cik)
    meta = get_filing_metadata(cik)

    row = {
        "Ticker": company.get("ticker", ""),
        "Company": company["name"],
        "CIK": cik,
        "SOX 404(b) Status": meta.get("filing_status", "N/A"),
        "Filer Category": meta.get("filer_category", "N/A"),
        "Is EGC": "Yes" if meta.get("is_egc") else "No",
        "Is SRC": "Yes" if meta.get("is_src") else "No",
        "Foreign Filer": "Yes" if meta.get("is_foreign_filer") else "No",
        "Exchange": meta.get("exchanges", "N/A"),
        "IPO Date": meta.get("ipo_date", "N/A"),
        "SIC Description": meta.get("sic_description", "N/A"),
        "Revenue (USD)": None,
        "Revenue Period": None,
        "Prior Revenue (USD)": None,
        "YOY Revenue Growth (%)": None,
        "Public Float (USD)": None,
        "Public Float (Shares)": None,
        "Public Float Period": None,
        "Public Float Approx": False,
    }

    if facts:
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
            row["Revenue (USD)"] = rev_val
            row["Revenue Period"] = rev_period
            for tax, concept in revenue_concepts:
                try:
                    units = facts["facts"][tax][concept]["units"]
                    unit_key = "USD" if "USD" in units else list(units.keys())[0]
                    entries = units[unit_key]
                    annual = [e for e in entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
                    annual.sort(key=lambda x: x["end"], reverse=True)
                    if len(annual) >= 2:
                        prior_val = annual[1]["val"]
                        row["Prior Revenue (USD)"] = prior_val
                        if prior_val and prior_val != 0:
                            row["YOY Revenue Growth (%)"] = round(((rev_val - prior_val) / abs(prior_val)) * 100, 2)
                        break
                except Exception:
                    continue

        float_result = get_latest_value(facts, "dei", "EntityPublicFloat")
        if float_result:
            row["Public Float (USD)"] = float_result[0]
            row["Public Float Period"] = float_result[1]
            row["Public Float Approx"] = False
        else:
            row["Public Float Approx"] = True

        try:
            shares_entries = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
            annual_shares = [e for e in shares_entries if e.get("form") in ("10-K", "10-K/A") and "end" in e]
            if annual_shares:
                annual_shares.sort(key=lambda x: x["end"], reverse=True)
                row["Public Float (Shares)"] = annual_shares[0]["val"]
        except Exception:
            pass

    return row

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown("# 📊 SEC EDGAR XBRL Dashboard")
st.markdown("**Pull latest 10-K data for all public companies directly from SEC EDGAR**")
st.markdown("---")

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    pull_mode = st.radio("Pull Mode", options=["Batch Range", "Full Pull (All CIKs)"], index=0)

    if pull_mode == "Batch Range":
        col_s, col_e = st.columns(2)
        with col_s:
            batch_start = st.number_input("Start #", min_value=1, max_value=50000, value=1, step=1)
        with col_e:
            batch_end = st.number_input("End #", min_value=1, max_value=50000, value=500, step=1)
        st.caption(f"Will process {max(0, int(batch_end) - int(batch_start) + 1):,} companies")
    else:
        batch_start = 1
        batch_end = 99999
        st.caption("⚠️ Full pull may take 1-2 hours")

    st.markdown("---")
    append_mode = st.checkbox("Append to existing results", value=True, help="ON: adds batch to existing data. OFF: replaces.")
    st.markdown("---")
    st.markdown("**Data Sources**")
    st.markdown("- 🏛️ SEC EDGAR Company Facts API")
    st.markdown("- 🏛️ SEC EDGAR Submissions API")
    st.markdown("- 📋 XBRL: us-gaap & dei")
    st.markdown("---")
    st.markdown("*Run quarterly for point-in-time snapshots*")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    pull_button = st.button("🔄 Pull Data from SEC EDGAR", use_container_width=True)

with col2:
    if "df" in st.session_state and st.session_state.df is not None:
        df_export = st.session_state.df.copy()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # Sheet 1: Raw numbers — force numeric so Excel recognizes them
            raw = df_export.copy()
            for col in ["Revenue (USD)", "Prior Revenue (USD)", "Public Float (USD)", "Public Float (Shares)", "YOY Revenue Growth (%)"]:
                if col in raw.columns:
                    raw[col] = pd.to_numeric(raw[col], errors="coerce")
            raw.to_excel(writer, index=False, sheet_name="Raw Data")
            # Sheet 2: Display formatted
            disp = df_export.copy()
            disp["Revenue (Display)"] = disp["Revenue (USD)"].apply(format_large_number)
            disp["Prior Revenue (Display)"] = disp["Prior Revenue (USD)"].apply(format_large_number)
            disp["Public Float USD (Display)"] = disp["Public Float (USD)"].apply(format_large_number)
            disp["Public Float Shares (Display)"] = disp["Public Float (Shares)"].apply(
                lambda x: f"{x/1e9:.2f}B" if x is not None and x >= 1e9 else (f"{x/1e6:.2f}M" if x is not None and x >= 1e6 else "N/A")
            )
            disp.to_excel(writer, index=False, sheet_name="Display")
        st.download_button(
            label="📥 Download Excel",
            data=buffer.getvalue(),
            file_name=f"sec_edgar_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        # CSV raw download — pure numbers, no formatting
        csv_raw = df_export.copy()
        for col in ["Revenue (USD)", "Prior Revenue (USD)", "Public Float (USD)", "Public Float (Shares)", "YOY Revenue Growth (%)"]:
            if col in csv_raw.columns:
                csv_raw[col] = pd.to_numeric(csv_raw[col], errors="coerce")
        st.download_button(
            label="📥 Download CSV (Raw Numbers)",
            data=csv_raw.to_csv(index=False).encode("utf-8"),
            file_name=f"sec_edgar_raw_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with col3:
    if "last_updated" in st.session_state:
        st.markdown(f"<div class='status-box'>Last updated:<br>{st.session_state.last_updated}</div>", unsafe_allow_html=True)
    if "df" in st.session_state and st.session_state.df is not None:
        st.markdown(f"<div class='status-box'>Total rows:<br>{len(st.session_state.df):,}</div>", unsafe_allow_html=True)

st.markdown("")

if pull_button:
    with st.spinner("Fetching company list from SEC EDGAR..."):
        try:
            all_companies = get_all_companies()
        except Exception as e:
            st.error(f"Failed to fetch company list: {e}")
            st.stop()

    start_idx = int(batch_start) - 1
    end_idx = int(batch_end)
    companies = all_companies[start_idx:end_idx]
    total = len(companies)

    st.markdown(f"**Processing {total:,} companies (#{batch_start} to #{min(int(batch_end), len(all_companies))})...**")
    progress_bar = st.progress(0)
    status_text = st.empty()

    rows = []
    errors = 0

    for i, company in enumerate(companies):
        status_text.markdown(
            f"<div class='status-box'>⏳ [{i+1}/{total}] <b>{company.get('ticker','N/A')}</b> — {company['name'][:50]}</div>",
            unsafe_allow_html=True
        )
        try:
            row = process_company(company)
            rows.append(row)
        except Exception:
            errors += 1

        progress_bar.progress((i + 1) / total)
        time.sleep(0.1)

    new_df = pd.DataFrame(rows)

    if append_mode and "df" in st.session_state and st.session_state.df is not None:
        combined = pd.concat([st.session_state.df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["CIK"], keep="last")
        st.session_state.df = combined
    else:
        st.session_state.df = new_df

    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_text.markdown(
        f"<div class='status-box'>✅ Done! {len(rows):,} processed. {errors} errors. Total dataset: {len(st.session_state.df):,}</div>",
        unsafe_allow_html=True
    )

if "df" in st.session_state and st.session_state.df is not None:
    df = st.session_state.df

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class='metric-card'><div class='metric-label'>Companies</div><div class='metric-value'>{len(df):,}</div></div>""", unsafe_allow_html=True)
    with col2:
        has_revenue = df["Revenue (USD)"].notna().sum()
        st.markdown(f"""<div class='metric-card'><div class='metric-label'>With Revenue</div><div class='metric-value'>{has_revenue:,}</div></div>""", unsafe_allow_html=True)
    with col3:
        src_count = (df["Is SRC"] == "Yes").sum()
        st.markdown(f"""<div class='metric-card'><div class='metric-label'>SRC Companies</div><div class='metric-value'>{src_count:,}</div></div>""", unsafe_allow_html=True)
    with col4:
        foreign_count = (df["Foreign Filer"] == "Yes").sum()
        st.markdown(f"""<div class='metric-card'><div class='metric-label'>Foreign Filers</div><div class='metric-value'>{foreign_count:,}</div></div>""", unsafe_allow_html=True)

    st.markdown("")

    with st.expander("🔍 Filter Results", expanded=False):
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            search = st.text_input("Search ticker or company", "")
        with col_b:
            sox_filter = st.multiselect("SOX 404(b) Status", options=df["SOX 404(b) Status"].dropna().unique().tolist(), default=[])
        with col_c:
            src_filter = st.selectbox("Is SRC", options=["All", "Yes", "No"], index=0)
        with col_d:
            foreign_filter = st.selectbox("Foreign Filer", options=["All", "Yes", "No"], index=0)

    filtered = df.copy()
    if search:
        filtered = filtered[filtered["Ticker"].str.contains(search, case=False, na=False) | filtered["Company"].str.contains(search, case=False, na=False)]
    if sox_filter:
        filtered = filtered[filtered["SOX 404(b) Status"].isin(sox_filter)]
    if src_filter != "All":
        filtered = filtered[filtered["Is SRC"] == src_filter]
    if foreign_filter != "All":
        filtered = filtered[filtered["Foreign Filer"] == foreign_filter]

    filtered = filtered.copy()
    filtered["Revenue"] = filtered["Revenue (USD)"].apply(format_large_number)
    filtered["Prior Revenue"] = filtered["Prior Revenue (USD)"].apply(format_large_number)
    filtered["Float USD"] = filtered["Public Float (USD)"].apply(format_large_number)
    filtered["Float Shares"] = filtered["Public Float (Shares)"].apply(
        lambda x: f"{x/1e9:.2f}B" if x is not None and x >= 1e9 else (f"{x/1e6:.2f}M" if x is not None and x >= 1e6 else "N/A")
    )

    display_cols = ["Ticker", "Company", "SOX 404(b) Status", "Filer Category", "Is EGC", "Is SRC", "Foreign Filer", "Exchange", "IPO Date", "Revenue", "Prior Revenue", "YOY Revenue Growth (%)", "Float USD", "Float Shares", "Revenue Period", "SIC Description"]

    st.markdown(f"**Showing {len(filtered):,} companies**")
    st.dataframe(filtered[display_cols], use_container_width=True, height=500, hide_index=True)

    if st.button("🗑️ Clear All Data"):
        st.session_state.df = None
        st.rerun()
