from fastapi import APIRouter, HTTPException
from services.data_fetcher import fetch_and_store_stock_data
from datetime import datetime, timedelta
import yfinance as yf
from database.supabase_client import supabase
import pandas as pd
import math  


router = APIRouter()


def calculate_RSI_series(prices, period=14):
    prices = pd.Series(prices)
    delta = prices.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder’s smoothing method (EMA with alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # ✅ Replace NaN/Inf with None so JSON is valid
    rsi_clean = []
    for val in rsi.tolist():
        if val is None or math.isnan(val) or math.isinf(val):
            rsi_clean.append(None)
        else:
            rsi_clean.append(float(val))
    return rsi_clean


def calculate_macd(prices: list[float]):
    """
    prices: list of close prices in chronological order
    returns: DataFrame with macd, signal, histogram
    """
    df = pd.DataFrame(prices, columns=["close"])
    
    # Calculate EMAs
    df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
    
    # MACD line
    df["macd"] = df["ema12"] - df["ema26"]
    
    # Signal line (9-day EMA of MACD)
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    
    # Histogram
    df["histogram"] = df["macd"] - df["signal"]
    
    return df[["macd", "signal", "histogram"]].to_dict(orient="records")


@router.get("/stock-price/{symbol}")
async def get_stock_data(symbol: str):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)

    # Check if data exists in Supabase for the last 30 days
    response = supabase.table("stock_prices") \
        .select("*") \
        .eq("symbol", symbol) \
        .gte("date", str(start_date)) \
        .execute()

    if response.data and len(response.data) >= 28:
        sorted_data = sorted(response.data, key=lambda x: x['date'])
    else:
        data = yf.download(symbol, period="30d", interval="1d")
        if data.empty:
            raise HTTPException(status_code=404, detail="Symbol not found or no data")

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

        sorted_data = sorted(response.data + new_rows, key=lambda x: x['date'])

    highest_price = max(row['avg_price'] for row in sorted_data)
    lowest_price = min(row['avg_price'] for row in sorted_data)
    avg_price = sum(row['avg_price'] for row in sorted_data) / len(sorted_data) if sorted_data else 0
    latest_price = sorted_data[-1]['avg_price'] if sorted_data else None
    price_deviation = (latest_price - avg_price) if avg_price else 0
    price_deviation_percent = (price_deviation / avg_price * 100) if avg_price else 0

    price_series = [row['avg_price'] for row in sorted_data]

    rsi_series = calculate_RSI_series(price_series, period=14) if len(price_series) >= 14 else []

    macd_data = calculate_macd(price_series)
    
    data_with_rsi = []
    for i, row in enumerate(sorted_data):
        rsi_val = rsi_series[i] if i < len(rsi_series) else None

        data_with_rsi.append({
            "date": row['date'],
            "avg_price": row['avg_price'],
            "rsi": rsi_val
        })

    latest_rsi = rsi_series[-1] if rsi_series else None

    return {
        "highest_price": highest_price,
        "lowest_price": lowest_price,
        "avg_price": avg_price,
        "latest_price": latest_price,
        "price_deviation": price_deviation,
        "price_deviation_percent": price_deviation_percent,
        "rsi": latest_rsi,  
        "data": data_with_rsi,   
        "macd_data": [
            {"date": sorted_data[i]["date"], **macd_data[i]}
            for i in range(len(sorted_data))
        ]
    }
