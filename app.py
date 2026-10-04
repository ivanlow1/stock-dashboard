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

# --- PANEL 3 & 4: COMPETITOR & INDUSTRY PEER METRICS ---
st.header("3. Competitor & Industry Peer Metrics")

@st.cache_data(ttl=3600)
def get_metrics_fast(sym):
    try:
        t = yf.Ticker(sym)
        
        # fast_info works reliably on Streamlit Cloud servers
        fast = t.fast_info
        
        # Retrieve basic valuation/price metrics safely
        mkt_cap = fast.get("market_cap", np.nan)
        last_price = fast.get("last_price", np.nan)
        
        # Fetch financial metrics directly from financial statements
        eps = np.nan
        pe_ratio = np.nan
        
        try:
            info_data = t.info
            pe_ratio = info_data.get("trailingPE", np.nan)
            forward_pe = info_data.get("forwardPE", np.nan)
            peg_ratio = info_data.get("pegRatio", np.nan)
            roe = info_data.get("returnOnEquity", np.nan)
            gross_margin = info_data.get("grossMargins", np.nan)
            debt_equity = info_data.get("debtToEquity", np.nan)
        except Exception:
            pe_ratio, forward_pe, peg_ratio = np.nan, np.nan, np.nan
            roe, gross_margin, debt_equity = np.nan, np.nan, np.nan

        return {
            "Ticker": sym,
            "Market Cap ($B)": round(mkt_cap / 1e9, 2) if mkt_cap and not np.isnan(mkt_cap) else np.nan,
            "Price ($)": round(last_price, 2) if last_price and not np.isnan(last_price) else np.nan,
            "P/E Ratio": round(pe_ratio, 2) if pe_ratio and not np.isnan(pe_ratio) else "N/A",
            "Forward P/E": round(forward_pe, 2) if forward_pe and not np.isnan(forward_pe) else "N/A",
            "PEG Ratio": round(peg_ratio, 2) if peg_ratio and not np.isnan(peg_ratio) else "N/A",
            "ROE (%)": round(roe * 100, 2) if roe and not np.isnan(roe) else "N/A",
            "Gross Margin (%)": round(gross_margin * 100, 2) if gross_margin and not np.isnan(gross_margin) else "N/A",
            "Debt-to-Equity": round(debt_equity, 2) if debt_equity and not np.isnan(debt_equity) else "N/A"
        }
    except Exception:
        return {"Ticker": sym, "Market Cap ($B)": np.nan, "Price ($)": np.nan, "P/E Ratio": "N/A"}

all_tickers = [ticker_symbol] + peers
metrics_list = []

with st.spinner("Fetching live peer metrics..."):
    for s in all_tickers:
        metrics_list.append(get_metrics_fast(s))

comparison_df = pd.DataFrame(metrics_list).set_index("Ticker")
st.dataframe(comparison_df)
