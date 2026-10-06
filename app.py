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
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").upper()
peer_symbols = st.sidebar.text_input(
    "Enter Peers (comma-separated):", 
    value="MU, META, AMZN, AVGO, MSFT, GOOGL, NVDA"
)
peers = [p.strip().upper() for p in peer_symbols.split(",") if p.strip()]

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

if info:
    company_name = info.get("longName", ticker_symbol)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    long_desc = info.get("longBusinessSummary", "No summary available.")
    age_str = info.get("calculated_age", "N/A")

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
