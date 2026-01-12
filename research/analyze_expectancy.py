import pandas as pd
import numpy as np
import os

def analyze_expectancy(csv_path="research/audit_results_v8.csv"):
    if not os.path.exists(csv_path):
        print(f"❌ Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        print("❌ Error: CSV is empty.")
        return

    print(f"📊 Analyzing {len(df)} trades from {csv_path}...")
    
    thresholds = np.arange(5.0, 9.5, 0.5)
    results = []

    for t in thresholds:
        filtered = df[df['confidence'] >= t]
        if filtered.empty:
            continue
            
        total_r = filtered['r'].sum()
        win_rate = (len(filtered[filtered['res'] == 'WIN']) / len(filtered)) * 100
        count = len(filtered)
        expectancy = total_r / count if count > 0 else 0
        
        results.append({
            'Threshold': t,
            'Trades': count,
            'Win Rate': f"{win_rate:.1f}%",
            'Total R': f"{total_r:+.1f}R",
            'Expectancy': f"{expectancy:+.2f}R/trade"
        })

    report = pd.DataFrame(results)
    print("\n" + "="*60)
    print("📈 CONFIDENCE THRESHOLD SENSITIVITY ANALYSIS")
    print("="*60)
    print(report.to_string(index=False))
    print("="*60)

if __name__ == "__main__":
    analyze_expectancy()
