# routers/wishlist.py
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase
import yfinance as yf

router = APIRouter()

@router.get("/wishlist-prices")
async def get_wishlist_prices(user_id: str = Query(...)):
    # 1. Fetch wishlist symbols from Supabase
    response = supabase.table("wishlists") \
        .select("stock_symbol") \
        .eq("user_id", user_id) \
        .execute()

    if not response.data:
        return []

    symbols = [item["stock_symbol"] for item in response.data]

    # 2. Fetch current prices using yfinance
    try:
        tickers = yf.Tickers(" ".join(symbols))
        result = []
        for symbol in symbols:
            ticker = tickers.tickers.get(symbol)
            if ticker and ticker.info.get("regularMarketPrice") is not None:
                price = ticker.info["regularMarketPrice"]
                result.append({"symbol": symbol, "price": price})
            else:
                result.append({"symbol": symbol, "price": None})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result
