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
    - **P/E Ratio:** Current price relative to historical earnings. Lower = cheaper; Higher = higher growth expectations.
    - **Forward P/E:** Price relative to estimated future earnings for the next 12 months.
    - **PEG Ratio:** P/E adjusted for earnings growth rate. A PEG < 1.0 often indicates good value relative to growth.
    - **ROE (%):** Efficiency in generating profit from shareholder capital. Higher is generally better.
    - **Gross Margin (%):** Profit left over after core production costs. Reflects pricing power and efficiency.
    - **Debt-to-Equity:** Measures financial leverage. High values signal greater debt load and risk.
    """)

@st.cache_data(ttl=3600)
def get_finviz_metrics(symbols):
    metrics_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    
    for sym in symbols:
        url = f"https://finviz.com/quote.ashx?t={sym.upper()}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Extract key-value cells from Finviz snapshot table
                table_bytes = soup.find_all("td", class_="snapshot-td2")
                table_keys = soup.find_all("td", class_="snapshot-td2-cp")
                
                data_dict = {}
                for key_elem, val_elem in zip(table_keys, table_bytes):
                    data_dict[key_elem.text.strip()] = val_elem.text.strip()

                metrics_list.append({
                    "Ticker": sym,
                    "P/E Ratio": data_dict.get("P/E", "N/A"),
                    "Forward P/E": data_dict.get("Forward P/E", "N/A"),
                    "PEG Ratio": data_dict.get("PEG", "N/A"),
                    "ROE (%)": data_dict.get("ROE", "N/A"),
                    "Gross Margin (%)": data_dict.get("Gross Margin", "N/A"),
                    "Debt-to-Equity": data_dict.get("Debt/Eq", "N/A")
                })
            else:
                metrics_list.append({"Ticker": sym, "P/E Ratio": "N/A", "Forward P/E": "N/A", "PEG Ratio": "N/A", "ROE (%)": "N/A", "Gross Margin (%)": "N/A", "Debt-to-Equity": "N/A"})
        except Exception:
            metrics_list.append({"Ticker": sym, "P/E Ratio": "N/A", "Forward P/E": "N/A", "PEG Ratio": "N/A", "ROE (%)": "N/A", "Gross Margin (%)": "N/A", "Debt-to-Equity": "N/A"})
            
    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching live peer metrics from Finviz..."):
    comparison_df = get_finviz_metrics(all_tickers)

st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_finviz_analyst_targets(sym):
    url = f"https://finviz.com/quote.ashx?t={sym.upper()}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            table_bytes = soup.find_all("td", class_="snapshot-td2")
            table_keys = soup.find_all("td", class_="snapshot-td2-cp")
            
            data_dict = {}
            for key_elem, val_elem in zip(table_keys, table_bytes):
                data_dict[key_elem.text.strip()] = val_elem.text.strip()
                
            price_str = data_dict.get("Price", "N/A")
            target_str = data_dict.get("Target Price", "N/A")
            
            curr_price = float(price_str) if price_str != "N/A" else None
            mean_target = float(target_str) if target_str != "N/A" else None
            
            return curr_price, mean_target
    except Exception:
        pass
    return None, None

curr_price, mean_target = get_finviz_analyst_targets(ticker_symbol)

if mean_target and curr_price:
    upside = round(((mean_target - curr_price) / curr_price) * 100, 2)
    upside_str = f"{'+' if upside > 0 else ''}{upside}%"

    c1, c2 = st.columns(2)
    c1.metric("Current Price", f"${curr_price}")
    c2.metric("Mean Price Target", f"${mean_target}", upside_str)
else:
    st.warning("Analyst price target data is currently unavailable.")
