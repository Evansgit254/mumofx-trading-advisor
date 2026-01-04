class ScoringEngine:
    @staticmethod
    def calculate_score(details: dict) -> float:
        """
        Scores a signal from 0 to 10.
        Expects: bias_strength, sweep_quality, displacement, pullback_depth, session, volatility
        """
        score = 0.0
        
        # 1. Bias alignment (Mandatory for setup, so we assume it exists if we reach here)
        score += 2.0
        
        # 2. Sweep quality (wick size, level importance)
        if details.get('sweep_type') in ['BEARISH_SWEEP', 'BULLISH_SWEEP']:
            score += 2.5
            
        # 3. Displacement strength
        if details.get('displaced'):
            score += 2.0
            
        # 4. Pullback depth & RSI
        if details.get('pullback'):
            score += 1.5
            
        # 5. Volatility (ATR expansion)
        if details.get('volatile'):
            score += 1.0
            
        # 6. Session quality
        if details.get('session') in ['London Open', 'London-NY Overlap']:
            score += 1.0
            
        return round(score, 1)
