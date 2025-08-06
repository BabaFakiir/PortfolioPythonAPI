from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta
import yfinance as yf
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware
import json

SUPABASE_URL = "https://fbcequeftvgcysbrjuma.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZiY2VxdWVmdHZnY3lzYnJqdW1hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMwOTQwNzcsImV4cCI6MjA2ODY3MDA3N30.oGrYI1pG5Pygtb-jnMq_vgULJtS72aeZ1r7YvIDoTLI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/stock-price/{symbol}")

async def get_stock_prices(symbol: str):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)

    # Check if data exists in Supabase for the last 30 days
    response = supabase.table("stock_prices") \
        .select("*") \
        .eq("symbol", symbol) \
        .gte("date", str(start_date)) \
        .execute()

    if response.data and len(response.data) >= 28:
        # Return sorted data from Supabase
        sorted_data = sorted(response.data, key=lambda x: x['date'])
        return [{"date": row['date'], "avg_price": row['avg_price']} for row in sorted_data]

    # Fetch from Yahoo Finance
    data = yf.download(symbol, period="30d", interval="1d")
    if data.empty:
        raise HTTPException(status_code=404, detail="Symbol not found or no data")

    # Get existing dates from Supabase
    existing_dates_response = supabase.table("stock_prices") \
        .select("date") \
        .eq("symbol", symbol) \
        .execute()

    existing_dates = {row["date"] for row in existing_dates_response.data}

    # Filter and prepare new rows only
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

    # Insert only new rows
    if new_rows:
        supabase.table("stock_prices").insert(new_rows).execute()

    # Combine existing + new data for return
    combined_data = response.data + new_rows
    sorted_data = sorted(combined_data, key=lambda x: x['date'])
    highest_price = max(row['avg_price'] for row in sorted_data)
    lowest_price = min(row['avg_price'] for row in sorted_data)
    avg_price = sum(row['avg_price'] for row in sorted_data) / len(sorted_data) if sorted_data else 0
    # get latest price from yfinance data
    latest_price = float(data['Close'].iloc[-1]) if not data.empty else None
    price_deviation = (latest_price - avg_price) if avg_price else 0
    price_deviation_percent = (price_deviation / avg_price * 100) if avg_price else 0

    return {
        "highest_price": highest_price,
        "lowest_price": lowest_price,
        "avg_price": avg_price,
        "latest_price": latest_price,
        "price_deviation": price_deviation,
        "price_deviation_percent": price_deviation_percent,
        "data": [{"date": row['date'], "avg_price": row['avg_price']} for row in sorted_data]
    }