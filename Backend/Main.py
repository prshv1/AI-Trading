from openai import OpenAI
import time
import requests
from datetime import datetime, timedelta

def get_24hr_data():

    Data = []
    interval = '15m'
    # Calculate timestamps for last 24 hours
    current_time = int(time.time())  # Current time in seconds (Unix timestamp)
    start_time = current_time - (24 * 60 * 60)  # 24 hours ago
    
    # Gatharing Data
    USDC_Data = requests.get(
        url = f"https://api.backpack.exchange/api/v1/klines", 
        params={
            "symbol": 'USDT_USDC',
            "interval": interval,
            "startTime": start_time,
            "endTime": current_time
    })
    Data.append({'USDC_Data:': USDC_Data.json()})
    
    BTC_Data = requests.get(
        url = f"https://api.backpack.exchange/api/v1/klines", 
        params={
            "symbol": 'BTC_USDC',
            "interval": interval,
            "startTime": start_time,
            "endTime": current_time
    })
    Data.append({'BTC_Data:': BTC_Data.json()})

    ETH_Data = requests.get(
        url = f"https://api.backpack.exchange/api/v1/klines", 
        params={
            "symbol": 'ETH_USDC',
            "interval": interval,
            "startTime": start_time,
            "endTime": current_time
    })
    Data.append({'ETH_Data:': ETH_Data.json()})

    SOL_Data = requests.get(
        url = f"https://api.backpack.exchange/api/v1/klines", 
        params={
            "symbol": 'SOL_USDC',
            "interval": interval,
            "startTime": start_time,
            "endTime": current_time
    })
    Data.append({'SOL_Data:': SOL_Data.json()})


    return (str(Data))

def deepseek(content):
    # Read API key from file
    with open('/Users/prshv/Documents/Coding/Ai-Trading-Api-Key.txt', 'r') as file: api_key = file.read().strip()
    # Read System Prompt
    with open('/Users/prshv/Documents/Coding/AI-Trading/Backend/system_prompt.txt', 'r') as file: system_prompt = file.read().strip()
    # Api Call
    start_time = time.perf_counter() # Record the start time
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    msg = client.chat.completions.create(
        model="deepseek/deepseek-chat-v3.1:free",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": content
            }
        ]
    )
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    return (elapsed_time, msg.choices[0].message.content)   

print(deepseek(get_24hr_data()))