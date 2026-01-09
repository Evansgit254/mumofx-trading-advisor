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
        else:
            # V8.1 AUDIT: 90% of losses had no displacement. Stricter momentum gate.
            score -= 2.0
            
        # 3.1. 4H Level Confluence (Institutional Sweep)
        if details.get('h4_sweep'):
            score += 2.5 # High probability institutional alignment
            
        # 4. Pullback depth & RSI Recovery
        if details.get('pullback'):
            score += 1.5
            
        # 5. V7.0 Quantum: FVG Confluence Bonus
        if details.get('has_fvg'):
            score += 2.0 # High value institutional footprint
            
        # 5.1 Candle Range Theory (CRT) Bonus
        crt_bonus = details.get('crt_bonus', 0)
        score += crt_bonus
        
        # V8.1 Institutional Opposition Penalty
        crt_phase = details.get('crt_phase', '')
        direction = details.get('direction', '')
        if direction == "BUY" and "SHORT" in crt_phase:
            score -= 2.5
        elif direction == "SELL" and "LONG" in crt_phase:
            score -= 2.5
            
        # 5. Volatility (Quality expansion)
        if details.get('volatile'):
            score += 0.5
            
        # 0. Gold Specialist Protection 🥇
        symbol = details.get('symbol', '')
        if symbol == "GC=F":
            # Mandatory H1 alignment for Gold
            if not details.get('h1_aligned'):
                score -= 5.0 
            
            # V8.1 Audit: Gold is prone to traps. Penalize if both are missing.
            if not details.get('displaced') and not details.get('has_fvg'):
                score -= 4.0 # Disqualify truly messy Gold setups
            elif not details.get('displaced') or not details.get('has_fvg'):
                score -= 1.5 # Minor penalty if missing one confluence
            
            # Stricter Asian Range for Gold (20 pips instead of 15)
            if details.get('asian_sweep') and not details.get('asian_quality'):
                score -= 3.0 
            
        # 6. V4.0 Ultra-Quant: Asian Sweep (Neutralized for V6)
        # Forensic Audit: Asian Sweeps are currently high-risk traps.
        if details.get('asian_sweep') and details.get('asian_quality'):
            score += 1.0 # Only reward high-quality sweeps
        elif details.get('asian_sweep') and not details.get('asian_quality'):
            score -= 1.5 # PENALTY for Low-Range Traps
            
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
            
        # 10. V6.0 Anti-Trap: Alpha Symbol Bonus
        symbol = details.get('symbol', '')
        if 'JPY' in symbol or 'IXIC' in symbol or 'GSPC' in symbol:
            score += 1.0
            
        # 11. V6.0 Anti-Trap: EMA Velocity (Slope) Filter
        # Penalize if trend slope is too steep against the reversal
        slope = details.get('ema_slope', 0)
        direction = details.get('direction', '')
        if (direction == "BUY" and slope < -0.05) or (direction == "SELL" and slope > 0.05):
            score -= 2.0 # Penalty for "Falling Knife" setups
            
        # 12. V6.1 Liquid Shield: Hyper-Extension Safety
        h1_dist = details.get('h1_dist', 0)
        if abs(h1_dist) > 0.008: # > 0.8% from Mean
            score -= 2.0 # Penalty for "Overextended" moves
            
        # 13. V6.2 Gold Specialist Bonus
        if symbol == "GC=F" and score >= 9.0:
            score += 1.0 # Reward elite Gold setups
            
        return round(score, 1)

    @staticmethod
    def get_quality_seal(score: float) -> str:
        """
        Classifies the setup quality based on its quant score.
        """
        if score >= 9.0: return "PREMIER A+"
        if score >= 7.5: return "SOLID A"
        if score >= 6.0: return "STANDARD B"
        return "LOW ❌"
