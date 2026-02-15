import datetime
import streamlit as st
import plotly.express as px
from backend import get_data, optimize_portfolio

st.set_page_config(page_title="Portfolio Optimizer", layout="wide")

st.title("🎯 Portfolio Optimizer")
st.sidebar.header("User Inputs")

# Data caching
@st.cache_data
def get_data(ticker_list, start_date, end_date):
    from backend import get_data as backend_get_data
    return backend_get_data(ticker_list, start_date, end_date)

# User Inputs
tickers = st.sidebar.text_input("Enter Tickers (comma separated)", value = "C, MS, GS, JPM, BAC, WFC")

today = datetime.date.today()
one_year_ago = today - datetime.timedelta(days=365)
start_date = st.sidebar.date_input("Start Date", value=one_year_ago, max_value=today)
end_date = st.sidebar.date_input("End Date", value=today - datetime.timedelta(days=1), min_value=start_date, max_value=today)

if st.sidebar.button("Optimize"):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        st.error("Please enter at least one valid ticker.")
    else:
        df = get_data(ticker_list, start_date, end_date)
    
    weights, perf = optimize_portfolio(df)
    
    # Display Results
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Optimal Weights")
        fig = px.pie(names=list(weights.keys()), values=list(weights.values()))
        st.plotly_chart(fig)
        
    with col2:
        st.subheader("Expected Performance")
        st.metric("Expected Annual Return", f"{perf[0]:.2%}")
        st.metric("Annual Volatility", f"{perf[1]:.2%}")
        st.metric("Sharpe Ratio", f"{perf[2]:.2f}")