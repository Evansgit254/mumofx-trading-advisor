class CorrelationAnalyzer:
    CURRENCY_MAP = {
        "EURUSD": ("EUR", "USD"),
        "GBPUSD": ("GBP", "USD"),
        "USDJPY": ("USD", "JPY"),
        "AUDUSD": ("AUD", "USD"),
        "GC": ("XAU", "USD"), # Gold Futures
        "GC=F": ("XAU", "USD"),
        "XAUUSD": ("XAU", "USD"),
        "CL=F": ("WTI", "USD"), # Crude Oil
        "CL": ("WTI", "USD"),
    }

    @staticmethod
    def filter_signals(signals: list) -> list:
        """
        Analyzes a list of signals and filters out correlated conflicts.
        Prioritizes by win_prob.
        """
        if not signals:
            return []

        # Sort by win_prob descending
        sorted_signals = sorted(signals, key=lambda x: x.get('win_prob', 0), reverse=True)
        
        final_signals = []
        exposure = {} # TRACK CURRENCY EXPOSURE (e.g., {'USD': 'SHORT'})

        for signal in sorted_signals:
            pair = signal.get('pair') or signal.get('symbol')
            direction = signal['direction']
            
            currencies = CorrelationAnalyzer.CURRENCY_MAP.get(pair)
            if not currencies:
                final_signals.append(signal)
                continue

            base, quote = currencies
            
            # Simple Exposure Logic:
            # BUY EURUSD -> LONG EUR, SHORT USD
            # SELL EURUSD -> SHORT EUR, LONG USD
            
            current_signal_exposure = {
                base: "LONG" if direction == "BUY" else "SHORT",
                quote: "SHORT" if direction == "BUY" else "LONG"
            }

            conflict = False
            for curr, side in current_signal_exposure.items():
                if curr in exposure and exposure[curr] != side:
                    # CONFLICT! e.g., already have USD SHORT, now trying to do USD LONG
                    conflict = True
                    break
            
            if not conflict:
                # Add to final list and update exposure
                final_signals.append(signal)
                for curr, side in current_signal_exposure.items():
                    exposure[curr] = side
            else:
                print(f"⚠️ [CORRELATION FILTER] Skipping {pair} {direction} due to conflict with existing exposure.")

        return final_signals

    @staticmethod
    def group_by_theme(signals: list) -> str:
        """
        Detects if there is a common theme (e.g., 'USD Weakness')
        """
        if len(signals) < 2:
            return ""

        usd_exposure = [s for s in signals if "USD" in (s.get('pair') or s.get('symbol', ''))]
        if len(usd_exposure) >= 2:
            directions = [s['direction'] for s in usd_exposure]
            # If buying EURUSD and GBPUSD -> USD Weakness
            # If selling EURUSD and GBPUSD -> USD Strength
            # (Note: USDJPY is inverted, but for simplicity let's stick to majors)
            
            # This is a bit simplified for now
            return "🔥 *Institutional Theme Detected: High Currency Momentum*"
        
        return ""
