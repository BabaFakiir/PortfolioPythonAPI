# routers/wishlist.py
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase
import yfinance as yf

router = APIRouter()
@router.get("/wishlist-prices")
async def get_wishlist_prices(user_id: str = Query(...)):
    # 1. Fetch wishlist items from Supabase
    response = supabase.table("wishlists") \
        .select("id, stock_symbol") \
        .eq("user_id", user_id) \
        .execute()

    if not response.data:
        return []

    wishlist_data = response.data
    symbols = [item["stock_symbol"] for item in wishlist_data]

    # 2. Fetch prices from yfinance
    try:
        tickers = yf.Tickers(" ".join(symbols))
        result = []
        for item in wishlist_data:
            symbol = item["stock_symbol"]
            ticker = tickers.tickers.get(symbol)
            price = None
            if ticker and ticker.info.get("regularMarketPrice") is not None:
                price = ticker.info["regularMarketPrice"]
            result.append({
                "id": item["id"],  
                "symbol": symbol,
                "price": price
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result
