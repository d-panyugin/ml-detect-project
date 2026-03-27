import sys
import os
import numpy as np
import pandas as pd
from scapy.all import rdpcap, IP, TCP, UDP
from collections import defaultdict

# --- НАСТРОЙКА ПУТЕЙ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_RAW_DIR = os.path.join(ROOT_DIR, 'data', 'raw')
DATA_PROCESSED_DIR = os.path.join(ROOT_DIR, 'data', 'processed')

def calculate_entropy(payload_bytes):
    """Считает энтропию Шеннона для массива байтов"""
    if not payload_bytes:
        return 0.0
    # Считаем частоту каждого байта (0-255)
    counts = np.bincount(np.frombuffer(payload_bytes, dtype=np.uint8), minlength=256)
    probabilities = counts[counts > 0] / len(payload_bytes)
    return -np.sum(probabilities * np.log2(probabilities))

class Flow:
    def __init__(self, first_packet, reverse_key):
        # canonical_key: (min_ip, max_ip, min_port, max_port, proto)
        self.canonical_key = reverse_key 
        
        # Определяем направление инициатора
        self.initiator_ip = first_packet[IP].src
        
        self.timestamps = [float(first_packet.time)]
        self.sizes = [len(first_packet)]
        self.payloads = [] # Храним пейлоады для энтропии (или считаем на лету)
        
        # Буфер для накопления байтов (чтобы не хранить гигабайты в памяти, считаем энтропию потоком или берем первые N пакетов)
        # Для простоты и экономии памяти: будем собирать первые 2KB payload'а каждого потока для оценки энтропии
        self.payload_sample = bytes(first_packet[IP].payload) if IP in first_packet and first_packet[IP].payload else b''

        self.up_bytes = 0
        self.down_bytes = 0
        self.up_pkts = 0
        self.down_pkts = 0
        
        self.update_direction(first_packet)

    def update_direction(self, packet):
        is_upstream = (packet[IP].src == self.initiator_ip)
        pkt_len = len(packet)
        
        if is_upstream:
            self.up_bytes += pkt_len
            self.up_pkts += 1
        else:
            self.down_bytes += pkt_len
            self.down_pkts += 1

    def add_packet(self, packet):
        self.timestamps.append(float(packet.time))
        self.sizes.append(len(packet))
        
        if IP in packet and packet[IP].payload:
            payload = bytes(packet[IP].payload)
            # Накапливаем только первые 20KB трафика для энтропии (этого достаточно для детекции шифрования)
            if len(self.payload_sample) < 20480: 
                self.payload_sample += payload
                
        self.update_direction(packet)

    def get_features(self):
        if len(self.timestamps) < 2:
            return None # Игнорируем потоки из 1 пакета

        sizes = np.array(self.sizes)
        timestamps = np.array(self.timestamps)
        
        durations = timestamps[-1] - timestamps[0]
        intervals = np.diff(timestamps)
        
        # Статистика
        features = {
            'duration': durations,
            'pkt_count': len(sizes),
            'size_mean': np.mean(sizes),
            'size_std': np.std(sizes),
            'size_max': np.max(sizes),
            'size_min': np.min(sizes),
            'time_mean': np.mean(intervals),
            'time_std': np.std(intervals),
            'flow_bytes': self.up_bytes + self.down_bytes,
            'ratio_up_down': self.up_bytes / (self.down_bytes + 1e-9),
            'entropy': calculate_entropy(self.payload_sample) # Считаем энтропию от накопленного сэмпла
        }
        return features

def get_flow_key(packet):
    if IP not in packet: return None
    proto = 'tcp' if TCP in packet else ('udp' if UDP in packet else 'other')
    if proto == 'other': return None
    
    # Нормализация ключа: (ip1, ip2, port1, port2, proto), где ip1 < ip2
    ip1, ip2 = packet[IP].src, packet[IP].dst
    if TCP in packet:
        p1, p2 = packet[TCP].sport, packet[TCP].dport
    else:
        p1, p2 = packet[UDP].sport, packet[UDP].dport
        
    if (ip1 > ip2) or (ip1 == ip2 and p1 > p2):
        ip1, ip2 = ip2, ip1
        p1, p2 = p2, p1
        
    return (ip1, ip2, p1, p2, proto)

def process_pcap(pcap_filename, label):
    full_path = os.path.join(DATA_RAW_DIR, pcap_filename)
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        return pd.DataFrame()

    print(f"Processing {pcap_filename}...")
    packets = rdpcap(full_path)
    
    flows = {}
    
    for pkt in packets:
        key = get_flow_key(pkt)
        if not key: continue
        
        if key not in flows:
            flows[key] = Flow(pkt, key)
        else:
            flows[key].add_packet(pkt)
            
    data_rows = []
    for key, flow in flows.items():
        feat = flow.get_features()
        if feat:
            feat['label'] = label
            feat['src_ip'] = flow.initiator_ip # Для отладки
            data_rows.append(feat)
            
    df = pd.DataFrame(data_rows)
    
    # Сохраняем
    output_name = os.path.splitext(pcap_filename)[0] + '.csv'
    output_path = os.path.join(DATA_PROCESSED_DIR, output_name)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} flows to {output_path}")
    return df

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_features.py <pcap_name> <label_0_or_1>")
        sys.exit(1)
        
    df = process_pcap(sys.argv[1], int(sys.argv[2]))
    print(df.head())