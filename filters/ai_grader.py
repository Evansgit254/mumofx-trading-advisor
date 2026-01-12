from ai.analyst import AIAnalyst
import asyncio
import json
import os

class AIGrader:
    def __init__(self):
        self.analyst = AIAnalyst()
        # V13.1: Allow disabling AI for fast benchmarking
        self.disabled = os.getenv('DISABLE_AI_GRADER', 'false').lower() == 'true'
        # V15.0: AI Response Caching (5-minute TTL)
        self.cache = {}

    async def get_score(self, setup_data: dict) -> float:
        """
        Grades a trading setup using AI behavior analysis.
        Returns a float between 0.0 and 10.0.
        
        V13.1: Uses CONTRARIAN logic - detects retail traps by identifying
        setups that appear "too obvious" to retail traders.
        """
        # Fast path: bypass AI for benchmarking
        if self.disabled or not self.analyst.client:
            return 7.0 # Default base score if AI is disabled

        # V15.0: Cache Lookup (Primacy: Symbol + Direction + Regime)
        cache_key = f"{setup_data.get('symbol')}_{setup_data.get('direction')}_{setup_data.get('regime')}"
        now = asyncio.get_event_loop().time()
        
        if cache_key in self.cache:
            entry_time, entry_score = self.cache[cache_key]
            if now - entry_time < 300: # 5 Minute Cache
                return entry_score

        prompt = f"""
        You are an INSTITUTIONAL Market Maker analyzing a retail trader's setup.
        Your job is to determine if this is a HIGH-PROBABILITY institutional play or a RETAIL TRAP.
        
        SETUP DETAILS:
        - Symbol: {setup_data.get('symbol')}
        - Strategy: {setup_data.get('strategy_id')}
        - Direction: {setup_data.get('direction')}
        - Market Regime: {setup_data.get('regime')}
        - RSI: {setup_data.get('rsi')}
        - ADR Status: {setup_data.get('adr_status')}
        - Macro Alignment: {setup_data.get('macro_bias')}
        - Value Area: {setup_data.get('va_status')}
        
        CRITICAL SMC ANALYSIS (Score HIGHER if these are TRUE):
        
        1. INDUCEMENT DETECTION:
           - Is this setup "too textbook"? (If yes, score LOWER - it's a trap)
           - Would retail traders see this as an "obvious" entry? (If yes, score LOWER)
           - Is this likely STOP HUNT bait for institutional liquidity grab? (If yes, score LOWER)
        
        2. HIDDEN SMART MONEY:
           - Is there DISPLACEMENT (rapid candle expansion) suggesting institutional interest?
           - Is the setup AGAINST the obvious retail narrative?
           - Is this entry at a "weird" level that only institutions would see?
        
        3. RISK/REWARD ASYMMETRY:
           - Is the stop loss BELOW recent retail stops (for buys) or ABOVE (for sells)?
           - Would breaking this level TRIGGER cascading retail liquidations?
        
        SCORING LOGIC (V13.1 CONTRARIAN):
        - 9.0-10.0: Clear institutional footprint, AGAINST retail narrative, hidden order flow
        - 7.0-8.9: Moderate institutional confluence, some retail visibility
        - 5.0-6.9: Neutral setup, could go either way
        - 3.0-4.9: Retail-obvious setup, likely inducement/trap
        - 0.0-2.9: Clear retail trap, institutional counter-move expected
        
        Return ONLY valid JSON:
        {{
            "score": float (0.0 to 10.0),
            "trap_risk": "HIGH" | "MEDIUM" | "LOW",
            "reason": "One sentence explaining institutional intent"
        }}
        """
        
        try:
            response = self.analyst.client.models.generate_content(
                model=self.analyst.model_id,
                contents=prompt
            )
            raw_text = response.text.strip()
            
            # Clean JSON formatting
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(raw_text)
            score = float(result.get("score", 5.0))
            
            # V13.1: Log trap risk for audit
            # trap_risk = result.get("trap_risk", "UNKNOWN")
            # print(f"🤖 AI [{setup_data.get('symbol')}]: {score} | Trap Risk: {trap_risk} | {result.get('reason')}")
            
            # V15.0: Update Cache
            self.cache[cache_key] = (now, score)
            
            return score
        except Exception as e:
            # print(f"⚠️ AI Grader Failed: {e}")
            return 6.5 # Conservative fallback
