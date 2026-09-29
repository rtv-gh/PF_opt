"""
Display module for Portfolio Optimizer UI.

This module handles all Streamlit UI rendering and visualization logic,
keeping it separate from business logic and calculations.

Supports multiple portfolio types (Max Sharpe, Min Variance, etc.) with
flexible layout and display options.
"""

from collections import Counter
import random
from typing import Dict, Optional, Tuple, List, Any
import pandas as pd
import streamlit as st
import plotly.express as px  # type: ignore

from app.config import (  # type: ignore
    PIE_CHART_WIDTH, PIE_CHART_HEIGHT,
    LINE_CHART_WIDTH, LINE_CHART_HEIGHT,
    COLUMN_WIDTH_SMALL, COLUMN_WIDTH_MEDIUM,
    MARKET_CONFIGS,
)
from app.export import generate_portfolio_csv
from utils import load_gics_sector_stocks


def _reset_market_inputs() -> None:
    """Reset market-specific ticker and random-count inputs after a market switch."""
    market_config = MARKET_CONFIGS[st.session_state.selected_market]
    st.session_state["manual_tickers_input"] = market_config["default_tickers"]
    for key in list(st.session_state):
        if key.startswith("random_count_"):
            del st.session_state[key]


def build_portfolio_tickers(
    manual_tickers: str,
    sector_random_counts: Dict[str, int],
    market: str = "USA",
) -> List[str]:
    """Combine manual tickers with unique random constituents from each sector."""
    manual_symbols = [
        ticker.strip().upper()
        for ticker in manual_tickers.replace("\n", ",").split(",")
        if ticker.strip()
    ]
    ticker_list = list(dict.fromkeys(manual_symbols))
    selected_tickers = set(ticker_list)
    stock_data = load_gics_sector_stocks(market)

    for sector, requested_count in sector_random_counts.items():
        if requested_count <= 0:
            continue
        sector_symbols = stock_data.loc[
            stock_data["GICS Sector"] == sector, "Symbol"
        ].tolist()
        available_symbols = [
            ticker for ticker in sector_symbols if ticker not in selected_tickers
        ]
        random_tickers = random.sample(
            available_symbols,
            k=min(requested_count, len(available_symbols)),
        )
        ticker_list.extend(random_tickers)
        selected_tickers.update(random_tickers)

    return ticker_list


