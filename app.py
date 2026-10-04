import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
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
    - **52W High / Low:** Highest and lowest prices at which the stock traded over the past year.
    - **P/E Ratio:** Current price relative to historical earnings. Lower = cheaper; Higher = higher growth expectations.
    - **Forward P/E:** Price relative to estimated future earnings for the next 12 months.
    - **PEG Ratio:** P/E adjusted for earnings growth rate. A PEG < 1.0 often indicates good value relative to growth.
    - **ROE (%):** Return on Equity; efficiency in generating profit from shareholder capital.
    - **Gross Margin (%):** Percentage of revenue kept after core production costs.
    - **Debt-to-Equity:** Financial leverage ratio; higher values indicate greater debt load.
    """)

@st.cache_data(ttl=3600)
def get_expanded_peer_metrics(symbols):
    metrics_list = []

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            
            # 1. Fast Info Stream Data
            fast = t.fast_info
            last_price = fast.get("lastPrice")
            mcap = fast.get("marketCap")
            year_high = fast.get("yearHigh")
            year_low = fast.get("yearLow")
            
            price_str = f"${round(last_price, 2)}" if last_price else "N/A"
            mcap_str = f"${round(mcap / 1e9, 2)}B" if mcap else "N/A"
            high_str = f"${round(year_high, 2)}" if year_high else "N/A"
            low_str = f"${round(year_low, 2)}" if year_low else "N/A"

            # 2. Comprehensive Info Object extraction
            info = t.info
            
            def fmt_val(val, is_pct=False, scale=1):
                if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                    return f"{round(val * scale, 2)}%" if is_pct else str(round(val * scale, 2))
                return "N/A"

            pe_ratio = fmt_val(info.get("trailingPE"))
            fwd_pe = fmt_val(info.get("forwardPE"))
            peg_ratio = fmt_val(info.get("pegRatio"))
            roe = fmt_val(info.get("returnOnEquity"), is_pct=True, scale=100)
            gross_margin = fmt_val(info.get("grossMargins"), is_pct=True, scale=100)
            debt_to_eq = fmt_val(info.get("debtToEquity"))

            metrics_list.append({
                "Ticker": sym,
                "Price": price_str,
                "Market Cap": mcap_str,
                "52W High": high_str,
                "52W Low": low_str,
                "P/E": pe_ratio,
                "Forward P/E": fwd_pe,
                "PEG": peg_ratio,
                "ROE": roe,
                "Gross Margin": gross_margin,
                "Debt/Equity": debt_to_eq
            })
        except Exception:
            metrics_list.append({
                "Ticker": sym, "Price": "N/A", "Market Cap": "N/A", "52W High": "N/A", "52W Low": "N/A",
                "P/E": "N/A", "Forward P/E": "N/A", "PEG": "N/A", "ROE": "N/A", "Gross Margin": "N/A", "Debt/Equity": "N/A"
            })

    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching expanded peer metrics..."):
    comparison_df = get_expanded_peer_metrics(all_tickers)

st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_analyst_consensus(sym):
    try:
        t = yf.Ticker(sym)
        info = t.info
        current = info.get("currentPrice") or info.get("regularMarketPrice") or t.fast_info.get("lastPrice")
        target = info.get("targetMeanPrice")
        low = info.get("targetLowPrice")
        high = info.get("targetHighPrice")
        return current, target, low, high
    except Exception:
        return None, None, None, None

current_price, mean_target, low_target, high_target = get_analyst_consensus(ticker_symbol)

if mean_target and current_price:
    upside = round(((mean_target - current_price) / current_price) * 100, 2)
    upside_str = f"{'+' if upside > 0 else ''}{upside}%"

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${round(current_price, 2)}")
    c2.metric("Mean Price Target", f"${round(mean_target, 2)}", upside_str)
    c3.metric("Target Range", f"${round(low_target, 2)} - ${round(high_target, 2)}" if low_target and high_target else "N/A")
else:
    st.warning("Analyst price target data is currently unavailable.")
