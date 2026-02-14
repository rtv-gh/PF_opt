import yfinance as yf
from pypfopt import EfficientFrontier, risk_models, expected_returns

def get_data(tickers, start_date, end_date):
    data = yf.download(tickers, start=start_date, end=end_date)['Adj Close']
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