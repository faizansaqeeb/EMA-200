from binance.client import Client
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

client = Client()

SYMBOL = "BTCUSDT"

TIMEFRAMES = {
    "5m": Client.KLINE_INTERVAL_5MINUTE,
    "15m": Client.KLINE_INTERVAL_15MINUTE,
    "1h": Client.KLINE_INTERVAL_1HOUR
}

HULL_LENGTH = 55
CANDLE_LIMIT = 200
UPDATE_INTERVAL_MS = 5000

def wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )

def hma(series, length):
    half = int(length / 2)
    sqrt_len = int(np.sqrt(length))
    return wma(2 * wma(series, half) - wma(series, length), sqrt_len)

def get_data(symbol, interval):
    klines = client.futures_klines(
        symbol=symbol,
        interval=interval,
        limit=CANDLE_LIMIT
    )

    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])

    df["close"] = df["close"].astype(float)
    return df

fig, axes = plt.subplots(3, 1, figsize=(15, 10))

def update(frame):
    for ax, (tf, interval) in zip(axes, TIMEFRAMES.items()):
        df = get_data(SYMBOL, interval)

        df["Indicator"] = hma(df["close"], HULL_LENGTH)
        df["SIndicator"] = df["Indicator"].shift(2)

        ax.clear()

        ax.plot(df["close"], color="lightgrey", alpha=0.4)

        for i in range(3, len(df)):
            if pd.isna(df["Indicator"].iloc[i]) or pd.isna(df["SIndicator"].iloc[i]):
                continue

            color = "green" if df["Indicator"].iloc[i] > df["SIndicator"].iloc[i] else "red"

            ax.plot(
                [i - 1, i],
                [df["Indicator"].iloc[i - 1], df["Indicator"].iloc[i]],
                color=color,
                linewidth=3
            )

        last = df.iloc[-1]
        trend = "UPTREND" if last.Indicator > last.SIndicator else "DOWNTREND"
        trend_color = "green" if trend == "UPTREND" else "red"
        trade_text = "ONLY BUY TRADES" if trend == "UPTREND" else "ONLY SELL TRADES"

        ax.text(
            0.01,
            0.95,
            f"{tf.upper()} TREND: {trend}\n{trade_text}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=11,
            weight="bold",
            color=trend_color,
            bbox=dict(
                facecolor="white",
                alpha=0.9,
                edgecolor=trend_color,
                boxstyle="round,pad=0.3"
            )
        )

        ax.set_title(f"{SYMBOL} | {tf} | Faizan's Indicator (Trend Filter)")
        ax.grid(alpha=0.3)

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.tight_layout()
plt.show()