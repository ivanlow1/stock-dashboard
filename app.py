import json
import re
import urllib.parse
from datetime import datetime
import bs4
import requests
import streamlit as st
import yfinance as yf

# Page setup
st.set_page_config(
    page_title="Company Dashboard & Profile",
    page_icon="📈",
    layout="wide",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# --- LOGO HELPER ---
def get_company_logo_url(website_url, ticker_symbol):
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

# --- DYNAMIC COMPETITOR & PEER FETCHING ---
def get_company_competitors(ticker_symbol, industry=""):
    """Fetches dynamic competitor list from Finviz quote page or industry fallback."""
    competitors = []
    
    # Method 1: Scrape Finviz Peers/Industry Screener for exact symbol
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker_symbol.upper()}"
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            soup = bs4.BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", class_="tab-link"):
                href = a.get("href", "")
                text = a.text.strip()
                if "quote.ashx?t=" in href and text != ticker_symbol.upper() and len(text) <= 5 and text.isalpha():
                    if text not in competitors:
                        competitors.append(text)
                if len(competitors) >= 5:
                    break
    except Exception:
        pass

    # Fallback Peer Mapping by Industry/Sector if scraping fails or returns < 2
    if len(competitors) < 2:
        fallback_map = {
            "Cybersecurity": ["PANW", "CRWD", "NET", "ZS", "CHKP"],
            "Software - Infrastructure": ["MSFT", "ORCL", "SNOW", "DDOG"],
            "Semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "INTC"],
            "Consumer Electronics": ["AAPL", "SONY", "DELL", "HPQ"],
            "Internet Retail": ["AMZN", "BABA", "EBAY", "PDD"],
        }
        for ind_key, peers in fallback_map.items():
            if ind_key.lower() in industry.lower():
                competitors = [p for p in peers if p != ticker_symbol.upper()]
                break

    return competitors if competitors else ["N/A"]

# --- DYNAMIC MOAT & ADVANTAGE GENERATOR ---
def generate_dynamic_moat(profile):
    """Generates ticker-specific Competitive Advantage & Economic Moat overview."""
    long_summary = profile.get("longBusinessSummary", "")
    industry = profile.get("industry", "N/A")
    sector = profile.get("sector", "N/A")
    mcap = profile.get("marketCap", 0)

    moat_type = "Narrow Moat"
    drivers = []

    # Detect Switching Costs & Platform Lock-in
    if any(k in long_summary.lower() for k in ["platform", "subscription", "cloud", "saas", "enterprise"]):
        drivers.append("High Switching Costs: Deep integration into customer workflows makes provider substitution costly.")
        moat_type = "Wide Moat" if mcap > 50000000000 else "Narrow Moat"

    # Detect Network Effects
    if any(k in long_summary.lower() for k in ["ecosystem", "network", "marketplace", "users"]):
        drivers.append("Network Effects: Value increases exponentially as user and developer
