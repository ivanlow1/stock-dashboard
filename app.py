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
    page_title="Stock Analysis Dashboard",
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


# --- DYNAMIC COMPETITOR FETCHING ---
def get_company_competitors(ticker_symbol, industry="", sector=""):
  """Dynamically pulls direct industry peers instead of generic mega-cap tech stocks."""
  competitors = []

  # Sector/Industry peer map
  industry_peer_map = {
      "cybersecurity": ["PANW", "CRWD", "CHKP", "ZS", "NET"],
      "software - infrastructure": ["MSFT", "ORCL", "SNOW", "DDOG", "PANW"],
      "software - application": ["CRM", "NOW", "ADBE", "ORCL", "SAP"],
      "semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "INTC"],
      "consumer electronics": ["AAPL", "DELL", "HPQ", "SONY"],
      "internet retail": ["AMZN", "BABA", "EBAY", "PDD"],
      "financial": ["JPM", "BAC", "MS", "GS", "C"],
  }

  # Attempt 1: Scrape Finviz quote page for peers
  try:
    url = f"https://finviz.com/quote.ashx?t={ticker_symbol.upper()}"
    resp = requests.get(url, headers=HEADERS, timeout=3)
    if resp.status_code == 200:
      soup = bs4.BeautifulSoup(resp.text, "html.parser")
      for a in soup.find_all("a", class_="tab-link"):
        href = a.get("href", "")
        text = a.text.strip()
        if (
            "quote.ashx?t=" in href
            and text != ticker_symbol.upper()
            and len(text) <= 5
            and text.isalpha()
        ):
          if text not in competitors:
            competitors.append(text)
        if len(competitors) >= 6:
          break
  except Exception:
    pass

  # Attempt 2: Fallback to Industry mapping if scraping yields < 2 peers
  if len(competitors) < 2:
    combined_text = f"{industry} {sector}".lower()
    for key, peers in industry_peer_map.items():
      if key in combined_text:
        competitors = [p for p in peers if p != ticker_symbol.upper()]
        break

  return competitors if competitors else ["N/A"]


# --- DYNAMIC MOAT & ADVANTAGE ANALYZER ---
def analyze_company_moat(profile, ticker_symbol):
  """Generates ticker-specific Competitive Advantages, Ecosystem, and MOAT Drivers."""
  summary = profile.get("longBusinessSummary", "")
  summary_lower = summary.lower()
  industry = profile.get("industry", "Technology")
  sector = profile.get("sector", "Technology")
  mcap = profile.get("marketCap", 0)
  company_name = profile.get("shortName") or profile.get("longName") or ticker_symbol

  # 1. Products & Ecosystem
  core_offerings = (
      f"Broad portfolio across {industry} solutions, specialized hardware/software"
      " products, and integrated enterprise services."
  )
  if "security" in summary_lower or "firewall" in summary_lower:
    core_offerings = (
        "Integrated cybersecurity platform, network security appliances"
        " (FortiGate), SASE, and AI-powered threat intelligence services."
    )
  elif "cloud" in summary_lower or "saas" in summary_lower:
    core_offerings = (
        "Cloud-native software platform, enterprise SaaS subscriptions, and"
        " workflow automation modules."
  )

  target_market = (
      f"Global enterprise clients, commercial organizations, and government"
      f" entities operating within the {sector} space."
  )

  # 2. Economic MOAT Drivers
  moat_drivers = []
  if any(
      k in summary_lower
      for k in ["platform", "subscription", "integration", "enterprise", "cloud"]
  ):
    moat_drivers.append((
        "High Switching Costs",
        (
            f"Deep embedding of {company_name}'s solutions into client mission-critical"
            " infrastructure makes vendor displacement high-cost and multi-year."
        ),
    ))

  if any(
      k in summary_lower
      for k in ["patent", "proprietary", "asic", "architecture", "security"]
  ):
    moat_drivers.append((
        "Proprietary Technology & ASICs",
        (
            f"Custom intellectual property and proprietary architectures provide"
            " price-to-performance advantages over off-the-shelf competition."
        ),
    ))

  if mcap > 20000000000:
    moat_drivers.append((
        "Scale & Global Footprint",
        (
            "Expansive global footprint and vast customer base enable heavy R&D"
            " reinvestment and broader telemetry data collection."
        ),
    ))

  if not moat_drivers:
    moat_drivers.append((
        "Niche Domain Expertise",
        (
            f"Specialized position within {industry} with established channel"
            " partner ecosystems."
        ),
    ))

  # 3. Key Uniqueness & Differentiation
  uniqueness = [
      (
          f"Consolidated architecture reducing total cost of ownership (TCO)"
          f" compared to point-product vendors in {industry}."
      ),
      (
          f"Strong brand equity and sticky enterprise customer retention"
          f" relative to generic {sector} peers."
      ),
  ]

  return {
      "core_offerings": core_offerings,
      "target_market": target_market,
      "moat_drivers": moat_drivers,
      "uniqueness": uniqueness,
  }


# --- PROFILE DATA FETCH ---
@st.cache_data(ttl=86400)
def get_company_profile(sym):
  try:
    t = yf.Ticker(sym)
    info = t.info or {}

    website = info.get("website", "")
    industry = info.get("industry", "")
    sector = info.get("sector", "")

    info["logo_image_url"] = get_company_logo_url(website, sym)
    info["competitors"] = get_company_competitors(sym, industry, sector)
    info["moat_analysis"] = analyze_company_moat(info, sym)

    return info
  except Exception as e:
    st.error(f"Error retrieving profile for {sym}: {e}")
    return {}


# --- STREAMLIT UI LAYOUT ---
st.title("📊 Stock Analysis Dashboard")

ticker = (
    st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").strip().upper()
)
