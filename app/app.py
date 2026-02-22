import sys
import pandas as pd   # pyright: ignore[reportMissingModuleSource]
from pathlib import Path
import datetime
import streamlit as st # type: ignore
import plotly.express as px # type: ignore

# Ensure the backend package is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from backend directly
from backend import (optimize_portfolio, calculate_series_metrics, calculate_end_pf_weights, get_data, get_bmk, get_fx) # type: ignore
from utils import load_index_metadata

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
# US Equity tickers -> AAPL,MA,META,V,AMZN,BA,BAC,BK,C,GS,JPM,MS,STT,WFC,LLY,BSX,JNJ,XOM,MDT,MSFT,GOOGL,NVDA,AVGO,CRM,UNH
tickers = st.sidebar.text_input("Enter Tickers (comma separated)", value="AAPL,MA,META,V,AMZN,BA,BAC,BK,C,GS,JPM,MS,STT,WFC,LLY,BSX,JNJ,XOM,MDT,MSFT,GOOGL,NVDA,AVGO,CRM,UNH")

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
                    "prices": df_prices,
                    "ticker_list": ticker_list,
                }
            else:
                st.error("Could not retrieve benchmark data.")
        except Exception as e:
            st.error(f"⚠️ {str(e)}")






# DISPLAY SECTION
if st.session_state.optimized_data:
    data = st.session_state.optimized_data
    
    # 1. Weights Pie Chart
    st.subheader("Maximum Sharpe Portfolio Weights")
    fig_pie = px.pie(names=list(data["weights"].keys()), values=list(data["weights"].values()))
    st.plotly_chart(fig_pie)

    # Holdings table: ticker, name, GICS Sector, weight start, weight end
    st.subheader("Holdings: Ticker, Name, GICS Sector, Weights")

    try:
        # Retrieve stored objects
        prices_df = st.session_state.optimized_data.get("prices")
        weights = st.session_state.optimized_data.get("weights")

        if prices_df is None or not weights:
            st.info("Price data or optimized weights not available to build holdings table.")
        else:
            # Compute start and end weights using the helper
            w_start, w_end = calculate_end_pf_weights(prices_df, weights)

            if w_start.empty:
                st.warning("No overlapping tickers between optimizer weights and price data.")
            else:
                # Build DataFrame
                holdings = pd.DataFrame({
                    "Weight Start": w_start,
                    "Weight End": w_end
                }).fillna(0)

                # Load metadata and join
                meta = load_index_metadata(sheet_name="SPX")
                if not meta.empty:
                    # Join on ticker index
                    holdings = holdings.join(meta, how="left")

                # Format percentages
                holdings_display = holdings.copy()
                holdings_display["Weight Start"] = holdings_display["Weight Start"].map("{:.2%}".format)
                holdings_display["Weight End"] = holdings_display["Weight End"].map("{:.2%}".format)

                # Reorder columns: Ticker, Security, GICS Sector, Weight Start, Weight End
                cols = ["Weight Start", "Weight End"]
                if "Security" in holdings_display.columns:
                    cols = ["Security"] + cols
                if "GICS Sector" in holdings_display.columns:
                    cols = ["GICS Sector"] + cols

                # Reset index to show ticker as a column
                holdings_display = holdings_display.reset_index().rename(columns={"index": "Ticker"})
                st.table(holdings_display[["Ticker"] + cols])
    except Exception as e:
        st.error(f"Failed to build holdings table: {e}")


# 2. Performance Comparison Table
    st.subheader("Optimized Portfolio vs Benchmark")

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
    st.subheader(f"Cumulative Return: Portfolio vs {data['benchmark_name']} (%)")
    
    fig = px.line(data["chart_data"] * 100,
              x=data["chart_data"].index,
              y=data["chart_data"].columns,
              labels={"value": "Cumulative Return (%)", "index": "Date"},
              #title=f"Cumulative Return: Portfolio vs {data['benchmark_name']} (%)",
              template="plotly_white")

    # Improve x-axis: show month abbrev and year on two lines, rotate for readability
    fig.update_xaxes(
        tickformat="%b\n%Y",   # e.g., "Feb\n2026"
        tickangle=0,
        tickmode="auto",
        nticks=12,             # target number of ticks (adjust as needed)
        showgrid=False
    )

    # Set explicit figure size (width used only when width="content")
    fig.update_layout(width=1400, height=600, margin=dict(l=40, r=20, t=60, b=40))

    # Render in Streamlit: use width="stretch" to fill the column, or width="content" to use fig.width
    st.plotly_chart(fig, width="content")   # fills the container; height controlled by fig.update_layout(height=...)



