import os
import yfinance as yf
import pandas as pd
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
SYMBOLS = {
    "XAU": "GC=F", "GOLD": "GC=F",
    "BTC": "BTC-USD", "BTCUSD": "BTC-USD",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X", "AUDUSD": "AUDUSD=X",
    "US30": "^DJI", "NAS100": "^NDX", "EURJPY": "EURJPY=X"
}

# === KEEP ALIVE FOR RENDER ===
app_flask = Flask('')
@app_flask.route('/')
def home(): return "EagleX-Pro V3 ICT+SMC is LIVE!"
def run(): app_flask.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# === ICT + SMC LOGIC ===
def get_data(ticker):
    df = yf.download(ticker, period="5d", interval="15m", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.dropna()

def detect_fvg(df):
    # Bullish FVG: low[2] > high[0]
    df['fvg_bull'] = (df['Low'].shift(2) > df['High'].shift(0)) & (df['Low'].shift(2) > df['High'].shift(1))
    df['fvg_bear'] = (df['High'].shift(2) < df['Low'].shift(0)) & (df['High'].shift(2) < df['Low'].shift(1))
    return df

def detect_liquidity(df):
    # Simple: Equal Highs/Lows in last 20 candles + Sweep with wick
    recent_high = df['High'].rolling(20).max().iloc[-2]
    recent_low = df['Low'].rolling(20).min().iloc[-2]
    last = df.iloc[-1]
    sweep_bsl = last['High'] > recent_high and last['Close'] < recent_high # Buy side sweep
    sweep_ssl = last['Low'] < recent_low and last['Close'] > recent_low # Sell side sweep
    return sweep_bsl, sweep_ssl, recent_high, recent_low

def detect_structure(df):
    # BOS / CHOCH simplified: Higher Highs / Lower Lows
    highs = df['High'].rolling(20).max()
    lows = df['Low'].rolling(20).min()
    bullish_bos = df['High'].iloc[-1] > highs.iloc[-2]
    bearish_bos = df['Low'].iloc[-1] < lows.iloc[-2]
    if bullish_bos: return "BULLISH BOS"
    if bearish_bos: return "BEARISH BOS"
    return "RANGING"

def analyze(symbol_key):
    ticker = SYMBOLS.get(symbol_key.upper(), "GC=F")
    df = get_data(ticker)
    if len(df) < 50: return f"{symbol_key}: Not enough data"

    df = detect_fvg(df)
    sweep_bsl, sweep_ssl, liq_high, liq_low = detect_liquidity(df)
    structure = detect_structure(df)

    price = df['Close'].iloc[-1]
    atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]

    # === ICT + SMC DECISION ===
    signal = "NEUTRAL"
    reason = []
    entry = price
    sl = 0
    tp1 = tp2 = tp3 = 0

    if sweep_ssl and structure in ["BULLISH BOS", "RANGING"]:
        signal = "BULLISH 🟢"
        reason.append(f"SSL Sweep at {liq_low:.2f} + {structure}")
        # Check for Bullish FVG near
        if df['fvg_bull'].iloc[-5:].any():
            reason.append("Bullish FVG + Order Block in Discount")
        sl = price - (atr * 1.5)
        tp1 = price + (atr * 1.0)
        tp2 = price + (atr * 2.0)
        tp3 = price + (atr * 3.0)

    elif sweep_bsl and structure in ["BEARISH BOS", "RANGING"]:
        signal = "BEARISH 🔴"
        reason.append(f"BSL Sweep at {liq_high:.2f} + {structure}")
        if df['fvg_bear'].iloc[-5:].any():
            reason.append("Bearish FVG + Order Block in Premium")
        sl = price + (atr * 1.5)
        tp1 = price - (atr * 1.0)
        tp2 = price - (atr * 2.0)
        tp3 = price - (atr * 3.0)
    else:
        # Fallback trend
        ema50 = df['Close'].ewm(span=50).mean().iloc[-1]
        signal = "BULLISH 🟢" if price > ema50 else "BEARISH 🔴"
        reason.append(f"{structure} | Trend above/below EMA50")
        sl = price - atr*1.5 if "BULLISH" in signal else price + atr*1.5
        tp1 = price + atr*1.0 if "BULLISH" in signal else price - atr*1.0
        tp2 = price + atr*2.0 if "BULLISH" in signal else price - atr*2.0
        tp3 = price + atr*3.0 if "BULLISH" in signal else price - atr*3.0

    # Format pips based on asset
    if "JPY" in symbol_key: pip_factor = 0.01
    elif "XAU" in symbol_key or "GOLD" in symbol_key: pip_factor = 0.1
    else: pip_factor = 0.0001

    def to_pips(diff): return abs(diff)/pip_factor

    msg = f"""
🦅 EAGLEX-PRO V3 ICT+SMC
Pair: {symbol_key.upper()} | {ticker}
Price: {price:.2f}
Signal: {signal}
Structure: {structure}

Logic: {', '.join(reason)}

ENTRY: {entry:.2f}
SL: {sl:.2f} ({to_pips(entry-sl):.1f} pips)
TP1: {tp1:.2f} ({to_pips(tp1-entry):.1f} pips)
TP2: {tp2:.2f} ({to_pips(tp2-entry):.1f} pips)
TP3: {tp3:.2f} ({to_pips(tp3-entry):.1f} pips)

RR: 1:{(to_pips(tp3-entry)/to_pips(entry-sl)):.1f}
Time: 15m ICT + SMC
"""
    return msg

# === TELEGRAM HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦅 EagleX-Pro V3 LIVE!\n\nSend:\nXAU / GOLD / BTC / EURUSD / GBPUSD / USDJPY\nOr ALL for all signals")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text == "ALL":
        for k in ["XAU", "BTC", "EURUSD", "GBPUSD", "USDJPY"]:
            await update.message.reply_text(analyze(k))
        return
    key = text.replace("/", "").split()[0]
    if key in SYMBOLS or key in ["XAUUSD", "BTCUSD"]:
        # Normalize
        if key == "XAUUSD": key = "XAU"
        if key == "BTCUSD": key = "BTC"
        await update.message.reply_text(analyze(key))
    else:
        await update.message.reply_text(f"Unknown pair {text}. Try: XAU, BTC, EURUSD, GBPUSD, USDJPY, ALL")

# === MAIN ===
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("EagleX-Pro V3 Starting...")
    app.run_polling()
