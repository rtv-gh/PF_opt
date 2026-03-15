"""
Configuration and constants for Portfolio Optimizer.

This module centralizes all configuration, constants, and defaults to provide
a single source of truth for the application.
"""

from typing import Dict

# ============================================================================
# BENCHMARKS
# ============================================================================
BENCHMARKS: Dict[str, str] = {
    "S&P 500": "SPY",
    "MSCI ACWI": "ACWI"
}

# ============================================================================
# DEFAULT VALUES
# ============================================================================
DEFAULT_TICKERS = "AAPL,MA,META,V,AMZN,BA,BAC,BK,C,GS,JPM,MS,STT,WFC,LLY,BSX,JNJ,XOM,MDT,MSFT,GOOGL,NVDA,AVGO,CRM,UNH"
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
    "Tracking Error"
]

METRICS_PERIOD = [
    "Cumulative Return",
    "Period Volatility",
    "Period Sharpe",
    "Tracking Error"
]

# ============================================================================
# UI COLUMN WIDTHS
# ============================================================================
COLUMN_WIDTH_SMALL = "small"
COLUMN_WIDTH_MEDIUM = "medium"

# ============================================================================
# CHART DIMENSIONS
# ============================================================================
PIE_CHART_WIDTH = 400
PIE_CHART_HEIGHT = 400
PIE_CHART_EMU_WIDTH = int(10 * 360000)  # 10cm in EMUs
PIE_CHART_EMU_HEIGHT = int(10 * 360000)

CUMULATIVE_CHART_WIDTH = 1000
CUMULATIVE_CHART_HEIGHT = 500
CUMULATIVE_CHART_EMU_WIDTH = int(30 * 360000)  # 30cm in EMUs
CUMULATIVE_CHART_EMU_HEIGHT = int(10 * 360000)

LINE_CHART_WIDTH = 1400
LINE_CHART_HEIGHT = 600

# ============================================================================
# EXCEL EXPORT SETTINGS
# ============================================================================
EXCEL_SCALE = 2  # DPI scale for images (2x = high quality)
EXCEL_PIE_WIDTH = 400
EXCEL_PIE_HEIGHT = 400
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
