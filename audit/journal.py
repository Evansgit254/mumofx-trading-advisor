import sqlite3
import os
from datetime import datetime
import pandas as pd

class SignalJournal:
    def __init__(self, db_path="database/signals.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
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
                    strategy_id TEXT,
                    status TEXT DEFAULT 'PENDING',
                    result_pips REAL DEFAULT 0,
                    res TEXT DEFAULT 'PENDING'
                )
            """)
            # V12.0 Migration: Ensure strategy_id exists
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN strategy_id TEXT")
            except sqlite3.OperationalError:
                pass # Already exists

    def log_signal(self, signal_data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO signals (timestamp, symbol, direction, entry_price, sl, tp0, tp1, tp2, confidence, session, strategy_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                signal_data['symbol'],
                signal_data['direction'],
                signal_data['entry_price'],
                signal_data['sl'],
                signal_data['tp0'],
                signal_data['tp1'],
                signal_data['tp2'],
                signal_data['confidence'],
                signal_data['session'],
                signal_data.get('strategy_id', 'unknown')
            ))
            
        # Also log to CSV for PerformanceAnalyzer audit
        csv_path = "audit/journal_v8.csv"
        df = pd.DataFrame([{
            't': datetime.now().isoformat(),
            'symbol': signal_data['symbol'],
            'dir': signal_data['direction'],
            'res': 'PENDING',
            'score': signal_data['confidence'],
            'strategy_id': signal_data.get('strategy_id', 'unknown')
        }])
        if not os.path.exists(csv_path):
            df.to_csv(csv_path, index=False)
        else:
            df.to_csv(csv_path, mode='a', header=False, index=False)

    def get_pending_signals(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM signals WHERE status = 'PENDING'")
            return [dict(row) for row in cursor.fetchall()]

    def update_signal_result(self, signal_id, status, pips):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE signals 
                SET status = ?, result_pips = ? 
                WHERE id = ?
            """, (status, pips, signal_id))

    def get_todays_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT COUNT(*) as count FROM signals WHERE timestamp LIKE ?", (f"{today}%",))
            return cursor.fetchone()['count']

    def get_all_time_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT COUNT(*) as total FROM signals")
            return cursor.fetchone()
