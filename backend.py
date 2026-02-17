import yfinance as yf # pyright: ignore[reportMissingImports]
from pypfopt import EfficientFrontier, risk_models, expected_returns # pyright: ignore[reportMissingImports]

def get_data(tickers, start_date, end_date):
    # Validate date range (max 5 years)
    max_days = 365 * 5
    date_diff = (end_date - start_date).days
    
    if date_diff > max_days:
        raise ValueError(
            f"Date range exceeds maximum allowed period of 5 years. "
            f"Requested: {date_diff} days, Maximum: {max_days} days."
        )
    
    data = yf.download(tickers, start=start_date, end=end_date)['Close']
    return data

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