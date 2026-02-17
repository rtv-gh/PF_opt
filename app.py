import datetime
import streamlit as st # pyright: ignore[reportMissingImports]
import plotly.express as px # pyright: ignore[reportMissingImports]
from backend import get_data, optimize_portfolio # pyright: ignore[reportMissingImports]

st.set_page_config(page_title="Portfolio Optimizer", layout="wide")

st.title("🎯 Portfolio Optimizer")
st.sidebar.header("User Inputs")

# Data caching
@st.cache_data
def get_data(ticker_list, start_date, end_date):
    from backend import get_data as backend_get_data # pyright: ignore[reportMissingImports]
    return backend_get_data(ticker_list, start_date, end_date)

# User Inputs
tickers = st.sidebar.text_input("Enter Tickers (comma separated)", value = "BAC, BK, C, GS, JPM, MS, SST, WFC")

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
            df = get_data(ticker_list, start_date, end_date)
            weights, perf = optimize_portfolio(df) # pyright: ignore[reportPossiblyUnboundVariable]
    
            # Display Results
            col1, col2 = st.columns(2)
    
            with col1:
                st.subheader("Weights | Max Sharpe Portfolio")
                fig = px.pie(names=list(weights.keys()), values=list(weights.values()))
                st.plotly_chart(fig)
        
            with col2:
                st.subheader("Simulated Performance of the Max Sharpe Portfolio")
                st.metric("Return", f"{perf[0]:.2%}")
                st.metric("Volatility", f"{perf[1]:.2%}")
                st.metric("Sharpe Ratio", f"{perf[2]:.2f}")
        except ValueError as e:
            st.error(f"⚠️ {str(e)}")