import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Risk-Free Hedge Visualizer", layout="wide")

# --- 1. SESSION STATE (Memory) ---
if 'legs' not in st.session_state:
    st.session_state.legs = []

# --- 2. LOGIC FUNCTIONS ---
def calculate_payoff(legs, spot_range_max=200):
    spot_range = np.linspace(0, spot_range_max, 1000)
    total_net_cash = 0
    total_pnl = np.zeros_like(spot_range)

    if not legs:
        return total_pnl, spot_range, 0

    strikes = [leg['Strike'] for leg in legs]
    max_strike = max(strikes) if strikes else 100
    spot_range = np.linspace(0, max_strike * 1.5, 1000)
    total_pnl = np.zeros_like(spot_range)

    for leg in legs:
        is_buy = 'Buy' in leg['Action']
        pos_direction = 1 if is_buy else -1
        
        direction_mult = 1 if 'Sell' in leg['Action'] else -1
        net_cash_flow = (leg['Price'] * 100 * leg['Qty'] * direction_mult) - leg['Fees']
        
        total_net_cash += net_cash_flow

        if leg['Type'] == 'Call':
            intrinsic = np.maximum(spot_range - leg['Strike'], 0)
        else: # Put
            intrinsic = np.maximum(leg['Strike'] - spot_range, 0)
        
        leg_pnl = (intrinsic * pos_direction * leg['Qty'] * 100) + net_cash_flow
        total_pnl += leg_pnl
        
    return total_pnl, spot_range, total_net_cash

# --- 3. SIDEBAR (Inputs) ---
st.sidebar.header("1. Market Data")
symbol = st.sidebar.text_input("Symbol", value="SPY").upper()

if st.sidebar.button("Get Live Price"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            price = data['Close'].iloc[-1]
            st.session_state['curr_price'] = round(price, 2)
        else:
            st.sidebar.error("Symbol not found.")
    except:
        st.sidebar.error("Error fetching data.")

curr_price = st.sidebar.number_input("Current Price", value=st.session_state.get('curr_price', 0.0), step=0.5)

st.sidebar.markdown("---")
st.sidebar.header("2. Add Trade Leg")

with st.sidebar.form("leg_form"):
    col1, col2 = st.columns(2)
    qty = col1.number_input("Qty", min_value=1, value=1)
    action = col2.selectbox("Action", ['Sell to Open', 'Buy to Open', 'Buy to Close', 'Sell to Close'])
    
    col3, col4 = st.columns(2)
    opt_type = col3.selectbox("Type", ['Put', 'Call'])
    strike = col4.number_input("Strike", value=400.0, step=1.0)
    
    col5, col6 = st.columns(2)
    exp_date = col5.date_input("Exp Date", datetime.date.today())
    price = col6.number_input("Price", value=1.50, step=0.05)
    
    fees = st.number_input("Fees", value=0.65, step=0.05)
    notes = st.text_input("Leg Notes", placeholder="e.g. Initial Entry")
    
    submitted = st.form_submit_button("Add Leg")
    
    if submitted:
        new_leg = {
            'Qty': qty, 'Action': action, 'Type': opt_type, 'Strike': strike,
            'Exp Date': str(exp_date), 'Price': price, 'Fees': fees, 'Leg Notes': notes
        }
        st.session_state.legs.append(new_leg)

if st.sidebar.button("Reset / Clear All"):
    st.session_state.legs = []

# --- 4. MAIN DASHBOARD ---
st.title(f"🛡️ Risk-Free Hedge Visualizer: {symbol}")

if st.session_state.legs:
    pnl, spots, net_cash = calculate_payoff(st.session_state.legs)
    # Re-calc if price is out of bounds
    if curr_price > spots[-1]:
         pnl, spots, net_cash = calculate_payoff(st.session_state.legs, spot_range_max=curr_price*1.1)
else:
    net_cash = 0

st.metric("Net Realized Cash (Banking)", f"${net_cash:,.2f}")

col_chart, col_table = st.columns([2, 1])

with col_chart:
    if st.session_state.legs:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(spots, pnl, color='blue', linewidth=2, label='PnL at Exp')
        
        # Color Fills
        ax.fill_between(spots, pnl, 0, where=(pnl >= 0), color='green', alpha=0.3)
        ax.fill_between(spots, pnl, 0, where=(pnl < 0), color='red', alpha=0.3)
        
        ax.axhline(0, color='black', linewidth=1)
        
        if curr_price > 0:
            ax.axvline(curr_price, color='orange', linestyle='--', linewidth=2, label=f'Current: ${curr_price}')
        
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Stock Price")
        ax.set_ylabel("P/L ($)")
        ax.legend(loc='upper left')
        st.pyplot(fig)
    else:
        st.info("👈 Add a trade leg in the sidebar to visualize the risk profile.")

with col_table:
    st.subheader("Trade Log")
    if st.session_state.legs:
        df = pd.DataFrame(st.session_state.legs)
        
        def get_cf(row):
            d = 1 if 'Sell' in row['Action'] else -1
            return (row['Price'] * 100 * row['Qty'] * d) - row['Fees']
        
        df['Net Cash'] = df.apply(get_cf, axis=1)
        df['Running Total'] = df['Net Cash'].cumsum()
        
        # --- FIXED: Added 'Leg Notes' and other useful columns to this list ---
        cols = ['Qty', 'Action', 'Type', 'Strike', 'Exp Date', 'Net Cash', 'Running Total', 'Leg Notes']
        display_df = df[cols].copy()
        
        display_df['Net Cash'] = display_df['Net Cash'].map('${:,.2f}'.format)
        display_df['Running Total'] = display_df['Running Total'].map('${:,.2f}'.format)
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.write("No active legs.")
