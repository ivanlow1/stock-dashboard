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
    website = info.get("website", "")

    # Fetch logo URL from yfinance or fallback to Clearbit via domain name
    logo_url = info.get("logo_url")
    if not logo_url and website:
        domain = urllib.parse.urlparse(website).netloc.replace("www.", "")
        if domain:
            logo_url = f"https://logo.clearbit.com/{domain}"

    # Display Logo and Company Title
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        if logo_url:
            st.image(logo_url, width=80)
    with col_title:
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
    except Exception:
        pass

    # 3. CNBC Search RSS
    try:
        cnbc_url = f"https://www.cnbc.com/id/100003114/device/rss/rss.html"
        req = urllib.request.Request(cnbc_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            root = ET.fromstring(res.read())
            count = 0
            for item in root.findall('./channel/item'):
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else "#"
                if title and sym.lower() in title.lower():
                    articles.append({'title': title, 'link': link, 'source': 'CNBC'})
                    count += 1
                    if count >= 3:
                        break
    except Exception:
        pass

    return articles

news_items = fetch_multi_source_news(ticker_symbol)

if news_items:
    news_data = []
    for item in news_items:
        title = item['title']
        link = item['link']
        source = item['source']
        
        score = analyzer.polarity_scores(title)['compound']
        sentiment = "🟢 Bullish" if score > 0.05 else ("🔴 Bearish" if score < -0.05 else "🟡 Neutral")
        
        news_data.append({
            "Source": source,
            "Headline": f"<a href='{link}' target='_blank'>{title}</a>",
            "Sentiment": sentiment,
            "Score": round(score, 2)
        })

    news_df = pd.DataFrame(news_data)
    st.write(news_df.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.write("No recent news found across Google News, Yahoo Finance, or CNBC.")

# --- PANEL 4: COMPETITOR & INDUSTRY PEER METRICS ---
st.header("4. Competitor & Industry Peer Metrics")

with st.expander("📖 What do these competitor metrics mean?"):
    st.markdown("""
    - **Market Cap:** Total market value of the company's outstanding shares.
    - **52W High / Low:** Highest and lowest prices at which the stock traded over the past year.
    - **Trailing P/E:** Current price divided by trailing 12-month net income per share (Lower = often cheaper/better value).
    - **Gross Margin (%):** Percentage of revenue retained after deducting cost of goods sold (Higher = better profitability).
    - **ROE (%):** Return on Equity; Net Income divided by total Stockholder Equity (Higher = better returns).
    - **Debt-to-Equity:** Ratio of total debt to shareholder equity (Lower = lower financial risk).
    """)

@st.cache_data(ttl=3600)
def get_raw_peer_metrics(symbols):
    metrics_list = []

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            fast = t.fast_info
            
            last_price = fast.get("lastPrice")
            mcap = fast.get("marketCap")
            year_high = fast.get("yearHigh")
            year_low = fast.get("yearLow")
            shares = fast.get("shares")

            pe_val, margin_val, roe_val, de_val = np.nan, np.nan, np.nan, np.nan

            try:
                income = t.financials
                balance = t.balance_sheet

                if not income.empty and not balance.empty:
                    net_income = income.loc['Net Income'].dropna().iloc[0] if 'Net Income' in income.index else None
                    revenue = income.loc['Total Revenue'].dropna().iloc[0] if 'Total Revenue' in income.index else None
                    gross_profit = income.loc['Gross Profit'].dropna().iloc[0] if 'Gross Profit' in income.index else None
                    equity = balance.loc['Stockholders Equity'].dropna().iloc[0] if 'Stockholders Equity' in balance.index else None
                    total_debt = balance.loc['Total Debt'].dropna().iloc[0] if 'Total Debt' in balance.index else None

                    if net_income and shares and net_income > 0 and last_price:
                        eps = net_income / shares
                        pe_val = round(last_price / eps, 2)

                    if gross_profit and revenue:
                        margin_val = round((gross_profit / revenue) * 100, 2)

                    if net_income and equity:
                        roe_val = round((net_income / equity) * 100, 2)

                    if total_debt is not None and equity:
                        de_val = round(total_debt / equity, 2)
            except Exception:
                pass

            metrics_list.append({
                "Ticker": sym,
                "Price": round(last_price, 2) if last_price else np.nan,
                "Market Cap ($B)": round(mcap / 1e9, 2) if mcap else np.nan,
                "52W High": round(year_high, 2) if year_high else np.nan,
                "52W Low": round(year_low, 2) if year_low else np.nan,
                "P/E": pe_val,
                "Gross Margin (%)": margin_val,
                "ROE (%)": roe_val,
                "Debt/Equity": de_val
            })
        except Exception:
            metrics_list.append({
                "Ticker": sym, "Price": np.nan, "Market Cap ($B)": np.nan, "52W High": np.nan, 
                "52W Low": np.nan, "P/E": np.nan, "Gross Margin (%)": np.nan, "ROE (%)": np.nan, "Debt/Equity": np.nan
            })

    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching live peer metrics..."):
    df_raw = get_raw_peer_metrics(all_tickers)

def style_relative_to_ref(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    if len(df) < 1:
        return styles

    green_style = 'background-color: #1e4620; color: #4cd964; font-weight: bold;'
    red_style = 'background-color: #5c1d24; color: #ff6b6b; font-weight: bold;'

    higher_is_better = {
        "Price": True,
        "Market Cap ($B)": True,
        "52W High": True,
        "52W Low": False,
        "P/E": False,
        "Gross Margin (%)": True,
        "ROE (%)": True,
        "Debt/Equity": False
    }

    ref_row = df.iloc[0]

    # --- COLOR ROW 0 RELATIVE TO PEER AVERAGE ---
    if len(df) > 1:
        peer_avg = df.iloc[1:].mean(numeric_only=True)
        for col in df.columns:
            val = ref_row[col]
            avg_val = peer_avg.get(col, np.nan)

            if pd.isna(val) or pd.isna(avg_val):
                continue

            prefer_higher = higher_is_better.get(col, True)

            if val > avg_val:
                styles.iloc[0][df.columns.get_loc(col)] = green_style if prefer_higher else red_style
            elif val < avg_val:
                styles.iloc[0][df.columns.get_loc(col)] = red_style if prefer_higher else green_style

    # --- COLOR ROWS 1+ RELATIVE TO ROW 0 ---
    for idx in range(1, len(df)):
        for col in df.columns:
            val = df.iloc[idx][col]
            ref_val = ref_row[col]

            if pd.isna(val) or pd.isna(ref_val):
                continue

            prefer_higher = higher_is_better.get(col, True)

            if val > ref_val:
                styles.iloc[idx][df.columns.get_loc(col)] = green_style if prefer_higher else red_style
            elif val < ref_val:
                styles.iloc[idx][df.columns.get_loc(col)] = red_style if prefer_higher else green_style

    return styles

styled_df = (
    df_raw.style.apply(style_relative_to_ref, axis=None)
    .format("{:.2f}", na_rep="N/A")
)

st.markdown(
    """
    <style>
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            color: #ffffff;
            font-family: inherit;
            background-color: #0e1117;
            margin-bottom: 20px;
        }
        .custom-table th {
            background-color: #1a1c23;
            padding: 10px;
            text-align: right;
            border: 1px solid #30363d;
        }
        .custom-table th:first-child {
            text-align: left;
        }
        .custom-table td {
            padding: 10px;
            text-align: right;
            border: 1px solid #30363d;
        }
        .custom-table td:first-child {
            text-align: left;
            font-weight: bold;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.write(styled_df.to_html(classes='custom-table'), unsafe_allow_html=True)

# --- PANEL 5: PROFESSIONAL STOCK ANALYST RECOMMENDATION & ANALYSIS ---
st.header("5. Professional Stock Analyst Recommendation")

with st.expander("📖 What do Overbought, Neutral, and Oversold mean?"):
    st.markdown("""
    - **🔴 Overbought:** The stock price has surged sharply or trades near the top of its historical band/valuation range, with elevated RSI indicators (>70). It may be due for a temporary pullback or consolidation.
    - **🟡 Neutral:** The stock is trading within fair value valuation bounds and balanced technical bands (RSI between 30 and 70). Risk/reward is currently balanced.
    - **🟢 Oversold:** The stock has experienced heavy selling pressure, driving technical momentum down (RSI < 30) or price below its lower trading band, often creating an attractive risk/reward entry point for long-term investors.
    """)

analyst_hist = ticker.history(period="1y")

if not analyst_hist.empty and len(analyst_hist) > 30:
    rsi_series = RSIIndicator(close=analyst_hist["Close"], window=14).rsi()
    current_rsi = round(rsi_series.dropna().iloc[-1], 2)
    
    current_price = analyst_hist["Close"].iloc[-1]
    bb_indicator = BollingerBands(close=analyst_hist["Close"], window=20, window_dev=2)
    bb_upper = bb_indicator.bollinger_hband().dropna().iloc[-1]
    bb_lower = bb_indicator.bollinger_lband().dropna().iloc[-1]
    bb_sma = bb_indicator.bollinger_mavg().dropna().iloc[-1]

    pe_val, margin_val, roe_val = "N/A", "N/A", "N/A"
    try:
        income = ticker.financials
        balance = ticker.balance_sheet
        shares = ticker.fast_info.get("shares")

        if not income.empty and not balance.empty:
            net_income = income.loc['Net Income'].dropna().iloc[0] if 'Net Income' in income.index else None
            revenue = income.loc['Total Revenue'].dropna().iloc[0] if 'Total Revenue' in income.index else None
            gross_profit = income.loc['Gross Profit'].dropna().iloc[0] if 'Gross Profit' in income.index else None
            equity = balance.loc['Stockholders Equity'].dropna().iloc[0] if 'Stockholders Equity' in balance.index else None

            if net_income and shares and net_income > 0:
                eps = net_income / shares
                pe_val = round(current_price / eps, 2)
            if gross_profit and revenue:
                margin_val = f"{round((gross_profit / revenue) * 100, 2)}%"
            if net_income and equity:
                roe_val = f"{round((net_income / equity) * 100, 2)}%"
    except Exception:
        pass

    if current_rsi > 70 or current_price >= bb_upper:
        rating = "OVERBOUGHT"
        rating_color = "🔴"
        recommendation_text = f"**{ticker_symbol}** is displaying strong bullish momentum that has pushed technical indicators into extended territory. With a 14-day RSI of **{current_rsi}** and trading near or above its upper Bollinger Band (${round(bb_upper, 2)}), the stock shows potential risk for short-term profit taking or consolidation."
    elif current_rsi < 30 or current_price <= bb_lower:
        rating = "OVERSOLD"
        rating_color = "🟢"
        recommendation_text = f"**{ticker_symbol}** is currently experiencing significant downward momentum. With an RSI of **{current_rsi}** and trading near or below its lower Bollinger Band (${round(bb_lower, 2)}), selling pressure appears extended, presenting potential mean-reversion buying opportunities."
    else:
        rating = "NEUTRAL"
        rating_color = "🟡"
        recommendation_text = f"**{ticker_symbol}** is currently trading within normal technical bounds. Its RSI stands at **{current_rsi}**, well within balanced territory, and price action remains centered near its 20-day moving average (${round(bb_sma, 2)})."

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Analyst Rating", f"{rating_color} {rating}")
    c2.metric("14-Day RSI", f"{current_rsi}")
    c3.metric("Current Price", f"${round(current_price, 2)}")
    c4.metric("20-Day SMA", f"${round(bb_sma, 2)}")

    st.markdown("### Executive Summary & Technical Breakdown")
    st.write(recommendation_text)

    st.info(f"""
    **Financial & Technical Breakdown Summary for {ticker_symbol}:**
    - **Valuation & Efficiency:** P/E Ratio: **{pe_val}** | Gross Margin: **{margin_val}** | ROE: **{roe_val}**
    - **Bollinger Bands:** Upper Bound: **${round(bb_upper, 2)}** | Lower Bound: **${round(bb_lower, 2)}**
    - **Analyst Note:** Always evaluate overall macroeconomic conditions and sector trends in tandem with technical RSI levels.
    """)
else:
    st.warning("Insufficient historical price data available to generate technical analyst analysis.")

# --- PANEL 6: COMPANY PERFORMANCE ---
st.header(f"6. Company Performance ({ticker_symbol})")

@st.cache_data(ttl=3600)
def get_quarterly_financials(sym):
    t = yf.Ticker(sym)
    q_financials = t.quarterly_financials
    if q_financials.empty:
        return pd.DataFrame()
    return q_financials

q_fin = get_quarterly_financials(ticker_symbol)

if not q_fin.empty and q_fin.shape[1] >= 1:
    cols = list(q_fin.columns)
    
    metric_keys = {
        "Total Revenue": "Revenue ($M)",
        "Gross Profit": "Gross Profit ($M)",
        "Operating Income": "Operating Income ($M)",
        "Net Income": "Net Income ($M)",
        "EBITDA": "EBITDA ($M)"
    }
    
    rows = []
    
    q0_date = cols[0].strftime("%Y-%m-%d") if hasattr(cols[0], "strftime") else str(cols[0])
    q1_date = cols[1].strftime("%Y-%m-%d") if len(cols) > 1 and hasattr(cols[1], "strftime") else (str(cols[1]) if len(cols) > 1 else "N/A")
    q4_date = cols[4].strftime("%Y-%m-%d") if len(cols) > 4 and hasattr(cols[4], "strftime") else (str(cols[4]) if len(cols) > 4 else "N/A")

    for key, display_name in metric_keys.items():
        if key in q_fin.index:
            v0 = q_fin.loc[key].iloc[0] / 1e6 if pd.notna(q_fin.loc[key].iloc[0]) else np.nan
            v1 = q_fin.loc[key].iloc[1] / 1e6 if len(cols) > 1 and pd.notna(q_fin.loc[key].iloc[1]) else np.nan
            v4 = q_fin.loc[key].iloc[4] / 1e6 if len(cols) > 4 and pd.notna(q_fin.loc[key].iloc[4]) else np.nan

            qoq_pct = ((v0 - v1) / abs(v1)) * 100 if pd.notna(v0) and pd.notna(v1) and v1 != 0 else np.nan
            yoy_pct = ((v0 - v4) / abs(v4)) * 100 if pd.notna(v0) and pd.notna(v4) and v4 != 0 else np.nan

            rows.append({
                "Financial Metric": display_name,
                f"Latest ({q0_date})": round(v0, 2) if pd.notna(v0) else np.nan,
                f"Prior Qtr ({q1_date})": round(v1, 2) if pd.notna(v1) else np.nan,
                "QoQ Growth (%)": round(qoq_pct, 2) if pd.notna(qoq_pct) else np.nan,
                f"Prior Year Qtr ({q4_date})": round(v4, 2) if pd.notna(v4) else np.nan,
                "YoY Growth (%)": round(yoy_pct, 2) if pd.notna(yoy_pct) else np.nan
            })

    df_perf = pd.DataFrame(rows).set_index("Financial Metric")

    def style_performance(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        green_style = 'background-color: #1e4620; color: #4cd964; font-weight: bold;'
        red_style = 'background-color: #5c1d24; color: #ff6b6b; font-weight: bold;'

        for idx in range(len(df)):
            for col in df.columns:
                if "Growth (%)" in col:
                    val = df.iloc[idx][col]
                    if pd.notna(val):
                        if val > 0:
                            styles.iloc[idx][df.columns.get_loc(col)] = green_style
                        elif val < 0:
                            styles.iloc[idx][df.columns.get_loc(col)] = red_style
        return styles

    styled_perf = (
        df_perf.style.apply(style_performance, axis=None)
        .format("{:+.2f}%", subset=[c for c in df_perf.columns if "Growth" in c], na_rep="N/A")
        .format("{:,.2f}", subset=[c for c in df_perf.columns if "Growth" not in c], na_rep="N/A")
    )

    st.write(styled_perf.to_html(classes='custom-table'), unsafe_allow_html=True)

else:
    st.warning("Quarterly financial report data is currently unavailable for this ticker.")
