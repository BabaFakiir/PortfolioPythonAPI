import yfinance as yf
import pandas as pd

symbol = "AAPL"
stock_data = yf.download(symbol, period="180d", interval="1d", auto_adjust=False)

print(stock_data.columns)  # MultiIndex

# Flatten columns if MultiIndex
if isinstance(stock_data.columns, pd.MultiIndex):
    # Select 'Close' price for symbol
    close_col = ('Close', symbol)
    df = stock_data[[close_col]].reset_index()
    # Rename to simple columns
    df.columns = ['Date', 'Close']
else:
    df = stock_data.reset_index()[['Date', 'Close']]

print(df.head())

df.rename(columns={"Date": "ds", "Close": "y"}, inplace=True)
df['ds'] = pd.to_datetime(df['ds'])
df['y'] = pd.to_numeric(df['y'], errors='coerce')
df = df.dropna(subset=['ds', 'y'])

print(df.head())
