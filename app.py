import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import urllib.request
import xml.etree.ElementTree as ET
from ta.volatility import BollingerBands
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📈 Interactive Stock Ticker Dashboard")

# --- SIDEBAR INPUTS ---
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").upper()
peer_symbols = st.sidebar.text_input("Enter Peers (comma-separated):", value="MSFT, GOOGL, NVDA")
peers = [p.strip().upper() for p in peer_symbols.split(",") if p.strip()]

ticker = yf.Ticker(ticker_symbol)

# --- PANEL 1: INDICATIVE FUTURE TRADING BANDS ---
st.header(f"1. Price & Trading Bands ({ticker_symbol})")

hist = ticker.history(period="1y")

if not hist.empty:
    indicator_bb = BollingerBands(close=hist["Close"], window=20, window_dev=2)
    hist["BB_Upper"] = indicator_bb.bollinger_hband()
    hist["BB_Lower"] = indicator_bb.bollinger_lband()
    hist["SMA_20"] = indicator_bb.bollinger_mavg()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
                                 low=hist['Low'], close=hist['Close'], name='Price'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], line=dict(color='red', width=1), name='Upper Band'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], line=dict(color='green', width=1), name='Lower Band', fill='tonexty'))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_20'], line=dict(color='blue', width=1), name='20-Day SMA'))

    fig.update_layout(title="Historical Price with Bollinger Bands (Indicative Bounds)", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Invalid ticker or missing historical data.")

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
                # Filter for stock keyword context
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
    - **Trailing P/E:** Current price divided by trailing 12-month net income per share.
    - **Gross Margin (%):** Percentage of revenue retained after deducting cost of goods sold.
    - **ROE (%):** Return on Equity; Net Income divided by total Stockholder Equity.
    - **Debt-to-Equity:** Ratio of total debt to shareholder equity.
    """)

@st.cache_data(ttl=3600)
def get_peer_metrics(symbols):
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
            
            price_str = f"${round(last_price, 2)}" if last_price else "N/A"
            mcap_str = f"${round(mcap / 1e9, 2)}B" if mcap else "N/A"
            high_str = f"${round(year_high, 2)}" if year_high else "N/A"
            low_str = f"${round(year_low, 2)}" if year_low else "N/A"

            pe_str, margin_str, roe_str, de_str = "N/A", "N/A", "N/A", "N/A"

            try:
                income = t.financials
                balance = t.balance_sheet

                if not income.empty and not balance.empty:
                    net_income = income.loc['Net Income'].dropna().iloc[0] if 'Net Income' in income.index else None
                    revenue = income.loc['Total Revenue'].dropna().iloc[0] if 'Total Revenue' in income.index else None
                    gross_profit = income.loc['Gross Profit'].dropna().iloc[0] if 'Gross Profit' in income.index else None

                    equity = balance.loc['Stockholders Equity'].dropna().iloc[0] if 'Stockholders Equity' in balance.index else None
                    total_debt = balance.loc['Total Debt'].dropna().iloc[0] if 'Total Debt' in balance.index else None

                    if net_income and shares and net_income > 0:
                        eps = net_income / shares
                        pe_str = str(round(last_price / eps, 2))

                    if gross_profit and revenue:
                        margin_str = f"{round((gross_profit / revenue) * 100, 2)}%"

                    if net_income and equity:
                        roe_str = f"{round((net_income / equity) * 100, 2)}%"

                    if total_debt is not None and equity:
                        de_str = str(round(total_debt / equity, 2))
            except Exception:
                pass

            metrics_list.append({
                "Ticker": sym,
                "Price": price_str,
                "Market Cap": mcap_str,
                "52W High": high_str,
                "52W Low": low_str,
                "P/E": pe_str,
                "Gross Margin": margin_str,
                "ROE": roe_str,
                "Debt/Equity": de_str
            })
        except Exception:
            metrics_list.append({
                "Ticker": sym, "Price": "N/A", "Market Cap": "N/A", "52W High": "N/A", "52W Low": "N/A",
                "P/E": "N/A", "Gross Margin": "N/A", "ROE": "N/A", "Debt/Equity": "N/A"
            })

    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching live peer metrics..."):
    comparison_df = get_peer_metrics(all_tickers)

st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_analyst_consensus(sym):
    try:
        t = yf.Ticker(sym)
        hist = t.history(period="1d")
        current = hist["Close"].iloc[-1] if not hist.empty else t.fast_info.get("lastPrice")
        
        rec = t.recommendations
        if rec is not None and not rec.empty:
            target = rec.get("targetMeanPrice", [None])[0] if "targetMeanPrice" in rec.columns else None
            return current, target
        return current, None
    except Exception:
        return None, None

current_price, mean_target = get_analyst_consensus(ticker_symbol)

if mean_target and current_price:
    upside = round(((mean_target - current_price) / current_price) * 100, 2)
    upside_str = f"{'+' if upside > 0 else ''}{upside}%"

    c1, c2 = st.columns(2)
    c1.metric("Current Price", f"${round(current_price, 2)}")
    c2.metric("Mean Price Target", f"${round(mean_target, 2)}", upside_str)
else:
    st.info("Analyst price target data is limited on this stream for the selected ticker.")
