from pathlib import Path
from typing import Tuple, Optional, List, Dict
import pandas as pd
import requests
import time
import tempfile
import shutil
import logging
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# Reliable public mirror (raw CSV) - fallback
GITHUB_SPX_RAW = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"

EXCEL_PATH = Path(__file__).resolve().parent / "equity_tickers_lists.xlsx"
SHEET_NAME_SPX = "SPX"
GICS_STOCKS_CSV_PATH = Path(__file__).resolve().parent / "gics_sector_stocks.csv"
GICS_UK_STOCKS_CSV_PATH = Path(__file__).resolve().parent / "gics_sector_stocks_uk.csv"
GICS_STOCKS_CSV_PATHS = {
    "USA": GICS_STOCKS_CSV_PATH,
    "UK": GICS_UK_STOCKS_CSV_PATH,
}
FTSE_100_URL = "https://en.wikipedia.org/wiki/FTSE_100_Index"
FTSE_250_URL = "https://en.wikipedia.org/wiki/FTSE_250_Index"

YAHOO_TO_GICS_SECTOR = {
    "Basic Materials": "Materials",
    "Communication Services": "Communication Services",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Energy": "Energy",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Industrials": "Industrials",
    "Real Estate": "Real Estate",
    "Technology": "Information Technology",
    "Utilities": "Utilities",
}


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
                df.attrs["source_url"] = WIKI_SP500_URL
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
        df.attrs["source_url"] = GITHUB_SPX_RAW
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
            df.attrs["source_url"] = str(EXCEL_PATH)
            return df
        except Exception as e:
            logger.exception("Failed to read local Excel cache: %s", e)

    # Nothing worked
    raise FileNotFoundError("Unable to obtain S&P 500 constituents from network or local cache")


def get_ftse350_constituents() -> pd.DataFrame:
    """Fetch FTSE constituents and map Yahoo Finance sectors to GICS sector names."""
    from io import StringIO

    constituent_tables = []
    for source_url in (FTSE_100_URL, FTSE_250_URL):
        html = _get_html_with_retries(source_url)
        tables = pd.read_html(StringIO(html))
        table = _find_ftse_constituent_table(tables)
        constituent_tables.append(table)

    constituents = pd.concat(constituent_tables, ignore_index=True)
    constituents = constituents.drop_duplicates(subset="Symbol", keep="first")
    with ThreadPoolExecutor(max_workers=4) as executor:
        fetched_rows = executor.map(
            _fetch_ftse_sector_data,
            constituents["Symbol"],
            constituents["Security"],
        )
        rows = [row for row in fetched_rows if row is not None]

    result = pd.DataFrame(rows)
    result.attrs["source_url"] = f"{FTSE_100_URL}; {FTSE_250_URL}; Yahoo Finance sector metadata"
    if result.empty:
        raise ValueError("No FTSE constituents with recognized Yahoo sector metadata were found")
    return result


def _find_ftse_constituent_table(tables: List[pd.DataFrame]) -> pd.DataFrame:
    """Select and normalize a Wikipedia constituent table across header variations."""
    for table in tables:
        columns = {str(column).strip().lower(): column for column in table.columns}
        symbol_column = next(
            (column for name, column in columns.items() if name in {"epic", "ticker", "symbol"}),
            None,
        )
        security_column = next(
            (column for name, column in columns.items() if name in {"company", "company name", "name"}),
            None,
        )
        if symbol_column is None or security_column is None:
            continue

        result = table[[symbol_column, security_column]].copy()
        result.columns = ["Symbol", "Security"]
        result["Symbol"] = result["Symbol"].fillna("").astype(str).str.strip().str.upper()
        result["Symbol"] = result["Symbol"].str.replace(r"\.(?!L$)", "-", regex=True)
        result["Symbol"] = result["Symbol"].where(
            result["Symbol"].str.endswith(".L"), result["Symbol"] + ".L"
        )
        result["Security"] = result["Security"].fillna("").astype(str).str.strip()
        return result[(result["Symbol"] != ".L") & (result["Security"] != "")]
    raise ValueError("Could not find a recognized FTSE constituent table")


