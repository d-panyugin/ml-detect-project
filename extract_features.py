import sys
import numpy as np
import pandas as pd
from scapy.all import rdpcap, IP, TCP, UDP
from collections import defaultdict

# Функция для расчета энтропии Шеннона
def calculate_entropy(byte_counts, total_bytes):
    if total_bytes == 0:
        return 0.0
    entropy = 0.0
    for count in byte_counts:
        if count > 0:
            p = count / total_bytes
            entropy -= p * np.log2(p)
    return entropy

# Класс для хранения состояния одной сессии
class Flow:
    def __init__(self, packet):
        # Создаем "канонический" ключ потока (сортируем IP и порта, чтобы A->B и B->A были одним потоком)
        # Но нам нужно знать направление. Считаем инициатором того, кто отправил первый пакет.
        self.src_init = packet[IP].src
        self.dst_init = packet[IP].dst
        self.sport_init = packet[TCP].sport if TCP in packet else (packet[UDP].sport if UDP in packet else 0)
        self.dport_init = packet[TCP].dport if TCP in packet else (packet[UDP].dport if UDP in packet else 0)
        
        self.timestamps = [float(packet.time)]
        self.sizes = [len(packet)]
        
        # Для энтропии считаем частоту каждого байта (0-255)
        self.byte_counts = np.zeros(256, dtype=int)
        if packet[IP].payload:
            payload = bytes(packet[IP].payload)
            for b in payload:
                self.byte_counts[b] += 1
        
        # Счетчики upstream/downstream относительно инициатора
        self.up_bytes = len(packet)
        self.down_bytes = 0
        self.up_pkts = 1
        self.down_pkts = 0

    def update(self, packet):
        cur_len = len(packet)
        self.sizes.append(cur_len)
        self.timestamps.append(float(packet.time))

        if packet[IP].payload:
            payload = bytes(packet[IP].payload)
            for b in payload:
                self.byte_counts[b] += 1

        # Определяем направление
        is_upstream = (packet[IP].src == self.src_init and packet[IP].dst == self.dst_init and
                      (TCP in packet and packet[TCP].sport == self.sport_init) and 
                      (TCP in packet and packet[TCP].dport == self.dport_init))
        
        # Простой эвристический fallback для UDP (если порты совпали в обратку)
        if not is_upstream:
             is_upstream = (packet[IP].src == self.src_init)

        if is_upstream:
            self.up_bytes += cur_len
            self.up_pkts += 1
        else:
            self.down_bytes += cur_len
            self.down_pkts += 1

    def get_features(self):
        sizes = np.array(self.sizes)
        timestamps = np.array(self.timestamps)
        
        # Интервалы между пакетами
        if len(timestamps) > 1:
            intervals = np.diff(timestamps)
            time_mean = np.mean(intervals)
            time_std = np.std(intervals)
        else:
            time_mean = 0
            time_std = 0

        # Соотношение потоков
        ratio = self.up_bytes / (self.down_bytes + 1e-9) # +epsilon чтобы не делить на 0

        # Энтропия
        total_bytes = np.sum(self.byte_counts)
        entropy = calculate_entropy(self.byte_counts, total_bytes)

        return {
            'duration': timestamps[-1] - timestamps[0],
            'pkt_count': len(sizes),
            'size_mean': np.mean(sizes),
            'size_std': np.std(sizes),
            'size_max': np.max(sizes),
            'size_min': np.min(sizes),
            'time_mean': time_mean,
            'time_std': time_std,
            'ratio_up_down': ratio,
            'entropy': entropy
        }

def process_pcap(filename, label):
    print(f"Processing {filename}...")
    try:
        packets = rdpcap(filename)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return pd.DataFrame()

    flows = {}
    # Таймаут сессии в секундах (если пакетов нет 60 сек - считаем сессию закрытой)
    FLOW_TIMEOUT = 60.0 
    
    processed_count = 0

    for pkt in packets:
        if IP not in pkt:
            continue
        
        # Формируем ключ (сортированный, чтобы объединять встречные потоки)
        # Но для простоты примера используем 5-tuple без сортировки для разделения направлений
        # Чтобы это сработало правильно для bidirectional flow, нужна хитрая логика.
        # Упростим: Ключ = (src_ip, dst_ip, proto, src_port, dst_port)
        # Это создаст две записи для A->B и B->A. Для ML это ок, так как признаки симметричны.
        
        if TCP in pkt:
            flow_key = (pkt[IP].src, pkt[IP].dst, 'tcp', pkt[TCP].sport, pkt[TCP].dport)
        elif UDP in pkt:
            flow_key = (pkt[IP].src, pkt[IP].dst, 'udp', pkt[UDP].sport, pkt[UDP].dport)
        else:
            continue

        if flow_key not in flows:
            flows[flow_key] = Flow(pkt)
        else:
            # Проверка таймаута
            last_time = flows[flow_key].timestamps[-1]
            if float(pkt.time) - last_time > FLOW_TIMEOUT:
                # Сохраняем старый поток и создаем новый
                # (в реальном коде это надо сохранять в список результатов, здесь для простоты пропустим или реализуем список завершенных)
                # Для быстрого прототипа просто обновляем, игнорируя разрывы
                pass
            flows[flow_key].update(pkt)
        
        processed_count += 1
        if processed_count % 1000 == 0:
            print(f"Processed {processed_count} packets...")

    # Сбор данных
    data = []
    for key, flow in flows.items():
        features = flow.get_features()
        features['label'] = label
        # Добавим инфо о потоке для отладки
        features['src_ip'] = key[0]
        data.append(features)

    return pd.DataFrame(data)

# --- Точка входа ---
if __name__ == "__main__":
    # Хардкод для быстрого теста, потом переделаем на аргументы
    # Usage: python extract_features.py <pcap_file> <label>
    
    if len(sys.argv) < 3:
        print("Usage: python extract_features.py <file.pcap> <label:0/1>")
        sys.exit(1)

    pcap_file = sys.argv[1]
    label = int(sys.argv[2])
    
    df = process_pcap(pcap_file, label)
    
    output_csv = pcap_file.replace('.pcap', '.csv')
    df.to_csv(output_csv, index=False)
    print(f"Saved to {output_csv}")
    print(df.head())
