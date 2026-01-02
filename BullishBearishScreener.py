from binance.client import Client
import pandas as pd
import numpy as np
import time
import requests

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# ================= CONFIG =================
TOP_COINS = 300
CANDLE_LIMIT = 220

TIMEFRAMES = {
    "5m":  Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE
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

def adx(df, length=14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    tr = atr(df, length)
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1/length).mean() / tr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/length).mean() / tr
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    return dx.ewm(alpha=1/length).mean()

def rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/length).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ================= SUCCESS RATE =================
def success_rate(direction, df):
    score = 0

    if adx(df).iloc[-1] < 18:
        return 0
    score += 25

    if atr(df).iloc[-1] / df["close"].iloc[-1] < 0.002:
        return 0
    score += 20

    r = rsi(df["close"]).iloc[-1]
    if direction == "LONG" and not (45 <= r <= 70):
        return 0
    if direction == "SHORT" and not (30 <= r <= 55):
        return 0
    score += 20

    if df["volume"].iloc[-1] < df["volume"].rolling(20).mean().iloc[-1]:
        return 0
    score += 15

    candle = df.iloc[-1]
    body = abs(candle["close"] - candle["open"])
    wick = (candle["high"] - candle["low"]) - body
    if body < wick:
        return 0
    score += 20

    return score

# ================= EMA 9 + EMA 20 TOUCH & EXPAND =================
def ema9_20_touch_expand_long(df):
    ema9 = ema(df["close"], 9)
    ema20 = ema(df["close"], 20)
    ema200 = ema(df["close"], 200)
    atr_val = atr(df).iloc[-1]

    if ema200.iloc[-1] <= ema200.iloc[-6]:
        return False
    if df["close"].iloc[-1] < ema200.iloc[-1]:
        return False

    touch9 = touch20 = None
    for i in range(1, 4):
        if touch9 is None and abs(ema9.iloc[-i] - ema200.iloc[-i]) <= 0.35 * atr_val:
            touch9 = -i
        if touch20 is None and abs(ema20.iloc[-i] - ema200.iloc[-i]) <= 0.35 * atr_val:
            touch20 = -i

    if touch9 is None or touch20 is None:
        return False

    if (ema9.iloc[-1] - ema9.iloc[touch9]) < 0.5 * atr_val:
        return False
    if (ema20.iloc[-1] - ema20.iloc[touch20]) < 0.5 * atr_val:
        return False

    if abs(ema9.iloc[-1] - ema200.iloc[-1]) <= abs(ema9.iloc[touch9] - ema200.iloc[touch9]):
        return False
    if abs(ema20.iloc[-1] - ema200.iloc[-1]) <= abs(ema20.iloc[touch20] - ema200.iloc[touch20]):
        return False

    candle = df.iloc[-1]
    if candle["close"] <= ema9.iloc[-1]:
        return False
    if abs(candle["close"] - candle["open"]) < 0.6 * atr_val:
        return False

    return True


def ema9_20_touch_expand_short(df):
    ema9 = ema(df["close"], 9)
    ema20 = ema(df["close"], 20)
    ema200 = ema(df["close"], 200)
    atr_val = atr(df).iloc[-1]

    if ema200.iloc[-1] >= ema200.iloc[-6]:
        return False
    if df["close"].iloc[-1] > ema200.iloc[-1]:
        return False

    touch9 = touch20 = None
    for i in range(1, 4):
        if touch9 is None and abs(ema9.iloc[-i] - ema200.iloc[-i]) <= 0.35 * atr_val:
            touch9 = -i
        if touch20 is None and abs(ema20.iloc[-i] - ema200.iloc[-i]) <= 0.35 * atr_val:
            touch20 = -i

    if touch9 is None or touch20 is None:
        return False

    if (ema9.iloc[touch9] - ema9.iloc[-1]) < 0.5 * atr_val:
        return False
    if (ema20.iloc[touch20] - ema20.iloc[-1]) < 0.5 * atr_val:
        return False

    if abs(ema9.iloc[-1] - ema200.iloc[-1]) <= abs(ema9.iloc[touch9] - ema200.iloc[touch9]):
        return False
    if abs(ema20.iloc[-1] - ema200.iloc[-1]) <= abs(ema20.iloc[touch20] - ema200.iloc[touch20]):
        return False

    candle = df.iloc[-1]
    if candle["close"] >= ema9.iloc[-1]:
        return False
    if abs(candle["open"] - candle["close"]) < 0.6 * atr_val:
        return False

    return True

# ================= MAIN LOOP =================
symbols = get_top_symbols()
send_telegram("🚀 EMA 9 + EMA 20 TOUCH & EXPAND SCREENER STARTED")

while True:
    for symbol in symbols:
        for tf, interval in TIMEFRAMES.items():
            try:
                df = fetch_data(symbol, interval)

                if ema9_20_touch_expand_long(df):
                    direction = "LONG"
                elif ema9_20_touch_expand_short(df):
                    direction = "SHORT"
                else:
                    continue

                score = success_rate(direction, df)
                if score < 70:
                    continue

                entry = df["close"].iloc[-1]
                atr_val = atr(df).iloc[-1]

                sl = entry - 2.5 * atr_val if direction == "LONG" else entry + 2.5 * atr_val
                tp = entry + 5 * atr_val if direction == "LONG" else entry - 5 * atr_val

                msg = (
                    f"🔥 <b>{direction} EMA 9 + EMA 20 TOUCH & EXPAND</b>\n\n"
                    f"🪙 <b>Coin:</b> {symbol}\n"
                    f"⏱ <b>TF:</b> {tf}\n"
                    f"🎯 <b>Score:</b> {score}%\n"
                    f"📍 <b>Entry:</b> {entry:.6f}\n"
                    f"🛑 <b>SL:</b> {sl:.6f}\n"
                    f"💰 <b>TP:</b> {tp:.6f} (RR ≈ 1:2)\n"
                )

                print(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram(msg)

            except Exception as e:
                print(symbol, tf, "error:", e)

    time.sleep(10)
