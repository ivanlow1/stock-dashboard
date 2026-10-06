import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

# --- HELPER: COMPANY LOGO ---
def get_company_logo_url(ticker_symbol, website_url):
    """Fetches high-resolution company logo using domain favicon with ticker fallback."""
    domain = ""
    if website_url:
        domain = website_url.replace("https://", "").replace("http://", "").strip()
        domain = domain.split("/")[0].replace("www.", "")

    if domain:
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    
    return f"https://eulerpool.com/api/logo/ticker/{ticker_symbol.upper()}"


# --- HELPER: COMPETITORS MAPPING ---
def get_competitors(ticker_symbol, sector, industry):
    """Maps direct industry peers dynamically."""
    PEER_MAP = {
        "cybersecurity": ["PANW", "CRWD", "CHKP", "ZS", "NET"],
        "software - infrastructure": ["MSFT", "ORCL", "SNOW", "DDOG", "PANW"],
        "software - application": ["CRM", "NOW", "ADBE", "ORCL", "SAP"],
        "semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "INTC"],
        "consumer electronics": ["AAPL", "DELL", "HPQ", "SONY"],
        "internet retail": ["AMZN", "BABA", "EBAY", "PDD"],
        "banks": ["JPM", "BAC", "MS", "GS", "C"],
        "automobiles": ["TSLA", "F", "GM", "TM"]
    }
    
    ticker_clean = ticker_symbol.upper()
    search_term = f"{industry} {sector}".lower()
    
    for key, peers in PEER_MAP.items():
        if key in search_term:
            return [p for p in peers if p != ticker_clean]
            
    return ["PANW", "CRWD", "CHKP", "MSFT"]


# --- HELPER: MOAT ANALYZER ---
def analyze_moat(profile, ticker_symbol):
    """Generates ticker-specific MOAT drivers and ecosystem details."""
    summary = profile.get("longBusinessSummary", "").lower()
    industry = profile.get("industry", "Technology")
    sector = profile.get("sector", "Technology")
    mcap = profile.get("marketCap", 0)
    company_name = profile.get("shortName") or profile.get("longName") or ticker_symbol

    if any(k in summary for k in ["security", "firewall", "cyber", "threat", "forti"]):
        core_offerings = "Integrated cybersecurity platform, network security appliances (e.g., FortiGate), SASE, and threat intelligence."
    elif any(k in summary for k in ["cloud", "saas", "software"]):
        core_offerings = "Cloud-native enterprise software, SaaS platform subscriptions, and automated workflow modules."
    else:
        core_offerings = f"Comprehensive {industry} product portfolio and specialized enterprise solution packages."

    target_market = f"Enterprise organizations, commercial clients, and public sector accounts within {sector}."

    moat_drivers = []
    if any(k in summary for k in ["platform", "subscription", "integration", "enterprise", "cloud"]):
        moat_drivers.append((
            "High Switching Costs",
            f"Deep integration of {company_name}'s platform into client IT architecture creates high migration friction."
        ))

    if any(k in summary for k in ["patent", "proprietary", "asic", "technology", "architecture"]):
        moat_drivers.append((
            "Proprietary Hardware / ASICs",
            f"Custom-engineered hardware architectures and proprietary IP provide superior performance over commodity software."
        ))

    if mcap > 20_000_000_000:
        moat_drivers.append((
            "Scale & R&D Velocity",
            f"Global operational scale enables continuous investment into R&D and threat detection infrastructure."
        ))

    if not moat_drivers:
        moat_drivers.append((
            "Specialized Market Position",
            f"Established domain focus and customer relationships within {industry}."
        ))

    uniqueness = [
        f"Consolidated architecture offering a reduced total cost of ownership (TCO) over fragmented point products.",
        f"High brand recognition and strong enterprise customer retention across {sector}."
    ]

    return {
        "core_offerings": core_offerings,
        "target_market": target_market,
        "moat_drivers": moat_drivers,
        "uniqueness": uniqueness
    }


# --- CACHED DATA LOAD ---
@st.cache_data(ttl=3600)
def load_stock_data(symbol):
    try:
        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info
        if not info or "shortName" not in info:
            return None
            
        industry = info.get("industry", "")
        sector = info.get("sector", "")
        website = info.get("website", "")
        
        info["logo_url"] = get_company_logo_url(symbol, website)
        info["peers"] = get_competitors(symbol, sector, industry)
        info["moat"] = analyze_moat(info, symbol)
        
        # Historical price data for Technical Analysis
        hist = ticker_obj.history(period="1y")
        
        return info, hist
    except Exception:
        return None, None


# --- STREAMLIT APP ---
st.title("📊 Interactive Stock Analysis Dashboard")

# Sidebar
ticker_input = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").strip().upper()

