"""
Metrics and data preparation module for Portfolio Optimizer.

This module handles all portfolio metric calculations, data transformations,
and preparation of data structures for display and export. It keeps UI logic
separate from business logic.
"""

from typing import Dict, Tuple, List, Optional
import pandas as pd
import numpy as np

from backend import (
    calculate_series_metrics,
    calculate_end_pf_weights,
    calculate_tracking_error,
    calculate_period_metrics
)
from utils import load_index_metadata
from app.config import METRICS_ANNUALIZED, METRICS_PERIOD, ANNUALIZATION_THRESHOLD_DAYS, PERCENTAGE_FORMAT, DECIMAL_FORMAT  # type: ignore


def prepare_portfolio_data(
    ticker_list: List[str],
    prices: pd.DataFrame,
    weights: Dict[str, float],
    bmk_series: pd.Series,
    period_days: int
) -> Dict:
    """
    Prepare all portfolio data in one pass, avoiding redundant calculations.
    
    This function consolidates all metric calculations and data transformations
    into a single, efficient pipeline.
    
    Args:
        ticker_list: List of tickers in portfolio
        prices: DataFrame of price history
        weights: Dict of ticker -> weight
        bmk_series: Series of benchmark prices
        period_days: Number of days in analysis period
    
    Returns:
        Dict containing:
            - port_perf: (return, volatility, sharpe) annualized
            - bmk_perf: (return, volatility, sharpe) conditional annualization
            - port_period_metrics: (cum_ret, volatility, sharpe) period metrics
            - bmk_period_metrics: (cum_ret, volatility, sharpe) period metrics
            - tracking_error: annualized tracking error
            - chart_data: DataFrame with cumulative returns time series
            - port_cum_rets: Series of portfolio cumulative returns
            - bmk_cum_rets: Series of benchmark cumulative returns
    """
    annualize = period_days >= ANNUALIZATION_THRESHOLD_DAYS
    
    # Portfolio returns
    port_returns = prices.pct_change().dropna()
    port_daily_rets = (port_returns * pd.Series(weights)).sum(axis=1)
    port_cum_rets = (1 + port_daily_rets).cumprod() - 1
    port_cum_ret_final = port_cum_rets.iloc[-1] if len(port_cum_rets) > 0 else 0
    
    # Benchmark returns
    bmk_daily_rets = bmk_series.pct_change().dropna()
    bmk_cum_rets = (bmk_series / bmk_series.iloc[0]) - 1
    bmk_cum_ret_final = bmk_cum_rets.iloc[-1] if len(bmk_cum_rets) > 0 else 0
    
    # Metrics calculation
    port_perf = calculate_series_metrics(prices.mean(axis=1), annualize=True)  # Portfolio annualized
    bmk_perf = calculate_series_metrics(bmk_series, annualize=annualize)  # Benchmark conditional
    tracking_error = calculate_tracking_error(port_daily_rets, bmk_daily_rets)
    
    # Period metrics
    port_period_metrics = calculate_period_metrics(port_daily_rets, port_cum_ret_final, len(port_daily_rets))
    bmk_period_metrics = calculate_period_metrics(bmk_daily_rets, bmk_cum_ret_final, len(bmk_daily_rets))
    
    # Chart data
    chart_data = pd.DataFrame({
        "Max Sharpe PF": port_cum_rets,
        "Benchmark": bmk_cum_rets
    }).fillna(0)
    
    return {
        "port_perf": port_perf,
        "bmk_perf": bmk_perf,
        "port_period_metrics": port_period_metrics,
        "bmk_period_metrics": bmk_period_metrics,
        "tracking_error": tracking_error,
        "chart_data": chart_data,
        "port_cum_rets": port_cum_rets,
        "bmk_cum_rets": bmk_cum_rets,
        "port_daily_rets": port_daily_rets,
        "bmk_daily_rets": bmk_daily_rets,
    }


