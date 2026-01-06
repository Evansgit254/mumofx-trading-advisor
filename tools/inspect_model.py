import joblib
import pandas as pd
import os

def inspect_model():
    model_path = "training/win_prob_model.joblib"
    if not os.path.exists(model_path):
        print("❌ Model file not found.")
        return

    print(f"🧠 Loading Model: {model_path}")
    model = joblib.load(model_path)
    
    # Check if it has feature importances (RandomForest/GradientBoosting)
    if hasattr(model, "feature_importances_"):
        # Features from backtest: [rsi, body_ratio, atr_ratio, displaced, h1_trend]
        features = ["RSI (Momentum)", "Candle Body % (Conviction)", "Volatility (ATR)", "Displacement (Speed)", "H1 Trend"]
        
        importances = model.feature_importances_
        print("\n📊 What matters to the AI?")
        
        # Sort and print
        for f, imp in sorted(zip(features, importances), key=lambda x: x[1], reverse=True):
            print(f"- {f}: {imp*100:.1f}% impact")
    else:
        print("Model type does not support feature importance inspection.")

if __name__ == "__main__":
    inspect_model()
