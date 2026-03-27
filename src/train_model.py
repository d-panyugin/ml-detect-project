import pandas as pd
import os
import joblib
from pathlib import Path

from sklearn.metrics import classification_report, accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier

ROOT_DIR = Path(__file__).parents[1]
DATA_PROCESSED_DIR = os.path.join(ROOT_DIR, 'data', 'processed')    
MODELS_DIR = os.path.join(ROOT_DIR, 'models')
def create_model():
    train_path = os.path.join(DATA_PROCESSED_DIR, 'train.csv')
    train_df = pd.read_csv(train_path)
    X_train = train_df.drop(columns=['label'])
    y_train = train_df['label']

    rf_clf = RandomForestClassifier(5000, n_jobs=-1, max_depth=15)
    lr_clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(random_state=42, max_iter=1000)
    )

    ensemble = VotingClassifier(
        estimators=[
            ('random_forest', rf_clf),
            ('logistic_regression', lr_clf)
        ],
        voting='soft'
    )

    ensemble.fit(X_train, y_train)

    model_filename = 'vpn_ensemble.pkl'
    model_path = os.path.join(MODELS_DIR, model_filename)
    joblib.dump(ensemble, model_path)
def rate_model():
    test_path = os.path.join(DATA_PROCESSED_DIR, 'test.csv')
    test_df = pd.read_csv(test_path)
    
    X_test = test_df.drop(columns=['label'])
    y_test = test_df['label']
    model_path = os.path.join(MODELS_DIR, 'vpn_ensemble.pkl')
    model = joblib.load(model_path)
    y_pred = model.predict(X_test)

    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    auc = roc_auc_score(y_test, y_pred)
    print(f"AUC-ROC: {auc:.4f}")



if __name__ == "__main__":
    rate_model()