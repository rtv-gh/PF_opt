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

def calculate_series_metrics(price_series):   #Calculates annualized return, volatility, and Sharpe ratio as SCALARS
    # Annualized Return - Ensure we get a single float, not a Series
    mu = expected_returns.mean_historical_return(price_series, returns_data=False)
    if isinstance(mu, pd.Series):
        mu = mu.iloc[0]  # Extract the single scalar value
        
    # Annualized Volatility
    returns = price_series.pct_change().dropna()
    sigma = returns.std() * np.sqrt(252)
    
    # Sharpe Ratio
    sharpe = mu / sigma if sigma != 0 else 0
    
    return mu, sigma, sharpe


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
