import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import requests
import pandas as pd
from openai import OpenAI, APIConnectionError, APIError, APITimeoutError
from requests.exceptions import ConnectionError, Timeout, RequestException

# ============================================================================
# CONFIGURATION
# ============================================================================

BACKPACK_API_URL = "https://api.backpack.exchange/api/v1/klines"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-oss-20b:free"

TRADING_SYMBOLS = ["USDT_USDC", "BTC_USDC", "ETH_USDC", "SOL_USDC"]
KLINE_INTERVAL = "15m"
LOOKBACK_HOURS = 12

OUTPUT_FILE = "AI-Trading/Data.csv"
API_KEY_PATH = "/Users/prshv/Documents/Coding/AI-Trading/Backend/Ai-Trading-Api-Key.txt"
SYSTEM_PROMPT_PATH = "/Users/prshv/Documents/Coding/AI-Trading/Backend/system_prompt.txt"

REQUEST_TIMEOUT = 30
API_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_DELAY = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# FILE I/O FUNCTIONS
# ============================================================================

def load_file_content(file_path: str) -> Optional[str]:
    """Load content from a file with comprehensive error handling."""
    if not file_path:
        logger.error("File path is empty")
        raise ValueError("File path cannot be empty")
    
    if not os.path.exists(file_path):
        logger.error(f"File not found at path: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not os.path.isfile(file_path):
        logger.error(f"Path is not a file: {file_path}")
        raise ValueError(f"Path is not a file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
            if not content:
                logger.warning(f"File is empty: {file_path}")
            return content
    except PermissionError as e:
        logger.error(f"Permission denied reading file {file_path}: {e}")
        raise IOError(f"Permission denied: {file_path}")
    except UnicodeDecodeError as e:
        logger.error(f"File encoding error {file_path}: {e}")
        raise IOError(f"File encoding error: {file_path}")
    except IOError as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise IOError(f"Error reading file {file_path}: {e}")


def validate_csv_structure(df: pd.DataFrame) -> bool:
    """Validate that the CSV has expected columns."""
    expected_columns = ["Tottal Holdings", "BTC", "ETH", "Sol", "USDC"]
    for col in expected_columns:
        if col not in df.columns:
            logger.warning(f"Expected column '{col}' not found in CSV")
            return False
    return True


# ============================================================================
# DATA RETRIEVAL FUNCTIONS
# ============================================================================

def get_previous_total_holdings(filename: str = OUTPUT_FILE) -> Dict[str, Any]:
    """Extract the last row's total holdings from the CSV file."""
    default_holdings = {
        "total_holdings": 10000,
        "BTC": 0,
        "ETH": 0,
        "SOL": 0,
        "USDC": 0
    }
    
    if not filename:
        logger.warning("No output filename provided, using defaults")
        return default_holdings
    
    if not os.path.exists(filename):
        logger.warning(f"Data file not found: {filename}. Using default holdings.")
        return default_holdings
    
    try:
        df = pd.read_csv(filename)
        
        if df.empty:
            logger.warning("Data.csv is empty. Starting with default holdings.")
            return default_holdings
        
        if not validate_csv_structure(df):
            logger.warning("CSV structure invalid. Using default holdings.")
            return default_holdings
        
        last_row = df.iloc[-1]
        
        try:
            total_holdings = float(last_row.get("Tottal Holdings", 10000))
            btc_holdings = float(last_row.get("BTC", 0))
            eth_holdings = float(last_row.get("ETH", 0))
            sol_holdings = float(last_row.get("Sol", 0))
            usdc_holdings = float(last_row.get("USDC", 0))
        except (ValueError, TypeError) as e:
            logger.error(f"Type conversion error reading holdings: {e}. Using defaults.")
            return default_holdings
        
        holdings_data = {
            "total_holdings": total_holdings,
            "BTC": btc_holdings,
            "ETH": eth_holdings,
            "SOL": sol_holdings,
            "USDC": usdc_holdings
        }
        
        logger.info(f"Previous total holdings: ${total_holdings:.2f}")
        return holdings_data
        
    except pd.errors.ParserError as e:
        logger.error(f"CSV parsing error: {e}. Using default holdings.")
        return default_holdings
    except pd.errors.EmptyDataError as e:
        logger.error(f"CSV is empty: {e}. Using default holdings.")
        return default_holdings
    except Exception as e:
        logger.error(f"Unexpected error reading previous holdings: {e}. Using defaults.")
        return default_holdings


def get_24hr_market_data() -> Optional[str]:
    """Fetch market data for all trading symbols with retry logic."""
    current_time = int(time.time())
    start_time = current_time - (LOOKBACK_HOURS * 60 * 60)
    market_data = []
    failed_symbols = []
    
    logger.info(f"Fetching market data for {len(TRADING_SYMBOLS)} symbols")
    
    for symbol in TRADING_SYMBOLS:
        retry_count = 0
        success = False
        
        while retry_count < MAX_RETRIES and not success:
            try:
                logger.debug(f"Fetching data for {symbol} (attempt {retry_count + 1})")
                
                response = requests.get(
                    url=BACKPACK_API_URL,
                    params={
                        "symbol": symbol,
                        "interval": KLINE_INTERVAL,
                        "startTime": start_time,
                        "endTime": current_time,
                    },
                    timeout=REQUEST_TIMEOUT
                )
                
                response.raise_for_status()
                market_data.append({f"{symbol}_data": response.json()})
                logger.info(f"Successfully fetched data for {symbol}")
                success = True
                
            except ConnectionError as e:
                logger.warning(f"Connection error for {symbol}: {e}")
                retry_count += 1
            except Timeout as e:
                logger.warning(f"Timeout error for {symbol}: {e}")
                retry_count += 1
            except requests.HTTPError as e:
                logger.error(f"HTTP error for {symbol} (status {response.status_code}): {e}")
                failed_symbols.append(symbol)
                break
            except ValueError as e:
                logger.error(f"Invalid JSON response for {symbol}: {e}")
                failed_symbols.append(symbol)
                break
            except RequestException as e:
                logger.error(f"Request exception for {symbol}: {e}")
                retry_count += 1
            
            if not success and retry_count < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        
        if not success:
            failed_symbols.append(symbol)
            logger.warning(f"Failed to fetch data for {symbol} after {MAX_RETRIES} retries")
    
    if not market_data:
        logger.error("Failed to fetch data for all symbols")
        return None
    
    if failed_symbols:
        logger.warning(f"Failed to fetch data for symbols: {', '.join(failed_symbols)}")
    
    return str(market_data)


# ============================================================================
# AI ANALYSIS FUNCTIONS
# ============================================================================

def analyze_with_ai_models(
    market_data: str,
    holdings_data: Dict[str, Any],
    timeout: int = API_TIMEOUT
) -> Optional[str]:
    """Analyze market data using OpenRouter API."""
    if not market_data:
        logger.error("Market data is empty, cannot analyze")
        return None
    
    if not holdings_data:
        logger.error("Holdings data is missing, cannot analyze")
        return None
    
    try:
        logger.info("Loading API credentials...")
        api_key = load_file_content(API_KEY_PATH)
        
        if not api_key:
            logger.error("API key is empty")
            return None
        
        system_prompt = load_file_content(SYSTEM_PROMPT_PATH)
        
        if not system_prompt:
            logger.error("System prompt is empty")
            return None
        
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt += f"\nTime now: {current_time}"
        
    except FileNotFoundError as e:
        logger.error(f"Required file not found: {e}")
        return None
    except IOError as e:
        logger.error(f"Error reading credentials: {e}")
        return None
    
    try:
        holdings_context = f"""
PREVIOUS TRADING ACCOUNT STATE:
- Total Available Holdings: ${holdings_data.get('total_holdings', 0):.2f}
- BTC Holdings: {holdings_data.get('BTC', 0):.8f}
- ETH Holdings: {holdings_data.get('ETH', 0):.8f}
- SOL Holdings: {holdings_data.get('SOL', 0):.4f}
- USDC Holdings: {holdings_data.get('USDC', 0):.2f}

MARKET DATA FOR ANALYSIS:
{market_data}
"""
    except Exception as e:
        logger.error(f"Error building holdings context: {e}")
        return None
    
    try:
        logger.info("Initializing OpenRouter API client...")
        
        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            timeout=timeout
        )
        
        logger.info("Sending analysis request to AI model...")
        
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": holdings_context
                }
            ]
        )
        
        if not response.choices or not response.choices[0].message.content:
            logger.error("Empty response from AI model")
            return None
        
        analysis = response.choices[0].message.content
        logger.info("AI analysis completed successfully")
        return analysis
        
    except APIConnectionError as e:
        logger.error(f"API connection error: {e}")
        return None
    except APITimeoutError as e:
        logger.error(f"API timeout error: {e}")
        return None
    except APIError as e:
        logger.error(f"API error (status {e.status_code}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during AI analysis: {e}")
        return None


