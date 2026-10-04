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

# --- FINNHUB API KEY ---
# Replace with your free key from https://finnhub.io/
FINNHUB_API_KEY = "YOUR_FINNHUB_API_KEY_HERE"

# --- SIDEBAR INPUTS ---
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="FTNT").upper()
peer_symbols = st.sidebar.text_input("Enter Peers (comma-separated):", value="MSFT, GOOGL, NVDA")
peers = [p.strip().upper() for p in peer_symbols.split(",")]

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
    - **P/E Ratio:** Current price relative to historical earnings. Lower = cheaper; Higher = higher growth expectations.
    - **Forward P/E:** Price relative to estimated future earnings for the next 12 months.
    - **PEG Ratio:** P/E adjusted for earnings growth rate. A PEG < 1.0 often indicates good value relative to growth.
    - **ROE (%):** Efficiency in generating profit from shareholder capital. Higher is generally better.
    - **Gross Margin (%):** Profit left over after core production costs. Reflects pricing power and efficiency.
    - **Debt-to-Equity:** Measures financial leverage. High values signal greater debt load and risk.
    """)

@st.cache_data(ttl=3600)
def get_finnhub_metrics(sym):
    url = f"https://finnhub.io/api/v1/stock/metric?symbol={sym}&metric=all&token={FINNHUB_API_KEY}"
    try:
        res = requests.get(url).json()
        metrics = res.get("metric", {})
        
        return {
            "Ticker": sym,
            "P/E Ratio": round(metrics.get("peBasicExclExtraTTM"), 2) if metrics.get("peBasicExclExtraTTM") else "N/A",
            "Forward P/E": round(metrics.get("peNormalizedAnnual"), 2) if metrics.get("peNormalizedAnnual") else "N/A",
            "ROE (%)": round(metrics.get("roeTTM"), 2) if metrics.get("roeTTM") else "N/A",
            "Gross Margin (%)": round(metrics.get("grossMarginTTM"), 2) if metrics.get("grossMarginTTM") else "N/A",
            "Debt-to-Equity": round(metrics.get("totalDebtToEquityQuarterly"), 2) if metrics.get("totalDebtToEquityQuarterly") else "N/A"
        }
    except Exception:
        return {"Ticker": sym, "P/E Ratio": "N/A", "Forward P/E": "N/A", "ROE (%)": "N/A", "Gross Margin (%)": "N/A", "Debt-to-Equity": "N/A"}

all_tickers = [ticker_symbol] + peers
metrics_list = []

with st.spinner("Fetching live peer metrics via Finnhub..."):
    for s in all_tickers:
        metrics_list.append(get_finnhub_metrics(s))

comparison_df = pd.DataFrame(metrics_list).set_index("Ticker")
st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_finnhub_analysts(sym):
    target_url = f"https://finnhub.io/api/v1/stock/price-target?symbol={sym}&token={FINNHUB_API_KEY}"
    quote_url = f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_API_KEY}"
    
    try:
        target_res = requests.get(target_url).json()
        quote_res = requests.get(quote_url).json()
        
        current_price = quote_res.get("c")
        mean_target = target_res.get("targetMean")
        low_target = target_res.get("targetLow")
        high_target = target_res.get("targetHigh")
        
        return {
            "current": current_price,
            "mean": mean_target,
            "low": low_target,
            "high": high_target
        }
    except Exception:
        return None

analyst_data = get_finnhub_analysts(ticker_symbol)

if analyst_data and analyst_data.get("mean"):
    current = analyst_data["current"]
    mean_target = analyst_data["mean"]
    low_target = analyst_data["low"]
    high_target = analyst_data["high"]

    upside = round(((mean_target - current) / current) * 100, 2) if current and mean_target else "N/A"
    upside_str = f"{'+' if isinstance(upside, float) and upside > 0 else ''}{upside}%"

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${current}" if current else "N/A")
    c2.metric("Mean Price Target", f"${mean_target}" if mean_target else "N/A", upside_str)
    c3.metric("Target Range", f"${low_target} - ${high_target}" if low_target and high_target else "N/A")

    if low_target and high_target and current:
        st.subheader("Price Target Spread")
        st.write(f"**Low:** ${low_target} | **Current:** ${current} | **Mean Target:** ${mean_target} | **High:** ${high_target}")
        spread = high_target - low_target
        if spread > 0:
            pos = min(max((current - low_target) / spread, 0.0), 1.0)
            st.progress(pos, text=f"Current Price Position in Analyst Range: {round(pos * 100, 1)}%")
else:
    st.warning("Analyst price target data is currently unavailable for this ticker.")
