"""
Display module for Portfolio Optimizer UI.

This module handles all Streamlit UI rendering and visualization logic,
keeping it separate from business logic and calculations.

Supports multiple portfolio types (Max Sharpe, Min Variance, etc.) with
flexible layout and display options.
"""

from typing import Dict, Optional, Tuple, List, Any
import pandas as pd
import streamlit as st
import plotly.express as px  # type: ignore

from app.config import (  # type: ignore
    PIE_CHART_WIDTH, PIE_CHART_HEIGHT,
    LINE_CHART_WIDTH, LINE_CHART_HEIGHT,
    COLUMN_WIDTH_SMALL, COLUMN_WIDTH_MEDIUM,
    BENCHMARKS, DEFAULT_TICKERS, DEFAULT_REPORTING_CURRENCY,
    DEFAULT_BENCHMARK
)


def display_sidebar_inputs() -> Tuple[str, str, str, str, Optional[float], Optional[float], Optional[float]]:
    """
    Display user input controls in the sidebar.
    
    Returns:
        Tuple of (tickers, benchmark_name, benchmark_ticker, reporting_currency, target_return, target_risk, target_te)
        where target_return, target_risk, and target_te are optional (None if not specified by user)
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
    
    # Optional target parameters for efficient frontier portfolios
    st.sidebar.subheader("Target-Based Portfolios (Optional)")
    
    target_return_pct = st.sidebar.number_input(
        "Target Return (%) - for Efficient Return portfolio",
        value=None,
        step=0.5,
        help="Leave blank to skip Efficient Return portfolio"
    )
    target_return = target_return_pct / 100.0 if target_return_pct is not None else None
    
    target_risk_pct = st.sidebar.number_input(
        "Target Risk/Volatility (%) - for Efficient Risk portfolio",
        value=None,
        step=0.5,
        help="Leave blank to skip Efficient Risk portfolio"
    )
    target_risk = target_risk_pct / 100.0 if target_risk_pct is not None else None
    
    target_te_pct = st.sidebar.number_input(
        "Target Tracking Error (%) - for Efficient TE portfolio",
        value=None,
        step=0.5,
        help="Tracking error relative to 1/n equal-weight benchmark. Leave blank to skip."
    )
    target_te = target_te_pct / 100.0 if target_te_pct is not None else None
    
    return tickers, benchmark_name, benchmark_ticker, reporting_currency, target_return, target_risk, target_te


def display_pie_chart(
    weights: Dict[str, float],
    portfolio_type: str = "max_sharpe",
    title: Optional[str] = None
) -> Optional:
    """
    Display portfolio weights pie chart.
    
    Filters out zero-weight stocks and uses explicit color palette.
    
    Args:
        weights: Dict of ticker -> weight
        portfolio_type: Portfolio type for display (e.g., "max_sharpe", "min_variance")
        title: Optional custom title. If None, generates from portfolio_type.
    
    Returns:
        Plotly figure object
    """
    if title is None:
        title = _get_portfolio_display_title(portfolio_type, "Weights")
    
    st.subheader(title)
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
            st.plotly_chart(fig_pie, use_container_width=False, key=f"pie_chart_{portfolio_type}")
            return fig_pie
        else:
            st.warning("No stocks with positive weights in portfolio.")
            return None


def display_holdings_table(
    holdings_df: pd.DataFrame,
    portfolio_type: str = "max_sharpe",
    title: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Display holdings table with metadata.
    
    Args:
        holdings_df: DataFrame with Ticker, Security, GICS Sector, Weight Start, Weight End
        portfolio_type: Portfolio type for display
        title: Optional custom title
    
    Returns:
        Formatted holdings DataFrame for display
    """
    if title is None:
        title = _get_portfolio_display_title(portfolio_type, "Holdings")
    
    st.subheader(title)
    
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
        hide_index=True,
        key=f"holdings_df_{portfolio_type}"
    )
    
    return holdings_display[display_cols]


