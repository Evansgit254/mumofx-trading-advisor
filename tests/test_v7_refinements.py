import pytest
import pandas as pd
import sqlite3
import os
from audit.optimizer import AutoOptimizer
from filters.risk_manager import RiskManager
from strategy.entry import EntryLogic

def test_auto_optimizer_logic(tmp_path):
    # Setup mock database
    db_path = str(tmp_path / "test_signals.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, symbol TEXT, status TEXT)")
    
    # 1. Test High BE Rate (Tighten TP)
    for _ in range(5):
        conn.execute("INSERT INTO signals (symbol, status) VALUES ('EURUSD=X', 'BE')")
    for _ in range(2):
        conn.execute("INSERT INTO signals (symbol, status) VALUES ('EURUSD=X', 'WIN')")
    conn.commit()
    
    opt = AutoOptimizer(db_path)
    mults = opt.get_optimized_multipliers()
    assert mults['EURUSD=X'] == 1.2
    
    # 2. Test Low BE Rate / Runners (Expand TP)
    for _ in range(10):
        conn.execute("INSERT INTO signals (symbol, status) VALUES ('IXIC', 'WIN')")
    conn.commit()
    
    mults = opt.get_optimized_multipliers()
    # IXIC has 10 WIN, 0 BE -> BE Rate = 0% -> Should expand to 1.8
    assert mults['IXIC'] == 1.8
    conn.close()

def test_aplus_layering_distribution():
    entry = 1.0000
    sl = 0.9900 # 100 pip SL
    direction = "BUY"
    
    # Test Standard Layering (40/40/20)
    standard_layers = RiskManager.calculate_layers(0.10, entry, sl, direction, quality="B")
    assert standard_layers[0]['lots'] == 0.04
    assert standard_layers[1]['lots'] == 0.04
    assert standard_layers[2]['lots'] == 0.02
    
    # Test A+ Layering (50/30/20)
    aplus_layers = RiskManager.calculate_layers(0.10, entry, sl, direction, quality="A+")
    assert aplus_layers[0]['lots'] == 0.05
    assert aplus_layers[1]['lots'] == 0.03
    assert aplus_layers[2]['lots'] == 0.02
    assert "💎" not in aplus_layers[0]['label'] # Label check
    assert "50%" in aplus_layers[0]['label']

def test_gold_partial_levels():
    df = pd.DataFrame({
        'close': [2000.0],
        'high': [2005.0],
        'low': [1995.0],
        'atr': [10.0]
    })
    sweep_level = 1990.0
    atr = 10.0
    
    # Gold Buy
    levels = EntryLogic.calculate_levels(df, "BUY", sweep_level, atr, symbol="GC=F")
    
    # TP0 (Partial) should be Entry + 0.4 * ATR (V15.1 Gold Optimization)
    # Entry is 2000.0, ATR is 10.0 -> TP0 = 2004.0
    assert levels['tp0'] == 2004.0
    
    # Test optimized multiplier integration
    levels_opt = EntryLogic.calculate_levels(df, "BUY", sweep_level, atr, opt_mult=1.2)
    # TP2 = Entry + 1.2 * ATR = 2000 + 12 = 2012
    assert levels_opt['tp2'] == 2012.0

def test_risk_manager_argument_count():
    # Verify the fix for RiskManager.calculate_lot_size(symbol, entry, sl)
    # It used to be (sl, direction, entry, symbol) in main.py
    # Now it is (symbol, entry, sl)
    res = RiskManager.calculate_lot_size("EURUSD=X", 1.0500, 1.0400)
    assert 'lots' in res
    assert res['lots'] > 0
