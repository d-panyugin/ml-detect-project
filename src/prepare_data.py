import pandas as pd
import numpy as np
import os

# Пути
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR = os.path.join(ROOT_DIR, 'data', 'raw')
DATA_PROCESSED_DIR = os.path.join(ROOT_DIR, 'data', 'processed')

def main():
    # 1. Загрузка основного датасета
    # Убедись, что файл называется именно так, или поправь путь
    input_file = os.path.join(DATA_RAW_DIR, 'consolidated_traffic_data.csv')
    
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        print("Положи файл consolidated_traffic_data.csv в папку data/raw/")
        return

    print(f"📂 Загрузка {input_file}...")
    # Если файл огромный, может потребоваться время
    df = pd.read_csv(input_file)
    
    print(f"✅ Загружено строк: {len(df)}")
    print(f"📋 Колонки: {df.columns.tolist()}")

    # 2. Анализ целевой переменной
    if 'traffic_type' not in df.columns:
        print("❌ Колонка 'traffic_type' не найдена! Не можем определить VPN.")
        return

    print(f"\n🔍 Найденные типы трафика:")
    print(df['traffic_type'].value_counts())

    # 3. Создание бинарной метки (VPN vs Non-VPN)
    # Предполагаем, что если в названии есть 'VPN', это класс 1, иначе 0
    df['label'] = df['traffic_type'].apply(lambda x: 1 if str(x).upper().startswith('VPN') else 0)
    
    vpn_count = df['label'].sum()
    non_vpn_count = len(df) - vpn_count
    
    print(f"\n📊 Распределение классов:")
    print(f"   VPN (1): {vpn_count}")
    print(f"   NON-VPN (0): {non_vpn_count}")

    if vpn_count == 0:
        print("\n⚠️ ВНИМАНИЕ: VPN трафик не найден (label=0 для всех). Модель нечему учить!")
        print("Проверь исходный файл, должны быть строки типа 'VPN-VOIP' или 'VPN-VIDEO'.")
        return

    # 4. Очистка данных (Preprocessing)
    # Удаляем колонку с текстом, она больше не нужна
    df = df.drop(columns=['traffic_type'])
    
    # Заменяем Infinite на NaN, затем удаляем строки с NaN
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    
    print(f"🧹 После очистки (удаление NaN/Inf): {len(df)} строк")

    # 5. Разделение на Train и Test (80% на обучение)
    train_df = df.sample(frac=0.8, random_state=42)
    test_df = df.drop(train_df.index)

    print(f"📦 Train set: {len(train_df)} строк")
    print(f"📦 Test set: {len(test_df)} строк")

    # 6. Сохранение
    train_path = os.path.join(DATA_PROCESSED_DIR, 'train.csv')
    test_path = os.path.join(DATA_PROCESSED_DIR, 'test.csv')

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    print(f"\n✅ ГОТОВО! Файлы сохранены:")
    print(f"   {train_path}")
    print(f"   {test_path}")

if __name__ == "__main__":
    main()
