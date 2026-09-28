"""
Metrics and data preparation module for Portfolio Optimizer.

This module handles all portfolio metric calculations, data transformations,
and preparation of data structures for display and export. It keeps UI logic
separate from business logic.

Supports multiple portfolio types (Max Sharpe, Min Variance, etc.) with a
scalable architecture for future extensions.
"""

from typing import Dict, Tuple, List, Optional, Any

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


def prepare_multiple_portfolio_data(
    ticker_list: List[str],
    prices: pd.DataFrame,
    portfolios: Dict[str, Dict[str, float]],
    bmk_series: pd.Series,
    period_days: int,
    beta_benchmark_series: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """
    Prepare data for multiple portfolio types in a single pass.
    
    This is the primary function for multi-portfolio analysis, computing all
    metrics and data structures efficiently.
    
    Args:
        ticker_list: List of tickers in each portfolio
        prices: DataFrame of price history (shared across all portfolios)
        portfolios: Dict mapping portfolio_type -> weights_dict
                   e.g., {"max_sharpe": {...}, "min_variance": {...}}
        bmk_series: Series of benchmark prices (shared across all portfolios)
        period_days: Number of days in analysis period
        beta_benchmark_series: Benchmark prices in the same currency as stock prices
    
    Returns:
        Dict with structure:
        {
            "portfolios": {
                "max_sharpe": {
                    "weights": dict,
                    "cum_rets": series,
                    "daily_rets": series,
                    "perf": tuple,
                    "period_metrics": tuple,
                    "tracking_error": float,
                    "holdings_df": dataframe,
                    "comparison_df": dataframe,
                },
                "min_variance": {...},
                ...
            },
            "benchmark": {
                "cum_rets": series,
                "daily_rets": series,
                "perf": tuple,
                "period_metrics": tuple,
            },
            "prices": dataframe,
            "period_days": int,
            "annualize": bool,
        }
    """
    # Compute benchmark metrics once (shared across all portfolios)
    bmk_daily_rets = bmk_series.pct_change().dropna()
    beta_benchmark_prices = (
        beta_benchmark_series if beta_benchmark_series is not None else bmk_series
    )
    beta_benchmark_returns = beta_benchmark_prices.pct_change().dropna()
    bmk_cum_rets = (bmk_series / bmk_series.iloc[0]) - 1
    bmk_cum_ret_final = bmk_cum_rets.iloc[-1] if len(bmk_cum_rets) > 0 else 0
    bmk_period_metrics = calculate_period_metrics(bmk_daily_rets, bmk_cum_ret_final, len(bmk_daily_rets))
    
    # Compute data for each portfolio type
    portfolios_data: Dict[str, Any] = {}
    cumulative_returns_dict = {"Benchmark": bmk_cum_rets}
    
    for portfolio_type, weights in portfolios.items():
        # The optimizer uses fixed daily weights, so all metrics use that same return series.
        asset_returns = prices.pct_change().dropna()
        weight_series = pd.Series(weights, dtype=float).reindex(prices.columns).fillna(0.0)
        if weight_series.sum() != 0:
            weight_series = weight_series / weight_series.sum()
        aligned_returns = pd.concat(
            [asset_returns, bmk_daily_rets.rename("Benchmark")], axis=1, join="inner"
        ).dropna()
        asset_returns = aligned_returns[asset_returns.columns]
        benchmark_returns = aligned_returns["Benchmark"]
        port_daily_rets = asset_returns.mul(weight_series, axis=1).sum(axis=1)
        port_cum_rets = (1 + port_daily_rets).cumprod() - 1
        port_cum_ret_final = port_cum_rets.iloc[-1] if len(port_cum_rets) > 0 else 0
        bmk_cum_rets = (1 + benchmark_returns).cumprod() - 1
        bmk_cum_ret_final = bmk_cum_rets.iloc[-1] if len(bmk_cum_rets) > 0 else 0
        
        # Annualize both portfolio and benchmark risk regardless of observation length.
        port_perf = _calculate_annualized_return_metrics(port_daily_rets)
        bmk_perf = _calculate_annualized_return_metrics(benchmark_returns)
        active_returns = port_daily_rets - benchmark_returns
        tracking_error = active_returns.std() * np.sqrt(252)
        information_ratio = (
            active_returns.mean() / active_returns.std() * np.sqrt(252)
            if active_returns.std() != 0 else 0.0
        )
        beta_aligned_returns = pd.concat(
            [prices.pct_change().dropna(), beta_benchmark_returns.rename("Beta Benchmark")],
            axis=1,
            join="inner",
        ).dropna()
        beta_benchmark_aligned = beta_aligned_returns["Beta Benchmark"]
        benchmark_variance = beta_benchmark_aligned.var()
        portfolio_beta = (
            beta_aligned_returns[prices.columns].mul(weight_series, axis=1).sum(axis=1)
            .cov(beta_benchmark_aligned) / benchmark_variance
            if benchmark_variance != 0 else 0.0
        )
        port_max_drawdown = _calculate_max_drawdown(port_daily_rets)
        bmk_max_drawdown = _calculate_max_drawdown(benchmark_returns)
        port_period_metrics = calculate_period_metrics(port_daily_rets, port_cum_ret_final, len(port_daily_rets))
        bmk_period_metrics = calculate_period_metrics(benchmark_returns, bmk_cum_ret_final, len(benchmark_returns))

        # Attribute each day's portfolio P&L to its stocks; contributions sum to total return.
        prior_portfolio_value = (1 + port_daily_rets).cumprod().shift(1, fill_value=1.0)
        return_contributions = asset_returns.mul(weight_series, axis=1).mul(
            prior_portfolio_value, axis=0
        ).sum(axis=0)
        relative_contributions = return_contributions - weight_series * bmk_cum_ret_final
        asset_betas = {
            ticker: (
                beta_aligned_returns[ticker].cov(beta_benchmark_aligned) / benchmark_variance
                if benchmark_variance != 0 else 0.0
            )
            for ticker in beta_aligned_returns[prices.columns].columns
        }
        best_relative = relative_contributions.idxmax() if not relative_contributions.empty else "-"
        worst_relative = relative_contributions.idxmin() if not relative_contributions.empty else "-"
        best_relative_label = (
            f"{best_relative} ({relative_contributions[best_relative]:+.2%})"
            if best_relative != "-" else "-"
        )
        worst_relative_label = (
            f"{worst_relative} ({relative_contributions[worst_relative]:+.2%})"
            if worst_relative != "-" else "-"
        )
        
        # Build comparison DataFrame
        comparison_df = _build_portfolio_comparison_dataframe(
            port_perf=port_perf,
            bmk_perf=bmk_perf,
            port_period_metrics=port_period_metrics,
            bmk_period_metrics=bmk_period_metrics,
            tracking_error=tracking_error,
            period_days=period_days,
            portfolio_beta=portfolio_beta,
            information_ratio=information_ratio,
            port_max_drawdown=port_max_drawdown,
            bmk_max_drawdown=bmk_max_drawdown,
            best_relative_contributor=best_relative_label,
            worst_relative_contributor=worst_relative_label,
        )
        
        # Build holdings DataFrame
        holdings_df = build_holdings_dataframe(
            prices,
            weight_series.to_dict(),
            format_percentages=False,
            asset_betas=asset_betas,
            return_contributions=return_contributions.to_dict(),
        )
        ucits_compliant = is_ucits_5_10_40_compliant(prices, weight_series.to_dict())
        
        # Store portfolio data
        portfolios_data[portfolio_type] = {
            "weights": weights,
            "cum_rets": port_cum_rets,
            "daily_rets": port_daily_rets,
            "perf": port_perf,
            "period_metrics": port_period_metrics,
            "tracking_error": tracking_error,
            "portfolio_beta": portfolio_beta,
            "information_ratio": information_ratio,
            "ucits_5_10_40_compliant": ucits_compliant,
            "holdings_df": holdings_df,
            "comparison_df": comparison_df,
        }
        
        # Add to cumulative returns chart data
        portfolio_label = _get_portfolio_display_name(portfolio_type)
        cumulative_returns_dict[portfolio_label] = port_cum_rets
    
    # Build combined performance chart
    chart_data = pd.DataFrame(cumulative_returns_dict).fillna(0)
    
    time_series = pd.DataFrame({
        _get_portfolio_display_name(portfolio_type): portfolio_data["daily_rets"]
        for portfolio_type, portfolio_data in portfolios_data.items()
    })
    time_series["Benchmark"] = bmk_daily_rets

    return {
        "portfolios": portfolios_data,
        "benchmark": {
            "cum_rets": bmk_cum_rets,
            "daily_rets": bmk_daily_rets,
            "perf": bmk_perf,
            "period_metrics": bmk_period_metrics,
        },
        "prices": prices,
        "period_days": period_days,
        "annualize": True,
        "chart_data": chart_data,
        "time_series": time_series,
    }


def _get_portfolio_display_name(portfolio_type: str) -> str:
    """
    Convert portfolio type key to display name.
    
    Args:
        portfolio_type: Internal portfolio type (e.g., "max_sharpe", "min_variance", "efficient_return", "efficient_risk", "efficient_te")
    
    Returns:
        Display name (e.g., "Max Sharpe", "Min Volatility", "Efficient Return", "Efficient Risk", "Efficient TE")
    """
    display_names = {
        "max_sharpe": "Max Sharpe",
        "min_variance": "Min Volatility",
        "efficient_return": "Efficient Return",
        "efficient_risk": "Efficient Risk",
        "efficient_te": "Efficient TE",
    }
    return display_names.get(portfolio_type, portfolio_type.replace("_", " ").title())


def _build_portfolio_comparison_dataframe(
    port_perf: Tuple[float, float, float],
    bmk_perf: Tuple[float, float, float],
    port_period_metrics: Tuple[float, float, float],
    bmk_period_metrics: Tuple[float, float, float],
    tracking_error: float,
    period_days: int,
    portfolio_beta: float = 0.0,
    information_ratio: float = 0.0,
    port_max_drawdown: float = 0.0,
    bmk_max_drawdown: float = 0.0,
    best_relative_contributor: str = "-",
    worst_relative_contributor: str = "-",
) -> pd.DataFrame:
    """
    Internal function to build comparison DataFrame for a single portfolio.
    
    This is used by both the single-portfolio and multi-portfolio preparation functions.
    """
    return pd.DataFrame({
        "Portfolio": [
            f"{port_period_metrics[0]:.1%}",
            f"{port_perf[0]:.1%}",
            f"{port_perf[1]:.1%}",
            f"{port_perf[2]:.2f}",
            f"{port_max_drawdown:.1%}",
            f"{tracking_error:.1%}",
            f"{portfolio_beta:.2f}",
            f"{information_ratio:.2f}",
            best_relative_contributor,
            worst_relative_contributor,
        ],
        "Benchmark": [
            f"{bmk_period_metrics[0]:.1%}",
            f"{bmk_perf[0]:.1%}",
            f"{bmk_perf[1]:.1%}",
            f"{bmk_perf[2]:.2f}",
            f"{bmk_max_drawdown:.1%}",
            "-",
            "-",
            "-",
            "-",
            "-",
        ],
    }, index=METRICS_ANNUALIZED)


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
    
    Legacy function for backward compatibility. Use _build_portfolio_comparison_dataframe().
    
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
    return _build_portfolio_comparison_dataframe(
        port_perf, bmk_perf, port_period_metrics, bmk_period_metrics, tracking_error, period_days
    )


def build_holdings_dataframe(
    prices: pd.DataFrame,
    weights: Dict[str, float],
    format_percentages: bool = False,
    asset_betas: Optional[Dict[str, float]] = None,
    return_contributions: Optional[Dict[str, float]] = None,
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
        "Weight End": w_end,
        "Beta to Benchmark": pd.Series(asset_betas or {}, dtype=float),
        "Return Contribution": pd.Series(return_contributions or {}, dtype=float),
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
    
    # Ensure column order: identifying fields, weights, then requested stock metrics.
    cols = ["Ticker", "Weight Start", "Weight End", "Beta to Benchmark", "Return Contribution"]
    if "Security" in holdings.columns:
        cols = ["Ticker", "Security", "Weight Start", "Weight End", "Beta to Benchmark", "Return Contribution"]
    if "GICS Sector" in holdings.columns:
        cols = ["Ticker", "GICS Sector", "Weight Start", "Weight End", "Beta to Benchmark", "Return Contribution"]
        if "Security" in holdings.columns:
            cols = ["Ticker", "Security", "GICS Sector", "Weight Start", "Weight End", "Beta to Benchmark", "Return Contribution"]
    
    return holdings[cols]


def _calculate_annualized_return_metrics(returns: pd.Series) -> Tuple[float, float, float]:
    """Calculate annualized geometric return, volatility, and zero-rate Sharpe ratio."""
    clean_returns = returns.dropna()
    if clean_returns.empty:
        return 0.0, 0.0, 0.0

    volatility = clean_returns.std() * np.sqrt(252)
    annualized_arithmetic_return = clean_returns.mean() * 252
    cumulative_growth = (1 + clean_returns).prod()
    annualized_return = (
        cumulative_growth ** (252 / len(clean_returns)) - 1
        if cumulative_growth > 0 else -1.0
    )
    sharpe = annualized_arithmetic_return / volatility if volatility != 0 else 0.0
    return annualized_return, volatility, sharpe


def _calculate_max_drawdown(returns: pd.Series) -> float:
    """Calculate peak-to-trough drawdown including the initial investment value."""
    wealth = (1 + returns.dropna()).cumprod()
    wealth = pd.concat([pd.Series([1.0], index=[-1]), wealth])
    return float((wealth / wealth.cummax() - 1).min()) if len(wealth) else 0.0


def is_ucits_5_10_40_compliant(
    prices: pd.DataFrame,
    weights: Dict[str, float],
    tolerance: float = 1e-8,
) -> bool:
    """Check the 5/10/40 limits against drifting issuer weights on each price date."""
    valid_weights = pd.Series(weights, dtype=float).reindex(prices.columns).fillna(0.0)
    if prices.empty or valid_weights.sum() <= 0:
        return False
    valid_weights = valid_weights / valid_weights.sum()
    relative_prices = prices.div(prices.iloc[0], axis=1)
    market_values = relative_prices.mul(valid_weights, axis=1)
    daily_weights = market_values.div(market_values.sum(axis=1), axis=0)
    largest_issuer_weight = daily_weights.max(axis=1)
    total_above_five_percent = daily_weights.where(
        daily_weights > 0.05 + tolerance,
        0.0,
    ).sum(axis=1)
    return bool(
        (largest_issuer_weight <= 0.10 + tolerance).all()
        and (total_above_five_percent <= 0.40 + tolerance).all()
    )


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
