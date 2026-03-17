import subprocess
import time
import sys
import os
import signal
import requests
import socket
import threading

# Configuration
BACKEND_DIR = "backend"
FRONTEND_DIR = "frontend"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# Path to virtual environment uvicorn
VENV_UVICORN = os.path.join(os.getcwd(), BACKEND_DIR, "venv", "bin", "uvicorn")

# Ensure log directories exist
os.makedirs(f"{BACKEND_DIR}/logs", exist_ok=True)
os.makedirs(f"{FRONTEND_DIR}/logs", exist_ok=True)

processes = []

def log_reader(pipe, log_file_path):
    with open(log_file_path, "a") as f:
        for line in iter(pipe.readline, b''):
            if line:
                f.write(line.decode('utf-8'))
                f.flush()

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def check_backend_health():
    try:
        response = requests.get(f"http://localhost:{BACKEND_PORT}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def signal_handler(sig, frame):
    print("\n\033[93mShutting down processes...\033[0m")
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    print("\033[94m" + "="*40)
    print("   AI PERSONAL ASSISTANT - STARTER")
    print("="*40 + "\033[0m")

    # Check for venv uvicorn
    if not os.path.exists(VENV_UVICORN):
        print(f"\033[91m[!] Error: Virtual environment not found at {VENV_UVICORN}\033[0m")
        print("[!] Please run: cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
        sys.exit(1)

    # 1. Start Backend using venv uvicorn
    # PRODUCTION TUNING: Use multiple workers and disable reload if in production
    is_prod = os.getenv("ENV") == "production"
    workers = ["--workers", "4"] if is_prod else []
    reload = ["--reload"] if not is_prod else []
    
    print(f"[*] Starting Backend on port {BACKEND_PORT} (Prod: {is_prod})...")
    backend_proc = subprocess.Popen(
        [VENV_UVICORN, "app.main:app", "--port", str(BACKEND_PORT)] + workers + reload,
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    processes.append(backend_proc)
    
    # 2. Start Frontend
    print(f"[*] Starting Frontend on port {FRONTEND_PORT}...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    processes.append(frontend_proc)

    # 3. Start Log Capture Threads
    threading.Thread(target=log_reader, args=(backend_proc.stdout, f"{BACKEND_DIR}/logs/app.log"), daemon=True).start()
    threading.Thread(target=log_reader, args=(frontend_proc.stdout, f"{FRONTEND_DIR}/logs/frontend.log"), daemon=True).start()

    print("\n\033[92mSystem is warming up. Please wait...\033[0m")
    time.sleep(5)

    try:
        while True:
            os.system('clear')
            print("\033[94m" + "="*40)
            print("   ASSISTANT MONITORING DASHBOARD")
            print("="*40 + "\033[0m")
            
            b_status = "\033[92mONLINE\033[0m" if check_backend_health() else "\033[91mSTARTING/ERROR\033[0m"
            print(f"Backend (:{BACKEND_PORT}): {b_status}")
            
            f_status = "\033[92mONLINE\033[0m" if is_port_open(FRONTEND_PORT) else "\033[91mSTARTING/ERROR\033[0m"
            print(f"Frontend (:{FRONTEND_PORT}): {f_status}")
            
            print("\n\033[90mLogs are being saved to:\033[0m")
            print(f" - {BACKEND_DIR}/logs/app.log")
            print(f" - {FRONTEND_DIR}/logs/frontend.log")
            
            print("\n\033[93mPress Ctrl+C to stop all services.\033[0m")
            time.sleep(10)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
