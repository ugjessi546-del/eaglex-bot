import os
import yfinance as yf
import pandas as pd
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

print("Checking BOT_TOKEN...")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN is MISSING! Add it in Render Environment!")
else:
    print("BOT_TOKEN found! Starting bot...")

SYMBOLS = {
    "XAU": "GC=F", "XAUUSD": "GC=F", "GOLD": "GC=F",
    "BTC": "BTC-USD", "BTCUSD": "BTC-USD",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
    "US30": "^DJI", "NAS100": "^NDX"
}

app_flask = Flask('')
@app_flask.route('/')
def home(): return "EagleX-Pro V3 LIVE!"
def run(): app_flask.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

def get_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception as e:
        print(f"yfinance error {ticker}: {e}")
        return pd.DataFrame()

def analyze(symbol_key):
    ticker = SYMBOLS.get(symbol_key.upper(), "GC=F")
    df = get_data(ticker)
    if len(df) < 50:
        return f"❌ {symbol_key}: No data for {ticker}. Try again later."

    price = float(df['Close'].iloc[-1])
    high = df['High']
    low = df['Low']
    
    recent_high = float(high.rolling(20).max().iloc[-2])
    recent_low = float(low.rolling(20).min().iloc[-2])
    last_high = float(high.iloc[-1])
    last_low = float(low.iloc[-1])
    
    sweep_bsl = last_high > recent_high
    sweep_ssl = last_low < recent_low
    
    bullish_bos = price > recent_high
    bearish_bos = price < recent_low
    structure = "BULLISH BOS" if bullish_bos else "BEARISH BOS" if bearish_bos else "RANGING"
    
    atr = float((high - low).rolling(14).mean().iloc[-1])
    if atr == 0: atr = price * 0.002
    
    signal = "NEUTRAL"
    reason = []
    
    if sweep_ssl:
        signal = "BULLISH 🟢 BUY"
        reason.append(f"SSL Sweep {recent_low:.2f}")
        reason.append(f"{structure}")
        sl = price - (atr * 1.5)
        tp1 = price + (atr * 1.2)
        tp2 = price + (atr * 2.5)
        tp3 = price + (atr * 4.0)
    elif sweep_bsl:
        signal = "BEARISH 🔴 SELL"
        reason.append(f"BSL Sweep {recent_high:.2f}")
        reason.append(f"{structure}")
        sl = price + (atr * 1.5)
        tp1 = price - (atr * 1.2)
        tp2 = price - (atr * 2.5)
        tp3 = price - (atr * 4.0)
    else:
        ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])
        if price > ema50:
            signal = "BULLISH 🟢 BUY"
            reason.append(f"{structure} | Price>EMA50")
            sl = price - (atr * 1.5)
            tp1 = price + (atr * 1.5)
            tp2 = price + (atr * 3.0)
            tp3 = price + (atr * 5.0)
        else:
            signal = "BEARISH 🔴 SELL"
            reason.append(f"{structure} | Price<EMA50")
            sl = price + (atr * 1.5)
            tp1 = price - (atr * 1.5)
            tp2 = price - (atr * 3.0)
            tp3 = price - (atr * 5.0)

    is_jpy = "JPY" in symbol_key
    is_gold = "XAU" in symbol_key or "GOLD" in symbol_key
    is_btc = "BTC" in symbol_key
    
    if is_jpy:
        pips_sl = abs(price - sl) / 0.01
        pips_tp3 = abs(tp3 - price) / 0.01
    elif is_gold:
        pips_sl = abs(price - sl) / 0.1
        pips_tp3 = abs(tp3 - price) / 0.1
    elif is_btc:
        pips_sl = abs(price - sl)
        pips_tp3 = abs(tp3 - price)
    else:
        pips_sl = abs(price - sl) / 0.0001
        pips_tp3 = abs(tp3 - price) / 0.0001

    rr = pips_tp3 / pips_sl if pips_sl != 0 else 0

    return f"""🦅 EAGLEX-PRO V3 ICT+SMC
Pair: {symbol_key.upper()} | {ticker}
Price: {price:.2f}

Signal: {signal}
Structure: {structure}
Logic: {' | '.join(reason)}

--- TRADE PLAN ---
ENTRY: {price:.2f}
SL: {sl:.2f} ({pips_sl:.1f} pips)
TP1: {tp1:.2f}
TP2: {tp2:.2f}
TP3: {tp3:.2f} ({pips_tp3:.1f} pips)

RR: 1:{rr:.1f}
Concept: Liquidity + BOS
TF: 15m
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦅 EagleX-Pro V3 LIVE!\nSend: XAU / BTC / EURUSD / GBPUSD / USDJPY / ALL")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text == "ALL":
        for k in ["XAU", "BTC", "EURUSD", "GBPUSD", "USDJPY"]:
            await update.message.reply_text(analyze(k))
        return
    if "START" in text:
        await start(update, context)
        return
    key = text.replace("/", "").replace(" ", "")[:10]
    clean = key[:6] if key[:6] in SYMBOLS else key[:3]
    if clean in SYMBOLS:
        await update.message.reply_text(analyze(clean))
    elif key in SYMBOLS:
        await update.message.reply_text(analyze(key))
    else:
        await update.message.reply_text("Use: XAU, BTC, EURUSD, GBPUSD, USDJPY, ALL")

if __name__ == "__main__":
    keep_alive()
    if not BOT_TOKEN:
        print("BOT_TOKEN missing - bot cannot start")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        print("EagleX-Pro V3 Starting... Polling...")
        app.run_polling()
