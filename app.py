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
                calculated
