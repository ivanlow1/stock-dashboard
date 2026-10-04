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

# Standard browser headers to avoid HTTP 403 / 429 blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def extract_year_from_text(text):
  """Extracts founding/incorporation year using broad regex patterns."""
  if not text:
    return None

  # Pattern 1: Verbal descriptions (e.g., "founded in 2000", "incorporated in October 1998", "established 1984")
  pattern_verbal = r"\b(?:founded|incorporated|established|started|formed)\b.*?\b(18\d\d|19\d\d|20\d\d)\b"
  match = re.search(pattern_verbal, text, re.IGNORECASE)
  if match:
    return int(match.group(1))

  # Pattern 2: Key-value structures (e.g., "Founded: 2000", "Incorporated: 1998")
  pattern_keyval = (
      r"\b(?:Founded|Incorporated|Established)\b\s*:\s*\b(18\d\d|19\d\d|20\d\d)\b"
  )
  match = re.search(pattern_keyval, text, re.IGNORECASE)
  if match:
    return int(match.group(1))

  return None


def get_founding_year_scraped(ticker_symbol):
  """Scrapes founding year from StockAnalysis or Yahoo Profile HTML."""
  # Attempt A: StockAnalysis
  try:
    url = f"https://stockanalysis.com/stocks/{ticker_symbol.lower()}/company/"
    resp = requests.get(url, headers=HEADERS, timeout=4)
    if resp.status_code == 200:
      soup = bs4.BeautifulSoup(resp.text, "html.parser")
      for element in soup.find_all(["td", "div", "span", "tr"]):
        if "Founded" in element.text:
          year = extract_year_from_text(element.text)
          if year:
            return year
  except Exception:
    pass

  # Attempt B: Yahoo Finance Profile Page
  try:
    url = f"https://finance.yahoo.com/quote/{ticker_symbol}/profile"
    resp = requests.get(url, headers=HEADERS, timeout=4)
    if resp.status_code == 200:
      year = extract_year_from_text(resp.text)
      if year:
        return year
  except Exception:
    pass

  return None


def get_founding_year_wikidata(company_name):
  """Queries Wikidata SPARQL API for company inception year (P571)."""
  try:
    search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(company_name)}&language=en&format=json"
    res = requests.get(search_url, headers=HEADERS, timeout=3).json()
    if not res.get("search"):
      return None

    entity_id = res["search"][0]["id"]

    sparql_query = f"""
        SELECT ?inception WHERE {{
          wd:{entity_id} wdt:P571 ?inception .
        }} LIMIT 1
        """
    wikidata_url = "https://query.wikidata.org/sparql"
    sparql_res = requests.get(
        wikidata_url,
        params={"query": sparql_query, "format": "json"},
        headers=HEADERS,
        timeout=3,
    ).json()

    bindings = sparql_res.get("results", {}).get("bindings", [])
    if bindings:
      date_str = bindings[0]["inception"]["value"]
      match = re.search(r"\b(18\d\d|19\d\d|20\d\d)\b", date_str)
      if match:
        return int(match.group(1))
  except Exception:
    pass

  return None


@st.cache_data(ttl=86400)
def get_company_profile(sym):
  """Fetches profile details and computes company age via multi-tiered strategy."""
  try:
    t = yf.Ticker(sym)
    info = t.info or {}

    current_year = datetime.now().year
    company_name = info.get("longName") or info.get("shortName") or sym

    founded_year = None
    age_label = ""

    # Strategy 1: Check Yahoo longBusinessSummary for "founded/incorporated in YYYY"
    summary = info.get("longBusinessSummary", "")
    parsed_year = extract_year_from_text(summary)
    if parsed_year:
      founded_year = parsed_year
      age_label = "Founded"

    # Strategy 2: StockAnalysis & Yahoo Profile Scraping
    if not founded_year:
      scraped_year = get_founding_year_scraped(sym)
      if scraped_year:
        founded_year = scraped_year
        age_label = "Founded"

    # Strategy 3: Wikidata Query
    if not founded_year:
      wiki_year = get_founding_year_wikidata(company_name)
      if wiki_year:
        founded_year = wiki_year
        age_label = "Founded via Wikidata"

    # Strategy 4: Fallback to IPO date or First Available Trading Year
    if founded_year:
      calculated_age = (
          f"{current_year - founded_year} years ({age_label} ~{founded_year})"
      )
    elif info.get("firstTradeDateEpochUtc"):
      ipo_year = datetime.fromtimestamp(
          info.get("firstTradeDateEpochUtc")
      ).year
      calculated_age = (
          f"Public for {current_year - ipo_year} years (IPO ~{ipo_year})"
      )
    else:
      # Price history fallback
      hist = t.history(period="max")
      if not hist.empty:
        first_year = hist.index[0].year
        calculated_age = (
            f"Public for {current_year - first_year}+ years (Trading since"
            f" {first_year})"
        )
      else:
        calculated_age = "N/A"

    info["calculated_age"] = calculated_age
    return info
  except Exception as e:
    st.error(f"Error retrieving company profile: {e}")
    return {}


# --- Streamlit Dashboard UI ---
st.title("📊 Company Financial & Profile Dashboard")

ticker = (
    st.sidebar.text_input("Enter Ticker Symbol", value="FTNT")
    .strip()
    .upper()
)

if ticker:
  with st.spinner(f"Loading profile for {ticker}..."):
    profile = get_company_profile(ticker)

  if profile:
    # Header Section: Company Name (Left) and Logo (Top Right)
    head_col1, head_col2 = st.columns([5, 1])

    with head_col1:
      st.header(f"{profile.get('longName', ticker)} ({ticker})")

    with head_col2:
      logo_url = profile.get("logo_url")
      if logo_url:
        st.image(logo_url, width=100)

    # Key Metrics Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
      price = profile.get(
          "currentPrice",
          profile.get(
              "regularMarketPrice", profile.get("previousClose", "N/A")
          ),
      )
      st.metric(label="Current Price", value=f"${price}")
    with col2:
      mcap = profile.get("marketCap")
      st.metric(label="Market Cap", value=f"${mcap:,}" if mcap else "N/A")
    with col3:
      st.metric(
          label="Company Age / Status",
          value=profile.get("calculated_age", "N/A"),
      )
    with col4:
      st.metric(label="Sector", value=profile.get("sector", "N/A"))

    st.subheader("Company Summary")
    st.write(profile.get("longBusinessSummary", "No summary available."))

    st.subheader("Key Details")
    details_df = {
        "Attribute": [
            "Industry",
            "Full-Time Employees",
            "Headquarters",
            "Website",
        ],
        "Value": [
            profile.get("industry", "N/A"),
            (
                f"{profile.get('fullTimeEmployees', 0):,}"
                if profile.get("fullTimeEmployees")
                else "N/A"
            ),
            (
                f"{profile.get('city', '')}, {profile.get('state', '')}"
                f" {profile.get('country', '')}"
            ),
            profile.get("website", "N/A"),
        ],
    }
    st.table(details_df)
else:
  st.info("Please enter a ticker symbol in the sidebar.")
