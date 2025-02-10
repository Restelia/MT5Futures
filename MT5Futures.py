import tkinter as tk
import threading
import MetaTrader5 as mt5
import asyncio
import discord
from discord.ext import commands

# Global variable to manage the running state of the script
running = True
stopping = False  # Additional flag to manage graceful shutdown
root = None
cumulative_pips = {}

# Function to create a simple tkinter window
def create_window():
    global root
    root = tk.Tk()
    root.title("MT5 Script Running")
    root.geometry("300x100")

    label = tk.Label(root, text="MT5 Script is running...\nClose this window to stop the script.", pady=10)
    label.pack()

    # Function to stop the script when the window is closed
    def on_close():
        stop_script()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# Function to gracefully stop the script
def stop_script():
    global running, stopping
    running = False  # Set the running flag to False to stop loops
    stopping = True  # Signal the MT5 loop to stop

    # Shutdown MetaTrader5 connection
    mt5.shutdown()
    print("Stopping the script...")

    # Stop the Discord bot loop
    async def stop_bot():
        await bot.close()  # Cleanly shut down the Discord bot

    if bot.loop.is_running():
        asyncio.run_coroutine_threadsafe(stop_bot(), bot.loop)

    # Close the tkinter window
    if root:
        root.quit()  # Quit the tkinter main loop to close the window

# Run the tkinter window in a separate thread
window_thread = threading.Thread(target=create_window, daemon=True)
window_thread.start()

# Configuration
DISCORD_BOT_TOKEN = "MTI5MTc5NzE0NjI1Mjg3MzgyOA.GAUIwK.R-c7Pn9H5ic3Q5Mcjzinv8c5XxzyretO0j6mnQ"
DISCORD_CHANNEL_ID = 807715215940255837  # Replace with your channel ID
TP1 = 40
TP2 = 70
TP3 = 100

# Initialize Discord bot
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Function to send a message with an embed
async def send_discord_message(channel_id, symbol, ticket, trade_type, open_price, sl, tp):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title=f"📈 New Trade Opened: {symbol}" if trade_type == "Buy" else f"📉 New Trade Opened: {symbol}",
            color=0x8e8e8e if trade_type == "Buy" else 0x8e8e8e  # Green for Buy, Red for Sell
        )
        embed.add_field(name="Ticket", value=f"{ticket}", inline=False)
        embed.add_field(name="Type", value=f"{trade_type}", inline=False)
        embed.add_field(name="Open Price", value=f"{open_price:.2f}", inline=False)
        # embed.add_field(name="Current SL", value=f"{sl:.2f}", inline=False)
        # embed.add_field(name="Current TP", value=f"{tp:.2f}", inline=False)

        await channel.send(embed=embed)

# Function to get the current price of a symbol
def get_current_price(symbol):
    symbol_info = mt5.symbol_info_tick(symbol)
    if symbol_info is None:
        return None
    return symbol_info.ask  # Return the ask price

# Calculate distance in pips between two prices
def calculate_pips(open_price, current_price, symbol, direction):
    pip_value = 0.01 if "JPY" in symbol else 0.1
    if direction == 'Buy':
        pips = (current_price - open_price) / pip_value
    elif direction == 'Sell':
        pips = (open_price - current_price) / pip_value
    return pips

def calculate_tp_levels(open_price, direction, pips_list, symbol):
    pip_value = 0.01 if "JPY" in symbol else 0.1
    tp_levels = []
    for pips in pips_list:
        if direction == 'Buy':
            tp_price = open_price + (pips * pip_value)
        else:
            tp_price = open_price - (pips * pip_value)
        tp_levels.append((pips, tp_price))
    return tp_levels

def calculate_cumulative_pips(ticket, entry_price, close_price, symbol, direction):
    global cumulative_pips

    # Calculate pips for the current closure
    pip_value = 0.01 if "JPY" in symbol else 0.1
    if direction == 'Buy':
        current_pips = (close_price - entry_price) / pip_value
    else:
        current_pips = (entry_price - close_price) / pip_value

    # Update cumulative pips for the ticket
    if ticket in cumulative_pips:
        cumulative_pips[ticket] += current_pips
    else:
        cumulative_pips[ticket] = current_pips

    return cumulative_pips[ticket]

def calculate_stop_loss(open_price, direction, stop_pips, symbol):
    pip_value = 0.01 if "JPY" in symbol else 0.1
    if direction == 'Buy':
        sl_price = open_price - (stop_pips * pip_value)
    else:
        sl_price = open_price + (stop_pips * pip_value)
    return sl_price

