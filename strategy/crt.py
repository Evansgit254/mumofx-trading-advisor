import pandas as pd
from indicators.calculations import IndicatorCalculator

class CRTAnalyzer:
    @staticmethod
    def validate_setup(df: pd.DataFrame, direction: str) -> dict:
        """
        Validates if the current state aligns with Candle Range Theory (PO3).
        A setup is valid if it's in the DISTRIBUTION phase and aligns with the direction.
        """
        crt = IndicatorCalculator.detect_crt_phases(df)
        if not crt:
            return {"valid": False, "reason": "Insufficient data for CRT", "score_bonus": 0}
        
        phase = crt['phase']
        valid = False
        score_bonus = 0
        
        if direction == "BUY":
            if phase == "DISTRIBUTION_LONG":
                valid = True
                score_bonus = 1.0 # Significant institutional confirmation
            elif phase == "MANIPULATION":
                # Price is in manipulation phase, high risk but potential early entry
                # We usually wait for expansion
                score_bonus = 0.5
        elif direction == "SELL":
            if phase == "DISTRIBUTION_SHORT":
                valid = True
                score_bonus = 1.0
            elif phase == "MANIPULATION":
                score_bonus = 0.5
                
        return {
            "valid": valid,
            "phase": phase,
            "score_bonus": score_bonus,
            "range_high": crt['range_high'],
            "range_low": crt['range_low']
        }
