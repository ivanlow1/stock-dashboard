import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import urllib.request
import xml.etree.ElementTree as ET
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

# --- PANEL 1: INDICATIVE FUTURE TRADING BANDS ---
st.header(f"1. Price & Trading Bands ({ticker_symbol})")

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

# --- PANEL 2: KEY NEWS & SENTIMENT ANALYSIS ---
st.header("2. Key News & Sentiment")

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

# --- PANEL 3: COMPETITOR & INDUSTRY PEER METRICS ---
st.header("3. Competitor & Industry Peer Metrics")

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

    # --- COLOR ROW 0 (REFERENCE TICKER) RELATIVE TO PEER AVERAGE ---
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

styled_df = df_raw.style.apply(style_relative_to_ref, axis=None)\
    .format("{:.2f}", na_rep="N/A")

# Custom CSS wrapper to ensure full table dark mode styling and visible background colors
html_table = f"""
<style>
    .custom-table-container {{
        width: 100%;
        overflow-x: auto;
        margin-bottom: 20px;
    }}
    .custom-table {{
        width: 100%;
        border-collapse: collapse;
        color: #ffffff;
        font-family: inherit;
        background-color: #0e1117;
    }}
    .custom-table th {{
        background-color: #1a1c23;
        padding: 10px;
        text-align: right;
        border: 1px solid #30363d;
    }}
    .custom-table th:first-child {{
        text-align: left;
    }}
    .custom-table td {{
        padding: 10px;
        text-align: right;
        border: 1px solid #30363d;
    }}
    .custom-table td:first-child {{
        text-align: left;
        font-weight: bold;
    }}
</style>
<div class="custom-table-container">
    {styled_df.to_html(classes='custom-table')}
</div>
"""

st.write(html_table, unsafe_allow_html=True)

# --- PANEL 4: PROFESSIONAL STOCK ANALYST RECOMMENDATION & ANALYSIS ---
st.header("4. Professional Stock Analyst Recommendation")

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
