import os
import json
import csv
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

# Configuration
API_KEY_FILE = 'AI-Trading /backend/API.txt'
SYSTEM_PROMPT_FILE = 'AI-Trading /backend/system_prompt.txt'
DATA_LOG_FILE = 'AI-Trading /backend/data.csv'
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openai/gpt-oss-20b:free" # Adjust based on available free models on OpenRouter

# Assets to track
ASSETS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
ASSET_NAMES = ['BTC', 'ETH', 'SOL'] # Mapped names for cleaner logic

def load_file_content(filepath):

    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None
    with open(filepath, 'r') as f:
        return f.read().strip()

def get_market_data():

    market_summary = {}
    current_prices = {}
    
    print("Fetching market data from Yahoo Finance...")
    
    for ticker, name in zip(ASSETS, ASSET_NAMES):
        try:
            # Fetch data: last 24 hours, 15 minute intervals
            stock = yf.Ticker(ticker)
            # "1d" period with "15m" interval gets us the intraday data needed
            hist = stock.history(period="1d", interval="15m")
            
            if hist.empty:
                print(f"Warning: No data found for {ticker}")
                current_prices[name] = 0
                market_summary[name] = []
                continue

            # Get current price (last close)
            current_price = hist['Close'].iloc[-1]
            current_prices[name] = current_price
            
            # Format history string for the AI
            # We take the last ~96 points (24h * 4 quarters)
            history_str = hist['Close'].tail(96).to_list()
            market_summary[name] = history_str
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None, None

    return current_prices, market_summary

def get_last_portfolio_state():

    if not os.path.exists(DATA_LOG_FILE):
        # Initialize with default imaginary money if file doesn't exist
        print("No history found. Starting new portfolio with $10,000 USDT.")
        return {
            "USDT": 10000.0,
            "BTC": 0.0,
            "ETH": 0.0,
            "SOL": 0.0
        }
    
    try:
        df = pd.read_csv(DATA_LOG_FILE)
        if df.empty:
            return {"USDT": 10000.0, "BTC": 0.0, "ETH": 0.0, "SOL": 0.0}
        
        last_row = df.iloc[-1]
        return {
            "USDT": float(last_row['Holdings_USDT']),
            "BTC": float(last_row['Holdings_BTC']),
            "ETH": float(last_row['Holdings_ETH']),
            "SOL": float(last_row['Holdings_SOL'])
        }
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return {"USDT": 10000.0, "BTC": 0.0, "ETH": 0.0, "SOL": 0.0}

def consult_oracle(api_key, system_prompt, current_prices, market_history, current_holdings):
    
    # specific formatting for the prompt
    user_prompt = f"""
    CURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    --- CURRENT MARKET PRICES (USD) ---
    BTC: ${current_prices.get('BTC', 0):.2f}
    ETH: ${current_prices.get('ETH', 0):.2f}
    SOL: ${current_prices.get('SOL', 0):.2f}
    
    --- MARKET HISTORY (Last 24h, 15m intervals) ---
    BTC History: {market_history.get('BTC')}
    ETH History: {market_history.get('ETH')}
    SOL History: {market_history.get('SOL')}
    
    --- CURRENT HOLDINGS ---
    USDT: {current_holdings['USDT']:.2f}
    BTC: {current_holdings['BTC']:.6f}
    ETH: {current_holdings['ETH']:.6f}
    SOL: {current_holdings['SOL']:.4f}
    
    Based on this data, provide the NEW TARGET PORTFOLIO allocation in USD value for each asset. 
    You can decide to hold cash (USDT) or buy specific coins.
    Response must be strictly JSON.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000", # OpenRouter requirement
        "X-Title": "AlphaArenaSim"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"} # Force JSON if supported, otherwise system prompt handles it
    }

    try:
        print("Consulting the AI Oracle...")
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        content = result['choices'][0]['message']['content']
        # Clean markdown if present (e.g. ```json ... ```)
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"API Error: {e}")
        if 'response' in locals():
            print(f"Response content: {response.text}")
        return None

def execute_trades_and_log(decision, current_prices, current_holdings):
    
    # 1. Calculate Total Portfolio Value first (to validate AI didn't hallucinate extra money)
    total_value_usd = (
        current_holdings['USDT'] +
        (current_holdings['BTC'] * current_prices['BTC']) +
        (current_holdings['ETH'] * current_prices['ETH']) +
        (current_holdings['SOL'] * current_prices['SOL'])
    )
    
    print(f"Total Portfolio Value before trade: ${total_value_usd:.2f}")
    
    # 2. Parse AI decision (The AI gives target USD values for each asset)
    # We normalize the AI's request to ensure it doesn't exceed our total balance
    target_btc_val = float(decision.get('BTC_USD_VALUE', 0))
    target_eth_val = float(decision.get('ETH_USD_VALUE', 0))
    target_sol_val = float(decision.get('SOL_USD_VALUE', 0))
    target_usdt_val = float(decision.get('USDT_VALUE', 0))
    
    total_requested = target_btc_val + target_eth_val + target_sol_val + target_usdt_val
    
    if total_requested == 0:
        print("AI returned zero values. Holding position.")
        new_holdings = current_holdings
    else:
        # Rebalance/Normalize if AI math is slightly off
        ratio = total_value_usd / total_requested
        
        final_btc_val = target_btc_val * ratio
        final_eth_val = target_eth_val * ratio
        final_sol_val = target_sol_val * ratio
        final_usdt_val = target_usdt_val * ratio
        
        # 3. Convert USD values back to Token Quantities
        new_holdings = {
            "BTC": final_btc_val / current_prices['BTC'] if current_prices['BTC'] > 0 else 0,
            "ETH": final_eth_val / current_prices['ETH'] if current_prices['ETH'] > 0 else 0,
            "SOL": final_sol_val / current_prices['SOL'] if current_prices['SOL'] > 0 else 0,
            "USDT": final_usdt_val
        }

    # 4. Log to CSV
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Check if file exists to write header
    file_exists = os.path.isfile(DATA_LOG_FILE)
    
    with open(DATA_LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'Total_Value_USD', 'Holdings_BTC', 'Holdings_ETH', 'Holdings_SOL', 'Holdings_USDT', 'BTC_Price', 'ETH_Price', 'SOL_Price'])
        
        writer.writerow([
            timestamp,
            round(total_value_usd, 2),
            f"{new_holdings['BTC']:.8f}",
            f"{new_holdings['ETH']:.8f}",
            f"{new_holdings['SOL']:.8f}",
            round(new_holdings['USDT'], 2),
            current_prices['BTC'],
            current_prices['ETH'],
            current_prices['SOL']
        ])
        
    print(f"Trade executed. New Portfolio Value: ${total_value_usd:.2f}")
    print(f"New Holdings: {json.dumps(new_holdings, indent=2)}")

# 1. Setup
    api_key = load_file_content(API_KEY_FILE)
    system_prompt = load_file_content(SYSTEM_PROMPT_FILE)
    
    if not api_key:
        print("Please put your API key in API.txt")
        return

    # 2. Get Data
    current_prices, market_history = get_market_data()
    if not current_prices:
        print("Failed to fetch market data. Aborting.")
        return

    # 3. Get Current State
    current_holdings = get_last_portfolio_state()
    
    # 4. Ask AI
    decision = consult_oracle(api_key, system_prompt, current_prices, market_history, current_holdings)
    
    if decision:
        # 5. Execute & Log
        execute_trades_and_log(decision, current_prices, current_holdings)
    else:
        print("Failed to get a valid decision from AI.")