# ============================================================================
# DATA PERSISTENCE FUNCTIONS
# ============================================================================

def save_analysis_to_csv(analysis: str, filename: str = OUTPUT_FILE) -> bool:
    """Save analysis results to CSV file with error handling."""
    if not analysis:
        logger.error("Analysis text is empty, cannot save")
        return False
    
    if not filename:
        logger.error("Output filename not provided")
        return False
    
    try:
        output_dir = os.path.dirname(filename)
        if output_dir and not os.path.exists(output_dir):
            logger.info(f"Creating output directory: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
        
        df = pd.DataFrame([{"analysis": analysis, "timestamp": datetime.now()}])
        
        logger.info(f"Saving analysis to {filename}")
        df.to_csv(filename, mode='a', header=not os.path.exists(filename), index=False)
        
        logger.info("Analysis saved successfully")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied writing to {filename}: {e}")
        return False
    except pd.errors.DatabaseError as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving analysis to CSV: {e}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main() -> None:
    """Main execution function with comprehensive error handling."""
    
    logger.info("Starting AI Trading Bot...")
    logger.info(f"Configuration: Symbols={TRADING_SYMBOLS}, Interval={KLINE_INTERVAL}, Lookback={LOOKBACK_HOURS}h")
    
    try:
        logger.info("Step 1: Retrieving previous holdings...")
        holdings_data = get_previous_total_holdings()
        if not holdings_data:
            logger.error("Failed to retrieve holdings data")
            return
        
        logger.info("Step 2: Fetching 24-hour market data...")
        market_data = get_24hr_market_data()
        if not market_data:
            logger.error("Failed to fetch market data")
            return
        
        logger.info("Step 3: Analyzing with AI model...")
        analysis = analyze_with_ai_models(market_data, holdings_data)
        if not analysis:
            logger.error("Failed to get AI analysis")
            return
        
        logger.info("Step 4: Saving results to CSV...")
        success = save_analysis_to_csv(analysis)
        if not success:
            logger.error("Failed to save analysis to CSV")
            return
        
        logger.info("Trade executed and logged successfully")
        
    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
    except RequestException as e:
        logger.error(f"Network error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)


if __name__ == "__main__":
    main()
