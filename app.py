import streamlit as st
import yfinance as yf
import requests

# Page configuration
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

# --- HELPER: COMPANY LOGO ---
def get_company_logo(website_url):
    """Generates a reliable favicon URL from the company domain."""
    if not website_url:
        return None
    domain = website_url.replace("https://", "").replace("http://", "").strip()
    domain = domain.split("/")[0].replace("www.", "")
    if domain:
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    return None


# --- HELPER: COMPETITORS MAP ---
def get_competitors(ticker_symbol, sector, industry):
    """Maps direct industry peers dynamically without triggering 403 web scrapers."""
    # Sector & Industry mapping table
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
    
    # Try finding sector key match
    for key, peers in PEER_MAP.items():
        if key in search_term:
            return [p for p in peers if p != ticker_clean]
            
    # Fallback to general tech peers if no match found
    return ["PANW", "CRWD", "CHKP", "MSFT"]


# --- HELPER: MOAT ANALYZER ---
def analyze_moat(profile, ticker_symbol):
    """Generates dynamic MOAT drivers and ecosystem details based on profile info."""
    summary = profile.get("longBusinessSummary", "").lower()
    industry = profile.get("industry", "Technology")
    sector = profile.get("sector", "Technology")
    mcap = profile.get("marketCap", 0)
    company_name = profile.get("shortName") or profile.get("longName") or ticker_symbol

    # Products & Ecosystem
    if any(k in summary for k in ["security", "firewall", "cyber", "threat"]):
        core_offerings = "Integrated cybersecurity platform, enterprise network security appliances, and AI-driven threat prevention."
    elif any(k in summary for k in ["cloud", "saas", "software"]):
        core_offerings = "Cloud-native enterprise software, SaaS platform subscriptions, and automated workflow modules."
    else:
        core_offerings = f"Comprehensive {industry} product portfolio and specialized enterprise solution packages."

    target_market = f"Enterprise organizations, commercial clients, and public sector accounts across the {sector} landscape."

    # Economic MOAT Drivers
    moat_drivers = []
    if any(k in summary for k in ["platform", "subscription", "integration", "enterprise", "cloud"]):
        moat_drivers.append((
            "High Switching Costs",
            f"Deep integration of {company_name}'s architecture into customer IT workflows makes vendor migration risky and expensive."
        ))

    if any(k in summary for k in ["patent", "proprietary", "asic", "technology", "algorithm"]):
        moat_drivers.append((
            "Proprietary Technology",
            f"Custom-engineered intellectual property and proprietary technology provide superior performance efficiency over competitors."
        ))

    if mcap > 20_000_000_000:
        moat_drivers.append((
            "Scale & Global Footprint",
            f"Large operating scale allows {company_name} to re-invest heavily into continuous R&D and maintain global channel presence."
        ))

    if not moat_drivers:
        moat_drivers.append((
            "Specialized Niche Position",
            f"Strong foothold within the {industry} market supported by tailored client relationships."
        ))

    uniqueness = [
        f"Consolidated product ecosystem offering a lower total cost of ownership (TCO) compared to point-solution peers.",
        f"Strong customer stickiness and established brand authority within {sector}."
    ]

    return {
        "core_offerings": core_offerings,
        "target_market": target_market,
        "moat_drivers": moat_drivers,
        "uniqueness": uniqueness
    }


# --- CACHED DATA FETCH ---
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
        
        info["logo_url"] = get_company_logo(website)
        info["peers"] = get_competitors(symbol, sector, industry)
        info["moat"] = analyze_moat(info, symbol)
        return info
    except Exception as e:
        return None


# --- MAIN APP INTERFACE ---
st.title("📊 Stock Analysis Dashboard")

# Sidebar
ticker_input = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").strip().upper()

if ticker_input:
    with st.spinner(f"Loading data for {ticker_input}..."):
        data = load_stock_data(ticker_input)

    if data:
        # Header section: Name + Logo
        col_title, col_logo = st.columns([4, 1])
        with col_title:
            st.header(f"{data.get('longName', ticker_input)} ({ticker_input})")
        with col_logo:
            if data.get("logo_url"):
                st.image(data["logo_url"], width=64)

        # Key Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        price = data.get("currentPrice") or data.get("regularMarketPrice") or data.get("previousClose") or "N/A"
        mcap = data.get("marketCap")
        
        m1.metric("Current Price", f"${price}" if isinstance(price, (int, float)) else price)
        m2.metric("Market Cap", f"${mcap:,.0f}" if isinstance(mcap, (int, float)) else "N/A")
        m3.metric("Sector", data.get("sector", "N/A"))
        m4.metric("Industry", data.get("industry", "N/A"))

        st.markdown("---")

        # MOAT Overview
        st.subheader("🏰 Competitive Advantage & MOAT Overview")
        left_col, right_col = st.columns(2)

        moat = data["moat"]
        peers = data["peers"]

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

        # Business Summary & Table
        st.subheader("📝 Business Summary")
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
        st.error(f"Could not load data for symbol '{ticker_input}'. Please verify the ticker symbol.")
else:
    st.info("Enter a ticker symbol in the sidebar to begin.")
