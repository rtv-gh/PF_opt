from utils import get_sp500_constituents, write_equity_lists_excel, save_gics_sector_stocks_csv, EXCEL_PATH, SHEET_NAME_SPX

df = get_sp500_constituents(fetch_live=True)
write_equity_lists_excel(str(EXCEL_PATH), {SHEET_NAME_SPX: df}, overwrite=True)
csv_path = save_gics_sector_stocks_csv(df)
print("Updated", EXCEL_PATH, "and", csv_path)