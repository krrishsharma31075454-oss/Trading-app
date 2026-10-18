# ============================================
# 📱 TRADING ANALYSIS APP - MOBILE VERSION
# Complete with Historical Data + Candlestick Patterns + Trading Signals
# Version: 2.1 (Secrets-ready + Bug fixes)
# ============================================

import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import traceback

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="📱 Trading Analysis Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile optimization
st.markdown("""
<style>
    .metric-card {
        background-color: #1a1a2e;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .signal-buy {
        background-color: #00c853;
        color: white;
        padding: 2px 8px;
        border-radius: 5px;
        font-weight: bold;
    }
    .signal-sell {
        background-color: #ff1744;
        color: white;
        padding: 2px 8px;
        border-radius: 5px;
        font-weight: bold;
    }
    .signal-wait {
        background-color: #ff9100;
        color: white;
        padding: 2px 8px;
        border-radius: 5px;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# API KEY CONFIGURATION (SECURE - uses Streamlit Secrets)
# ============================================
class APIManager:
    """Manage API keys securely from Streamlit secrets or environment variables"""
    
    def __init__(self):
        # Priority: Streamlit secrets → environment variables → empty
        try:
            self.twelvedata_key = st.secrets.get("TWELVEDATA_API_KEY", "")
        except Exception:
            self.twelvedata_key = os.getenv("TWELVEDATA_API_KEY", "")
            
        try:
            self.fastforex_key = st.secrets.get("FASTFOREX_API_KEY", "")
        except Exception:
            self.fastforex_key = os.getenv("FASTFOREX_API_KEY", "")
        
    def validate_keys(self):
        return {
            "twelvedata": bool(self.twelvedata_key),
            "fastforex": bool(self.fastforex_key)
        }

api_manager = APIManager()

# ============================================
# TWELVEDATA API - Stock, Forex, Crypto Data
# ============================================
def fetch_twelvedata_candles(symbol, interval="15min", outputsize=200):
    """Fetch candlestick data from TwelveData"""
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_manager.twelvedata_key,
        "format": "JSON"
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        data = response.json()
        
        if "values" in data:
            df = pd.DataFrame(data["values"])
            # Standardize column names
            df = df.rename(columns={
                "datetime": "datetime",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close"
            })
            df["datetime"] = pd.to_datetime(df["datetime"])
            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["open", "high", "low", "close"])
            return df.sort_values("datetime").reset_index(drop=True)
        
        # Handle error messages from API
        if "message" in data:
            st.error(f"TwelveData: {data['message']}")
        return None
    except Exception as e:
        st.error(f"TwelveData Error: {str(e)}")
        return None


def fetch_twelvedata_quote(symbol):
    """Fetch current quote from TwelveData"""
    url = "https://api.twelvedata.com/quote"
    params = {
        "symbol": symbol,
        "apikey": api_manager.twelvedata_key
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if "close" in data:
            return data
        return None
    except Exception:
        return None


# ============================================
# FASTFOREX API (mainly for live rates)
# ============================================
def fetch_fastforex_rates(from_currency="USD"):
    """Fetch forex rates from FastForex"""
    if not api_manager.fastforex_key:
        return None
    url = "https://api.fastforex.io/fetch-all"
    params = {
        "from": from_currency,
        "api_key": api_manager.fastforex_key
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data.get("results", {})
    except Exception:
        return None


# ============================================
# CANDLESTICK PATTERN DETECTION
# ============================================
class CandlestickAnalyzer:
    """Detect major candlestick patterns"""
    
    def __init__(self, df):
        self.df = df.copy()
        self.patterns = []
        
    def analyze_patterns(self):
        """Analyze candlestick patterns (robust version)"""
        self.patterns = []
        
        if len(self.df) < 3:
            return self.patterns
        
        for i in range(2, len(self.df)):
            try:
                row = self.df.iloc[i]
                prev = self.df.iloc[i-1]
                prev2 = self.df.iloc[i-2]
                
                open_ = float(row["open"])
                high_ = float(row["high"])
                low_ = float(row["low"])
                close_ = float(row["close"])
                
                prev_open = float(prev["open"])
                prev_close = float(prev["close"])
                prev_high = float(prev["high"])
                prev_low = float(prev["low"])
                
                prev2_open = float(prev2["open"])
                prev2_close = float(prev2["close"])
                
                body = abs(close_ - open_)
                full_range = high_ - low_ if high_ != low_ else 0.0001
                upper_shadow = high_ - max(open_, close_)
                lower_shadow = min(open_, close_) - low_
                
                prev_body = abs(prev_close - prev_open)
                
                is_bullish = close_ > open_
                is_bearish = close_ < open_
                prev_bullish = prev_close > prev_open
                prev_bearish = prev_close < prev_open
                prev2_bullish = prev2_close > prev2_open
                
                # ---------- SINGLE CANDLE ----------
                # Doji
                if body / full_range < 0.1:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Doji",
                        "category": "Indecision",
                        "signal": "Wait",
                        "strength": "Medium",
                        "description": "Open ≈ Close – market indecision"
                    })
                
                # Dragonfly Doji (bullish)
                if lower_shadow > body * 2.5 and upper_shadow < body * 0.4 and body / full_range < 0.15:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Dragonfly Doji",
                        "category": "Bullish Reversal",
                        "signal": "Buy",
                        "strength": "Strong",
                        "description": "Long lower shadow – potential bottom"
                    })
                
                # Gravestone Doji (bearish)
                if upper_shadow > body * 2.5 and lower_shadow < body * 0.4 and body / full_range < 0.15:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Gravestone Doji",
                        "category": "Bearish Reversal",
                        "signal": "Sell",
                        "strength": "Strong",
                        "description": "Long upper shadow – potential top"
                    })
                
                # Hammer
                if lower_shadow > body * 2 and upper_shadow < body * 0.5 and is_bullish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Hammer",
                        "category": "Bullish Reversal",
                        "signal": "Buy",
                        "strength": "Strong",
                        "description": "Bullish reversal after decline"
                    })
                
                # Inverted Hammer
                if upper_shadow > body * 2 and lower_shadow < body * 0.5 and is_bullish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Inverted Hammer",
                        "category": "Bullish Reversal",
                        "signal": "Buy",
                        "strength": "Medium",
                        "description": "Potential bullish reversal"
                    })
                
                # Hanging Man
                if lower_shadow > body * 2 and upper_shadow < body * 0.5 and is_bearish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Hanging Man",
                        "category": "Bearish Reversal",
                        "signal": "Sell",
                        "strength": "Strong",
                        "description": "Bearish reversal after uptrend"
                    })
                
                # Shooting Star
                if upper_shadow > body * 2 and lower_shadow < body * 0.5 and is_bearish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Shooting Star",
                        "category": "Bearish Reversal",
                        "signal": "Sell",
                        "strength": "Strong",
                        "description": "Rejection at resistance"
                    })
                
                # Marubozu
                if upper_shadow < full_range * 0.05 and lower_shadow < full_range * 0.05:
                    if is_bullish:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bullish Marubozu",
                            "category": "Continuation",
                            "signal": "Strong Buy",
                            "strength": "Very Strong",
                            "description": "Strong bullish momentum (almost no shadows)"
                        })
                    else:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bearish Marubozu",
                            "category": "Continuation",
                            "signal": "Strong Sell",
                            "strength": "Very Strong",
                            "description": "Strong bearish momentum (almost no shadows)"
                        })
                
                # ---------- TWO CANDLE ----------
                # Bullish Engulfing
                if is_bullish and prev_bearish:
                    if open_ < prev_close and close_ > prev_open and body > prev_body:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bullish Engulfing",
                            "category": "Bullish Reversal",
                            "signal": "Strong Buy",
                            "strength": "Very Strong",
                            "description": "Bullish candle engulfs previous bearish candle"
                        })
                
                # Bearish Engulfing
                if is_bearish and prev_bullish:
                    if open_ > prev_close and close_ < prev_open and body > prev_body:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bearish Engulfing",
                            "category": "Bearish Reversal",
                            "signal": "Strong Sell",
                            "strength": "Very Strong",
                            "description": "Bearish candle engulfs previous bullish candle"
                        })
                
                # Piercing Line
                if is_bullish and prev_bearish:
                    mid_point = (prev_open + prev_close) / 2
                    if open_ < prev_low and close_ > mid_point:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Piercing Line",
                            "category": "Bullish Reversal",
                            "signal": "Buy",
                            "strength": "Medium",
                            "description": "Bullish recovery into previous body"
                        })
                
                # Dark Cloud Cover
                if is_bearish and prev_bullish:
                    mid_point = (prev_open + prev_close) / 2
                    if open_ > prev_high and close_ < mid_point:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Dark Cloud Cover",
                            "category": "Bearish Reversal",
                            "signal": "Sell",
                            "strength": "Medium",
                            "description": "Bearish counter-attack"
                        })
                
                # Harami
                if body < prev_body * 0.5:
                    if is_bullish and prev_bearish and open_ > prev_close and close_ < prev_open:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bullish Harami",
                            "category": "Bullish Reversal",
                            "signal": "Buy",
                            "strength": "Medium",
                            "description": "Small bullish candle inside previous body"
                        })
                    elif is_bearish and prev_bullish and open_ < prev_close and close_ > prev_open:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Bearish Harami",
                            "category": "Bearish Reversal",
                            "signal": "Sell",
                            "strength": "Medium",
                            "description": "Small bearish candle inside previous body"
                        })
                
                # ---------- THREE CANDLE ----------
                # Morning Star (simplified)
                if prev_bearish and is_bullish and prev_body > body * 1.5:
                    if close_ > (prev_open + prev_close) / 2:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Morning Star",
                            "category": "Bullish Reversal",
                            "signal": "Strong Buy",
                            "strength": "Strong",
                            "description": "Three-candle bullish reversal"
                        })
                
                # Evening Star (simplified)
                if prev_bullish and is_bearish and prev_body > body * 1.5:
                    if close_ < (prev_open + prev_close) / 2:
                        self.patterns.append({
                            "time": row["datetime"],
                            "pattern": "Evening Star",
                            "category": "Bearish Reversal",
                            "signal": "Strong Sell",
                            "strength": "Strong",
                            "description": "Three-candle bearish reversal"
                        })
                
                # Three White Soldiers
                if (is_bullish and prev_bullish and prev2_bullish and
                    close_ > prev_close and prev_close > prev2_close):
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Three White Soldiers",
                        "category": "Bullish Continuation",
                        "signal": "Strong Buy",
                        "strength": "Very Strong",
                        "description": "Three consecutive strong bullish candles"
                    })
                
                # Three Black Crows
                if (is_bearish and prev_bearish and not prev2_bullish and
                    close_ < prev_close and prev_close < prev2_close):
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Three Black Crows",
                        "category": "Bearish Continuation",
                        "signal": "Strong Sell",
                        "strength": "Very Strong",
                        "description": "Three consecutive strong bearish candles"
                    })
                
                # Tweezer Bottom / Top
                if abs(low_ - prev_low) / full_range < 0.02 and is_bullish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Tweezer Bottom",
                        "category": "Bullish Reversal",
                        "signal": "Buy",
                        "strength": "Medium",
                        "description": "Matching lows – support"
                    })
                if abs(high_ - prev_high) / full_range < 0.02 and is_bearish:
                    self.patterns.append({
                        "time": row["datetime"],
                        "pattern": "Tweezer Top",
                        "category": "Bearish Reversal",
                        "signal": "Sell",
                        "strength": "Medium",
                        "description": "Matching highs – resistance"
                    })
                    
            except Exception:
                continue   # skip bad candles
        
        return self.patterns


# ============================================
# TECHNICAL INDICATORS
# ============================================
class TechnicalIndicators:
    
    @staticmethod
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_sma(series, period=20):
        return series.rolling(window=period).mean()
    
    @staticmethod
    def calculate_ema(series, period=12):
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_macd(series):
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist
    
    @staticmethod
    def calculate_bollinger(series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + std * std_dev
        lower = sma - std * std_dev
        return upper, sma, lower


# ============================================
# SIGNAL GENERATOR
# ============================================
class SignalGenerator:
    
    def __init__(self, df, patterns):
        self.df = df
        self.patterns = patterns
        
    def analyze(self):
        score = 0
        reasons = []
        
        latest = self.df.iloc[-1]
        price = float(latest["close"])
        
        # Indicators
        rsi = TechnicalIndicators.calculate_rsi(self.df["close"])
        sma20 = TechnicalIndicators.calculate_sma(self.df["close"], 20)
        sma50 = TechnicalIndicators.calculate_sma(self.df["close"], 50)
        macd, macd_signal, _ = TechnicalIndicators.calculate_macd(self.df["close"])
        bb_upper, _, bb_lower = TechnicalIndicators.calculate_bollinger(self.df["close"])
        
        current_rsi = rsi.iloc[-1]
        current_sma20 = sma20.iloc[-1]
        current_sma50 = sma50.iloc[-1]
        current_macd = macd.iloc[-1]
        current_macd_sig = macd_signal.iloc[-1]
        current_bb_u = bb_upper.iloc[-1]
        current_bb_l = bb_lower.iloc[-1]
        
        # RSI
        if pd.notna(current_rsi):
            if current_rsi < 30:
                score += 2
                reasons.append(f"RSI Oversold ({current_rsi:.1f}) → Buy bias")
            elif current_rsi > 70:
                score -= 2
                reasons.append(f"RSI Overbought ({current_rsi:.1f}) → Sell bias")
            else:
                reasons.append(f"RSI Neutral ({current_rsi:.1f})")
        
        # MACD
        if pd.notna(current_macd) and pd.notna(current_macd_sig):
            if current_macd > current_macd_sig:
                score += 1
                reasons.append("MACD above Signal → Bullish")
            else:
                score -= 1
                reasons.append("MACD below Signal → Bearish")
        
        # Moving Averages
        if pd.notna(current_sma20):
            if price > current_sma20:
                score += 1
                reasons.append("Price above SMA-20 → Bullish")
            else:
                score -= 1
                reasons.append("Price below SMA-20 → Bearish")
        
        if pd.notna(current_sma50) and pd.notna(current_sma20):
            if current_sma20 > current_sma50:
                score += 1
                reasons.append("SMA-20 > SMA-50 → Uptrend")
            else:
                score -= 1
                reasons.append("SMA-20 < SMA-50 → Downtrend")
        
        # Bollinger
        if pd.notna(current_bb_l) and pd.notna(current_bb_u):
            if price < current_bb_l:
                score += 1
                reasons.append("Price below lower Bollinger → Oversold")
            elif price > current_bb_u:
                score -= 1
                reasons.append("Price above upper Bollinger → Overbought")
        
        # Recent patterns (last 8)
        for p in self.patterns[-8:]:
            if p["signal"] == "Strong Buy":
                score += 2
                reasons.append(f"🔥 {p['pattern']} (Strong Buy)")
            elif p["signal"] == "Buy":
                score += 1
                reasons.append(f"🔥 {p['pattern']} (Buy)")
            elif p["signal"] == "Strong Sell":
                score -= 2
                reasons.append(f"🔥 {p['pattern']} (Strong Sell)")
            elif p["signal"] == "Sell":
                score -= 1
                reasons.append(f"🔥 {p['pattern']} (Sell)")
        
        # Final recommendation
        if score >= 5:
            rec = "🚀 STRONG BUY"
        elif score >= 2:
            rec = "📈 BUY"
        elif score <= -5:
            rec = "🚨 STRONG SELL"
        elif score <= -2:
            rec = "📉 SELL"
        else:
            rec = "⏳ HOLD / NEUTRAL"
        
        return {
            "recommendation": rec,
            "score": score,
            "reasons": reasons,
            "price": price,
            "rsi": current_rsi if pd.notna(current_rsi) else None,
            "pattern_count": len(self.patterns)
        }


# ============================================
# CHART
# ============================================
def create_chart(df):
    if df is None or len(df) == 0:
        return None
    
    df = df.copy()
    df["SMA_20"] = df["close"].rolling(20).mean()
    df["SMA_50"] = df["close"].rolling(50).mean()
    
    bb_u, bb_m, bb_l = TechnicalIndicators.calculate_bollinger(df["close"])
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color="#00c853",
        decreasing_line_color="#ff1744",
        name="Price"
    ))
    
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["SMA_20"],
        line=dict(color="orange", width=1.5),
        name="SMA-20"
    ))
    
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["SMA_50"],
        line=dict(color="#2196f3", width=1.5),
        name="SMA-50"
    ))
    
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=bb_u,
        line=dict(color="purple", width=1, dash="dash"),
        name="BB Upper", showlegend=True
    ))
    
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=bb_l,
        line=dict(color="purple", width=1, dash="dash"),
        name="BB Lower", showlegend=True
    ))
    
    fig.update_layout(
        title="Price Chart + Indicators",
        yaxis_title="Price",
        height=520,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig


# ============================================
# MAIN APP
# ============================================
def main():
    st.title("📱 Trading Analysis Pro")
    st.caption("Multi-asset • Candlestick patterns • Technical signals")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.subheader("API Status")
        keys = api_manager.validate_keys()
        st.write("TwelveData:", "✅" if keys["twelvedata"] else "❌ Missing")
        st.write("FastForex:", "✅" if keys["fastforex"] else "❌ Missing")
        
        if not keys["twelvedata"]:
            st.error("Add TWELVEDATA_API_KEY in Streamlit Secrets")
        
        st.subheader("Analysis")
        interval = st.selectbox(
            "Timeframe",
            ["1min", "5min", "15min", "30min", "1h", "4h", "1day"],
            index=2
        )
        outputsize = st.slider("Candles", 50, 300, 150)
        
        st.info("This app works best on phone in landscape mode for charts.")
    
    # Main inputs
    col1, col2 = st.columns([2, 1])
    with col1:
        symbol = st.text_input("Symbol (e.g. EUR/USD, BTC/USD, AAPL)", value="EUR/USD")
    with col2:
        market = st.selectbox("Market", ["FOREX", "CRYPTO", "STOCKS"])
    
    analyze = st.button("🚀 Analyze Now", type="primary", use_container_width=True)
    
    if analyze:
        if not api_manager.twelvedata_key:
            st.error("TwelveData API key is missing. Add it in Streamlit Cloud → App settings → Secrets.")
            st.stop()
        
        with st.spinner("Fetching data & detecting patterns..."):
            try:
                # Fetch data (TwelveData works for Forex, Crypto & Stocks)
                df = fetch_twelvedata_candles(symbol, interval=interval, outputsize=outputsize)
                
                if df is None or len(df) < 30:
                    st.error("Could not fetch enough data. Check symbol and API key/credits.")
                    st.stop()
                
                # Patterns
                analyzer = CandlestickAnalyzer(df)
                patterns = analyzer.analyze_patterns()
                
                # Signals
                signal_gen = SignalGenerator(df, patterns)
                result = signal_gen.analyze()
                
                # ========== RESULTS ==========
                st.subheader("📊 Results")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Signal", result["recommendation"], delta=f"Score {result['score']}")
                m2.metric("Price", f"{result['price']:.5f}")
                rsi_val = result["rsi"]
                m3.metric("RSI (14)", f"{rsi_val:.1f}" if rsi_val else "N/A")
                m4.metric("Patterns Found", result["pattern_count"])
                
                # Chart
                st.subheader("📈 Chart")
                fig = create_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Patterns list
                st.subheader("🕯️ Recent Candlestick Patterns")
                if patterns:
                    for p in patterns[-8:][::-1]:
                        badge = {
                            "Strong Buy": "<span class='signal-buy'>STRONG BUY</span>",
                            "Buy": "<span class='signal-buy'>BUY</span>",
                            "Strong Sell": "<span class='signal-sell'>STRONG SELL</span>",
                            "Sell": "<span class='signal-sell'>SELL</span>",
                            "Wait": "<span class='signal-wait'>WAIT</span>"
                        }.get(p["signal"], "")
                        
                        st.markdown(f"""
                        <div style="padding:8px 12px; margin:4px 0; border-left:4px solid #555; background:#1e1e2e; border-radius:6px;">
                            <b>{p['pattern']}</b> <small>({p['category']})</small>
                            <span style="float:right">{badge}</span>
                            <div style="clear:both; font-size:0.85em; color:#aaa; margin-top:2px;">
                                {p['description']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No strong patterns detected in the recent candles.")
                
                # Reasons
                st.subheader("💡 Why this signal?")
                for r in result["reasons"]:
                    st.write("• " + r)
                
                st.success(f"**Final Recommendation: {result['recommendation']}**")
                
                st.warning("⚠️ For educational purposes only. Not financial advice. Always do your own research.")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.code(traceback.format_exc())
    
    # Help section
    with st.expander("📚 How to use"):
        st.markdown("""
        **Symbols examples**
        - Forex: `EUR/USD`, `GBP/USD`, `USD/JPY`, `USD/INR`
        - Crypto: `BTC/USD`, `ETH/USD`, `SOL/USD`
        - Stocks: `AAPL`, `TSLA`, `MSFT`, `GOOGL`
        
        **Timeframes**
        - Scalping → 1min / 5min
        - Intraday → 15min / 30min / 1h
        - Swing → 4h / 1day
        
        **Signal meaning**
        - Score ≥ 5 → Strong Buy
        - Score 2–4 → Buy
        - Score -1 to 1 → Hold
        - Score -2 to -4 → Sell
        - Score ≤ -5 → Strong Sell
        """)


if __name__ == "__main__":
    main()
