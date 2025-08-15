from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import stocks
from routers import predict
from routers import wishlist

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to your frontend domain if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(predict.router)
app.include_router(wishlist.router)