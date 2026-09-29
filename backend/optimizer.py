import numpy as np # pyright: ignore[reportMissingImports]
import pandas as pd # pyright: ignore[reportMissingModuleSource]
import yfinance as yf # pyright: ignore[reportMissingImports]
import cvxpy as cp # pyright: ignore[reportMissingImports]
from pypfopt import EfficientFrontier, risk_models, expected_returns, objective_functions # pyright: ignore[reportMissingImports]
from typing import Dict, Tuple, Optional


class PortfolioOptimizationError(ValueError):
    """Raised when one or more portfolio optimization requests fail."""


def _add_ucits_constraints(ef: EfficientFrontier, prices: pd.DataFrame) -> None:
    """Constrain the portfolio to the 5/10/40 limits at every observed price date."""
    price_relatives = (prices / prices.iloc[0]).to_numpy()
    largest_count = min(8, len(prices.columns))

    for relative_prices in price_relatives:
        ef.add_constraint(
            lambda weights, relatives=relative_prices: (
                cp.multiply(weights, relatives)
                - 0.10 * cp.sum(cp.multiply(weights, relatives))
                <= 0
            )
        )
        ef.add_constraint(
            lambda weights, relatives=relative_prices, count=largest_count: (
                cp.sum_largest(cp.multiply(weights, relatives), count)
                - 0.40 * cp.sum(cp.multiply(weights, relatives))
                <= 0
            )
        )


def _create_frontier(
    expected_returns_series: pd.Series,
    covariance: pd.DataFrame,
    prices: pd.DataFrame,
    ucits_5_10_40: bool,
) -> EfficientFrontier:
    if ucits_5_10_40:
        ef = EfficientFrontier(
            expected_returns_series,
            covariance,
            solver="CLARABEL",
            solver_options={
                "tol_gap_abs": 1e-8,
                "tol_gap_rel": 1e-8,
                "tol_feas": 1e-8,
                "max_iter": 1000,
            },
        )
        _add_ucits_constraints(ef, prices)
        return ef
    return EfficientFrontier(expected_returns_series, covariance)


def max_sharpe_portfolio(
    data: pd.DataFrame,
    ucits_5_10_40: bool = False,
) -> Tuple[Dict[str, float], Tuple[float, float, float]]:
    """
    Optimize for maximum Sharpe ratio portfolio.
    
    Args:
        data: DataFrame of price history with tickers as columns
    
    Returns:
        Tuple of (weights_dict, perf_tuple) where:
            - weights_dict: Dict mapping ticker -> weight
            - perf_tuple: (annualized_return, annualized_volatility, sharpe_ratio)
    """
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)
    
    ef = _create_frontier(mu, S, data, ucits_5_10_40)
    weights = ef.max_sharpe()
    cleaned_weights = ef.clean_weights()
    
    perf = ef.portfolio_performance(verbose=False)
    return cleaned_weights, perf


def min_variance_portfolio(
    data: pd.DataFrame,
    ucits_5_10_40: bool = False,
) -> Tuple[Dict[str, float], Tuple[float, float, float]]:
    """
    Optimize for minimum variance (volatility) portfolio.
    
    Args:
        data: DataFrame of price history with tickers as columns
    
    Returns:
        Tuple of (weights_dict, perf_tuple) where:
            - weights_dict: Dict mapping ticker -> weight
            - perf_tuple: (annualized_return, annualized_volatility, sharpe_ratio)
    """
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)
    
    ef = _create_frontier(mu, S, data, ucits_5_10_40)
    weights = ef.min_volatility()
    cleaned_weights = ef.clean_weights()
    
    perf = ef.portfolio_performance(verbose=False)
    return cleaned_weights, perf


def efficient_return_portfolio(
    data: pd.DataFrame,
    target_return: float,
    ucits_5_10_40: bool = False,
) -> Tuple[Dict[str, float], Tuple[float, float, float]]:
    """
    Optimize for efficient return portfolio (minimum risk for target return).
    
    Given a target expected return, finds the portfolio with minimum volatility
    that achieves that return. This is on the Efficient Frontier.
    
    Args:
        data: DataFrame of price history with tickers as columns
        target_return: Target expected return (e.g., 0.10 for 10%)
    
    Returns:
        Tuple of (weights_dict, perf_tuple) where:
            - weights_dict: Dict mapping ticker -> weight
            - perf_tuple: (annualized_return, annualized_volatility, sharpe_ratio)
    
    Raises:
        ValueError: If target return is outside achievable range
    """
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)
    
    ef = _create_frontier(mu, S, data, ucits_5_10_40)
    
    try:
        weights = ef.efficient_return(target_return)
        cleaned_weights = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        return cleaned_weights, perf
    except ValueError as e:
        raise ValueError(f"Target return {target_return:.2%} not achievable. Error: {str(e)}")