def display_metrics_table(
    comparison_df: pd.DataFrame,
    portfolio_type: str = "max_sharpe",
    title: Optional[str] = None
):
    """
    Display metrics comparison table.
    
    Args:
        comparison_df: DataFrame with Portfolio and Benchmark columns
        portfolio_type: Portfolio type for display
        title: Optional custom title
    """
    if title is None:
        title = _get_portfolio_display_title(portfolio_type, "Metrics")
    
    st.subheader(title)
    
    st.dataframe(
        comparison_df,
        column_config={
            "Portfolio": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
            "Benchmark": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        },
        width="content",
        hide_index=False,
        key=f"metrics_df_{portfolio_type}"
    )


def _get_portfolio_display_title(portfolio_type: str, section: str = "") -> str:
    """
    Generate display title for a portfolio section.
    
    Args:
        portfolio_type: Portfolio type (e.g., "max_sharpe", "min_variance", "efficient_return", "efficient_risk", "efficient_te")
        section: Section name (e.g., "Weights", "Holdings", "Metrics")
    
    Returns:
        Display title
    """
    display_names = {
        "max_sharpe": "Max Sharpe",
        "min_variance": "Min Volatility",
        "efficient_return": "Efficient Return",
        "efficient_risk": "Efficient Risk",
        "efficient_te": "Efficient Tracking Error",
    }
    portfolio_name = display_names.get(portfolio_type, portfolio_type.replace("_", " ").title())
    if section:
        return f"{portfolio_name}: {section}"
    return portfolio_name


def display_cumulative_returns_chart(
    chart_data: pd.DataFrame,
    benchmark_name: str,
    title: Optional[str] = None
):
    """
    Display cumulative returns performance chart.
    
    Args:
        chart_data: DataFrame with portfolio and benchmark cumulative return columns
        benchmark_name: Name of benchmark for display
        title: Optional custom title
    
    Returns:
        Plotly figure object
    """
    if title is None:
        title = f"Cumulative Return: All Portfolios vs {benchmark_name} (%)"
    
    st.divider()
    st.subheader(title)
    
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
    
    st.plotly_chart(fig, use_container_width=False, key="cumulative_returns_chart")
    return fig


def display_portfolio_column(
    portfolio_type: str,
    portfolio_data: Dict[str, Any]
) -> None:
    """
    Display a single portfolio in a column: pie chart, holdings, metrics.
    
    This is a reusable component for displaying portfolio analysis.
    
    Args:
        portfolio_type: Portfolio type (e.g., "max_sharpe", "min_variance")
        portfolio_data: Dict containing:
            - weights: Dict of ticker -> weight
            - holdings_df: Holdings DataFrame
            - comparison_df: Comparison DataFrame
    """
    display_pie_chart(
        portfolio_data.get("weights", {}),
        portfolio_type=portfolio_type
    )
    
    display_holdings_table(
        portfolio_data.get("holdings_df", pd.DataFrame()),
        portfolio_type=portfolio_type
    )
    
    display_metrics_table(
        portfolio_data.get("comparison_df", pd.DataFrame()),
        portfolio_type=portfolio_type
    )


