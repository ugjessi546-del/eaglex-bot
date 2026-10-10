import os, threading
from flask import Flask
app = Flask(__name__)
@app.route('/')
def home(): return "EagleX Bot is Running!"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_web, daemon=True).start()

import requests, telebot
from datetime import datetime

TWELVE_KEY = "420a171a746d4502bd641761a0aa1da0"
TELEGRAM_TOKEN = "8808356960:AAF6daw9QsQGvcpj16ZSaBV_V4XEYXhdm_U"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_real_analysis():
    try:
        s="XAU/USD"; b="https://api.twelvedata.com"
        p=float(requests.get(f"{b}/price?symbol={s}&apikey={TWELVE_KEY}",timeout=10).json()['price'])
        rsi=float(requests.get(f"{b}/rsi?symbol={s}&interval=15min&apikey={TWELVE_KEY}",timeout=10).json()['values'][0]['rsi'])
        ema=float(requests.get(f"{b}/ema?symbol={s}&interval=15min&period=20&apikey={TWELVE_KEY}",timeout=10).json()['values'][0]['ema'])
        atr=float(requests.get(f"{b}/atr?symbol={s}&interval=15min&apikey={TWELVE_KEY}",timeout=10).json()['values'][0]['atr'])
        trend="BULLISH" if p>ema else "BEARISH"
        sl=p-atr*1.5 if "BULLISH" in trend else p+atr*1.5
        tp1=p+atr*1 if "BULLISH" in trend else p-atr*1
        tp2=p+atr*2 if "BULLISH" in trend else p-atr*2
        tp3=p+atr*3 if "BULLISH" in trend else p-atr*3
        return f"EAGLEX-PRO LIVE {datetime.utcnow().strftime('%H:%M UTC')}\nXAUUSD {p:.2f} {trend}\nRSI {rsi:.1f} EMA {ema:.2f}\nENTRY {p:.2f}\nSL {sl:.2f}\nTP1 {tp1:.2f} TP2 {tp2:.2f} TP3 {tp3:.2f}"
    except Exception as e:
        return f"Error: {e}"

@bot.message_handler(func=lambda m: m.text and "START" in m.text.upper())
def handle(m): bot.send_message(m.chat.id, get_real_analysis())

bot.infinity_polling()
