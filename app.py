import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ta.volatility import BollingerBands
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📈 Interactive Stock Ticker Dashboard")

# --- SIDEBAR INPUTS ---
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol:", value="AAPL").upper()
peer_symbols = st.sidebar.text_input("Enter Peers (comma-separated):", value="MSFT, GOOGL, NVDA")
peers = [p.strip().upper() for p in peer_symbols.split(",")]

ticker = yf.Ticker(ticker_symbol)

# --- PANEL 1: INDICATIVE FUTURE TRADING BANDS ---
st.header(f"1. Price & Trading Bands ({ticker_symbol})")

hist = ticker.history(period="1y")

if not hist.empty:
    # Calculate Bollinger Bands
    indicator_bb = BollingerBands(close=hist["Close"], window=20, window_dev=2)
    hist["BB_Upper"] = indicator_bb.bollinger_hband()
    hist["BB_Lower"] = indicator_bb.bollinger_lband()
    hist["SMA_20"] = indicator_bb.bollinger_mavg()

    # Plot Candlestick with Bands
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
news_items = ticker.news

if news_items:
    news_data = []
    for item in news_items[:5]:
        title = item.get('title') or item.get('content', {}).get('title', 'N/A')
        link = item.get('link') or item.get('content', {}).get('canonicalUrl', {}).get('url', '#')
        
        # Calculate sentiment score
        score = analyzer.polarity_scores(title)['compound']
        sentiment = "🟢 Bullish" if score > 0.05 else ("🔴 Bearish" if score < -0.05 else "🟡 Neutral")
        
        news_data.append({"Title": f"[{title}]({link})", "Sentiment": sentiment, "Score": score})

    st.write(pd.DataFrame(news_data).to_html(escape=False), unsafe_allow_html=True)
else:
    st.write("No recent news found.")

# --- PANEL 3 & 4: COMPETITOR & INDUSTRY METRICS ---
st.header("3. Competitor & Industry Peer Metrics")

def get_metrics(sym):
    info = yf.Ticker(sym).info
    return {
        "Ticker": sym,
        "P/E Ratio": info.get("trailingPE", np.nan),
        "Forward P/E": info.get("forwardPE", np.nan),
        "PEG Ratio": info.get("pegRatio", np.nan),
        "ROE (%)": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else np.nan,
        "Gross Margin (%)": round(info.get("grossMargins", 0) * 100, 2) if info.get("grossMargins") else np.nan,
        "Debt-to-Equity": info.get("debtToEquity", np.nan)
    }

all_tickers = [ticker_symbol] + peers
metrics_list = [get_metrics(s) for s in all_tickers]
comparison_df = pd.DataFrame(metrics_list).set_index("Ticker")

st.dataframe(comparison_df.style.highlight_max(axis=0, color="lightgreen").highlight_min(axis=0, color="lightpink"))