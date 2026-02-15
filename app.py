import streamlit as st
import plotly.express as px
from backend import get_data, optimize_portfolio

st.set_page_config(page_title="Smart Beta Optimizer", layout="wide")

st.title("🎯 Portfolio Optimizer")
st.sidebar.header("User Inputs")

# User Inputs
tickers = st.sidebar.text_input("Enter Tickers (comma separated)", "C, MS, GS, JPM, BAC, WFC")
start_date = st.sidebar.date_input("Start Date", value=None)

if st.sidebar.button("Optimize"):
    ticker_list = [t.strip() for t in tickers.split(",")]
    df = get_data(ticker_list, start_date, None)
    
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