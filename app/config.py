"""
Configuration and constants for Portfolio Optimizer.

This module centralizes all configuration, constants, and defaults to provide
a single source of truth for the application.
"""

from typing import Dict

# ============================================================================
# MARKET CONFIGURATION
# ============================================================================
DEFAULT_TICKERS_USA = "AAPL,MA,META,V,AMZN,BA,BAC,BNY,C,GS,JPM,MS,STT,WFC,LLY,BSX,JNJ,XOM,MDT,MSFT,GOOGL,NVDA,AVGO,CRM,UNH"
DEFAULT_TICKERS_UK = "AZN.L,HSBA.L,SHEL.L,ULVR.L,BP.L,BARC.L,REL.L,RR.L,GSK.L,NG.L"
MARKET_CONFIGS: Dict[str, Dict] = {
    "USA": {
        "benchmarks": {
            "S&P 500": "SPY",
            "MSCI ACWI": "ACWI",
        },
        "default_benchmark": "S&P 500",
        "default_currency": "USD",
        "default_tickers": DEFAULT_TICKERS_USA,
    },
    "UK": {
        "benchmarks": {
            "FTSE 350": "^FTLC",
            "FTSE All-Share": "^FTAS",
        },
        "default_benchmark": "FTSE 350",
        "default_currency": "GBP",
        "default_tickers": DEFAULT_TICKERS_UK,
    },
}

# Backward-compatible USA defaults.
BENCHMARKS: Dict[str, str] = {
    **MARKET_CONFIGS["USA"]["benchmarks"]
}

# ============================================================================
# DEFAULT VALUES
# ============================================================================
DEFAULT_TICKERS = DEFAULT_TICKERS_USA
DEFAULT_REPORTING_CURRENCY = "USD"
DEFAULT_BENCHMARK = "S&P 500"

# ============================================================================
# METRICS CONFIGURATION
# ============================================================================
# Threshold for deciding between annualized vs period metrics (in days)
ANNUALIZATION_THRESHOLD_DAYS = 365

# Metric display names
METRICS_ANNUALIZED = [
    "Cumulative Return",
    "Annualised Return",
    "Annualised Volatility",
    "Sharpe Ratio",
    "Maximum Drawdown",
    "Tracking Error",
    "Portfolio Beta",
    "Information Ratio",
    "Largest Relative Return Contributor",
    "Largest Relative Return Detractor",
]

METRICS_PERIOD = METRICS_ANNUALIZED

# ============================================================================
# UI COLUMN WIDTHS
# ============================================================================
COLUMN_WIDTH_SMALL = "small"
COLUMN_WIDTH_MEDIUM = "medium"

# ============================================================================
# CHART DIMENSIONS
# ============================================================================
# Display charts (Streamlit UI)
PIE_CHART_WIDTH = 400
PIE_CHART_HEIGHT = 400

CUMULATIVE_CHART_WIDTH = 1000
CUMULATIVE_CHART_HEIGHT = 500

LINE_CHART_WIDTH = 1400
LINE_CHART_HEIGHT = 600

# Excel export charts (pixel dimensions)
EXCEL_PIE_CHART_WIDTH = 400
EXCEL_PIE_CHART_HEIGHT = 400
EXCEL_CUMULATIVE_CHART_WIDTH = 1200
EXCEL_CUMULATIVE_CHART_HEIGHT = 400

# ============================================================================
# EXCEL EXPORT SETTINGS
# ============================================================================
EXCEL_SCALE = 2  # DPI scale for images (2x = high quality)
EXCEL_MAX_COLUMN_WIDTH = 50

# ============================================================================
# DATA VALIDATION
# ============================================================================
MIN_TICKERS = 1
MAX_TICKERS = 100
MIN_PRICE_DATA_POINTS = 10  # Minimum trading days required for analysis

# ============================================================================
# FORMATTING
# ============================================================================
PERCENTAGE_FORMAT = "{:.1%}"
PERCENTAGE_FORMAT_DETAILED = "{:.2%}"
DECIMAL_FORMAT = "{:.2f}"
RETURN_FORMAT_HOVER = "{:.2f}%"

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
PAGE_TITLE = "Portfolio Optimizer"
PAGE_LAYOUT = "wide"
