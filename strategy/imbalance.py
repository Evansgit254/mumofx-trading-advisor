import pandas as pd

class ImbalanceDetector:
    @staticmethod
    def detect_fvg(df: pd.DataFrame) -> list:
        """
        Detects Fair Value Gaps (FVG) / Imbalances in the last 5 bars.
        An FVG occurs when there is a gap between the low of candle 1 
        and the high of candle 3 in a 3-candle sequence.
        """
        if len(df) < 3:
            return []

        fvgs = []
        # Check the last 10 bars for imbalances
        for i in range(len(df) - 3, len(df) - 13, -1):
            if i < 0: break
            
            c1 = df.iloc[i]     # First candle
            c2 = df.iloc[i+1]   # The 'impulse' candle
            c3 = df.iloc[i+2]   # Third candle
            
            # Bullish FVG: Low of candle 3 > High of candle 1
            if c3['low'] > c1['high']:
                fvgs.append({
                    'type': 'BULLISH',
                    'top': c3['low'],
                    'bottom': c1['high'],
                    'index': i+1
                })
            
            # Bearish FVG: High of candle 3 < Low of candle 1
            elif c3['high'] < c1['low']:
                fvgs.append({
                    'type': 'BEARISH',
                    'top': c1['low'],
                    'bottom': c3['high'],
                    'index': i+1
                })
        
        return fvgs

    @staticmethod
    def is_price_in_fvg(price: float, fvgs: list, direction: str) -> bool:
        """
        Checks if the current price is within or has recently reacted to an FVG.
        For a Buy, we want to see price pulling back into a Bullish FVG.
        """
        if not fvgs:
            return False
            
        for fvg in fvgs:
            if direction == "BUY" and fvg['type'] == 'BULLISH':
                # Price is at or slightly above the FVG top (approaching or inside)
                if price <= fvg['top'] * 1.001 and price >= fvg['bottom'] * 0.999:
                    return True
            elif direction == "SELL" and fvg['type'] == 'BEARISH':
                if price >= fvg['bottom'] * 0.999 and price <= fvg['top'] * 1.001:
                    return True
        return False
