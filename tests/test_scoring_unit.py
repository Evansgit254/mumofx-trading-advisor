import pytest
from strategy.scoring import ScoringEngine

def test_calculate_score_base():
    # Test base score with minimal features
    details = {
        'h1_aligned': False,
        'sweep_type': '',
        'symbol': 'EURUSD=X',
        'direction': 'BUY'
    }
    # Base: 1.5 (h1_aligned False)
    # V8.1 Penalty: -2.0 (No displacement)
    # Total: -0.5
    assert ScoringEngine.calculate_score(details) == -0.5

def test_calculate_score_h1_aligned():
    details = {'h1_aligned': True, 'symbol': 'EURUSD=X'}
    # Base: 3.0 (True)
    # V8.1 Penalty: -2.0 (No displacement)
    # Total: 1.0
    assert ScoringEngine.calculate_score(details) == 1.0

def test_calculate_score_sweeps():
    # M15 Sweep
    # 1.5 (h1 False) + 3.0 (Sweep) - 2.0 (No displacement) = 2.5
    assert ScoringEngine.calculate_score({'sweep_type': 'M15_SWEEP'}) == 2.5
    # M5 Sweep
    # 1.5 + 2.0 - 2.0 = 1.5
    assert ScoringEngine.calculate_score({'sweep_type': 'M5_SWEEP'}) == 1.5

def test_calculate_score_confluences():
    details = {
        'h1_aligned': True,
        'displaced': True,
        'pullback': True,
        'volatile': True,
        'has_fvg': True
    }
    # 3.0 (H1) + 2.0 (Displaced) + 1.5 (Pullback) + 0.5 (Volatile) + 2.0 (FVG) = 9.0
    assert ScoringEngine.calculate_score(details) == 9.0

def test_calculate_score_gold_protections():
    # Gold: No H1 alignment -> -5.0
    details = {'symbol': 'GC=F', 'h1_aligned': False}
    # 1.5 (base) - 5.0 (Alignment) - 2.0 (No displacement) - 4.0 (Gold trap penalty: no displaced/fvg) = -9.5
    assert ScoringEngine.calculate_score(details) == -9.5
    
    # Gold: Asian sweep low quality -> -3.0
    details = {
        'symbol': 'GC=F', 
        'h1_aligned': True, 
        'asian_sweep': True, 
        'asian_quality': False
    }
    # 3.0 (base) - 1.5 (asian sweep low quality) - 3.0 (gold asian penalty) - 2.0 (no displacement) - 4.0 (trap) = -7.5
    # Wait, check scoring.py:
    # slope = details.get('ema_slope', 0) -> default 0, no penalty.
    # at_value = details.get('at_value') -> default None/False, no penalty.
    # Total: 3.0 - 1.5 - 3.0 - 2.0 - 4.0 = -7.5
    assert ScoringEngine.calculate_score(details) == -7.5

def test_calculate_score_asian_sweeps():
    # Good Asian Sweep
    details = {'asian_sweep': True, 'asian_quality': True, 'displaced': True}
    # 1.5 (base) + 1.0 (Asian) + 0.5 (Asian V8) + 2.0 (Displaced) = 5.0
    assert ScoringEngine.calculate_score(details) == 5.0
    
    # Bad Asian Sweep (No displacement)
    details = {'asian_sweep': True, 'asian_quality': False}
    # 1.5 (base) - 1.5 (Asian trap) - 2.0 (No displacement) = -2.0
    assert ScoringEngine.calculate_score(details) == -2.0

def test_calculate_score_adr_exhaustion():
    details = {'adr_exhausted': True}
    # 1.5 (base) - 3.0 (ADR) - 2.0 (No displacement) = -3.5
    assert ScoringEngine.calculate_score(details) == -3.5

def test_calculate_score_at_value():
    details = {'at_value': True}
    # 1.5 (base) - 3.0 (Value) - 2.0 (No displacement) = -3.5
    assert ScoringEngine.calculate_score(details) == -3.5

def test_calculate_score_alpha_symbols():
    # JPY Bonus
    # 1.5 (base) + 1.0 (Alpha) - 2.0 (No displacement) = 0.5
    assert ScoringEngine.calculate_score({'symbol': 'USDJPY=X'}) == 0.5
    # NASDAQ Bonus
    assert ScoringEngine.calculate_score({'symbol': '^IXIC'}) == 0.5

def test_calculate_score_ema_slope_penalty():
    # Buy with bearish slope
    details = {'direction': 'BUY', 'ema_slope': -0.1}
    # 1.5 (base) - 2.0 (Slope) - 2.0 (No displacement) = -2.5
    assert ScoringEngine.calculate_score(details) == -2.5
    # Sell with bullish slope
    details = {'direction': 'SELL', 'ema_slope': 0.1}
    # 1.5 (base) - 2.0 (Slope) - 2.0 (No displacement) = -2.5
    assert ScoringEngine.calculate_score(details) == -2.5

def test_calculate_score_hyper_extension():
    details = {'h1_dist': 0.01} # 1% extension
    # 1.5 (base) - 2.0 (Extension) - 2.0 (No displacement) = -2.5
    assert ScoringEngine.calculate_score(details) == -2.5

def test_calculate_score_gold_premium():
    details = {
        'symbol': 'GC=F',
        'h1_aligned': True,
        'displaced': True,
        'pullback': True,
        'volatile': True,
        'has_fvg': True # Quantum Shield bonus
    }
    # Score is 9.0 (Premier), Gold gets +1.0 -> 10.0
    assert ScoringEngine.calculate_score(details) == 10.0

def test_get_quality_seal():
    assert ScoringEngine.get_quality_seal(9.5) == "PREMIER A+"
    assert ScoringEngine.get_quality_seal(8.0) == "SOLID A"
    assert ScoringEngine.get_quality_seal(6.5) == "STANDARD B"
    assert ScoringEngine.get_quality_seal(4.0) == "LOW ❌"
