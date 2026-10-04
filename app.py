import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
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
try:
    news_items = ticker.news
except Exception:
    news_items = []

if news_items:
    news_data = []
    for item in news_items[:5]:
        content = item.get('content', {}) if isinstance(item.get('content'), dict) else {}
        title = item.get('title') or content.get('title') or 'No Title Available'
        link = item.get('link') or content.get('canonicalUrl', {}).get('url') or '#'
        
        score = analyzer.polarity_scores(title)['compound']
        sentiment = "🟢 Bullish" if score > 0.05 else ("🔴 Bearish" if score < -0.05 else "🟡 Neutral")
        
        news_data.append({"Title": f"[{title}]({link})", "Sentiment": sentiment, "Score": score})

    st.write(pd.DataFrame(news_data).to_html(escape=False), unsafe_allow_html=True)
else:
    st.write("No recent news found.")

# --- PANEL 3: COMPETITOR & INDUSTRY PEER METRICS ---
st.header("3. Competitor & Industry Peer Metrics")

with st.expander("📖 What do these competitor metrics mean?"):
    st.markdown("""
    - **Market Cap:** Total market value of the company's outstanding shares.
    - **52-Week High / Low:** The highest and lowest prices at which a stock has traded in the past year.
    - **Year High/Low Ratio:** Indicates how close the current stock price is relative to its 52-week peak.
    """)

@st.cache_data(ttl=3600)
def get_fast_peer_metrics(symbols):
    metrics_list = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            fast = t.fast_info
            
            last_price = fast.get("lastPrice")
            mcap = fast.get("marketCap")
            year_high = fast.get("yearHigh")
            year_low = fast.get("yearLow")
            
            mcap_str = f"${round(mcap / 1e9, 2)}B" if mcap else "N/A"
            price_str = f"${round(last_price, 2)}" if last_price else "N/A"
            high_str = f"${round(year_high, 2)}" if year_high else "N/A"
            low_str = f"${round(year_low, 2)}" if year_low else "N/A"

            metrics_list.append({
                "Ticker": sym,
                "Price": price_str,
                "Market Cap": mcap_str,
                "52W High": high_str,
                "52W Low": low_str
            })
        except Exception:
            metrics_list.append({
                "Ticker": sym, "Price": "N/A", "Market Cap": "N/A", "52W High": "N/A", "52W Low": "N/A"
            })
    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching peer valuation metrics via fast-info stream..."):
    comparison_df = get_fast_peer_metrics(all_tickers)

st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_analyst_consensus(sym):
    # Uses public open API endpoint to bypass scraping blocks
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=financialData"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            result = data.get('quoteSummary', {}).get('result', [])
            if result:
                financial_data = result[0].get('financialData', {})
                current = financial_data.get('currentPrice', {}).get('raw')
                target = financial_data.get('targetMeanPrice', {}).get('raw')
                low = financial_data.get('targetLowPrice', {}).get('raw')
                high = financial_data.get('targetHighPrice', {}).get('raw')
                return current, target, low, high
    except Exception:
        pass
    return None, None, None, None

current_price, mean_target, low_target, high_target = get_analyst_consensus(ticker_symbol)

if mean_target and current_price:
    upside = round(((mean_target - current_price) / current_price) * 100, 2)
    upside_str = f"{'+' if upside > 0 else ''}{upside}%"

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${current_price}")
    c2.metric("Mean Price Target", f"${mean_target}", upside_str)
    c3.metric("Target Range", f"${low_target} - ${high_target}" if low_target and high_target else "N/A")
else:
    st.warning("Analyst price target data is currently unavailable on standard public streams.")
