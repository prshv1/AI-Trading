import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
import pandas as pd
from openai import OpenAI
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException


# Configuration
BACKPACK_API_URL = "https://api.backpack.exchange/api/v1/klines"
TRADING_SYMBOLS = ["USDT_USDC", "BTC_USDC", "ETH_USDC", "SOL_USDC"]
KLINE_INTERVAL = "15m"
LOOKBACK_HOURS = 12
OUTPUT_FILE = "AI-Trading/Data.csv"

# File paths 
API_KEY_PATH = "AI-Trading/Backend/Ai-Trading-Api-Key.txt" #file to create Ai-Trading-Api-Key.txt and make sure to add your OpenRouter API key in it
SYSTEM_PROMPT_PATH = "AI-Trading/Backend/system_prompt.txt"


def load_file_content(file_path: str) -> str:
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except IOError as e:
        raise IOError(f"Error reading file {file_path}: {e}")


def get_24hr_market_data() -> str:
    current_time = int(time.time())
    start_time = current_time - (LOOKBACK_HOURS * 60 * 60)
    
    market_data = []
    
    for symbol in TRADING_SYMBOLS:
        try:
            response = requests.get(
                url=BACKPACK_API_URL,
                params={
                    "symbol": symbol,
                    "interval": KLINE_INTERVAL,
                    "startTime": start_time,
                    "endTime": current_time,
                }
            )
            response.raise_for_status()
            market_data.append({f"{symbol}_data": response.json()})
            
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch data for {symbol}: {e}")
            continue
    
    return str(market_data)

def analyze_with_deepseek(market_data: str, timeout: int = 120) -> str:
    # Load API credentials
    api_key = load_file_content(API_KEY_PATH)
    system_prompt = load_file_content(SYSTEM_PROMPT_PATH)
    
    # Initialize OpenRouter client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    # Make API call
    response = client.chat.completions.create(
        model="deepseek/deepseek-chat-v3.1:free",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": market_data
            }
        ]
    )
    
    return response.choices[0].message.content

def save_analysis_to_csv(analysis: str, filename: str = OUTPUT_FILE) -> None:
    df = pd.DataFrame([analysis])
    df.to_csv(filename, mode='a', header=False, index=False)

# Main execution
try:
    print("Fetching 24-hour market data...")
    market_data = get_24hr_market_data()
    
    print("Analyzing with DeepSeek AI...")
    analysis = analyze_with_deepseek(market_data)
    
    print("Saving results to CSV...")
    save_analysis_to_csv(analysis)
    
    print("Trade executed and logged successfully")
    
except FileNotFoundError as e:
    print(f"Error: {e}")
except requests.RequestException as e:
    print(f"API Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
