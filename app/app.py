import sys
import pandas as pd  
from pathlib import Path
import datetime
import streamlit as st
import plotly.express as px

# Ensure the backend package is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from backend directly
from backend import (optimize_portfolio, calculate_series_metrics, get_data, get_bmk, get_fx)

# Initialize session state keys if they don't exist
if 'optimized_data' not in st.session_state:
    st.session_state.optimized_data = None

st.set_page_config(page_title="Portfolio Optimizer", layout="wide")
st.title("🎯 Portfolio Optimizer")
st.sidebar.header("User Inputs")

# Data caching
@st.cache_data
def cached_get_data(ticker_list, start_date, end_date):
    return get_data(ticker_list, start_date, end_date)

# User Inputs
tickers = st.sidebar.text_input("Enter Tickers (comma separated)", value="BAC, BK, C, GS, JPM, MS, SST, WFC")

st.sidebar.subheader("Benchmark")
BENCHMARKS = {"S&P 500": "SPY", "MSCI ACWI": "ACWI"}
benchmark_name = st.sidebar.selectbox("Benchmark", options=list(BENCHMARKS.keys()))
benchmark_ticker = BENCHMARKS[benchmark_name]

st.sidebar.subheader("Reporting currency")
reporting_currency = st.sidebar.selectbox("Reporting currency", options=["USD", "GBP", "EUR"], index=0)

# Dates inputs with validation
today = datetime.date.today()
one_year_ago = today - datetime.timedelta(days=365)
start_date = st.sidebar.date_input("Start Date", value=one_year_ago, max_value=today)
end_date = st.sidebar.date_input("End Date", value=today - datetime.timedelta(days=1), min_value=start_date, max_value=today - datetime.timedelta(days=1))

if st.sidebar.button("Optimize"):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        st.error("Please enter at least one valid ticker.")
    else:
        try:
            # 1. Portfolio Optimization
            df_prices = cached_get_data(ticker_list, start_date, end_date)
            weights, port_perf = optimize_portfolio(df_prices)
            
            # 2. Portfolio Cumulative Returns
            port_returns = df_prices.pct_change().dropna()
            port_daily_rets = (port_returns * pd.Series(weights)).sum(axis=1)
            port_cum_rets = (1 + port_daily_rets).cumprod() - 1
            
            # 3. Benchmark Processing
            bmk_df, bmk_meta = get_bmk(benchmark_ticker, start_date.isoformat(), end_date.isoformat(), reporting_currency)
            
            if not bmk_df.empty:  
                bmk_series = bmk_df["benchmark_adj_close_converted"]
                bmk_perf = calculate_series_metrics(bmk_series)
                
                # FIXED: Created missing bmk_cum_rets and chart_df
                bmk_cum_rets = (bmk_series / bmk_series.iloc[0]) - 1
                chart_df = pd.DataFrame({
                    "Portfolio": port_cum_rets,
                    "Benchmark": bmk_cum_rets
                }).fillna(0)

                # 4. Save to Session State
                st.session_state.optimized_data = {
                    "weights": weights,
                    "port_perf": port_perf,
                    "bmk_perf": bmk_perf,
                    "chart_data": chart_df, 
                    "benchmark_name": benchmark_name,
                }
            else:
                st.error("Could not retrieve benchmark data.")
        except Exception as e:
            st.error(f"⚠️ {str(e)}")


# DISPLAY SECTION
if st.session_state.optimized_data:
    data = st.session_state.optimized_data
    
    # 1. Weights Pie Chart
    st.subheader("Max Sharpe Portfolio Weights")
    fig_pie = px.pie(names=list(data["weights"].keys()), values=list(data["weights"].values()))
    st.plotly_chart(fig_pie)

# 2. Performance Comparison Table
    st.subheader("Simulated Analytics vs Benchmark")

    # Construct the comparison table
    comparison_df = pd.DataFrame({
        "Portfolio": [
            f"{data['port_perf'][0]:.1%}",  # Return
            f"{data['port_perf'][1]:.1%}",  # Volatility
            f"{data['port_perf'][2]:.2f}"   # Sharpe
        ],
        "Benchmark": [
            f"{data['bmk_perf'][0]:.1%}",   # Return
            f"{data['bmk_perf'][1]:.1%}",   # Volatility
            f"{data['bmk_perf'][2]:.2f}"    # Sharpe
        ]
        
    }, index=["Annual Return", "Annual Volatility", "Sharpe Ratio"])

    # Display as a static table (cleaner for 3x3 metrics than a scrollable dataframe)
    st.table(comparison_df)
    # 3. Normalized Cumulative Returns Chart
    st.divider()
    st.subheader(f"Cumulative Return: Portfolio vs. {data['benchmark_name']} (%)")
    st.line_chart(data["chart_data"] * 100)