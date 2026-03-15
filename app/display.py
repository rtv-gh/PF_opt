"""
Display module for Portfolio Optimizer UI.

This module handles all Streamlit UI rendering and visualization logic,
keeping it separate from business logic and calculations.
"""

from typing import Dict, Optional, Tuple, List
import pandas as pd
import streamlit as st
import plotly.express as px

from .config import (
    PIE_CHART_WIDTH, PIE_CHART_HEIGHT,
    LINE_CHART_WIDTH, LINE_CHART_HEIGHT,
    COLUMN_WIDTH_SMALL, COLUMN_WIDTH_MEDIUM,
    BENCHMARKS, DEFAULT_TICKERS, DEFAULT_REPORTING_CURRENCY,
    DEFAULT_BENCHMARK
)


def display_sidebar_inputs() -> Tuple[str, str, str, str, str]:
    """
    Display user input controls in the sidebar.
    
    Returns:
        Tuple of (tickers, benchmark_name, benchmark_ticker, reporting_currency, error_message)
    """
    st.sidebar.header("User Inputs")
    
    tickers = st.sidebar.text_input(
        "Enter Tickers (comma separated)",
        value=DEFAULT_TICKERS
    )
    
    st.sidebar.subheader("Benchmark")
    benchmark_name = st.sidebar.selectbox(
        "Benchmark",
        options=list(BENCHMARKS.keys()),
        index=list(BENCHMARKS.keys()).index(DEFAULT_BENCHMARK)
    )
    benchmark_ticker = BENCHMARKS[benchmark_name]
    
    st.sidebar.subheader("Reporting currency")
    reporting_currency = st.sidebar.selectbox(
        "Reporting currency",
        options=["USD", "GBP", "EUR"],
        index=0
    )
    
    return tickers, benchmark_name, benchmark_ticker, reporting_currency


def display_pie_chart(weights: Dict[str, float]) -> Optional:
    """
    Display portfolio weights pie chart.
    
    Filters out zero-weight stocks and uses explicit color palette.
    
    Args:
        weights: Dict of ticker -> weight
    
    Returns:
        Plotly figure object
    """
    st.subheader("Maximum Sharpe Portfolio Weights")
    col_pie, col_spacer = st.columns([1.2, 2])
    
    with col_pie:
        # Filter weights to only show stocks with weight > 0%
        weights_filtered = {ticker: weight for ticker, weight in weights.items() if weight > 0}
        
        if weights_filtered:
            fig_pie = px.pie(
                names=list(weights_filtered.keys()),
                values=list(weights_filtered.values()),
                color_discrete_sequence=px.colors.qualitative.Plotly
            )
            fig_pie.update_layout(
                width=PIE_CHART_WIDTH,
                height=PIE_CHART_HEIGHT,
                showlegend=True,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig_pie, use_container_width=False)
            return fig_pie
        else:
            st.warning("No stocks with positive weights in portfolio.")
            return None


def display_holdings_table(holdings_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Display holdings table with metadata.
    
    Args:
        holdings_df: DataFrame with Ticker, Security, GICS Sector, Weight Start, Weight End
    
    Returns:
        Formatted holdings DataFrame for display
    """
    st.subheader("Holdings: Ticker, Name, GICS Sector, Weights")
    
    if holdings_df.empty:
        st.warning("No holdings data available.")
        return None
    
    # Make a copy for display and format percentages
    holdings_display = holdings_df.copy()
    holdings_display["Weight Start"] = holdings_display["Weight Start"].map("{:.2%}".format)
    holdings_display["Weight End"] = holdings_display["Weight End"].map("{:.2%}".format)
    
    # Determine columns to display
    display_cols = [col for col in holdings_display.columns if col in
                    ["Ticker", "Security", "GICS Sector", "Weight Start", "Weight End"]]
    
    # Create column config for narrow columns
    column_config = {
        "Ticker": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Weight Start": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Weight End": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
    }
    if "Security" in display_cols:
        column_config["Security"] = st.column_config.TextColumn(width=COLUMN_WIDTH_MEDIUM)
    if "GICS Sector" in display_cols:
        column_config["GICS Sector"] = st.column_config.TextColumn(width=COLUMN_WIDTH_MEDIUM)
    
    st.dataframe(
        holdings_display[display_cols],
        column_config=column_config,
        width="content",
        hide_index=True
    )
    
    return holdings_display[display_cols]


def display_metrics_table(comparison_df: pd.DataFrame):
    """
    Display metrics comparison table.
    
    Args:
        comparison_df: DataFrame with Portfolio and Benchmark columns
    """
    st.subheader("Max Sharpe Portfolio vs Benchmark")
    
    st.dataframe(
        comparison_df,
        column_config={
            "Portfolio": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
            "Benchmark": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        },
        width="content",
        hide_index=False
    )


def display_cumulative_returns_chart(
    chart_data: pd.DataFrame,
    benchmark_name: str
):
    """
    Display cumulative returns performance chart.
    
    Args:
        chart_data: DataFrame with 'Max Sharpe PF' and 'Benchmark' columns
        benchmark_name: Name of benchmark for display
    
    Returns:
        Plotly figure object
    """
    st.divider()
    st.subheader(f"Cumulative Return: Max Sharpe Portfolio vs {benchmark_name} (%)")
    
    # Create line chart
    fig = px.line(
        chart_data * 100,
        x=chart_data.index,
        y=chart_data.columns,
        labels={"value": "Cumulative Return (%)", "index": "Date"},
        template="plotly_white"
    )
    
    # Improve x-axis
    fig.update_xaxes(
        tickformat="%b\n%Y",
        tickangle=0,
        tickmode="auto",
        nticks=12,
        showgrid=False
    )
    
    # Set hover template
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Return: %{y:.2f}%<extra></extra>"
    )
    
    # Layout settings
    fig.update_layout(
        width=LINE_CHART_WIDTH,
        height=LINE_CHART_HEIGHT,
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(x=0, y=1, xanchor="left", yanchor="top")
    )
    
    st.plotly_chart(fig, use_container_width=False)
    return fig


def display_optimization_section(data: Dict) -> Optional[Tuple]:
    """
    Display the full optimization results section.
    
    This is the main display orchestration function called after optimization.
    
    Args:
        data: Session state data dictionary containing:
            - weights: portfolio weights
            - prices: price history
            - comparison_df: metrics comparison
            - holdings_df: holdings data
            - chart_data: cumulative returns
            - benchmark_name: benchmark name
    
    Returns:
        Tuple of (fig_pie, fig_chart, holdings_display) or None if data incomplete
    """
    if not data or not data.get("weights"):
        return None
    
    # 1. Pie chart
    fig_pie = display_pie_chart(data.get("weights", {}))
    
    # 2. Holdings table
    holdings_display = display_holdings_table(data.get("holdings_df", pd.DataFrame()))
    
    # 3. Metrics table
    display_metrics_table(data.get("comparison_df", pd.DataFrame()))
    
    # 4. Cumulative returns chart
    fig_chart = display_cumulative_returns_chart(
        data.get("chart_data", pd.DataFrame()),
        data.get("benchmark_name", "Benchmark")
    )
    
    return fig_pie, fig_chart, holdings_display
