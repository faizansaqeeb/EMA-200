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
TOP_COINS = 500
CANDLE_LIMIT = 210

TIMEFRAMES = {
    "5m": {
        "interval": Client.KLINE_INTERVAL_5MINUTE,
        "seconds": 300,
        "max_age": 15   # minutes
    },
    "15m": {
        "interval": Client.KLINE_INTERVAL_15MINUTE,
        "seconds": 900,
        "max_age": 45   # minutes
    }
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
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=CANDLE_LIMIT)
    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "x1","x2","x3","x4","x5","x6"
    ])
    df[["open","high","low","close","volume"]] = df[
        ["open","high","low","close","volume"]
    ].astype(float)
    return df.iloc[:-1]

# ================= INDICATORS =================
def ema(s, l):
    return s.ewm(span=l, adjust=False).mean()

def atr(df, l=14):
    pc = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/l, adjust=False).mean()

def adx(df, l=14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    tr = atr(df, l)
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1/l).mean() / tr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/l).mean() / tr
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    return dx.ewm(alpha=1/l).mean()

def rsi(series, l=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/l).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/l).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hma(series, length=55):
    half = int(length / 2)
    sqrt_len = int(np.sqrt(length))
    wma1 = series.rolling(half).apply(
        lambda x: np.dot(x, np.arange(1, half + 1)) / np.arange(1, half + 1).sum(),
        raw=True
    )
    wma2 = series.rolling(length).apply(
        lambda x: np.dot(x, np.arange(1, length + 1)) / np.arange(1, length + 1).sum(),
        raw=True
    )
    raw = 2 * wma1 - wma2
    return raw.rolling(sqrt_len).mean()

# ================= SUCCESS RATE =================
def success_rate(direction, df):
    score = 0

    adx_val = adx(df).iloc[-1]
    if adx_val < 18:
        return 0
    score += min(30, adx_val)

    ema9 = ema(df["close"], 9).iloc[-1]
    ema20 = ema(df["close"], 20).iloc[-1]
    ema200 = ema(df["close"], 200).iloc[-1]
    rsi_val = rsi(df["close"]).iloc[-1]

    if direction == "LONG":
        if ema9 > ema20 > ema200:
            score += 25
        if 45 <= rsi_val <= 65:
            score += 25
    else:
        if ema9 < ema20 < ema200:
            score += 25
        if 35 <= rsi_val <= 55:
            score += 25

    vol_now = df["volume"].iloc[-1]
    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    if vol_now > vol_avg:
        score += 20

    hull = hma(df["close"], 55)
    if direction == "LONG" and hull.iloc[-1] > hull.iloc[-3]:
        score += 15
    if direction == "SHORT" and hull.iloc[-1] < hull.iloc[-3]:
        score += 15

    return min(score, 100)

# ================= MAIN LOOP =================
symbols = get_top_symbols()
send_telegram("🚀 EMA 200 + Hull Trend Screener (5m & 15m) Started")

while True:
    now = time.time()

    for symbol in symbols:
        for tf, cfg in TIMEFRAMES.items():
            try:
                df = fetch_data(symbol, cfg["interval"])

                close = df["close"].iloc[-1]
                ema200_series = ema(df["close"], 200)

                prev_close = df["close"].iloc[-2]
                prev_ema200 = ema200_series.iloc[-2]
                curr_ema200 = ema200_series.iloc[-1]

                long_signal = prev_close < prev_ema200 and close > curr_ema200
                short_signal = prev_close > prev_ema200 and close < curr_ema200

                if not (long_signal or short_signal):
                    continue

                candle_close = df["time"].iloc[-1] / 1000 + cfg["seconds"]
                age_minutes = int((now - candle_close) / 60)
                if age_minutes < 0:
                    age_minutes = 0

                if age_minutes > cfg["max_age"]:
                    continue

                direction = "LONG" if long_signal else "SHORT"
                score = success_rate(direction, df)
                if score < 60:
                    continue

                msg = (
                    f"🔥 <b>{direction} EMA 200 TREND</b>\n\n"
                    f"🪙 <b>Coin:</b> {symbol}\n"
                    f"⏱ <b>Timeframe:</b> {tf}\n"
                    f"⚡ <b>Signal Age:</b> {age_minutes} min\n"
                    f"🎯 <b>Success Rate:</b> {score}%\n"
                )

                print(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram(msg)

            except Exception as e:
                print(symbol, tf, "error:", e)

    time.sleep(5)