async def mt5_main_loop():
    # Connect to MetaTrader 5
    pineapple_entries = []
    
    if not mt5.initialize():
        print(f"Failed to initialize MT5, error code: {mt5.last_error()}")
        return

    print("MT5 initialized successfully")
    tracked_positions = {}
    tp_pips = [TP1, TP2, TP3]
    stop_pips = 40  # 40 pips stop loss

    try:
        while True:
            positions = mt5.positions_get()
            current_tickets = set()

            if positions:
                for position in positions:
                    current_tickets.add(position.ticket)

                    # If the position already exists, check for updates
                    if position.ticket in tracked_positions:
                        old_position = tracked_positions[position.ticket]["position"]

                        # Stop Loss adjustment logic
                        if position.sl != old_position.sl:
                            sl_distance_pips = calculate_pips(
                                old_position.price_open, position.sl, position.symbol,
                                'Buy' if position.type == mt5.ORDER_TYPE_BUY else 'Sell'
                            )
                            channel = bot.get_channel(DISCORD_CHANNEL_ID)
                            if abs(sl_distance_pips) <= 5:
                                # BE Alert
                                if channel:
                                    embed = discord.Embed(
                                        title=f"⚠️ BE Alert: {position.symbol}",
                                        description=f"**New Stop Loss:** {position.sl:.2f}",
                                        color=0xFFA500  # Orange for BE alert
                                    )
                                    await channel.send(embed=embed)
                                print(f"BE Alert: {position.symbol}, New Stop Loss: {position.sl:.2f}")
                            else:
                                # General Stop Loss adjustment
                                if channel:
                                    embed = discord.Embed(
                                        title=f"🔄 Stop Loss Adjusted: {position.symbol}",
                                        description=f"**New Stop Loss:** {position.sl:.2f}\n"
                                                    f"**Pips from Entry:** {sl_distance_pips:.2f}",
                                        color=0x3498DB  # Blue for SL adjustment
                                    )
                                    await channel.send(embed=embed)
                                print(f"Stop Loss Adjusted for {position.symbol}: New SL: {position.sl:.2f}")

                        # Take Profit adjustment logic
                        if position.tp != old_position.tp:
                            tp_distance_pips = calculate_pips(
                                old_position.price_open, position.tp, position.symbol,
                                'Buy' if position.type == mt5.ORDER_TYPE_BUY else 'Sell'
                            )
                            channel = bot.get_channel(DISCORD_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title=f"🔄 Take Profit Adjusted: {position.symbol}",
                                    description=f"**New Take Profit:** {position.tp:.2f}\n"
                                                f"**Pips from Entry:** {tp_distance_pips:.2f}",
                                    color=0x3498DB  # Blue for TP adjustment
                                )
                                await channel.send(embed=embed)
                            print(f"Take Profit Adjusted for {position.symbol}: New TP: {position.tp:.2f}")

                        # Update tracked position
                        tracked_positions[position.ticket]["position"] = position

                        # Check if the volume has increased (adding pineapple)
                        if position.volume > tracked_positions[position.ticket]["volume"]:
                            pineapple_entry = {
                                "ticket": position.ticket,
                                "symbol": position.symbol,
                                "price": position.price_open,
                                "volume": position.volume
                            }
                            pineapple_entries.append(pineapple_entry)
                            print(f"Pineapple added: {pineapple_entry}")

                            # Announce "Adding Pineapple" to Discord
                            channel = bot.get_channel(DISCORD_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="🍍 Adding Pineapple!",
                                    description=f"**Entry Price:** {position.price_open:.2f}",
                                    color=0x3498DB
                                )
                                await channel.send(embed=embed)

                            tracked_positions[position.ticket]["volume"] = position.volume

                        # Check if the volume has decreased (partial closure)
                        if position.volume < tracked_positions[position.ticket]["volume"]:
                            volume_closed = tracked_positions[position.ticket]["volume"] - position.volume

                            # Calculate pips for the partial closure
                            for pineapple in pineapple_entries:
                                if pineapple["ticket"] == position.ticket:
                                    current_price = get_current_price(pineapple["symbol"])
                                    pips = calculate_cumulative_pips(
                                        pineapple["ticket"], pineapple["price"], current_price,
                                        pineapple["symbol"], 'Buy' if position.type == mt5.ORDER_TYPE_BUY else 'Sell'
                                    )

                                    # Send a specific embed for partial closures
                                    channel = bot.get_channel(DISCORD_CHANNEL_ID)
                                    if channel:
                                        embed = discord.Embed(
                                            title=f"⚠️ Partial Closure: {position.symbol}",
                                            color=0xFFA500
                                        )
                                        embed.add_field(name="Entry Price", value=f"{pineapple['price']:.2f}", inline=False)
                                        embed.add_field(name="Close Price", value=f"{current_price:.2f}", inline=False)
                                        embed.add_field(name="Pips (Cumulative)", value=f"{pips:.2f}", inline=False)
                                        await channel.send(embed=embed)

                                    # Remove the pineapple entry from the array
                                    pineapple_entries.remove(pineapple)
                                    break

                            # Update the tracked volume
                            tracked_positions[position.ticket]["volume"] = position.volume

                    else:
                        # Process a new trade
                        position_type = 'Buy' if position.type == mt5.ORDER_TYPE_BUY else 'Sell'
                        tp_levels = calculate_tp_levels(position.price_open, position_type, tp_pips, position.symbol)
                        stop_loss_price = calculate_stop_loss(position.price_open, position_type, stop_pips, position.symbol)

                        # Calculate TP for the embed
                        tp_price = tp_levels[0][1] if tp_levels else 0.0

                        await send_discord_message(
                            DISCORD_CHANNEL_ID,
                            symbol=position.symbol,
                            ticket=position.ticket,
                            trade_type=position_type,
                            open_price=position.price_open,
                            sl=stop_loss_price,
                            tp=tp_price
                        )
                        print(f"New Trade Opened: {position.symbol}")

                        tracked_positions[position.ticket] = {
                            "position": position,
                            "stop_loss": stop_loss_price,
                            "take_profit": tp_price,
                            "volume": position.volume,
                        }

            # Handle closed tickets
            closed_tickets = set(tracked_positions) - current_tickets
            for ticket in list(tracked_positions):
                if ticket in closed_tickets:
                    # Handle full closure
                    old_position = tracked_positions[ticket]["position"]
                    current_price = get_current_price(old_position.symbol)

                    if current_price is not None:
                        direction = 'Buy' if old_position.type == mt5.ORDER_TYPE_BUY else 'Sell'
                        pips_closed = calculate_pips(
                            old_position.price_open,
                            current_price,
                            old_position.symbol,
                            direction
                        )

                        # Fetch cumulative pips
                        cumulative_pips_closed = calculate_cumulative_pips(
                            ticket,
                            old_position.price_open,
                            current_price,
                            old_position.symbol,
                            direction
                        )

                        # Send a specific embed for full closures
                        channel = bot.get_channel(DISCORD_CHANNEL_ID)
                        if channel:
                            # Determine the color of the embed based on pips_closed
                            if pips_closed > 5:
                                embed_color = 0x00FF00  # Green for gains of 5 pips or more
                            elif pips_closed < -5:
                                embed_color = 0xFF0000  # Red for losses of -5 pips or less
                            else:
                                embed_color = 0xFFFF00  # Yellow for break-even (-5 to 5 pips)

                            # Create the embed with the dynamically determined color
                            embed = discord.Embed(
                                title=f"❌ Trade Closed: {old_position.symbol}",
                                description=f"**Pips Closed:** {pips_closed:.2f}\n"
                                            f"**Cumulative Pips:** {cumulative_pips_closed:.2f}",
                                color=embed_color
                            )
                            embed.add_field(name="Entry Price", value=f"{old_position.price_open:.2f}", inline=False)
                            embed.add_field(name="Close Price", value=f"{current_price:.2f}", inline=False)
                            await channel.send(embed=embed)

                        # Log to console
                        print(f"Trade Closed for {old_position.symbol}: Entry Price: {old_position.price_open:.2f}, "
                            f"Close Price: {current_price:.2f}, Pips Closed: {pips_closed:.2f}, "
                            f"Cumulative Pips: {cumulative_pips_closed:.2f}")

                    # Clear the pineapple entries for this ticket
                    pineapple_entries = [entry for entry in pineapple_entries if entry["ticket"] != ticket]

                    # Remove the ticket from tracking
                    del tracked_positions[ticket]
            await asyncio.sleep(0.15)

    except KeyboardInterrupt:
        print("Stopping the script")
    finally:
        mt5.shutdown()
        print("MT5 connection closed")

# Run the Discord bot
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(mt5_main_loop())

bot.run(DISCORD_BOT_TOKEN)