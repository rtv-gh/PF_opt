from utils import get_sp500_constituents, write_equity_lists_excel, EXCEL_PATH, SHEET_NAME_SPX

df = get_sp500_constituents(fetch_live=True)
write_equity_lists_excel(str(EXCEL_PATH), {SHEET_NAME_SPX: df}, overwrite=True)
print("Updated", EXCEL_PATH)