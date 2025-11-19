import time
import subprocess
import os
import sys

# Configuration
# Using os.path.join ensures this works on Windows, Mac, and Linux
TARGET_SCRIPT = os.path.join("Gemini 3.0 Test", "backend", "main.py")
INTERVAL_MINUTES = 16
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

def run_script():
    """Checks if file exists and runs it using the current Python interpreter."""
    
    if not os.path.exists(TARGET_SCRIPT):
        print(f"[Error] Could not find file: {TARGET_SCRIPT}")
        return

    print(f"--- Starting {TARGET_SCRIPT} at {time.strftime('%H:%M:%S')} ---")
    
    try:
        # sys.executable ensures we use the same python environment running this script
        subprocess.run([sys.executable, TARGET_SCRIPT], check=True)
        print("--- Execution finished successfully ---")
        
    except subprocess.CalledProcessError as e:
        print(f"[Error] Script crashed with exit code {e.returncode}")
    except Exception as e:
        print(f"[Error] An unexpected error occurred: {e}")

def start_scheduler():
    print(f"Scheduler started. Running every {INTERVAL_MINUTES} minutes.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            run_script()
            
            # Wait for the next interval
            print(f"Waiting {INTERVAL_MINUTES} minutes...")
            time.sleep(INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")

if __name__ == "__main__":
    start_scheduler()