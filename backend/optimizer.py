import numpy as np
import pandas as pd
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