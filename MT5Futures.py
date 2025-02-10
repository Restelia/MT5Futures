import tkinter as tk
import threading
import MetaTrader5 as mt5
import asyncio
import discord
from discord.ext import commands

# Global variables
running = True
root = None
trades = []  # List to track open trades

# Discord bot configuration
DISCORD_BOT_TOKEN = "MTI5MTc5NzE0NjI1Mjg3MzgyOA.GAUIwK.R-c7Pn9H5ic3Q5Mcjzinv8c5XxzyretO0j6mnQ"
DISCORD_CHANNEL_ID = 807715215940255837  # Replace with actual channel ID

# Initialize Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize MT5
if not mt5.initialize():
    print(f"Failed to initialize MT5, error code: {mt5.last_error()}")
    exit()

def open_trade(symbol, lot_size, direction):
    """Function to open a trade on MT5 and announce it on Discord."""
    order_type = mt5.ORDER_TYPE_BUY if direction == "Buy" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if direction == "Buy" else mt5.symbol_info_tick(symbol).bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "deviation": 10,
        "magic": 0,
        "comment": "Opened via UI",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        trades.append({"ticket": result.order, "symbol": symbol, "lot": lot_size, "direction": direction})
        update_trade_list()
        send_message_in_thread(symbol, lot_size, direction, price)
    else:
        print(f"Trade failed: {result.comment}")

def close_trade(ticket):
    """Function to close an open trade on MT5 and update the UI."""
    for trade in trades:
        if trade["ticket"] == ticket:
            symbol = trade["symbol"]
            price = mt5.symbol_info_tick(symbol).bid if trade["direction"] == "Buy" else mt5.symbol_info_tick(symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": trade["lot"],
                "type": mt5.ORDER_TYPE_SELL if trade["direction"] == "Buy" else mt5.ORDER_TYPE_BUY,
                "price": price,
                "deviation": 10,
                "magic": 0,
                "comment": "Closed via UI",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                trades.remove(trade)
                update_trade_list()
            else:
                print(f"Failed to close trade: {result.comment}")
            break

def update_trade_list():
    """Function to update the displayed trade list in the UI."""
    trade_listbox.delete(0, tk.END)
    for trade in trades:
        trade_listbox.insert(tk.END, f"{trade['symbol']} | {trade['direction']} | {trade['lot']} lots")

def send_message_in_thread(symbol, lot_size, direction, price):
    """Ensures the message is sent inside the running event loop."""
    asyncio.run_coroutine_threadsafe(send_discord_message(symbol, lot_size, direction, price), bot.loop)

async def send_discord_message(symbol, lot_size, direction, price):
    """Function to send trade notifications to Discord."""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"{'📈 Buy' if direction == 'Buy' else '📉 Sell'} Trade Opened",
            description=f"**Symbol:** {symbol}\n**Lot Size:** {lot_size}\n**Entry Price:** {price:.2f}",
            color=0x00FF00 if direction == "Buy" else 0xFF0000,
        )
        await channel.send(embed=embed)

def create_ui():
    """Function to create the tkinter UI."""
    global root, trade_listbox
    root = tk.Tk()
    root.title("MT5 Trading App")
    root.geometry("400x300")
    
    tk.Label(root, text="Symbol:").pack()
    symbol_entry = tk.Entry(root)
    symbol_entry.pack()
    
    tk.Label(root, text="Lot Size:").pack()
    lot_size_entry = tk.Entry(root)
    lot_size_entry.pack()
    
    direction_var = tk.StringVar(value="Buy")
    tk.Radiobutton(root, text="Buy", variable=direction_var, value="Buy").pack()
    tk.Radiobutton(root, text="Sell", variable=direction_var, value="Sell").pack()
    
    tk.Button(root, text="Open Trade", command=lambda: open_trade(symbol_entry.get(), float(lot_size_entry.get()), direction_var.get())).pack()
    
    tk.Label(root, text="Open Trades:").pack()
    trade_listbox = tk.Listbox(root)
    trade_listbox.pack()
    
    tk.Button(root, text="Close Selected Trade", command=lambda: close_trade(trades[trade_listbox.curselection()[0]]["ticket"] if trade_listbox.curselection() else None)).pack()
    
    root.mainloop()

# Run tkinter in a separate thread
threading.Thread(target=create_ui, daemon=True).start()

# Run Discord bot
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(DISCORD_BOT_TOKEN)