def efficient_risk_portfolio(
    data: pd.DataFrame,
    target_risk: float,
    ucits_5_10_40: bool = False,
) -> Tuple[Dict[str, float], Tuple[float, float, float]]:
    """
    Optimize for efficient risk portfolio (maximum return for target risk).
    
    Given a target volatility level, finds the portfolio with maximum return
    that achieves that volatility. This is on the Efficient Frontier.
    
    Args:
        data: DataFrame of price history with tickers as columns
        target_risk: Target volatility/risk level as std dev (e.g., 0.15 for 15%)
    
    Returns:
        Tuple of (weights_dict, perf_tuple) where:
            - weights_dict: Dict mapping ticker -> weight
            - perf_tuple: (annualized_return, annualized_volatility, sharpe_ratio)
    
    Raises:
        ValueError: If target risk is outside achievable range
    """
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)
    
    ef = _create_frontier(mu, S, data, ucits_5_10_40)
    
    try:
        weights = ef.efficient_risk(target_risk)
        cleaned_weights = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        return cleaned_weights, perf
    except ValueError as e:
        raise ValueError(f"Target risk {target_risk:.2%} not achievable. Error: {str(e)}")


def efficient_tracking_error_portfolio(
    data: pd.DataFrame, 
    target_te: float,
    benchmark_weights: Optional[np.ndarray] = None,
    ucits_5_10_40: bool = False,
) -> Tuple[Dict[str, float], Tuple[float, float, float]]:
    """
    Optimize for maximum return with a target tracking error constraint.
    
    Given a target tracking error, finds the portfolio with maximum return
    while staying within the tracking error budget relative to a benchmark.
    This is useful for portfolios designed to follow a benchmark closely
    while potentially outperforming it.
    
    Args:
        data: DataFrame of price history with tickers as columns
        target_te: Target tracking error (annualized, e.g., 0.05 for 5% TE)
        benchmark_weights: Array of benchmark weights (must sum to 1).
                          If None, uses equal weights (1/n portfolio).
    
    Returns:
        Tuple of (weights_dict, perf_tuple) where:
            - weights_dict: Dict mapping ticker -> weight
            - perf_tuple: (annualized_return, annualized_volatility, sharpe_ratio)
    
    Raises:
        ValueError: If target tracking error is outside achievable range
    """
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)
    
    # Use equal weights (1/n) if benchmark not provided
    if benchmark_weights is None:
        benchmark_weights = np.ones(len(mu)) / len(mu)
    
    ef = _create_frontier(mu, S, data, ucits_5_10_40)
    
    try:
        # Add constraint: tracking error <= target_te
        # Note: ex_ante_tracking_error returns squared TE, so we compare target_te**2
        ef.add_constraint(
            lambda w: objective_functions.ex_ante_tracking_error(w, S, benchmark_weights) <= target_te**2
        )
        
        # Optimize for maximum Sharpe ratio (balances return vs risk while tracking)
        weights = ef.max_sharpe()
        cleaned_weights = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        return cleaned_weights, perf
    except ValueError as e:
        raise ValueError(f"Target tracking error {target_te:.2%} not achievable. Error: {str(e)}")


def optimize_multiple_portfolios(
    data: pd.DataFrame, 
    target_return: Optional[float] = None, 
    target_risk: Optional[float] = None,
    target_te: Optional[float] = None,
    benchmark_weights: Optional[np.ndarray] = None,
    ucits_5_10_40: bool = False,
) -> Dict[str, Tuple[Dict[str, float], Tuple[float, float, float]]]:
    """
    Optimize multiple portfolio types in a single pass.
    
    This function computes multiple portfolio optimizations efficiently by reusing
    the covariance matrix and expected returns calculations.
    
    Args:
        data: DataFrame of price history with tickers as columns
        target_return: Target return for efficient_return portfolio (optional, e.g., 0.10 for 10%)
        target_risk: Target volatility for efficient_risk portfolio (optional, e.g., 0.15 for 15%)
        target_te: Target tracking error for efficient_te portfolio (optional, e.g., 0.05 for 5%)
        benchmark_weights: Benchmark weights for tracking error calculation (optional)
    
    Returns:
        Dict mapping portfolio type -> (weights, performance)
        Always includes:
        - "max_sharpe": Portfolio with maximum Sharpe ratio (risk-adjusted returns)
        - "min_variance": Portfolio with minimum volatility
        
        Optionally includes (if targets provided):
        - "efficient_return": Portfolio with minimum volatility at target return
        - "efficient_risk": Portfolio with maximum return at target volatility
        - "efficient_te": Portfolio with max return at target tracking error
    
    Raises:
        PortfolioOptimizationError: If one or more portfolio optimizations fail
    """
    portfolio_jobs = [
        ("Max Sharpe", "max_sharpe", lambda: max_sharpe_portfolio(data, ucits_5_10_40)),
        ("Minimum Variance", "min_variance", lambda: min_variance_portfolio(data, ucits_5_10_40)),
    ]
    if target_return is not None:
        portfolio_jobs.append((
            f"Efficient Return (target return {target_return:.2%})",
            "efficient_return",
            lambda: efficient_return_portfolio(data, target_return, ucits_5_10_40),
        ))
    if target_risk is not None:
        portfolio_jobs.append((
            f"Efficient Risk (target risk {target_risk:.2%})",
            "efficient_risk",
            lambda: efficient_risk_portfolio(data, target_risk, ucits_5_10_40),
        ))
    if target_te is not None:
        portfolio_jobs.append((
            f"Efficient Tracking Error (target tracking error {target_te:.2%})",
            "efficient_te",
            lambda: efficient_tracking_error_portfolio(
                data,
                target_te,
                benchmark_weights=benchmark_weights,
                ucits_5_10_40=ucits_5_10_40,
            ),
        ))

    portfolios = {}
    failures = []
    for display_name, portfolio_key, optimize in portfolio_jobs:
        try:
            portfolios[portfolio_key] = optimize()
        except Exception as error:
            details = "; ".join(str(argument) for argument in error.args) or str(error)
            failures.append(f"- {display_name}: {details}")

    if failures:
        raise PortfolioOptimizationError(
            "The following portfolio optimizations failed:\n" + "\n".join(failures)
        )

    return portfolios