def display_multiple_portfolios(optimized_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Display multiple portfolios with flexible layout for varying portfolio counts.
    
    This is the main display orchestration function for multi-portfolio analysis.
    Supports dynamic layouts:
    - 2 portfolios: 1 row of 2
    - 3 portfolios: 1 row of 2, then 1 row of 3
    - 4 portfolios: 2 rows of 2
    - 5 portfolios: 1 row of 2, then 1 row of 3
    
    Layout:
    - Row 1-N: Flexible columns (Pie charts, Holdings, Metrics with adaptive layout)
    - Final Row: Combined performance chart (all portfolios vs benchmark)
    
    Args:
        optimized_data: Multi-portfolio data structure from prepare_multiple_portfolio_data()
            {
                "portfolios": {
                    "max_sharpe": {...},
                    "min_variance": {...},
                    ...
                },
                "benchmark": {...},
                "chart_data": df,
            }
    
    Returns:
        Dict with generated figures for export, or None if data incomplete
    """
    if not optimized_data or not optimized_data.get("portfolios"):
        return None
    
    portfolios = optimized_data["portfolios"]
    portfolio_types = list(portfolios.keys())
    
    # If only one portfolio, fall back to original layout
    if len(portfolio_types) == 1:
        return _display_single_portfolio_legacy(optimized_data)
    
    def _display_section(section_type):
        """Helper to display a section (pie charts, holdings, or metrics) with adaptive layout"""
        # First row: portfolios 0-1 (2 columns)
        col1, col2 = st.columns(2)
        
        with col1:
            if section_type == "pie":
                display_pie_chart(
                    portfolios[portfolio_types[0]].get("weights", {}),
                    portfolio_type=portfolio_types[0]
                )
            elif section_type == "holdings":
                display_holdings_table(
                    portfolios[portfolio_types[0]].get("holdings_df", pd.DataFrame()),
                    portfolio_type=portfolio_types[0]
                )
            else:  # metrics
                display_metrics_table(
                    portfolios[portfolio_types[0]].get("comparison_df", pd.DataFrame()),
                    portfolio_type=portfolio_types[0]
                )
        
        if len(portfolio_types) >= 2:
            with col2:
                if section_type == "pie":
                    display_pie_chart(
                        portfolios[portfolio_types[1]].get("weights", {}),
                        portfolio_type=portfolio_types[1]
                    )
                elif section_type == "holdings":
                    display_holdings_table(
                        portfolios[portfolio_types[1]].get("holdings_df", pd.DataFrame()),
                        portfolio_type=portfolio_types[1]
                    )
                else:  # metrics
                    display_metrics_table(
                        portfolios[portfolio_types[1]].get("comparison_df", pd.DataFrame()),
                        portfolio_type=portfolio_types[1]
                    )
        
        # Remaining portfolios: Display in their own row(s)
        if len(portfolio_types) > 2:
            remaining_types = portfolio_types[2:]
            if len(remaining_types) <= 3:
                # Display 3 or fewer remaining portfolios in one row
                cols = st.columns(len(remaining_types))
                for idx, col in enumerate(cols):
                    with col:
                        if section_type == "pie":
                            display_pie_chart(
                                portfolios[remaining_types[idx]].get("weights", {}),
                                portfolio_type=remaining_types[idx]
                            )
                        elif section_type == "holdings":
                            display_holdings_table(
                                portfolios[remaining_types[idx]].get("holdings_df", pd.DataFrame()),
                                portfolio_type=remaining_types[idx]
                            )
                        else:  # metrics
                            display_metrics_table(
                                portfolios[remaining_types[idx]].get("comparison_df", pd.DataFrame()),
                                portfolio_type=remaining_types[idx]
                            )
            else:
                # Display 4+ remaining portfolios in pairs
                for i in range(0, len(remaining_types), 2):
                    cols = st.columns(2)
                    with cols[0]:
                        if section_type == "pie":
                            display_pie_chart(
                                portfolios[remaining_types[i]].get("weights", {}),
                                portfolio_type=remaining_types[i]
                            )
                        elif section_type == "holdings":
                            display_holdings_table(
                                portfolios[remaining_types[i]].get("holdings_df", pd.DataFrame()),
                                portfolio_type=remaining_types[i]
                            )
                        else:  # metrics
                            display_metrics_table(
                                portfolios[remaining_types[i]].get("comparison_df", pd.DataFrame()),
                                portfolio_type=remaining_types[i]
                            )
                    
                    if i + 1 < len(remaining_types):
                        with cols[1]:
                            if section_type == "pie":
                                display_pie_chart(
                                    portfolios[remaining_types[i + 1]].get("weights", {}),
                                    portfolio_type=remaining_types[i + 1]
                                )
                            elif section_type == "holdings":
                                display_holdings_table(
                                    portfolios[remaining_types[i + 1]].get("holdings_df", pd.DataFrame()),
                                    portfolio_type=remaining_types[i + 1]
                                )
                            else:  # metrics
                                display_metrics_table(
                                    portfolios[remaining_types[i + 1]].get("comparison_df", pd.DataFrame()),
                                    portfolio_type=remaining_types[i + 1]
                                )
    
    # Display all sections with adaptive layout
    _display_section("pie")
    _display_section("holdings")
    _display_section("metrics")
    
    # Combined performance chart (spanning full width)
    fig_chart = display_cumulative_returns_chart(
        optimized_data.get("chart_data", pd.DataFrame()),
        benchmark_name="Benchmark"
    )
    
    return {"fig_chart": fig_chart}


def _display_single_portfolio_legacy(optimized_data: Dict[str, Any]) -> Optional[Tuple]:
    """
    Legacy display for single portfolio (backward compatibility).
    
    This function is called when only one portfolio type is present.
    """
    portfolios = optimized_data.get("portfolios", {})
    if not portfolios:
        return None
    
    portfolio_type = list(portfolios.keys())[0]
    portfolio_data = portfolios[portfolio_type]
    
    # 1. Pie chart
    fig_pie = display_pie_chart(
        portfolio_data.get("weights", {}),
        portfolio_type=portfolio_type
    )
    
    # 2. Holdings table
    holdings_display = display_holdings_table(
        portfolio_data.get("holdings_df", pd.DataFrame()),
        portfolio_type=portfolio_type
    )
    
    # 3. Metrics table
    display_metrics_table(
        portfolio_data.get("comparison_df", pd.DataFrame()),
        portfolio_type=portfolio_type
    )
    
    # 4. Cumulative returns chart
    fig_chart = display_cumulative_returns_chart(
        optimized_data.get("chart_data", pd.DataFrame()),
        benchmark_name="Benchmark"
    )
    
    return fig_pie, fig_chart, holdings_display


def display_optimization_section(data: Dict) -> Optional[Tuple]:
    """
    Display the full optimization results section.
    
    Legacy function for backward compatibility. Can handle both old and new data structures.
    
    This is the main display orchestration function called after optimization.
    
    Args:
        data: Session state data dictionary - either:
            OLD FORMAT:
            - weights: portfolio weights
            - prices: price history
            - comparison_df: metrics comparison
            - holdings_df: holdings data
            - chart_data: cumulative returns
            - benchmark_name: benchmark name
            
            NEW FORMAT (from prepare_multiple_portfolio_data):
            - portfolios: dict of portfolio types
            - benchmark: benchmark data
            - chart_data: combined chart data
            - period_days: int
    
    Returns:
        Tuple of (fig_pie, fig_chart, holdings_display) or None if data incomplete
    """
    if not data:
        return None
    
    # Detect which format we're using
    if "portfolios" in data:
        # New multi-portfolio format
        return display_multiple_portfolios(data)
    elif "weights" in data:
        # Old single-portfolio format
        if not data.get("weights"):
            return None
        
        # 1. Pie chart
        fig_pie = display_pie_chart(data.get("weights", {}), portfolio_type="max_sharpe")
        
        # 2. Holdings table
        holdings_display = display_holdings_table(data.get("holdings_df", pd.DataFrame()), portfolio_type="max_sharpe")
        
        # 3. Metrics table
        display_metrics_table(data.get("comparison_df", pd.DataFrame()), portfolio_type="max_sharpe")
        
        # 4. Cumulative returns chart
        fig_chart = display_cumulative_returns_chart(
            data.get("chart_data", pd.DataFrame()),
            data.get("benchmark_name", "Benchmark")
        )
        
        return fig_pie, fig_chart, holdings_display
    
    return None
