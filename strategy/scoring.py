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
            
        # 6. V4.0 Ultra-Quant: Asian Sweep Bonus
        if details.get('asian_sweep'):
            score += 1.5
            
        # 7. V4.0 Ultra-Quant: ADR Exhaustion Penalty (Safety Switch)
        if details.get('adr_exhausted'):
            score -= 3.0
            
        # 8. V5.0 Hyper-Quant: Asian Range Quality
        if details.get('asian_sweep') and details.get('asian_quality'):
            score += 0.5
            
        # 9. V5.2 Hyper-Quant: institutional Value (POC proximity)
        # PENALTY: Consolidation Zone (POC) is high risk for reversals.
        if details.get('at_value'):
            score -= 3.0 
            
        return round(score, 1)
