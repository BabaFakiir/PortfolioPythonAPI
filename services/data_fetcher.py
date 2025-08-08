from datetime import datetime, timedelta
import yfinance as yf
from database.supabase_client import supabase

def fetch_and_store_stock_data(symbol: str, days: int = 30):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days)

    response = supabase.table("stock_prices") \
        .select("*") \
        .eq("symbol", symbol) \
        .gte("date", str(start_date)) \
        .execute()
    
    if response.data and len(response.data) >= 28:
        sorted_data = sorted(response.data, key=lambda x: x['date'])
        return sorted_data, False

    print("Fetching data from Yahoo Finance...")
    data = yf.download('AAPL', period="30d", interval="1d")
    print(data)
    if data.empty:
        return None, None

    existing_dates_response = supabase.table("stock_prices") \
        .select("date") \
        .eq("symbol", symbol) \
        .execute()

    existing_dates = {row["date"] for row in existing_dates_response.data}
    new_rows = []

    for date, row in data.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        if date_str not in existing_dates:
            avg_price = float(row['Close'])
            new_rows.append({
                "symbol": symbol,
                "date": date_str,
                "avg_price": avg_price
            })

    if new_rows:
        supabase.table("stock_prices").insert(new_rows).execute()

    combined_data = response.data + new_rows
    sorted_data = sorted(combined_data, key=lambda x: x['date'])
    return sorted_data, True
