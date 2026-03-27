import pandas as pd
import os
from pathlib import Path
from sklearn.metrics import classification_report, accuracy_score
from sklearn.ensemble import RandomForestClassifier, VotingClassifier

ROOT_DIR = Path(__file__).parents[1]
DATA_PROCESSED_DIR = os.path.join(ROOT_DIR, 'data', 'processed')
MODELS_DIR = os.path.join(ROOT_DIR, 'models')
def main():
    train_path = os.path.join(DATA_PROCESSED_DIR, 'train.csv')
    test_path = os.path.join(DATA_PROCESSED_DIR, 'test.csv')
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    X_train = train_df.drop(columns=['label'])
    y_train = train_df['label']
    
    X_test = test_df.drop(columns=['label'])
    y_test = test_df['label']

    rf_clf = RandomForestClassifier(5000, n_jobs=-1, max_depth=15)

if __name__ == "__main__":
    main()