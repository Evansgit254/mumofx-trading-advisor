import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

def train_model():
    print("🧠 Training Winning Probability Model...")
    
    if not os.path.exists("training/historical_data.csv"):
        print("❌ Error: No training data found. Run data_collector.py first.")
        return

    df = pd.read_csv("training/historical_data.csv")
    
    if len(df) < 50:
        print(f"⚠️ Warning: Dataset too small ({len(df)} samples). Model may be unreliable.")

    # Features: RSI, Body Ratio, Normalized ATR, Displaced (Binary), H1 Trend (1/-1)
    X = df[['rsi', 'body_ratio', 'atr_norm', 'displaced', 'h1_trend']]
    y = df['outcome']

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Model: Conservative Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_leaf=5,
        class_weight='balanced',
        ccp_alpha=0.01,
        random_state=42
    )
    
    model.fit(X_train, y_train)

    # Eval
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"✅ Model Trained! Accuracy: {acc:.2f}")
    print("\nReport:")
    print(classification_report(y_test, y_pred))

    # Save
    joblib.dump(model, "training/win_prob_model.joblib")
    print("📁 Model saved to training/win_prob_model.joblib")

if __name__ == "__main__":
    train_model()
