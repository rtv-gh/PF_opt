import numpy as np # pyright: ignore[reportMissingImports]
import pandas as pd # pyright: ignore[reportMissingModuleSource]
import yfinance as yf # pyright: ignore[reportMissingImports]
from pypfopt import EfficientFrontier, risk_models, expected_returns # pyright: ignore[reportMissingImports]


def optimize_portfolio(data):
    # Calculate expected returns and sample covariance
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)

    # Optimize for maximal Sharpe ratio
    ef = EfficientFrontier(mu, S)
    weights = ef.max_sharpe()
    cleaned_weights = ef.clean_weights()
    
    # Get performance metrics
    perf = ef.portfolio_performance(verbose=False)
    return cleaned_weights, perf

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
