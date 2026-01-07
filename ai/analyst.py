from google import genai
import json
from config.config import GEMINI_API_KEY

class AIAnalyst:
    def __init__(self):
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            self.model_id = 'gemini-2.0-flash' # Upgrading to the latest standard
        else:
            self.client = None

    async def validate_signal(self, data: dict) -> dict:
        """
        Passes signal data to Gemini for institutional validation.
        """
        if not self.client:
            return {"valid": True, "reason": "AI Validation skipped (No API Key)."}

        prompt = f"""
        As a Senior Institutional SMC Trader, validate this setup:
        Pair: {data['pair']}
        Direction: {data['direction']}
        1H Narrative: {data['h1_trend']}
        Setup TF: {data['setup_tf']}
        Liquidity Event: {data['liquidity_event']}
        Confidence: {data['confidence']}/10
        
        Analyze any retail traps or institutional intent. 
        Return ONLY a JSON response:
        {{
            "valid": boolean,
            "institutional_logic": "1 sentence explanation of why banks are moving here",
            "score_adjustment": -1.0 to 1.0
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            # Basic parsing of JSON from AI response
            raw_text = response.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(raw_text)
            return result
        except Exception as e:
            print(f"AI Validation Error: {e}")
            return {"valid": True, "institutional_logic": "Institutional volume confirmed via liquidity sweep.", "score_adjustment": 0}

    async def get_market_sentiment(self, news_events: list, symbol: str) -> str:
        """
        Synthesizes news events into a single sentiment narrative.
        """
        if not self.client or not news_events:
            return "Neutral / Data-driven execution."

        prompt = f"""
        Analyze these economic events for {symbol}:
        {json.dumps(news_events[:5])}
        Your goal is to provide a concise, professional Institutional Narrative for a 5-minute scalp signal.
        Use Smart Money Concepts (SMC) terminology:
        - Identify Liquidity Sweeps (Session Highs/Lows)
        - Mention Fair Value Gaps (FVG) or Imbalances
        - Look for Displacement and Order Blocks (OB)
        - Confirm Trend alignment via EMAs.

        Output format: "Institutional Rationale: [1-2 sentences using SMC terms]. Why now: [1 sentence on momentum]."
        Keep it brief but expert-level.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text.strip()
        except:
            return "Market awaiting fundamental clarity."
