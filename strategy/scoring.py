class ScoringEngine:
    @staticmethod
    def calculate_score(details: dict) -> float:
        """
        Tuned Scoring Engine (v2.0)
        Increased strictness for Intraday setups.
        """
        score = 0.0
        
        # 0. Global Macro Alignment
        if details.get('macro_aligned'):
            score += 1.5
        elif details.get('macro_aligned') == False:
            score -= 2.0 # Conflicting macro is a major penalty
            
        # 0.1 Phase 6: Daily Bias Alignment
        daily_bias = details.get('daily_bias', 'NEUTRAL')
        daily_strength = details.get('daily_strength', 'WEAK')
        direction = details.get('direction', '')
        
        if daily_strength == "STRONG":
            if daily_bias == direction:
                score += 2.0 # Major bonus for riding Daily Expansion
            elif daily_bias != "NEUTRAL":
                score -= 3.0 # Severe penalty for fighting Strong Daily Trend
        elif daily_bias == direction:
            score += 0.5 # Tie-breaker bonus

            
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
            # V12.0: Loosened penalty to allow for institutional footprints with low momentum.
            score -= 1.0
            
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
            # Mandatory H1 alignment for Gold (Loosened penalty for V12.0)
            if not details.get('h1_aligned'):
                score -= 2.5 
            
            # V8.1 Audit: Gold is prone to traps. Penalize if both are missing.
            if not details.get('displaced') and not details.get('has_fvg'):
                score -= 3.0 # Disqualify truly messy Gold setups
            elif not details.get('displaced') or not details.get('has_fvg'):
                score -= 1.0 # Minor penalty if missing one confluence
            
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
            
        # 9. V12.0: Institutional Value (POC proximity)
        # Research shows Volumetric confirmation is key.
        if details.get('at_value'):
            score += 1.5
            
        # 10. V12.0: BOS Confirmation Bonus
        if details.get('bos_confirmed'):
            score += 3.0 # High weight for sequential confirmation
            
        # 11. V6.0 Anti-Trap: Alpha Symbol Bonus
        symbol = details.get('symbol', '')
        if 'JPY' in symbol or 'IXIC' in symbol or 'GSPC' in symbol:
            score += 1.0
            
        # 12. V6.1 Liquid Shield: Hyper-Extension Safety
        h1_dist = details.get('h1_dist', 0)
        if abs(h1_dist) > 0.008: # > 0.8% from Mean
            score -= 2.0 # Penalty for "Overextended" moves
            
        # 13. Gold-DXY Inverse Correlation (V15.1)
        if details.get('dxy_bonus'):
            score += details['dxy_bonus']
        if details.get('dxy_penalty'):
            score += details['dxy_penalty']  # Already negative
            
        # 14. V6.2 Gold Specialist Bonus
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
