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
                est_year = datetime.fromtimestamp(founded_year).
