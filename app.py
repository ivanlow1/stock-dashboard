import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import bs4
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📈 Interactive Stock Ticker Dashboard")

# --- SIDEBAR INPUTS ---
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").upper()
peer_symbols = st.sidebar.text_input(
    "Enter Peers (comma-separated):", 
    value="MU, META, AMZN, AVGO, MSFT, GOOGL, NVDA"
)
peers = [p.strip().upper() for p in peer_symbols.split(",") if p.strip()]

ticker = yf.Ticker(ticker_symbol)

# --- HELPER: COMPANY LOGO RETRIEVAL ---
def get_company_logo_url(website_url):
    """Fetches company logo via Clearbit or Google Favicon service using domain."""
    domain = ""
    if website_url:
        domain = website_url.replace("https://", "").replace("http://", "").strip()
        domain = domain.split("/")[0].replace("www.", "")

    if domain:
        clearbit_url = f"https://logo.clearbit.com/{domain}"
        try:
            resp = requests.get(clearbit_url, timeout=2)
            if resp.status_code == 200:
                return clearbit_url
        except Exception:
            pass
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    return None

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

if info:
    company_name = info.get("longName", ticker_symbol)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    long_desc = info.get("longBusinessSummary", "No summary available.")
    age_str = info.get("calculated_age", "N/A")
    website = info.get("website", "")
    
    logo_url = get_company_logo_url(website)

    c_logo, c1, c2, c3 = st.columns([1, 3, 3, 3])
    with c_logo:
        if logo_url:
            st.image(logo_url, width=80)
        else:
            st.write(f"### {ticker_symbol}")
    with c1:
        st.metric("Company Name", company_name)
    with c2:
        st.metric("Sector / Industry", f"{sector} | {industry}")
    with c3:
        st.metric("Company Age / History", age_str)

    st.markdown("### 🏢 Business Overview & Products")
    st.write(long_desc)

    st.markdown("### 🏰 Competitive Advantage & MOAT Overview")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        **🔑 Products & Ecosystem:**
        - **Core Offerings:** Broad portfolio across {industry} solutions, enterprise software, and integrated services.
        - **Target Market:** Global enterprise clients, cloud service providers, and commercial customers.
        """)
        
        st.markdown(f"""
        **🛡️ Economic MOAT Drivers:**
        - **High Switching Costs:** Deep integration into customer enterprise IT infrastructure makes migration expensive and high-risk.
        - **Network & Scale Effects:** Proprietary technology stacks and large customer bases create high barriers to entry for new market players.
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
    index=3,  # Default to '1 Year'
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
        x=hist.index, 
        y=hist['BB_Lower'], 
        line=dict(color='rgba(0, 128, 0, 0.3)', width=1), 
        name='Lower Band',
        showlegend=True
    ))

    fig.add_trace(go.Scatter(
        x=hist.index, 
        y=hist['BB_Upper'], 
        line=dict(color='rgba(255, 0, 0, 0.3)', width=1), 
        name='Upper Band',
        fill='tonexty',
        fillcolor='rgba(128, 128, 128, 0.1)',
        showlegend=True
    ))

    fig.add_trace(go.Scatter(
        x=hist.index, 
        y=hist['SMA_20'], 
        line=dict(color='blue', width=1.5), 
        name=f'{window_size}-Period SMA'
    ))

    fig.update_layout(
        title=f"Historical Price with Bollinger Bands ({selected_label})", 
        xaxis_rangeslider_visible=False,
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Invalid ticker or missing historical data for the selected timeframe.")

# --- PANEL 3: KEY NEWS & SENTIMENT ANALYSIS ---
st.header("3. Key News & Sentiment")

analyzer = SentimentIntensityAnalyzer()

@st.cache_data(ttl=1800)
def fetch_multi_source_news(sym):
    articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # 1. Google News RSS
    try:
        gn_url = f"https://news.google.com/rss/search?q={sym}+stock&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(gn_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            root = ET.fromstring(res.read())
            for item in root.findall('./channel/item')[:4]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else "#"
                if title:
                    articles.append({'title': title, 'link': link, 'source': 'Google News'})
    except Exception:
        pass

    # 2. Yahoo Finance RSS
    try:
        yf_url = f"https://finance.yahoo.com/rss/headline?s={sym}"
        req = urllib.request.Request(yf_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            root = ET.fromstring(res.read())
            for item in root.findall('./channel/item')[:4]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else "#"
                if title:
                    articles.append({'title': title, 'link': link, 'source': 'Yahoo Finance'})
