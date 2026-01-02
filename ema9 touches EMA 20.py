from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8565575662:AAGkqeUhSI0qXzXBFDdzIgEzR4gzm2iohAw"
TELEGRAM_CHAT_ID = "2137177601"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================= CONFIG =================
TOP_COINS = 300
CANDLE_LIMIT = 210

TIMEFRAMES = {
    "5m":  {"interval": Client.KLINE_INTERVAL_5MINUTE,  "seconds": 300},
    "15m": {"interval": Client.KLINE_INTERVAL_15MINUTE, "seconds": 900}
}

client = Client()

# ================= SYMBOL LIST =================
def get_top_symbols():
    df = pd.DataFrame(client.futures_ticker())
    df = df[df["symbol"].str.endswith("USDT")]
    df["vol"] = df["quoteVolume"].astype(float)
    return df.sort_values("vol", ascending=False)["symbol"].head(TOP_COINS).tolist()

# ================= DATA =================
def fetch_data(symbol, interval):
    klines = client.futures_klines(
        symbol=symbol,
        interval=interval,
        limit=CANDLE_LIMIT
    )
    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "x1","x2","x3","x4","x5","x6"
    ])
    df[["open","high","low","close","volume"]] = df[
        ["open","high","low","close","volume"]
    ].astype(float)
    return df.iloc[:-1]

# ================= INDICATORS =================
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def atr(df, length=14):
    pc = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

# ================= EMA 9 TOUCH EMA 200 =================
def ema9_touch_ema200_long(df):
    ema9 = ema(df["close"], 9)
    ema200 = ema(df["close"], 200)
    atr_val = atr(df).iloc[-1]

    # EMA 200 must be rising
    if ema200.iloc[-1] <= ema200.iloc[-5]:
        return False

    # Price above EMA 200
    if df["close"].iloc[-1] < ema200.iloc[-1]:
        return False

    # EMA 9 near EMA 200 (touch zone)
    if abs(ema9.iloc[-1] - ema200.iloc[-1]) > 0.3 * atr_val:
        return False

    # No breakdown
    if ema9.iloc[-1] < ema200.iloc[-1]:
        return False

    return True


def ema9_touch_ema200_short(df):
    ema9 = ema(df["close"], 9)
    ema200 = ema(df["close"], 200)
    atr_val = atr(df).iloc[-1]

    if ema200.iloc[-1] >= ema200.iloc[-5]:
        return False

    if df["close"].iloc[-1] > ema200.iloc[-1]:
        return False

    if abs(ema9.iloc[-1] - ema200.iloc[-1]) > 0.3 * atr_val:
        return False

    if ema9.iloc[-1] > ema200.iloc[-1]:
        return False

    return True

# ================= MAIN LOOP =================
symbols = get_top_symbols()
send_telegram("🚀 EMA 9 TOUCH EMA 200 SCREENER STARTED (5m / 15m)")

while True:
    for symbol in symbols:
        for tf, cfg in TIMEFRAMES.items():
            try:
                df = fetch_data(symbol, cfg["interval"])

                if ema9_touch_ema200_long(df):
                    direction = "LONG"
                elif ema9_touch_ema200_short(df):
                    direction = "SHORT"
                else:
                    continue

                price = df["close"].iloc[-1]

                msg = (
                    f"🔥 <b>{direction} EMA 9 TOUCH EMA 200</b>\n\n"
                    f"🪙 <b>Coin:</b> {symbol}\n"
                    f"⏱ <b>TF:</b> {tf}\n"
                    f"📍 <b>Price:</b> {price:.6f}\n"
                )

                print(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram(msg)

            except Exception as e:
                print(symbol, tf, "error:", e)

    time.sleep(10)