def build_comparison_dataframe(
    port_perf: Tuple[float, float, float],
    bmk_perf: Tuple[float, float, float],
    port_period_metrics: Tuple[float, float, float],
    bmk_period_metrics: Tuple[float, float, float],
    tracking_error: float,
    period_days: int
) -> pd.DataFrame:
    """
    Build the metrics comparison DataFrame (used for both display and export).
    
    This eliminates duplication between UI display and Excel export.
    
    Args:
        port_perf: Portfolio annualized metrics (return, vol, sharpe)
        bmk_perf: Benchmark metrics (conditional annualization)
        port_period_metrics: Portfolio period metrics (cum_ret, vol, sharpe)
        bmk_period_metrics: Benchmark period metrics (cum_ret, vol, sharpe)
        tracking_error: Annualized tracking error
        period_days: Number of days in analysis period
    
    Returns:
        DataFrame with Portfolio and Benchmark columns
    """
    annualize = period_days >= ANNUALIZATION_THRESHOLD_DAYS
    
    if annualize:
        comparison_df = pd.DataFrame({
            "Portfolio": [
                f"{port_period_metrics[0]:.1%}",  # Cumulative Return
                f"{port_perf[0]:.1%}",  # Annualized Return
                f"{port_perf[1]:.1%}",  # Annualized Volatility
                f"{port_perf[2]:.2f}",  # Sharpe Ratio
                f"{tracking_error:.1%}"  # Annualized Tracking Error
            ],
            "Benchmark": [
                f"{bmk_period_metrics[0]:.1%}",  # Cumulative Return
                f"{bmk_perf[0]:.1%}",  # Annualized Return
                f"{bmk_perf[1]:.1%}",  # Annualized Volatility
                f"{bmk_perf[2]:.2f}",  # Sharpe Ratio
                "-"  # No tracking error for benchmark
            ]
        }, index=METRICS_ANNUALIZED)
    else:
        comparison_df = pd.DataFrame({
            "Portfolio": [
                f"{port_period_metrics[0]:.1%}",  # Cumulative Return
                f"{port_period_metrics[1]:.1%}",  # Period Volatility
                f"{port_period_metrics[2]:.2f}",  # Period Sharpe
                f"{tracking_error:.1%}"  # Annualized Tracking Error
            ],
            "Benchmark": [
                f"{bmk_period_metrics[0]:.1%}",  # Cumulative Return
                f"{bmk_period_metrics[1]:.1%}",  # Period Volatility
                f"{bmk_period_metrics[2]:.2f}",  # Period Sharpe
                "-"  # No tracking error for benchmark
            ]
        }, index=METRICS_PERIOD)
    
    return comparison_df


def build_holdings_dataframe(
    prices: pd.DataFrame,
    weights: Dict[str, float],
    format_percentages: bool = False
) -> pd.DataFrame:
    """
    Build the holdings DataFrame with ticker, name, sector, and weights.
    
    This eliminates duplication between display and export logic.
    
    Args:
        prices: DataFrame of price history
        weights: Dict of ticker -> weight
        format_percentages: If True, format weights as percentage strings
    
    Returns:
        DataFrame with columns: Ticker, Security, GICS Sector, Weight Start, Weight End
    """
    # Calculate start and end weights
    w_start, w_end = calculate_end_pf_weights(prices, weights)
    
    if w_start.empty:
        return pd.DataFrame()
    
    holdings = pd.DataFrame({
        "Weight Start": w_start,
        "Weight End": w_end
    }).fillna(0)
    
    # Load metadata and join
    meta = load_index_metadata(sheet_name="SPX")
    if not meta.empty:
        holdings = holdings.join(meta, how="left")
    
    # Sort by Weight Start descending
    holdings = holdings.sort_values("Weight Start", ascending=False)
    
    # Reset index to put ticker in a column
    holdings = holdings.reset_index().rename(columns={"index": "Ticker"})
    
    # Format percentages if requested
    if format_percentages:
        holdings["Weight Start"] = holdings["Weight Start"].map("{:.2%}".format)
        holdings["Weight End"] = holdings["Weight End"].map("{:.2%}".format)
    
    # Ensure column order: Ticker, Security, GICS Sector, Weight Start, Weight End
    cols = ["Ticker", "Weight Start", "Weight End"]
    if "Security" in holdings.columns:
        cols = ["Ticker", "Security", "Weight Start", "Weight End"]
    if "GICS Sector" in holdings.columns:
        cols = ["Ticker", "GICS Sector", "Weight Start", "Weight End"]
        if "Security" in holdings.columns:
            cols = ["Ticker", "Security", "GICS Sector", "Weight Start", "Weight End"]
    
    return holdings[cols]


def get_pie_chart_data(weights: Dict[str, float]) -> Tuple[List[str], List[float]]:
    """
    Filter and prepare data for pie chart visualization.
    
    Excludes stocks with 0% weight to reduce chart clutter.
    
    Args:
        weights: Dict of ticker -> weight
    
    Returns:
        Tuple of (tickers_list, weights_list) filtered to non-zero weights
    """
    weights_filtered = {ticker: weight for ticker, weight in weights.items() if weight > 0}
    return list(weights_filtered.keys()), list(weights_filtered.values())