if ticker_input:
    with st.spinner(f"Fetching financial analysis for {ticker_input}..."):
        data, hist_df = load_stock_data(ticker_input)

    if data:
        # Header Row with Logo
        company_display_name = data.get('longName', ticker_input)
        logo_url = data.get("logo_url")

        col_title, col_logo = st.columns([5, 1])
        with col_title:
            st.header(f"{company_display_name} ({ticker_input})")
        with col_logo:
            if logo_url:
                st.image(logo_url, width=80)

        # Overview Cards
        m1, m2, m3, m4 = st.columns(4)
        price = data.get("currentPrice") or data.get("regularMarketPrice") or data.get("previousClose") or "N/A"
        mcap = data.get("marketCap")
        
        m1.metric("Current Price", f"${price}" if isinstance(price, (int, float)) else price)
        m2.metric("Market Cap", f"${mcap:,.0f}" if isinstance(mcap, (int, float)) else "N/A")
        m3.metric("Sector", data.get("sector", "N/A"))
        m4.metric("Industry", data.get("industry", "N/A"))

        st.markdown("---")

        # ==========================================
        # SECTION 1: COMPANY PROFILE & STRATEGIC OVERVIEW
        # ==========================================
        st.subheader("1. Company Profile & Strategic Overview")
        moat = data["moat"]
        peers = data["peers"]

        sec1_left, sec1_right = st.columns(2)

        with sec1_left:
            st.markdown("🔑 **Products & Ecosystem:**")
            st.markdown(f"- **Core Offerings:** {moat['core_offerings']}")
            st.markdown(f"- **Target Market:** {moat['target_market']}")
            
            st.write("")
            st.markdown("🗣️ **Economic MOAT Drivers:**")
            for title, desc in moat["moat_drivers"]:
                st.markdown(f"- **{title}:** {desc}")

        with sec1_right:
            st.markdown("⚔️ **Key Industry Competitors:**")
            peer_list_str = ", ".join([f"`{p}`" for p in peers])
            st.markdown(f"- **Primary peer ecosystem includes:** {peer_list_str}")

            st.write("")
            st.markdown("⭐ **Key Uniqueness & Differentiation:**")
            for point in moat["uniqueness"]:
                st.markdown(f"- {point}")

        st.markdown("---")

        # ==========================================
        # SECTION 2: FINANCIAL METRICS & VALUATION
        # ==========================================
        st.subheader("2. Financial Metrics & Valuation")
        
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("P/E Ratio (TTM)", f"{data.get('trailingPE', 0):.2f}" if data.get('trailingPE') else "N/A")
        f2.metric("Forward P/E", f"{data.get('forwardPE', 0):.2f}" if data.get('forwardPE') else "N/A")
        f3.metric("PEG Ratio", f"{data.get('pegRatio', 0):.2f}" if data.get('pegRatio') else "N/A")
        f4.metric("Price-to-Sales (TTM)", f"{data.get('priceToSalesTrailing12Months', 0):.2f}" if data.get('priceToSalesTrailing12Months') else "N/A")

        f5, f6, f7, f8 = st.columns(4)
        f5.metric("Gross Margin", f"{data.get('grossMargins', 0)*100:.2f}%" if data.get('grossMargins') else "N/A")
        f6.metric("Operating Margin", f"{data.get('operatingMargins', 0)*100:.2f}%" if data.get('operatingMargins') else "N/A")
        f7.metric("Profit Margin", f"{data.get('profitMargins', 0)*100:.2f}%" if data.get('profitMargins') else "N/A")
        f8.metric("Return on Equity (ROE)", f"{data.get('returnOnEquity', 0)*100:.2f}%" if data.get('returnOnEquity') else "N/A")

        st.markdown("---")

        # ==========================================
        # SECTION 3: TECHNICAL INDICATORS & PRICE ACTION
        # ==========================================
        st.subheader("3. Technical Indicators & Price Performance")
        
        if hist_df is not None and not hist_df.empty:
            # Calculate Moving Averages & RSI
            hist_df['SMA_50'] = hist_df['Close'].rolling(window=50).mean()
            hist_df['SMA_200'] = hist_df['Close'].rolling(window=200).mean()
            
            delta = hist_df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist_df['RSI'] = 100 - (100 / (1 + rs))

            latest_close = hist_df['Close'].iloc[-1]
            latest_rsi = hist_df['RSI'].iloc[-1]
            sma_50 = hist_df['SMA_50'].iloc[-1]
            sma_200 = hist_df['SMA_200'].iloc[-1]

            t1, t2, t3, t4 = st.columns(4)
            t1.metric("52-Week High", f"${data.get('fiftyTwoWeekHigh', 'N/A')}")
            t2.metric("52-Week Low", f"${data.get('fiftyTwoWeekLow', 'N/A')}")
            t3.metric("RSI (14-Day)", f"{latest_rsi:.1f}" if not np.isnan(latest_rsi) else "N/A")
            t4.metric("50D / 200D SMA", f"${sma_50:.2f} /${sma_200:.2f}" if not np.isnan(sma_50) else "N/A")

            # Stock Chart
            st.line_chart(hist_df[['Close', 'SMA_50', 'SMA_200']])
        else:
            st.info("Historical price data not available for chart generation.")

        st.markdown("---")

        # ==========================================
        # SECTION 4: RISK ANALYSIS & KEY DETAILS
        # ==========================================
        st.subheader("4. Risk Analysis & Company Details")
        
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("⚠️ **Risk Factors:**")
            beta = data.get('beta', 'N/A')
            st.markdown(f"- **Beta (Volatility):** `{beta}`")
            st.markdown("- **Macro Risks:** Supply chain delays, foreign currency exchange headwinds, and IT spending deceleration.")
            st.markdown("- **Competitive Risks:** Aggressive pricing and platform consolidation from major sector peers.")

        with r2:
            st.markdown("📋 **Corporate Info:**")
            st.table({
                "Attribute": ["Full Name", "Headquarters", "Full-Time Employees", "Website"],
                "Value": [
                    data.get("longName", "N/A"),
                    f"{data.get('city', '')}, {data.get('state', '')} {data.get('country', '')}".strip(", "),
                    f"{data.get('fullTimeEmployees', 0):,}" if data.get("fullTimeEmployees") else "N/A",
                    data.get("website", "N/A")
                ]
            })

    else:
        st.error(f"Could not load data for symbol '{ticker_input}'. Please check the ticker symbol.")
else:
    st.info("Please enter a ticker symbol in the sidebar.")
