class ScoringEngine:
    @staticmethod
    def calculate_score(details: dict) -> float:
        """
        Tuned Scoring Engine (v2.0)
        Increased strictness for Intraday setups.
        """
        score = 0.0
        
        # 1. Bias alignment (Narrative Alignment)
        if details.get('h1_aligned'):
            score += 3.0 # Increase weight for H1 Narrative
        else:
            score += 1.5
        
        # 2. Sweep quality (wick size, level importance)
        sweep_type = details.get('sweep_type', '')
        if 'M15' in sweep_type:
            score += 3.0 # M15 sweeps are higher probability
        elif 'M5' in sweep_type:
            score += 2.0
            
        # 3. Displacement strength
        if details.get('displaced'):
            score += 2.0
            
        # 4. Pullback depth & RSI Recovery
        if details.get('pullback'):
            score += 1.5
            
        # 5. Volatility (Quality expansion)
        if details.get('volatile'):
            score += 0.5
            
        return round(score, 1)
