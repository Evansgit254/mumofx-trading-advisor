import json
import os
import pandas as pd
from typing import Dict

class PerformanceAnalyzer:
    def __init__(self, journal_path: str = "audit/journal_v8.csv"):
        self.journal_path = journal_path
        self.weights_path = "audit/strategy_weights.json"

    def calculate_weights(self) -> Dict[str, float]:
        """
        Analyzes the journal and returns a dictionary of strategy weights.
        """
        if not os.path.exists(self.journal_path):
            return {"smc_institutional": 1.0, "breakout_master": 1.0, "price_action_specialist": 1.0}

        try:
            df = pd.read_csv(self.journal_path)
            if 'strategy_id' not in df.columns:
                return {"smc_institutional": 1.0, "breakout_master": 1.0, "price_action_specialist": 1.0}

            # Calculate win rate per strategy
            stats = df.groupby('strategy_id')['res'].apply(lambda x: (x == 'WIN').sum() / len(x))
            
            weights = {}
            for strategy_id, win_rate in stats.items():
                # Dynamic multiplier: 
                # > 35% WR: Boost (up to 1.5)
                # 25-35% WR: Neutral (1.0)
                # < 25% WR: Penalize (drop to 0.7)
                if win_rate > 0.35:
                    multiplier = 1.0 + (win_rate * 0.5)
                elif win_rate < 0.25:
                    multiplier = 0.7
                else:
                    multiplier = 1.0
                weights[strategy_id] = round(multiplier, 2)
            
            # Ensure defaults for new strategies
            for sid in ["smc_institutional", "breakout_master", "price_action_specialist"]:
                if sid not in weights:
                    weights[sid] = 1.0
                    
            with open(self.weights_path, 'w') as f:
                json.dump(weights, f)
                
            return weights
        except Exception as e:
            print(f"Error calculating weights: {e}")
            return {"smc_institutional": 1.0, "breakout_master": 1.0, "price_action_specialist": 1.0}

    @staticmethod
    def get_strategy_multiplier(strategy_id: str) -> float:
        weights_path = "audit/strategy_weights.json"
        if os.path.exists(weights_path):
            with open(weights_path, 'r') as f:
                weights = json.load(f)
                return weights.get(strategy_id, 1.0)
        return 1.0
