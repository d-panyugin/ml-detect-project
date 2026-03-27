import time
import subprocess
import os

# --- ИМЕНА КОНТЕЙНЕРОВ ---
TARGET_CONTAINER = "vpn_target"
CLIENT_CONTAINER = "vpn_client"
SNIFFER_CONTAINER = "vpn_sniffer"
TARGET_IP = "10.5.0.5"

# --- НАСТРОЙКИ ---
NORMAL_FILE_SIZE_MB = 50
NORMAL_DOWNLOADS = 5
VPN_DATA_MB = 100

def run_cmd(container, cmd):
    """Выполняет команду внутри контейнера"""
    full_cmd = f"docker exec {container} {cmd}"
    print(f"Executing: {full_cmd}")
    result = subprocess.run(full_cmd, shell=True, check=False)
    if result.returncode != 0:
        if "pkill" not in cmd:
            print(f"Warning: Command returned code {result.returncode}")

def run_bg_cmd(container, cmd):
    """
    Запускает команду в ФОНЕ внутри контейнера.
    Критически важный момент: используем 'docker exec -d',
    чтобы процесс не умер после завершения команды.
    """
    full_cmd = f"docker exec -d {container} {cmd}"
    print(f"Executing BG: {full_cmd}")
    subprocess.run(full_cmd, shell=True, check=True)

def start_capture(filename):
    """Запускает tcpdump"""
    container_path = f"/data/raw/{filename}"
    # tcpdump тоже лучше запускать через -d, но & работает, так как это долгий процесс
    cmd = f"tcpdump -i any -w {container_path} &"
    run_cmd(SNIFFER_CONTAINER, cmd)
    time.sleep(2) 

def stop_capture():
    """Убивает tcpdump"""
    cmd = "pkill tcpdump"
    run_cmd(SNIFFER_CONTAINER, cmd)
    time.sleep(2)

def generate_normal_traffic():
    print(f"\n[+] Generating NORMAL traffic (HTTP). Total: ~{NORMAL_FILE_SIZE_MB * NORMAL_DOWNLOADS}MB")
    
    print(f"[Server] Creating {NORMAL_FILE_SIZE_MB}MB file...")
    run_cmd(TARGET_CONTAINER, f"dd if=/dev/zero of=/var/www/html/bigfile.bin bs=1M count={NORMAL_FILE_SIZE_MB}")
    
    print(f"[Client] Downloading file {NORMAL_DOWNLOADS} times...")
    for i in range(NORMAL_DOWNLOADS):
        time.sleep(0.2)
        run_cmd(CLIENT_CONTAINER, f"curl http://{TARGET_IP}/bigfile.bin -o /dev/null")
        
    print("[Client] Small requests...")
    for i in range(20):
        run_cmd(CLIENT_CONTAINER, f"curl http://{TARGET_IP}/index.html -o /dev/null")
        time.sleep(0.1)

def generate_fake_vpn_traffic():
    print(f"\n[+] Generating FAKE VPN traffic (High Entropy /dev/urandom). Total: {VPN_DATA_MB}MB")
    
    # 1. Подготовка скрипта-сервера
    # Мы пишем скрипт в файл, чтобы избежать проблем с кавычками и фоном
    server_script_content = """
import socket
import sys

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Позволяет быстро переиспользовать порт
    s.bind(("0.0.0.0", 9999))
    s.listen(1)
    print("SERVER_STARTED", file=sys.stderr, flush=True)
    
    conn, addr = s.accept()
    # Открываем /dev/null и просто пишем туда все, что приходит
    with open('/dev/null', 'wb') as dev_null:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            dev_null.write(data)
    conn.close()
    s.close()
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr, flush=True)
"""

    # 2. Записываем скрипт в контейнер
    print("[Server] Creating server script...")
    # echo с многострочной строкой может быть капризным, используем cat
    # Экранируем кавычки для shell
    safe_script = server_script_content.replace('"', '\\"')
    
    create_script_cmd = f"""
    cat << 'EOF' > /tmp/server.py
{server_script_content}
EOF
    """
    run_cmd(TARGET_CONTAINER, create_script_cmd)

    # 3. Убиваем старые процессы, если зависли
    run_cmd(TARGET_CONTAINER, "pkill -9 -f server.py || true")

    # 4. Запускаем сервер в фоне
    print("[Server] Starting Python listener via script file...")
    run_bg_cmd(TARGET_CONTAINER, "python3 /tmp/server.py")

    # 5. КРИТИЧЕСКИЙ ШАГ: Проверка, что порт открыт
    # Ждем 2 секунды
    time.sleep(2)
    print("[Server] Checking if port 9999 is listening...")
    
    # ss -ltn слушает tcp порты (-t), в режиме прослушивания (-l), числовой (-n)
    check_cmd = "ss -ltn | grep 9999"
    result = subprocess.run(f"docker exec {TARGET_CONTAINER} {check_cmd}", shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ FATAL ERROR: Port 9999 is NOT OPEN! Server script failed to start.")
        print("Trying to read error log from container...")
        run_cmd(TARGET_CONTAINER, "cat /tmp/server.log 2>/dev/null || echo 'No log found'")
        # Принудительно выходим, чтобы не тратить время на клиент, который все равно не соединится
        return 

    print("✅ Port 9999 is OPEN. Starting client transmission...")

    # 6. Запускаем клиента
    # Если сервер работает, nc должен соединиться
    cmd = f"dd if=/dev/urandom bs=1M count={VPN_DATA_MB} status=progress | nc {TARGET_IP} 9999"
    run_cmd(CLIENT_CONTAINER, cmd)
    
    print("[Server] Stopping server script...")
    run_cmd(TARGET_CONTAINER, "pkill -f server.py")
if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    
    # --- ЦИКЛ 1 ---
    print("--- Starting Cycle 1: Normal Traffic ---")
    start_capture("synthetic_normal.pcap")
    generate_normal_traffic()
    print("[+] Waiting for buffers to flush...")
    time.sleep(5) 
    stop_capture()
    
    time.sleep(2)
    
    # --- ЦИКЛ 2 ---
    print("--- Starting Cycle 2: Fake VPN Traffic ---")
    start_capture("synthetic_vpn.pcap")
    generate_fake_vpn_traffic()
    print("[+] Waiting for buffers to flush...")
    time.sleep(5)
    stop_capture()
    
    print("\n[✓] Traffic generation complete.")
    print("    Next steps:")
    print("    python3 src/extract_features.py synthetic_normal.pcap 0")
    print("    python3 src/extract_features.py synthetic_vpn.pcap 1")