def display_sidebar_inputs() -> Tuple[
    str, Dict[str, int], bool, str, str, str,
    Optional[float], Optional[float], Optional[float]
]:
    """
    Display user input controls in the sidebar.
    
    Returns:
        Tuple of (manual_tickers, sector_random_counts, enforce_ucits_5_10_40, benchmark_name,
        benchmark_ticker, reporting_currency, target_return, target_risk, target_te)
        where target_return, target_risk, and target_te are optional (None if not specified by user)
    """
    market = st.sidebar.radio(
        "Equity market",
        options=list(MARKET_CONFIGS),
        horizontal=True,
        key="selected_market",
        on_change=_reset_market_inputs,
    )
    st.sidebar.header("User Inputs")
    market_config = MARKET_CONFIGS[market]
    st.session_state.setdefault("manual_tickers_input", market_config["default_tickers"])
    enforce_ucits_5_10_40 = st.sidebar.checkbox(
        "Constrain to UCITS 5/10/40",
        value=False,
        help=(
            "Keep each issuer at or below 10% and the largest eight issuers at or below 40% "
            "throughout the observation period. This conservative constraint may exclude "
            "some otherwise-compliant portfolios."
        ),
    )
    if market == "UK":
        with st.spinner("Loading UK equity constituents..."):
            stocks = load_gics_sector_stocks(market)
    else:
        stocks = load_gics_sector_stocks(market)
    if stocks.empty:
        st.sidebar.error(f"No {market} stock universe is available. Check the constituent data source.")
    sectors = sorted(stocks["GICS Sector"].dropna().unique().tolist())

    def add_random_stocks() -> None:
        requested_counts = {
            sector: int(st.session_state.get(f"random_count_{sector}", 0))
            for sector in sectors
        }
        current_tickers = st.session_state.get(
            "manual_tickers_input", market_config["default_tickers"]
        )
        added_tickers = build_portfolio_tickers(current_tickers, requested_counts, market)
        st.session_state["manual_tickers_input"] = ", ".join(added_tickers)
        for sector in sectors:
            key = f"random_count_{sector}"
            if key in st.session_state:
                del st.session_state[key]

    title_column, add_column = st.sidebar.columns([4, 1])
    title_column.subheader("Random Stocks by GICS Sector")
    with add_column:
        st.button(
            "Add",
            key="add_random_sector_stocks",
            on_click=add_random_stocks,
            help="Add the requested random stocks to the manual ticker list.",
        )

    sector_random_counts: Dict[str, int] = {}
    for sector in sectors:
        sector_stocks = stocks[stocks["GICS Sector"] == sector]
        sector_label, count_input = st.sidebar.columns([3, 1])
        sector_label.markdown(f"**{sector}**")
        with count_input:
            sector_random_counts[sector] = st.number_input(
                f"Random stock count for {sector}",
                min_value=0,
                max_value=len(sector_stocks),
                value=0,
                step=1,
                label_visibility="collapsed",
                key=f"random_count_{sector}",
            )

    st.sidebar.subheader("Manually Add Tickers")
    manual_tickers = st.sidebar.text_area(
        "Enter individual tickers (comma or newline separated)",
        height=100,
        key="manual_tickers_input",
    )
    manual_symbols = [
        ticker.strip().upper()
        for ticker in manual_tickers.replace("\n", ",").split(",")
        if ticker.strip()
    ]
    st.sidebar.caption(f"Selected stocks: {len(set(manual_symbols))}")
    duplicate_tickers = sorted(
        ticker for ticker, count in Counter(manual_symbols).items() if count > 1
    )
    if duplicate_tickers:
        st.sidebar.warning(
            f"Duplicate tickers found: {', '.join(duplicate_tickers)}. "
            "Each ticker should appear only once."
        )

    manual_set = set(manual_symbols)
    unavailable_counts = []
    for sector, requested_count in sector_random_counts.items():
        sector_symbols = set(stocks.loc[stocks["GICS Sector"] == sector, "Symbol"])
        available_count = len(sector_symbols - manual_set)
        if requested_count > available_count:
            unavailable_counts.append(f"{sector}: {available_count} available")
    if unavailable_counts:
        st.sidebar.warning(
            "Some random counts exceed the unselected stocks remaining: "
            + "; ".join(unavailable_counts)
        )
    
    st.sidebar.subheader("Benchmark")
    benchmark_name = st.sidebar.selectbox(
        "Benchmark",
        options=list(market_config["benchmarks"]),
        index=list(market_config["benchmarks"]).index(market_config["default_benchmark"])
    )
    benchmark_ticker = market_config["benchmarks"][benchmark_name]
    
    st.sidebar.subheader("Reporting currency")
    reporting_currency = st.sidebar.selectbox(
        "Reporting currency",
        options=["USD", "GBP", "EUR"],
        index=["USD", "GBP", "EUR"].index(market_config["default_currency"])
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
    
    return (
        manual_tickers,
        sector_random_counts,
        enforce_ucits_5_10_40,
        benchmark_name,
        benchmark_ticker,
        reporting_currency,
        target_return,
        target_risk,
        target_te,
    )


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
            st.plotly_chart(fig_pie, width="content", key=f"pie_chart_{portfolio_type}")
            return fig_pie
        else:
            st.warning("No stocks with positive weights in portfolio.")
            return None


def display_holdings_table(
    holdings_df: pd.DataFrame,
    portfolio_type: str = "max_sharpe",
    title: Optional[str] = None,
    comparison_df: Optional[pd.DataFrame] = None,
) -> Optional[pd.DataFrame]:
    """
    Display holdings table with metadata.
    
    Args:
        holdings_df: DataFrame with Ticker, Security, GICS Sector, Weight Start, Weight End
        portfolio_type: Portfolio type for display
        title: Optional custom title
        comparison_df: Matching portfolio and benchmark metrics
    
    Returns:
        Formatted holdings DataFrame for display
    """
    if title is None:
        title = _get_portfolio_display_title(portfolio_type, "Holdings")
    
    if holdings_df.empty:
        st.warning("No holdings data available.")
        return None

    title_col, export_col = st.columns([5, 1])
    with title_col:
        st.subheader(title)
    with export_col:
        st.download_button(
            "Export CSV",
            data=generate_portfolio_csv(
                holdings_df,
                comparison_df if comparison_df is not None else pd.DataFrame(),
            ),
            file_name=f"{portfolio_type}_report.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"holdings_csv_{portfolio_type}",
        )
    
    # Make a copy for display and format percentages
    holdings_display = holdings_df.copy()
    holdings_display["Weight Start"] = holdings_display["Weight Start"].map("{:.2%}".format)
    holdings_display["Weight End"] = holdings_display["Weight End"].map("{:.2%}".format)
    if "Beta to Benchmark" in holdings_display:
        holdings_display["Beta to Benchmark"] = holdings_display["Beta to Benchmark"].map("{:.2f}".format)
    if "Return Contribution" in holdings_display:
        holdings_display["Return Contribution"] = holdings_display["Return Contribution"].map("{:+.2%}".format)
    
    # Determine columns to display
    display_cols = [col for col in holdings_display.columns if col in
                    ["Ticker", "Security", "GICS Sector", "Weight Start", "Weight End",
                     "Beta to Benchmark", "Return Contribution"]]
    
    # Create column config for narrow columns
    column_config = {
        "Ticker": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Weight Start": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Weight End": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Beta to Benchmark": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
        "Return Contribution": st.column_config.TextColumn(width=COLUMN_WIDTH_SMALL),
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
    line_styles = {
        "Benchmark": {"color": "#000000", "dash": "dot", "width": 2.5},
        "Min Volatility": {"color": "#006400", "dash": "solid", "width": 2.5},
        "Max Sharpe": {"color": "#D62728", "dash": "solid", "width": 2.5},
        "Efficient Return": {"color": "#1F77B4", "dash": "solid", "width": 2.5},
        "Efficient Risk": {"color": "#FF7F0E", "dash": "solid", "width": 2.5},
        "Efficient TE": {"color": "#FF7F0E", "dash": "dot", "width": 2.5},
    }
    for trace in fig.data:
        if trace.name in line_styles:
            trace.update(line=line_styles[trace.name])
    
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
    
    st.plotly_chart(fig, width="content", key="cumulative_returns_chart")
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
    st.subheader(_get_portfolio_display_title(portfolio_type))
    holdings_col, metrics_col = st.columns([1.5, 1])
    with holdings_col:
        display_holdings_table(
            portfolio_data.get("holdings_df", pd.DataFrame()),
            portfolio_type=portfolio_type,
            comparison_df=portfolio_data.get("comparison_df", pd.DataFrame()),
        )
    with metrics_col:
        display_metrics_table(
            portfolio_data.get("comparison_df", pd.DataFrame()),
            portfolio_type=portfolio_type
        )
        if portfolio_data.get("ucits_5_10_40_compliant", False):
            st.success("This portfolio is compliant with the 5/10/40 UCITS rules.")
        else:
            st.warning("This portfolio is not compliant with the 5/10/40 UCITS rules.")
    with st.expander("Portfolio allocation"):
        display_pie_chart(
            portfolio_data.get("weights", {}),
            portfolio_type=portfolio_type
        )


def display_multiple_portfolios(optimized_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Display multiple portfolios with flexible layout for varying portfolio counts.
    
    This is the main display orchestration function for multi-portfolio analysis.
    Each portfolio is displayed as a section, with holdings beside its metrics.
    
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
    
    for portfolio_type in portfolio_types:
        display_portfolio_column(portfolio_type, portfolios[portfolio_type])
    
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
    
    display_portfolio_column(portfolio_type, portfolio_data)
    fig_chart = display_cumulative_returns_chart(
        optimized_data.get("chart_data", pd.DataFrame()),
        benchmark_name="Benchmark"
    )
    return {"fig_chart": fig_chart}


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
        holdings_display = display_holdings_table(
            data.get("holdings_df", pd.DataFrame()),
            portfolio_type="max_sharpe",
            comparison_df=data.get("comparison_df", pd.DataFrame()),
        )
        
        # 3. Metrics table
        display_metrics_table(data.get("comparison_df", pd.DataFrame()), portfolio_type="max_sharpe")
        
        # 4. Cumulative returns chart
        fig_chart = display_cumulative_returns_chart(
            data.get("chart_data", pd.DataFrame()),
            data.get("benchmark_name", "Benchmark")
        )
        
        return fig_pie, fig_chart, holdings_display
    
    return None
