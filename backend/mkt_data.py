from typing import Tuple, Dict, Optional, List
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

BUSINESS_FREQ = "B"

# -----------------------
# Public functions
# -----------------------
def get_data(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Download adjusted close prices for a list of tickers and return a DataFrame
    with columns = tickers, indexed by business-day dates. Missing values are forward-filled.
    """
    if not tickers:
        return pd.DataFrame()
    series_list = []
    for t in tickers:
        s = _download_series(t, start_date, end_date)
        if not s.empty:
            series_list.append(s)
    if not series_list:
        return pd.DataFrame()
    df = pd.concat(series_list, axis=1).sort_index()
    df = df.asfreq(BUSINESS_FREQ)
    df = df.bfill().ffill()
    return df

def get_fx(from_ccy: str, to_ccy: str, start_date: str, end_date: str) -> Tuple[pd.Series, Optional[str]]:
    """
    Return an FX series that converts amounts denominated in from_ccy into to_ccy.
    Returns (fx_series, fx_pair_used) where fx_pair_used is the yfinance symbol used (or None).
    If from_ccy == to_ccy, returns a series of 1.0 and fx_pair_used=None.
    """
    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()
    if from_ccy == to_ccy:
        idx = pd.date_range(start=start_date, end=end_date, freq=BUSINESS_FREQ)
        return pd.Series(1.0, index=idx, name=f"{from_ccy}{to_ccy}"), None

    # Try direct pair e.g. GBPUSD=X
    direct = f"{from_ccy}{to_ccy}=X"
    s = _download_series(direct, start_date, end_date)
    if not s.empty:
        s.name = direct
        return s, direct

    # Try reverse pair and invert
    reverse = f"{to_ccy}{from_ccy}=X"
    s_rev = _download_series(reverse, start_date, end_date)
    if not s_rev.empty:
        s_inv = 1.0 / s_rev.replace(0, np.nan)
        s_inv.name = reverse + "_inverted"
        return s_inv, s_inv.name

    # Not available
    return pd.Series(dtype=float), None



def get_bmk(ticker: str, start_date: str, end_date: str, reporting_currency: Optional[str] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Download benchmark series and (optionally) convert to reporting_currency.
    Returns (df, meta) where df has columns:
      - 'benchmark_adj_close' (original)
      - 'benchmark_adj_close_converted' (converted to reporting_currency if possible)
    meta contains:
      - 'bench_ccy': detected or heuristic currency (ISO)
      - 'fx_pair_used': FX pair symbol used for conversion or None
    """
    meta: Dict = {"bench_ccy": None, "fx_pair_used": None}

    series = _download_series(ticker, start_date, end_date)
    if series.empty:
        return pd.DataFrame(), meta

    df = series.to_frame(name="benchmark_adj_close")

    # Detect currency
    bench_ccy = _get_ticker_currency(ticker)
    if bench_ccy is None:
        # Heuristic defaults
        if ticker.upper().startswith("^FTSE") or ticker.upper().startswith("^FTMC"):
            bench_ccy = "GBP"
        else:
            bench_ccy = "USD"
    bench_ccy = bench_ccy.upper()
    meta["bench_ccy"] = bench_ccy

    # If no conversion requested or same currency, set converted = original
    if not reporting_currency or reporting_currency.upper() == bench_ccy:
        df["benchmark_adj_close_converted"] = df["benchmark_adj_close"]
        df.index = pd.to_datetime(df.index)
        return df, meta

    # Fetch FX and apply
    fx_series, fx_pair = get_fx(from_ccy=bench_ccy, to_ccy=reporting_currency, start_date=start_date, end_date=end_date)
    meta["fx_pair_used"] = fx_pair
    if fx_series.empty:
        # conversion not possible; return original but meta indicates no fx pair
        df["benchmark_adj_close_converted"] = df["benchmark_adj_close"]
        df.index = pd.to_datetime(df.index)
        return df, meta

    fx_series = fx_series.reindex(df.index).ffill().bfill()
    df["benchmark_adj_close_converted"] = df["benchmark_adj_close"] * fx_series.values
    df.index = pd.to_datetime(df.index)
    return df, meta



# -----------------------
# Low-level helpers
# -----------------------
def _download_series(ticker: str, start: str, end: str) -> pd.Series:
    """Download adjusted close (or close) and return a cleaned Series indexed by date."""
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        return pd.Series(dtype=float)
    col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        return pd.Series(dtype=float)
    s = df[col].squeeze().rename(ticker)
    s = s.dropna(how="all")
    s = s.asfreq(BUSINESS_FREQ)
    s = s.ffill().bfill() 
    s.index = pd.to_datetime(s.index)
    return s

def _get_ticker_currency(ticker: str) -> Optional[str]:
    """Best-effort detection of ticker currency via yfinance info; returns ISO code or None."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        c = info.get("currency")
        if c:
            return c.upper()
    except Exception:
        pass
    return None

