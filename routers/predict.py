from fastapi import APIRouter, HTTPException
from datetime import datetime
import yfinance as yf
from prophet import Prophet
from database.supabase_client import supabase
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

router = APIRouter()

def create_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(50, activation='relu', input_shape=input_shape))
    model.add(Dense(4))  # Predict Open, High, Low, Close
    model.compile(optimizer='adam', loss='mse')
    return model

def prepare_lstm_data(df, seq_len=30):
    data = df[['Open', 'High', 'Low', 'Close']].values
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i:i+seq_len])
        y.append(data[i+seq_len])
    return np.array(X), np.array(y)

@router.get("/predict/{symbol}")
async def predict_candlestick(symbol: str):
    today_str = datetime.today().strftime("%Y-%m-%d")
    symbol = symbol.upper()

    # Check Supabase cache first
    existing = supabase.table("candlestick_predictions") \
        .select("*") \
        .eq("symbol", symbol) \
        .eq("prediction_date", today_str) \
        .execute()

    if existing.data:
        cached = existing.data[0]
        return {
            "symbol": symbol,
            "prediction_date": today_str,
            "predicted_open": float(cached["predicted_open"]),
            "predicted_high": float(cached["predicted_high"]),
            "predicted_low": float(cached["predicted_low"]),
            "predicted_close": float(cached["predicted_close"]),
            "trend": cached["trend"],
            "confidence": float(cached.get("confidence", 0)),
            "source": "supabase_cache"
        }

    # Fetch 180 days of OHLC data
    stock_data = yf.download(symbol, period="180d", interval="1d", auto_adjust=False)
    if stock_data.empty:
        raise HTTPException(status_code=404, detail="No data found for symbol")

    # Handle MultiIndex columns if any
    if isinstance(stock_data.columns, pd.MultiIndex):
        cols_needed = [('Open', symbol), ('High', symbol), ('Low', symbol), ('Close', symbol)]
        for col in cols_needed:
            if col not in stock_data.columns:
                raise HTTPException(status_code=404, detail=f"Missing {col[0]} data for symbol {symbol}")
        df = stock_data[list(cols_needed)].reset_index()
        df.columns = ['ds', 'Open', 'High', 'Low', 'Close']
    else:
        df = stock_data.reset_index()[['Date', 'Open', 'High', 'Low', 'Close']]
        df.rename(columns={"Date": "ds"}, inplace=True)

    df['ds'] = pd.to_datetime(df['ds'])
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['ds', 'Open', 'High', 'Low', 'Close'])

    # --- Prophet predictions ---
    def fit_prophet(col_name):
        model_df = df[['ds', col_name]].rename(columns={col_name: 'y'})
        m = Prophet(daily_seasonality=True)
        m.fit(model_df)
        future = m.make_future_dataframe(periods=1)
        forecast = m.predict(future)
        return forecast.iloc[-1]['yhat']

    predicted_open_prophet = fit_prophet('Open')
    predicted_high_prophet = fit_prophet('High')
    predicted_low_prophet = fit_prophet('Low')
    predicted_close_prophet = fit_prophet('Close')

    # --- LSTM predictions ---
    SEQ_LEN = 30
    X, y = prepare_lstm_data(df, seq_len=SEQ_LEN)
    if len(X) == 0:
        raise HTTPException(status_code=400, detail="Not enough data for LSTM")

    model = create_lstm_model((SEQ_LEN, 4))
    model.fit(X, y, epochs=20, verbose=0)

    last_seq = df[['Open', 'High', 'Low', 'Close']].values[-SEQ_LEN:]
    last_seq = np.expand_dims(last_seq, axis=0)  # shape (1, SEQ_LEN, 4)
    predicted_lstm = model.predict(last_seq)[0]  # array of 4 values

    predicted_open_lstm, predicted_high_lstm, predicted_low_lstm, predicted_close_lstm = predicted_lstm

    # Combine predictions (simple average here)
    predicted_open = (predicted_open_prophet + predicted_open_lstm) / 2
    predicted_high = (predicted_high_prophet + predicted_high_lstm) / 2
    predicted_low = (predicted_low_prophet + predicted_low_lstm) / 2
    predicted_close = (predicted_close_prophet + predicted_close_lstm) / 2

    trend = "bullish" if predicted_close > predicted_open else "bearish"
    confidence = abs(predicted_close - predicted_open) / predicted_open

    # Save prediction in Supabase
    insert_response = supabase.table("candlestick_predictions").insert({
        "symbol": symbol,
        "prediction_date": today_str,
        "predicted_open": float(predicted_open),
        "predicted_high": float(predicted_high),
        "predicted_low": float(predicted_low),
        "predicted_close": float(predicted_close),
        "trend": trend,
        "confidence": confidence
    }).execute()

    return {
        "symbol": symbol,
        "prediction_date": today_str,
        "predicted_open": round(predicted_open, 2),
        "predicted_high": round(predicted_high, 2),
        "predicted_low": round(predicted_low, 2),
        "predicted_close": round(predicted_close, 2),
        "trend": trend,
        "confidence": round(confidence, 4),
        "source": "model"
    }
