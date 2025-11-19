import time
import subprocess
import os
import sys

# Configuration
# I removed the trailing space from "AI-Trading ". 
# If your folder name actually ends with a space, change "AI-Trading" to "AI-Trading "
TARGET_SCRIPT = os.path.join("AI-Trading", "backend", "main.py")

INTERVAL_MINUTES = 16
INTERVAL_SECONDS = INTERVAL_MINUTES * 60
TIMEOUT_SECONDS = 300  # 5 minutes max runtime per execution

def run_script():
    """Checks if file exists and runs it with a timeout safety."""
    
    if not os.path.exists(TARGET_SCRIPT):
        print(f"[Error] Could not find file: {TARGET_SCRIPT}")
        print(f"Current Working Directory: {os.getcwd()}")
        return

    print(f"--- Starting {TARGET_SCRIPT} at {time.strftime('%H:%M:%S')} ---")
    
    try:
        # Timeout added to protect RAM
        subprocess.run(
            [sys.executable, TARGET_SCRIPT], 
            check=True, 
            timeout=TIMEOUT_SECONDS
        )
        print("--- Execution finished successfully ---")
        
    except subprocess.TimeoutExpired:
        print(f"[Error] Script timed out after {TIMEOUT_SECONDS}s! Killed to save RAM.")
    except subprocess.CalledProcessError as e:
        print(f"[Error] Script crashed with exit code {e.returncode}")
    except Exception as e:
        print(f"[Error] An unexpected error occurred: {e}")

def start_scheduler():
    print(f"Scheduler started for: {TARGET_SCRIPT}")
    print(f"Running every {INTERVAL_MINUTES} minutes.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            run_script()
            print(f"Waiting {INTERVAL_MINUTES} minutes...")
            time.sleep(INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")

if __name__ == "__main__":
    start_scheduler()