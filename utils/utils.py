from pathlib import Path
from typing import Tuple, Optional, List, Dict
import pandas as pd
import requests
import time
import tempfile
import shutil
import logging

logger = logging.getLogger(__name__)
WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# Reliable public mirror (raw CSV) - fallback
GITHUB_SPX_RAW = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"

EXCEL_PATH = Path(__file__).resolve().parent / "equity_tickers_lists.xlsx"
SHEET_NAME_SPX = "SPX"


# --- network helper with retries
def _get_html_with_retries(url: str, max_retries: int = 3, backoff: float = 1.0, timeout: float = 10.0) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0 Safari/537.36"
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            logger.warning("HTTP error fetching %s: %s (attempt %d/%d)", url, status, e, attempt, max_retries)
            # If 403, don't hammer — wait longer
            if status == 403:
                time.sleep(backoff * attempt * 2)
            else:
                time.sleep(backoff * attempt)
        except requests.RequestException as e:
            logger.warning("Network error fetching %s: %s (attempt %d/%d)", url, e, attempt, max_retries)
            time.sleep(backoff * attempt)
    raise requests.HTTPError(f"Failed to fetch {url} after {max_retries} attempts")

# --- primary fetch function with fallbacks
def get_sp500_constituents(fetch_live: bool = True, use_cache_if_exists: bool = True) -> pd.DataFrame:
    """
    Return a DataFrame of S&P 500 constituents with columns including:
    ['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry'] where available.

    Behavior:
      - If fetch_live=True, attempt to fetch from Wikipedia (with retries).
      - If that fails, attempt to fetch from a GitHub raw CSV mirror.
      - If both network attempts fail and use_cache_if_exists=True, read local EXCEL_PATH sheet 'SPX'.
      - Raises FileNotFoundError if no data available.
    """
    # 1) Try Wikipedia (HTML table)
    if fetch_live:
        try:
            html = _get_html_with_retries(WIKI_SP500_URL)
            # pandas can parse the first table into a DataFrame
            from io import StringIO
            tables = pd.read_html(StringIO(html), header=0)

            if tables:
                df = tables[0]
                # Prefer canonical columns if present
                expected = ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]
                available = [c for c in expected if c in df.columns]
                if available:
                    df = df[available].copy()
                # Normalize Symbol column to string and strip whitespace
                if "Symbol" in df.columns:
                    df["Symbol"] = df["Symbol"].astype(str).str.strip()
                # Optionally write to local Excel for caching
                try:
                    write_equity_lists_excel(str(EXCEL_PATH), {SHEET_NAME_SPX: df}, overwrite=True)
                except Exception:
                    logger.exception("Failed to write local Excel cache after fetching Wikipedia")
                return df
        except Exception as e:
            logger.warning("Failed to fetch/parse Wikipedia S&P 500 table: %s", e)

    # 2) Fallback: GitHub raw CSV mirror
    try:
        logger.info("Attempting fallback fetch from GitHub raw CSV")
        csv_text = _get_html_with_retries(GITHUB_SPX_RAW)
        from io import StringIO
        df = pd.read_csv(StringIO(csv_text))
        # Normalize columns if needed
        if "Symbol" in df.columns:
            df["Symbol"] = df["Symbol"].astype(str).str.strip()
        try:
            write_equity_lists_excel(str(EXCEL_PATH), {SHEET_NAME_SPX: df}, overwrite=True)
        except Exception:
            logger.exception("Failed to write local Excel cache after fetching GitHub CSV")
        return df
    except Exception as e:
        logger.warning("Fallback GitHub CSV fetch failed: %s", e)

    # 3) Final fallback: read local Excel snapshot if present
    if use_cache_if_exists and EXCEL_PATH.exists():
        try:
            df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME_SPX)
            if "Symbol" in df.columns:
                df["Symbol"] = df["Symbol"].astype(str).str.strip()
            return df
        except Exception as e:
            logger.exception("Failed to read local Excel cache: %s", e)

    # Nothing worked
    raise FileNotFoundError("Unable to obtain S&P 500 constituents from network or local cache")

# --- atomic Excel writer (reused from earlier)
def write_equity_lists_excel(path: str, sheets: Dict[str, pd.DataFrame], overwrite: bool = True) -> None:
    """
    Write multiple DataFrames to an Excel workbook atomically.
    - path: target file path (e.g., 'equity_tickers_lists.xlsx')
    - sheets: dict mapping sheet_name -> DataFrame
    - overwrite: if False and file exists, will raise
    """
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{path} exists and overwrite=False")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                safe_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=safe_name, index=False)
        shutil.move(str(tmp_path), str(target))
        logger.info("Wrote equity lists to %s", target)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.exception("Failed to write equity lists to Excel")
        raise

# --- convenience reader
def get_ticker_list_from_sheet(sheet_name: str, symbol_col: str = "Symbol") -> list:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"{EXCEL_PATH} not found")
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)

    if symbol_col not in df.columns:
        # try common alternatives
        for c in ["Ticker", "SYMBOL", "symbol"]:
            if c in df.columns:
                symbol_col = c
                break
        else:
            raise KeyError(f"Symbol column not found in sheet {sheet_name}")
    tickers = df[symbol_col].dropna().astype(str).str.strip().tolist()
    return tickers

def load_index_metadata(sheet_name: str = "SPX") -> pd.DataFrame:
    """
    Load index metadata (ticker, name, sector) from Excel sheet.
    Returns DataFrame indexed by Symbol with columns: Security, GICS Sector.
    """
    if not EXCEL_PATH.exists():
        # Try fetching fresh data if file doesn't exist
        try:
            df = get_sp500_constituents(fetch_live=True, use_cache_if_exists=False)
        except Exception as e:
            logger.warning("Could not fetch fresh metadata: %s", e)
            return pd.DataFrame()
    else:
        try:
            df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)
        except Exception as e:
            logger.warning("Could not read metadata from Excel: %s", e)
            return pd.DataFrame()
    
    # Ensure Symbol column exists and set as index
    if "Symbol" not in df.columns:
        logger.warning("Symbol column not found in metadata")
        return pd.DataFrame()
    
    # Keep relevant columns and set Symbol as index
    cols_to_keep = [c for c in ["Symbol", "Security", "GICS Sector"] if c in df.columns]
    result = df[cols_to_keep].set_index("Symbol")
    return result