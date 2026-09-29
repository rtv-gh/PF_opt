from utils import get_ftse350_constituents, save_gics_sector_stocks_csv

data = get_ftse350_constituents()
csv_path = save_gics_sector_stocks_csv(data, market="UK")
print(f"Updated {len(data)} UK constituents at {csv_path}")