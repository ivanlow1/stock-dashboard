import json
import re
import urllib.parse
from datetime import datetime
import bs4
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Company Dashboard & Profile",
    page_icon="📈",
    layout="wide",
)


def get_founding_year_wikidata(company_name):
  """Queries Wikidata SPARQL API for the inception year of a company."""
  try:
    search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(company_name)}&language=en&format=json"
    res = requests.get(search_url, timeout=3).json()
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
        headers={"User-Agent": "StreamlitCompanyApp/1.0"},
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


def get_founding_year_scraped(ticker_symbol):
  """Fallback scraper checking StockAnalysis and Yahoo Profile for founded year."""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  # Strategy A: StockAnalysis
  try:
    url = f"https://stockanalysis.com/stocks/{ticker_symbol.lower()}/company/"
    resp = requests.get(url, headers=headers, timeout=4)
    if resp.status_code == 200:
      soup = bs4.BeautifulSoup(resp.text, "html.parser")
      for td in soup.find_all(["td", "div", "span"]):
        if "Founded" in td.text:
          match = re.search(r"\b(18\d\d|19\d\d|20\d\d)\b", td.parent.text)
          if match:
            return int(match.group(1))
  except Exception:
    pass

  # Strategy B: Yahoo Finance HTML
  try:
    url = f"https://finance.yahoo.com/quote/{ticker_symbol}/profile"
    resp = requests.get(url, headers=headers, timeout=4)
    if resp.status_code == 200:
      match = re.search(
          r"founded\s+(?:in\s+)?(18\d\d|19\d\d|20\d\d)", resp.text, re.IGNORECASE
      )
      if match:
        return int(match.group(1))
  except Exception:
    pass

  return None


@st.cache_data(ttl=86400)
def get_company_profile(sym):
  """Fetches profile details and computes company age cleanly across fallback sources."""
  try:
    t = yf.Ticker(sym)
    info = t.info
    current_year = datetime.now().year
    company_name = info.get("longName") or info.get("shortName") or sym

    founded_year = None
    age_label = ""

    # 1. Regex parse "founded in YYYY" directly from Yahoo business summary
    summary = info.get("longBusinessSummary", "")
    if summary:
      match = re.search(
          r"\bfounded\s+(?:in\s+)?(18\d\d|19\d\d|20\d\d)\b",
          summary,
          re.IGNORECASE,
      )
      if match:
        founded_year = int(match.group(1))
        age_label = "Founded"

    # 2. Query Wikidata / Wikipedia
    if not founded_year:
      wiki_year = get_founding_year_wikidata(company_name)
      if wiki_year:
        founded_year = wiki_year
        age_label = "Founded via Wikipedia"

    # 3. Web Scrape Fallback (StockAnalysis & Yahoo Profile)
    if not founded_year:
      scraped_year = get_founding_year_scraped(sym)
      if scraped_year:
        founded_year = scraped_year
        age_label = "Founded"

    # 4. Compile Result or Fallback to IPO / Historical Trading Data
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
      # Get earliest price record date
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
    st.error(f"Error fetching profile: {e}")
    return {}


# Streamlit UI
st.title("📊 Company Financial & Profile Dashboard")

ticker = (
    st.sidebar.text_input("Enter Ticker Symbol", value="FTNT")
    .strip()
    .upper()
)

if ticker:
  with st.spinner(f"Loading data for {ticker}..."):
    profile = get_company_profile(ticker)

  if profile:
    st.header(f"{profile.get('longName', ticker)} ({ticker})")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
      st.metric(
          label="Current Price",
          value=f"${profile.get('currentPrice', profile.get('regularMarketPrice', 'N/A'))}",
      )
    with col2:
      st.metric(
          label="Market Cap",
          value=(
              f"${profile.get('marketCap', 0):,}"
              if profile.get("marketCap")
              else "N/A"
          ),
      )
    with col3:
      st.metric(label="Company Age / Status", value=profile.get("calculated_age", "N/A"))
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
