"""
Portfolio Optimizer - Main Application

A professional portfolio optimization tool built with Streamlit that allows users
to input a list of tickers and calculates optimal weights based on the Sharpe ratio.

This module serves as the orchestrator for the application, coordinating between
data fetching, calculations, and UI display.
"""

import sys
import datetime
from pathlib import Path
from typing import List, Tuple

import streamlit as st  # type: ignore
import pandas as pd  # pyright: ignore[reportMissingModuleSource]

# Ensure the backend package is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from backend
from backend import optimize_portfolio, get_data, get_bmk  # type: ignore

# Import from app modules (absolute imports for Streamlit compatibility)
from app import config  # type: ignore
from app.metrics import prepare_portfolio_data, build_comparison_dataframe, build_holdings_dataframe  # type: ignore
from app.display import display_sidebar_inputs, display_optimization_section  # type: ignore
from app.export import generate_csv_holdings, generate_excel_full_page  # type: ignore


# ============================================================================
# PAGE CONFIGURATION & SESSION STATE
# ============================================================================

st.set_page_config(page_title=config.PAGE_TITLE, layout=config.PAGE_LAYOUT)
st.title("🎯 Portfolio Optimizer")

# Initialize session state
if 'optimized_data' not in st.session_state:
    st.session_state.optimized_data = None


# ============================================================================
# DATA CACHING
# ============================================================================

@st.cache_data
def cached_get_data(ticker_list: List[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """Cached data retrieval from yfinance."""
    return get_data(ticker_list, start_date, end_date)


# ============================================================================
# OPTIMIZATION WORKFLOW
# ============================================================================

def run_optimization(
    ticker_list: List[str],
    start_date: datetime.date,
    end_date: datetime.date,
    benchmark_name: str,
    benchmark_ticker: str,
    reporting_currency: str
) -> bool:
    """
    Execute the complete optimization workflow.
    
    Performs: data fetch → optimization → metric calculation → state storage
    
    Args:
        ticker_list: List of tickers to optimize
        start_date: Analysis start date
        end_date: Analysis end date
        benchmark_name: Display name of benchmark
        benchmark_ticker: Ticker symbol of benchmark
        reporting_currency: Currency for reporting
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Calculate period length
        period_days = (end_date - start_date).days
        
        # 1. Fetch price data
        df_prices = cached_get_data(ticker_list, start_date, end_date)
        if df_prices.empty:
            st.error("Could not retrieve price data for the specified tickers.")
            return False
        
        # 2. Portfolio optimization
        weights, port_perf = optimize_portfolio(df_prices)
        
        # 3. Fetch benchmark data
        bmk_df, bmk_meta = get_bmk(
            benchmark_ticker,
            start_date.isoformat(),
            end_date.isoformat(),
            reporting_currency
        )
        
        if bmk_df.empty:
            st.error("Could not retrieve benchmark data.")
            return False
        
        bmk_series = bmk_df["benchmark_adj_close_converted"]
        
        # 4. Prepare all portfolio data (single-pass calculation)
        portfolio_data = prepare_portfolio_data(
            ticker_list,
            df_prices,
            weights,
            bmk_series,
            period_days
        )
        
        # 5. Build display dataframes
        comparison_df = build_comparison_dataframe(
            port_perf=port_perf,
            bmk_perf=portfolio_data["bmk_perf"],
            port_period_metrics=portfolio_data["port_period_metrics"],
            bmk_period_metrics=portfolio_data["bmk_period_metrics"],
            tracking_error=portfolio_data["tracking_error"],
            period_days=period_days
        )
        
        holdings_df = build_holdings_dataframe(df_prices, weights, format_percentages=False)
        
        # 6. Store in session state for display
        st.session_state.optimized_data = {
            "weights": weights,
            "prices": df_prices,
            "holdings_df": holdings_df,
            "comparison_df": comparison_df,
            "chart_data": portfolio_data["chart_data"],
            "benchmark_name": benchmark_name,
            "period_days": period_days,
            "port_perf": port_perf,
            "bmk_perf": portfolio_data["bmk_perf"],
            "port_period_metrics": portfolio_data["port_period_metrics"],
            "bmk_period_metrics": portfolio_data["bmk_period_metrics"],
            "tracking_error": portfolio_data["tracking_error"],
        }
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error during optimization: {str(e)}")
        return False


# ============================================================================
# SIDEBAR INPUT SECTION
# ============================================================================

tickers, benchmark_name, benchmark_ticker, reporting_currency = display_sidebar_inputs()

# Date inputs
today = datetime.date.today()
one_year_ago = today - datetime.timedelta(days=365)
start_date = st.sidebar.date_input("Start Date", value=one_year_ago, max_value=today)
end_date = st.sidebar.date_input(
    "End Date",
    value=today - datetime.timedelta(days=1),
    min_value=start_date,
    max_value=today - datetime.timedelta(days=1)
)

# Optimize button
if st.sidebar.button("Optimize"):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    
    if not ticker_list:
        st.error("Please enter at least one valid ticker.")
    elif len(ticker_list) > config.MAX_TICKERS:
        st.error(f"Please enter no more than {config.MAX_TICKERS} tickers.")
    else:
        run_optimization(
            ticker_list,
            start_date,
            end_date,
            benchmark_name,
            benchmark_ticker,
            reporting_currency
        )


# ============================================================================
# DISPLAY SECTION
# ============================================================================

if st.session_state.optimized_data:
    data = st.session_state.optimized_data
    
    # Display all optimization results
    result = display_optimization_section(data)
    
    if result:
        fig_pie, fig_chart, holdings_display = result
        
        # Export section
        st.divider()
        st.subheader("📊 Export Results")
        
        try:
            col1, col2 = st.columns(2)
            
            # CSV export for holdings
            if holdings_display is not None:
                csv_data = generate_csv_holdings(holdings_display)
                with col1:
                    st.download_button(
                        label="📥 Download Holdings as CSV",
                        data=csv_data,
                        file_name="portfolio_holdings.csv",
                        mime="text/csv",
                        key="holdings_csv"
                    )
            
            # Excel export with charts
            if holdings_display is not None:
                excel_buffer = generate_excel_full_page(
                    data["comparison_df"],
                    holdings_display,
                    data["period_days"],
                    data["chart_data"],
                    data["weights"]
                )
                
                with col2:
                    st.download_button(
                        label="📊 Download Full Report as Excel",
                        data=excel_buffer,
                        file_name="portfolio_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="full_export_excel"
                    )
        
        except Exception as e:
            st.warning(f"Export functionality: {str(e)}")
