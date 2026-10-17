import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📈 Interactive Stock Ticker Dashboard")

# --- SIDEBAR INPUTS ---
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="AMD").upper()
ticker = yf.Ticker(ticker_symbol)

# --- HELPER: WIKIDATA / WIKIPEDIA FOUNDING YEAR RETRIEVAL ---
def get_founding_year_wikidata(company_name):
    try:
        search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(company_name)}&language=en&format=json"
        headers = {'User-Agent': 'StockDashboardApp/1.0'}
        res = requests.get(search_url, headers=headers, timeout=5).json()
        if not res.get('search'):
            return None
        entity_id = res['search'][0]['id']
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        data = requests.get(entity_url, headers=headers, timeout=5).json()
        claims = data['entities'][entity_id]['claims']
        # P571 = Inception / Founded date in Wikidata
        if 'P571' in claims:
            time_str = claims['P571'][0]['mainsnak']['datavalue']['value']['time']
            founding_year = int(time_str.split('-')[0].replace('+', ''))
            return founding_year
    except Exception:
        pass
    return None

# --- PANEL 1: COMPANY PROFILE & MOAT ANALYSIS ---
st.header(f"1. Company Profile & Strategic Overview ({ticker_symbol})")

@st.cache_data(ttl=86400)
def get_company_profile(sym):
    try:
        t = yf.Ticker(sym)
        info = t.info
        current_year = datetime.now().year
        company_name = info.get("longName", sym)
        
        # 1. Try yfinance metadata
        founded_year = info.get("startDate") or info.get("firstTradeDateEpochUtc")
        calculated_age = None
        if founded_year:
            if isinstance(founded_year, int) and founded_year > 1800:
                calculated_age = f"{current_year - founded_year} years (Founded ~{founded_year})"
            elif isinstance(founded_year, (int, float)):
                est_year = datetime.fromtimestamp(founded_year).year
                calculated_age = f"Public for {current_year - est_year} years (IPO ~{est_year})"
        
        # 2. Try Wikidata / Wikipedia lookup
        if not calculated_age:
            wiki_year = get_founding_year_wikidata(company_name)
            if wiki_year:
                calculated_age = f"{current_year - wiki_year} years (Founded ~{wiki_year} via Wikipedia)"
                
        # 3. Fallback to earliest stock trade history date
        if not calculated_age:
            hist = t.history(period="max")
            if not hist.empty:
                first_year = hist.index[0].year
                calculated_age = f"Public for {current_year - first_year}+ years (Trading since {first_year})"
            else:
                calculated_age = "N/A"
                
        info["calculated_age"] = calculated_age
        return info
    except Exception:
        return {}

info = get_company_profile(ticker_symbol)

# AUTOMATIC PEER DETERMINATION
def get_dynamic_peers(sym, sector):
    peer_map = {
        "AMD": ["NVDA", "INTC", "QCOM", "AVGO", "TXN", "ARM"],
        "NVDA": ["AMD", "INTC", "AVGO", "QCOM", "TSM"],
        "RMD": ["PHG", "INSP", "INGN", "SYK", "MDT"],
        "FTNT": ["PANW", "CRWD", "NET", "ZS", "CHKP"],
        "AAPL": ["MSFT", "GOOGL", "AMZN", "SSNLF", "SONY"],
        "MSFT": ["GOOGL", "AMZN", "AAPL", "ORCL", "IBM"],
        "GOOGL": ["MSFT", "AMZN", "META", "AAPL"],
        "AMZN": ["WMT", "MSFT", "GOOGL", "BABA"],
        "META": ["GOOGL", "SNAP", "PINS", "MSFT"]
    }
    if sym in peer_map:
        return peer_map[sym]
    
    sector_defaults = {
        "Technology": ["MSFT", "GOOGL", "NVDA", "AAPL", "AVGO"],
        "Healthcare": ["MDT", "SYK", "PHG", "JNJ", "PFE"],
        "Financial Services": ["JPM", "BAC", "WFC", "C", "GS"],
        "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD"]
    }
    return sector_defaults.get(sector, ["MSFT", "GOOGL", "AMZN", "NVDA"])

peers = get_dynamic_peers(ticker_symbol, info.get("sector", ""))

if info:
    company_name = info.get("longName", ticker_symbol)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    long_desc = info.get("longBusinessSummary", "No summary available.")
    age_str = info.get("calculated_age", "N/A")
    website = info.get("website", "")
    
    # Reliable Favicon / Logo Retrieval Strategy
    logo_url = None
    if website:
        domain = urllib.parse.urlparse(website).netloc.replace("www.", "")
        if domain:
            logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            
    # Display Header with Logo
    if logo_url:
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                <img src="{logo_url}" style="width: 48px; height: 48px; object-fit: contain; border-radius: 8px; background-color: #ffffff; padding: 4px; border: 1px solid #30363d;">
                <h2 style="margin: 0; padding: 0;">{company_name} ({ticker_symbol})</h2>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.subheader(f"{company_name} ({ticker_symbol})")
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Company Name", company_name)
    c2.metric("Sector / Industry", f"{sector} | {industry}")
    c3.metric("Company Age / History", age_str)
    
    st.markdown("### 🏢 Business Overview & Products")
    st.write(long_desc)
    
    st.markdown("### 🏰 Competitive Advantage & MOAT Overview")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        **🔑 Products & Ecosystem:**
        - **Core Offerings:** Broad portfolio across {industry} solutions, enterprise software, and integrated services.
        - **Target Market:** Global enterprise clients, healthcare providers, and commercial customers.
        """)
        st.markdown(f"""
        **🛡️ Economic MOAT Drivers:**
        - **High Switching Costs:** Deep integration into customer cloud ecosystems and IT infrastructure makes migration expensive and high-risk.
        - **Network & Scale Effects:** Proprietary technology stacks and large active user bases create high barriers to entry for new market players.
        """)
    with col_b:
        st.markdown(f"""
        **⚔️ Key Industry Competitors:**
        - Primary peer ecosystem includes: **{', '.join(peers)}**.
        """)
        st.markdown(f"""
        **⭐ Key Uniqueness & Differentiation:**
        - Proprietary hardware/software integration offering superior price-to-performance relative to pure legacy competitors.
        - Strong brand reputation backed by extensive domain expertise in the {sector} sector.
        """)
else:
    st.warning(f"Unable to fetch company profile info for {ticker_symbol}.")

st.divider()

# --- PANEL 2: INDICATIVE FUTURE TRADING BANDS ---
st.header(f"2. Price & Trading Bands ({ticker_symbol})")

timeframe_options = {
    "1 Week": "5d",
    "1 Month": "1mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "5 Years": "5y",
    "10 Years": "10y"
}
selected_label = st.radio(
    "Select Timeframe:",
    options=list(timeframe_options.keys()),
    index=3, # Default to '1 Year'
    horizontal=True
)
period_param = timeframe_options[selected_label]

hist = ticker.history(period=period_param)

if not hist.empty and len(hist) >= 5:
    window_size = min(20, len(hist))
    indicator_bb = BollingerBands(close=hist["Close"], window=window_size, window_dev=2)
    hist["BB_Upper"] = indicator_bb.bollinger_hband()
    hist["BB_Lower"] = indicator_bb.bollinger_lband()
    hist["SMA_20"] = indicator_bb.bollinger_mavg()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name='Price'
    ))
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['BB_Lower'],
        line=dict(color='rgba(0, 128, 0, 0.3)', width=1),
        name='Lower Band', showlegend=True
    ))
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist['BB_Upper'],
        line=dict(color='rgba
