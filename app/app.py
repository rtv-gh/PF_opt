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
import numpy as np  # pyright: ignore[reportMissingImports]

# Ensure the backend package is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from backend
from backend import optimize_multiple_portfolios, get_data, get_bmk  # type: ignore

# Import from app modules (absolute imports for Streamlit compatibility)
from app import config  # type: ignore
from app.metrics import prepare_multiple_portfolio_data, build_holdings_dataframe  # type: ignore
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
    reporting_currency: str,
    target_return: float = None,
    target_risk: float = None,
    target_te: float = None
) -> bool:
    """
    Execute the complete optimization workflow.
    
    Performs: data fetch → multi-portfolio optimization → metric calculation → state storage
    
    Supports multiple portfolio types (Max Sharpe, Min Variance, Efficient Return/Risk/TE) 
    with a scalable architecture for future extensions.
    
    Args:
        ticker_list: List of tickers to optimize
        start_date: Analysis start date
        end_date: Analysis end date
        benchmark_name: Display name of benchmark
        benchmark_ticker: Ticker symbol of benchmark
        reporting_currency: Currency for reporting
        target_return: Optional target return for efficient_return portfolio (e.g., 0.10 for 10%)
        target_risk: Optional target volatility for efficient_risk portfolio (e.g., 0.15 for 15%)
        target_te: Optional target tracking error for efficient_te portfolio (e.g., 0.05 for 5%)
    
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
        
        # 2. Create benchmark weights (using 1/n equal weights)
        benchmark_weights = np.ones(len(ticker_list)) / len(ticker_list)
        
        # 3. Multi-portfolio optimization (Max Sharpe, Min Variance, Efficient Return/Risk/TE)
        portfolios_raw = optimize_multiple_portfolios(
            df_prices, 
            target_return=target_return, 
            target_risk=target_risk,
            target_te=target_te,
            benchmark_weights=benchmark_weights
        )
        
        # Extract just the weights from (weights, perf) tuples
        portfolios_dict = {
            ptype: weights for ptype, (weights, perf) in portfolios_raw.items()
        }
        
        # 4. Fetch benchmark data
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
        
        # 5. Prepare all portfolio data (multi-portfolio, single-pass calculation)
        optimized_data = prepare_multiple_portfolio_data(
            ticker_list,
            df_prices,
            portfolios_dict,
            bmk_series,
            period_days
        )
        
        # 6. Add benchmark name for display
        optimized_data["benchmark_name"] = benchmark_name
        
        # 7. Store in session state for display
        st.session_state.optimized_data = optimized_data
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error during optimization: {str(e)}")
        return False


# ============================================================================
# SIDEBAR INPUT SECTION
# ============================================================================

tickers, benchmark_name, benchmark_ticker, reporting_currency, target_return, target_risk, target_te = display_sidebar_inputs()

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
            reporting_currency,
            target_return=target_return,
            target_risk=target_risk,
            target_te=target_te
        )


# ============================================================================
# DISPLAY SECTION
# ============================================================================

if st.session_state.optimized_data:
    data = st.session_state.optimized_data
    
    # Display all optimization results
    result = display_optimization_section(data)
    
    if result:
        # Handle both old tuple format and new dict format
        if isinstance(result, dict):
            holdings_display = None
            comparison_df = None
            weights = None
        else:
            # Old tuple format: (fig_pie, fig_chart, holdings_display)
            fig_pie, fig_chart, holdings_display = result
        
        # Extract data for export (from either old or new format)
        # For multi-portfolio, export the Max Sharpe portfolio (primary portfolio)
        if "portfolios" in data and "max_sharpe" in data["portfolios"]:
            # New multi-portfolio format
            max_sharpe_data = data["portfolios"]["max_sharpe"]
            comparison_df = max_sharpe_data.get("comparison_df")
            holdings_display = max_sharpe_data.get("holdings_df")
            weights = max_sharpe_data.get("weights")
        elif "comparison_df" in data and "weights" in data:
            # Old single-portfolio format
            comparison_df = data.get("comparison_df")
            holdings_display = data.get("holdings_df")
            weights = data.get("weights")
        
        # Only show export if we have the necessary data
        if comparison_df is not None and weights is not None:
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
                        comparison_df,
                        holdings_display,
                        data["period_days"],
                        data["chart_data"],
                        weights
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