def _normalize_gics_sector_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize constituent data to a stable schema for the app and CSV snapshot."""
    data = df.copy()
    if "Symbol" not in data.columns and "Ticker" in data.columns:
        data = data.rename(columns={"Ticker": "Symbol"})
    required = ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]
    for column in required:
        if column not in data.columns:
            data[column] = ""

    for column in required:
        data[column] = data[column].fillna("").astype(str).str.strip()
    data["Symbol"] = data["Symbol"].str.upper()
    data = data[(data["Symbol"] != "") & (data["GICS Sector"] != "")]
    data = data.drop_duplicates(subset="Symbol", keep="last")

    optional = [column for column in ["Source", "Retrieved At"] if column in data.columns]
    return data[required + optional].sort_values(["GICS Sector", "Security", "Symbol"]).reset_index(drop=True)


def load_gics_sector_stocks(market: str = "USA") -> pd.DataFrame:
    """Load a market's GICS dataset, fetching UK constituents if no local snapshot exists."""
    market = market.upper()
    if market not in GICS_STOCKS_CSV_PATHS:
        raise ValueError(f"Unsupported equity market: {market}")
    csv_path = GICS_STOCKS_CSV_PATHS[market]
    try:
        if csv_path.exists():
            data = pd.read_csv(csv_path)
        elif market == "UK":
            data = get_ftse350_constituents()
            save_gics_sector_stocks_csv(data, market=market)
        elif EXCEL_PATH.exists():
            data = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME_SPX)
        else:
            data = get_sp500_constituents(fetch_live=True, use_cache_if_exists=False)
        return _normalize_gics_sector_stocks(data)
    except Exception as e:
        logger.warning("Could not load GICS sector stocks: %s", e)
        return pd.DataFrame(columns=["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"])


def save_gics_sector_stocks_csv(df: Optional[pd.DataFrame] = None, market: str = "USA") -> Path:
    """Refresh and atomically save a market's GICS dataset as a structured CSV."""
    market = market.upper()
    if market not in GICS_STOCKS_CSV_PATHS:
        raise ValueError(f"Unsupported equity market: {market}")
    source_data = df if df is not None else (
        get_ftse350_constituents() if market == "UK" else get_sp500_constituents(fetch_live=True)
    )
    data = _normalize_gics_sector_stocks(source_data)
    if data.empty:
        raise ValueError(f"No {market} GICS sector data is available to save")

    data["Source"] = source_data.attrs.get(
        "source_url",
        (
            f"{FTSE_100_URL}; {FTSE_250_URL}; Yahoo Finance sector metadata"
            if market == "UK"
            else f"{WIKI_SP500_URL} (GitHub mirror fallback: {GITHUB_SPX_RAW})"
        ),
    )
    data["Retrieved At"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", delete=False,
        dir=GICS_STOCKS_CSV_PATHS[market].parent, suffix=".csv"
    ) as temp_file:
        temp_path = Path(temp_file.name)
        data.to_csv(temp_file, index=False)
    try:
        shutil.move(str(temp_path), str(GICS_STOCKS_CSV_PATHS[market]))
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    logger.info("Wrote GICS sector stock data to %s", GICS_STOCKS_CSV_PATHS[market])
    return GICS_STOCKS_CSV_PATHS[market]

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


def _fetch_ftse_sector_data(symbol: str, security: str) -> Optional[Dict[str, str]]:
    """Fetch one UK listing's Yahoo sector and map it to a GICS sector label."""
    try:
        yahoo_info = yf.Ticker(symbol).info or {}
    except Exception as error:
        logger.warning("Could not fetch Yahoo sector metadata for %s: %s", symbol, error)
        return None
    yahoo_sector = yahoo_info.get("sector")
    gics_sector = YAHOO_TO_GICS_SECTOR.get(yahoo_sector)
    if not gics_sector:
        logger.warning("No recognized sector metadata for %s (%s)", symbol, yahoo_sector)
        return None
    return {
        "Symbol": symbol,
        "Security": security,
        "GICS Sector": gics_sector,
        "GICS Sub-Industry": yahoo_info.get("industry", ""),
    }