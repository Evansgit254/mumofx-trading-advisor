import joblib
import pandas as pd
import sklearn
import sys

print(f"Python version: {sys.version}")
print(f"Scikit-learn version: {sklearn.__version__}")
print(f"Joblib version: {joblib.__version__}")

try:
    print("Attempting to load model...")
    model = joblib.load("training/win_prob_model.joblib")
    print("Model loaded successfully!")
except Exception as e:
    print(f"Failed to load model: {e}")
    sys.exit(1)
