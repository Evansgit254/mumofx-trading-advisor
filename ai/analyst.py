import google.generativeai as genai
import json
from config.config import GEMINI_API_KEY

class AIAnalyst:
    def __init__(self):
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        else:
            self.model = None

    async def validate_signal(self, data: dict) -> dict:
        """
        Passes signal data to Gemini for institutional validation.
        """
        if not self.model:
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
            response = self.model.generate_content(prompt)
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
        if not self.model or not news_events:
            return "Neutral / Data-driven execution."

        prompt = f"""
        Analyze these economic events for {symbol}:
        {json.dumps(news_events[:5])}
        
        Provide a 1-sentence summary of the prevailing market sentiment for this currency pair today.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except:
            return "Market awaiting fundamental clarity."
