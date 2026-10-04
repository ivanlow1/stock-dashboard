import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ta.volatility import BollingerBands
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📈 Interactive Stock Ticker Dashboard")

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
def get_peer_metrics_yq(symbols):
    yq = YQTicker(symbols)
    summary = yq.summary_detail
    fin = yq.financial_data
    stats = yq.key_stats
    
    metrics_list = []
    for sym in symbols:
        s_data = summary.get(sym, {}) if isinstance(summary, dict) else {}
        f_data = fin.get(sym, {}) if isinstance(fin, dict) else {}
        k_data = stats.get(sym, {}) if isinstance(stats, dict) else {}
        
        def fmt_val(val, scale=1):
            if isinstance(val, (int, float)) and not np.isnan(val):
                return round(val * scale, 2)
            return "N/A"

        metrics_list.append({
            "Ticker": sym,
            "P/E Ratio": fmt_val(s_data.get("trailingPE")),
            "Forward P/E": fmt_val(s_data.get("forwardPE")),
            "PEG Ratio": fmt_val(k_data.get("pegRatio")),
            "ROE (%)": fmt_val(f_data.get("returnOnEquity"), scale=100),
            "Gross Margin (%)": fmt_val(f_data.get("grossMargins"), scale=100),
            "Debt-to-Equity": fmt_val(f_data.get("debtToEquity"))
        })
    return pd.DataFrame(metrics_list).set_index("Ticker")

all_tickers = [ticker_symbol] + peers
with st.spinner("Fetching live peer metrics via YahooQuery..."):
    comparison_df = get_peer_metrics_yq(all_tickers)

st.dataframe(comparison_df)

# --- PANEL 4: WALL STREET ANALYST TARGETS & RATINGS ---
st.header("4. Wall Street Analyst Price Targets & Consensus")

@st.cache_data(ttl=3600)
def get_analysts_yq(sym):
    yq = YQTicker(sym)
    price_data = yq.price.get(sym, {}) if isinstance(yq.price, dict) else {}
    target_data = yq.financial_data.get(sym, {}) if isinstance(yq.financial_data, dict) else {}
    
    current = price_data.get("regularMarketPrice")
    mean_target = target_data.get("targetMeanPrice")
    low_target = target_data.get("targetLowPrice")
    high_target = target_data.get("targetHighPrice")
    
    return current, mean_target, low_target, high_target

with st.spinner("Fetching analyst price targets..."):
    current, mean_target, low_target, high_target = get_analysts_yq(ticker_symbol)

if mean_target and current and not isinstance(mean_target, str):
    upside = round(((mean_target - current) / current) * 100, 2)
    upside_str = f"{'+' if upside > 0 else ''}{upside}%"

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${round(current, 2)}")
    c2.metric("Mean Price Target", f"${round(mean_target, 2)}", upside_str)
    c3.metric("Target Range", f"${round(low_target, 2)} - ${round(high_target, 2)}")

    if low_target and high_target and current:
        st.subheader("Price Target Spread")
        st.write(f"**Low:** ${round(low_target, 2)} | **Current:** ${round(current, 2)} | **Mean Target:** ${round(mean_target, 2)} | **High:** ${round(high_target, 2)}")
        spread = high_target - low_target
        if spread > 0:
            pos = min(max((current - low_target) / spread, 0.0), 1.0)
            st.progress(pos, text=f"Current Price Position in Analyst Range: {round(pos * 100, 1)}%")
else:
    st.warning("Analyst price target data is currently unavailable for this ticker.")
