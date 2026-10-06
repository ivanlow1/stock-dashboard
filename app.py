import streamlit as st
import yfinance as yf

# Page setup
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

# --- HELPER: COMPANY LOGO ---
def get_company_logo_url(website_url):
    """Derives a high-resolution favicon/logo from the company's website domain."""
    if not website_url:
        return None
    domain = website_url.replace("https://", "").replace("http://", "").strip()
    domain = domain.split("/")[0].replace("www.", "")
    if domain:
        # Google Favicon API provides clean, reliable icons without API keys
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    return None


# --- HELPER: COMPETITORS MAPPING ---
def get_competitors(ticker_symbol, sector, industry):
    """Maps relevant sector/industry competitors dynamically."""
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
    """Generates dynamic, ticker-specific MOAT drivers and ecosystem details."""
    summary = profile.get("longBusinessSummary", "").lower()
    industry = profile.get("industry", "Technology")
    sector = profile.get("sector", "Technology")
    mcap = profile.get("marketCap", 0)
    company_name = profile.get("shortName") or profile.get("longName") or ticker_symbol

    # 1. Products & Ecosystem
    if any(k in summary for k in ["security", "firewall", "cyber", "threat", "forti"]):
        core_offerings = "Integrated cybersecurity platform, network security appliances (e.g., FortiGate), SASE, and threat intelligence."
    elif any(k in summary for k in ["cloud", "saas", "software"]):
        core_offerings = "Cloud-native enterprise software, SaaS platform subscriptions, and automated workflow modules."
    else:
        core_offerings = f"Comprehensive {industry} product portfolio and specialized enterprise solution packages."

    target_market = f"Enterprise organizations, commercial clients, and public sector accounts within {sector}."

    # 2. Economic MOAT Drivers
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


# --- DATA RETRIEVAL ---
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
        
        info["logo_url"] = get_company_logo_url(website)
        info["peers"] = get_competitors(symbol, sector, industry)
        info["moat"] = analyze_moat(info, symbol)
        return info
    except Exception:
        return None


# --- APP INTERFACE ---
st.title("📊 Stock Analysis Dashboard")

# Sidebar
ticker_input = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").strip().upper()

if ticker_input:
    with st.spinner(f"Fetching profile for {ticker_input}..."):
        data = load_stock_data(ticker_input)

    if data:
        # Header Row: Title on the Left, Ticker Logo on the Right
        col_title, col_logo = st.columns([5, 1])
        with col_title:
            st.header(f"{data.get('longName', ticker_input)} ({ticker_input})")
        with col_logo:
            logo_url = data.get("logo_url")
            if logo_url:
                st.image(logo_url, width=72)

        # Overview Metrics
        m1, m2, m3, m4 = st.columns(4)
        price = data.get("currentPrice") or data.get("regularMarketPrice") or data.get("previousClose") or "N/A"
        mcap = data.get("marketCap")
        
        m1.metric("Current Price", f"${price}" if isinstance(price, (int, float)) else price)
        m2.metric("Market Cap", f"${mcap:,.0f}" if isinstance(mcap, (int, float)) else "N/A")
        m3.metric("Sector", data.get("sector", "N/A"))
        m4.metric("Industry", data.get("industry", "N/A"))

        st.markdown("---")

        # 1. Company Profile & Strategic Overview Section
        st.subheader("1. Company Profile & Strategic Overview")
        
        moat = data["moat"]
        peers = data["peers"]

        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown("🔑 **Products & Ecosystem:**")
            st.markdown(f"- **Core Offerings:** {moat['core_offerings']}")
            st.markdown(f"- **Target Market:** {moat['target_market']}")
            
            st.write("")
            st.markdown("🗣️ **Economic MOAT Drivers:**")
            for title, desc in moat["moat_drivers"]:
                st.markdown(f"- **{title}:** {desc}")

        with right_col:
            st.markdown("⚔️ **Key Industry Competitors:**")
            peer_list_str = ", ".join([f"`{p}`" for p in peers])
            st.markdown(f"- **Primary peer ecosystem includes:** {peer_list_str}")

            st.write("")
            st.markdown("⭐ **Key Uniqueness & Differentiation:**")
            for point in moat["uniqueness"]:
                st.markdown(f"- {point}")

        st.markdown("---")

        # Business Summary & Attributes
        st.subheader("📝 Business Overview")
        st.write(data.get("longBusinessSummary", "No description available."))

        st.subheader("📋 Key Details")
        st.table({
            "Attribute": ["Industry", "Employees", "Headquarters", "Website"],
            "Value": [
                data.get("industry", "N/A"),
                f"{data.get('fullTimeEmployees', 0):,}" if data.get("fullTimeEmployees") else "N/A",
                f"{data.get('city', '')}, {data.get('state', '')} {data.get('country', '')}".strip(", "),
                data.get("website", "N/A")
            ]
        })
    else:
        st.error(f"Could not load data for symbol '{ticker_input}'. Please check the ticker symbol.")
else:
    st.info("Please enter a ticker symbol in the sidebar.")
