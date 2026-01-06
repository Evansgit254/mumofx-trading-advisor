import pytest
import sqlite3
import pandas as pd
import os
from unittest.mock import MagicMock, patch
from tools.gsheets_syncer import GSheetsSyncer

@pytest.fixture
def temp_db():
    db_path = "tests/test_gsheets.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            exit_price REAL,
            result_pips REAL,
            status TEXT,
            risk_percent REAL,
            session TEXT,
            confidence REAL,
            sl REAL,
            tp0 REAL,
            tp1 REAL,
            tp2 REAL
        )
    """)
    # Insert 3 trades: 2 old (already in sheet), 1 new
    conn.execute("""
        INSERT INTO signals (id, timestamp, symbol, direction, entry_price, exit_price, result_pips, status, risk_percent, session)
        VALUES 
        (1, '2024-01-01 10:00:00', 'EURUSD', 'BUY', 1.0500, 1.0520, 20, 'WIN', 1.0, 'London'),
        (2, '2024-01-01 12:00:00', 'GBPUSD', 'SELL', 1.2500, 1.2510, -10, 'LOSS', 1.0, 'NY'),
        (3, '2024-01-01 14:00:00', 'USDJPY', 'BUY', 150.00, 150.50, 50, 'WIN', 0.5, 'Asian')
    """)
    conn.commit()
    conn.close()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)

@patch("gspread.authorize")
@patch("oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_name")
def test_sync_logic(mock_creds, mock_auth, temp_db):
    # Mock Google Sheets Client and Worksheet
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_worksheet = MagicMock()
    
    mock_auth.return_value = mock_client
    mock_client.open.return_value = mock_sheet
    mock_sheet.sheet1 = mock_worksheet
    
    # Mock existing tickets in sheet (Tickets "1" and "2" exist)
    # col_values(1) returns ['Ticket', '1', '2']
    mock_worksheet.col_values.return_value = ['Ticket', '1', '2']

    # Initialize Syncer
    syncer = GSheetsSyncer(db_path=temp_db, creds_file="dummy.json")
    
    # Fake existence of creds file for the connect check
    with patch("os.path.exists", return_value=True):
        syncer.sync()

    # Verify append_rows was called with ONLY trade #3
    mock_worksheet.append_rows.assert_called_once()
    
    args, _ = mock_worksheet.append_rows.call_args
    rows = args[0]
    
    assert len(rows) == 1
    new_trade = rows[0]
    
    # Check Trade #3 Data
    assert new_trade[0] == '3'          # Ticket
    assert new_trade[1] == 'USDJPY'     # Symbol
    assert new_trade[2] == 'BUY'        # Type
    assert new_trade[7] == 50           # Pips
    assert new_trade[8] == 'WIN'        # Status
    assert new_trade[10] == 'Asian'     # Session