def optimize_portfolio(data):
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use max_sharpe_portfolio() or optimize_multiple_portfolios() instead.
    """
    return max_sharpe_portfolio(data)

def calculate_series_metrics(price_series, annualize=True):   
    """
    Calculates return, volatility, and Sharpe ratio.
    
    Args:
        price_series: Series of prices
        annualize: If True, annualize metrics. If False, return period metrics.
    
    Returns:
        tuple: (return, volatility, sharpe) as SCALARS
    """
    # Return - Ensure we get a single float, not a Series
    mu = expected_returns.mean_historical_return(price_series, returns_data=False)
    if isinstance(mu, pd.Series):
        mu = mu.iloc[0]  # Extract the single scalar value
        
    # Volatility
    returns = price_series.pct_change().dropna()
    sigma = returns.std() * np.sqrt(252)
    
    # Sharpe Ratio
    sharpe = mu / sigma if sigma != 0 else 0
    
    # If not annualizing, convert annualized metrics back to period metrics
    if not annualize:
        num_periods = len(returns) / 252
        mu = (1 + mu) ** num_periods - 1
        sigma = sigma / np.sqrt(252 / num_periods)
        sharpe = mu / sigma if sigma != 0 else 0
    
    return mu, sigma, sharpe


def calculate_tracking_error(portfolio_returns, benchmark_returns):
    """
    Calculate annualized tracking error between portfolio and benchmark.
    
    Args:
        portfolio_returns: Series of portfolio daily returns
        benchmark_returns: Series of benchmark daily returns
    
    Returns:
        float: Annualized tracking error as a scalar
    """
    # Ensure same length and alignment
    common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
    pf_ret = portfolio_returns.loc[common_dates]
    bmk_ret = benchmark_returns.loc[common_dates]
    
    # Tracking error = std dev of (pf returns - bmk returns)
    tracking_error = (pf_ret - bmk_ret).std() * np.sqrt(252)
    
    return tracking_error


def calculate_period_metrics(returns_series, cumulative_return, num_trading_days=None):
    """
    Calculate non-annualized (period) metrics for returns over a specific period.
    
    Args:
        returns_series: Series of daily returns
        cumulative_return: The final cumulative return over the period
        num_trading_days: Number of trading days (optional, defaults to len(returns_series))
    
    Returns:
        tuple: (cumulative_return, period_volatility, period_sharpe) as SCALARS
    """
    if num_trading_days is None:
        num_trading_days = len(returns_series)
    
    # Period volatility: scale daily volatility by sqrt of trading days
    daily_vol = returns_series.std()
    period_vol = daily_vol * np.sqrt(num_trading_days)
    
    # Period Sharpe: cumulative return / period volatility
    period_sharpe = cumulative_return / period_vol if period_vol != 0 else 0
    
    return cumulative_return, period_vol, period_sharpe


def calculate_end_pf_weights(prices_df, weights):
    """
    Calculate start and end portfolio weights.
    
    Args:
        prices_df: DataFrame of prices with tickers as columns
        weights: dict of ticker -> weight (from optimizer)
    
    Returns:
        (w_start, w_end): pd.Series of start and end weights
    """
    # Filter weights to only existing tickers in price data
    valid_tickers = [t for t in weights.keys() if t in prices_df.columns]
    w_start = pd.Series({t: weights[t] for t in valid_tickers})
    
    if w_start.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    
    # Calculate end-of-period values
    price_ratios = prices_df[valid_tickers].iloc[-1] / prices_df[valid_tickers].iloc[0]
    ending_values = w_start * price_ratios
    w_end = ending_values / ending_values.sum()
    
    return w_start, w_end
