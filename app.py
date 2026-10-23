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
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="NVDA").upper()
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
        
        founded_year = info.get("startDate") or info.get("firstTradeDateEpochUtc")
        calculated_age = None
        if founded_year:
            if isinstance(founded_year, int) and founded_year > 1800:
                calculated_age = f"{current_year - founded_year} years (Founded ~{founded_year})"
            elif isinstance(founded_year, (int, float)):
                est_year = datetime.fromtimestamp(founded_year).year
                calculated_age = f"Public for {current_year - est_year} years (IPO ~{est_year})"
        
        if not calculated_age:
            wiki_year = get_founding_year_wikidata(company_name)
            if wiki_year:
                calculated_age = f"{current_year - wiki_year} years (Founded ~{wiki_year} via Wikipedia)"
                
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

def get_dynamic_peers(sym, sector):
    peer_map = {
        "NVDA": ["AMD", "INTC", "AVGO", "QCOM", "TSM"],
        "AMD": ["NVDA", "INTC", "QCOM", "AVGO", "TXN", "ARM"],
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
    
    logo_url = None
    if website:
        domain = urllib.parse.urlparse(website).netloc.replace("www.", "")
        if domain:
            logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            
    if logo_url:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                <img src="{logo_url}" style="width: 48px; height: 48px; object-fit: contain; border-radius: 8px; background-color: #ffffff; padding: 4px; border: 1px solid #30363d;">
                <h2 style="margin: 0; padding: 0;">{company_name} ({ticker_symbol})</h2>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.subheader(f"{company_name} ({ticker_symbol})")
        
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background-color: #1a1c23; border: 1px solid #30363d; border-radius: 8px; padding: 15px; height: 100%;">
            <div style="color: #8b949e; font-size: 14px; margin-bottom: 5px;">Company Name</div>
            <div style="color: #ffffff; font-size: 18px; font-weight: bold; word-break: break-word;">{company_name}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="background-color: #1a1c23; border: 1px solid #30363d; border-radius: 8px; padding: 15px; height: 100%;">
            <div style="color: #8b949e; font-size: 14px; margin-bottom: 5px;">Sector / Industry</div>
            <div style="color: #ffffff; font-size: 16px; font-weight: bold; word-break: break-word;">{sector} | {industry}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div style="background-color: #1a1c23; border: 1px solid #30363d; border-radius: 8px; padding: 15px; height: 100%;">
            <div style="color: #8b949e; font-size: 14px; margin-bottom: 5px;">Company Age / History</div>
            <div style="color: #ffffff; font-size: 16px; font-weight: bold; word-break: break-word;">{age_str}</div>
        </div>
