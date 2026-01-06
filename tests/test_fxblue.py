import pytest
import sqlite3
import pandas as pd
import os
from tools.fxblue_exporter import FXBlueExporter

@pytest.fixture
def temp_db():
    db_path = "tests/test_fxblue.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp0 REAL,
            tp1 REAL,
            tp2 REAL,
            confidence REAL,
            session TEXT,
            status TEXT,
            result_pips REAL
        )
    """)
    # Insert 2 trades: 1 WIN (Buy), 1 LOSS (Sell)
    conn.execute("""
        INSERT INTO signals (timestamp, symbol, direction, entry_price, status, result_pips)
        VALUES 
        ('2024-01-01 10:00:00', 'EURUSD', 'BUY', 1.0500, 'WIN', 20),
        ('2024-01-01 12:00:00', 'GBPUSD', 'SELL', 1.2500, 'LOSS', -10)
    """)
    conn.commit()
    conn.close()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists("tests/fxblue_test.csv"):
        os.remove("tests/fxblue_test.csv")

def test_export_csv_format(temp_db):
    exporter = FXBlueExporter(temp_db)
    output_file = "tests/fxblue_test.csv"
    exporter.export(output_file)
    
    assert os.path.exists(output_file)
    df = pd.read_csv(output_file)
    
    assert len(df) == 2
    
    # Check Buy Trade
    buy_trade = df.iloc[0]
    assert buy_trade['Symbol'] == 'EURUSD'
    assert buy_trade['Type'] == 'BUY'
    assert buy_trade['Profit'] == 20
    # ClosePrice = 1.0500 + (20 * 0.0001) = 1.0520
    assert buy_trade['ClosePrice'] == pytest.approx(1.0520)
    
    # Check Sell Trade
    sell_trade = df.iloc[1]
    assert sell_trade['Symbol'] == 'GBPUSD'
    assert sell_trade['Type'] == 'SELL'
    assert sell_trade['Profit'] == -10
    # ClosePrice = 1.2500 - (-10 * 0.0001) = 1.2510 (Stop Loss hit above entry)
    assert sell_trade['ClosePrice'] == pytest.approx(1.2510)

