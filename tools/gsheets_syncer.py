import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime

class GSheetsSyncer:
    def __init__(self, db_path="database/signals.db", creds_file="service_account.json", sheet_name="TradingJournal"):
        self.db_path = db_path
        self.creds_file = creds_file
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None

    def connect(self):
        """Authenticates with Google Sheets API"""
        if not os.path.exists(self.creds_file):
            print(f"⚠️ Credentials file not found: {self.creds_file}")
            print("Please create a Service Account key and save it as 'service_account.json'")
            return False

        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, scope)
            self.client = gspread.authorize(creds)
            return True
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return False

    def get_or_create_worksheet(self):
        """Opens the spreadsheet or creates it if missing"""
        if not self.client: return None
        
        try:
            # Try to open existing sheet
            try:
                sheet = self.client.open(self.sheet_name).sheet1
            except gspread.SpreadsheetNotFound:
                # Create if not exists
                print(f"✨ Creating new spreadsheet: {self.sheet_name}")
                sh = self.client.create(self.sheet_name)
                # Share with the user's email if possible (extracted from client_email in json)
                # parsing json to find email
                with open(self.creds_file) as f:
                    data = json.load(f)
                    client_email = data.get('client_email')
                    if client_email:
                        print(f"   (Service Account Email: {client_email})")
                        print(f"   IMPORTANT: Share this sheet with your personal email to view it!")
                
                sheet = sh.sheet1
                # Initialize headers
                headers = ['Ticket', 'Symbol', 'Type', 'OpenTime', 'CloseTime', 'Entry', 'Exit', 'Pips', 'Status', 'Risk %', 'Session']
                sheet.append_row(headers)

            self.sheet = sheet
            return sheet
        except Exception as e:
            print(f"❌ Worksheet Error: {e}")
            return None

    def sync(self):
        """Reads DB and upserts new trades to Sheets"""
        if not self.connect(): return
        worksheet = self.get_or_create_worksheet()
        if not worksheet: return

        print("🔄 Syncing trades to Google Sheets...")

        # 1. Get existing Ticket IDs from Sheet (Column A)
        try:
            existing_tickets = set(worksheet.col_values(1)[1:]) # Skip header
        except:
            existing_tickets = set()

        # 2. Get Closed Trades from DB
        with sqlite3.connect(self.db_path) as conn:
            query = """
            SELECT 
                idStr,
                symbol,
                direction,
                timestamp,
                entry_price,
                exit_price,
                result_pips,
                status,
                risk_percent,
                session
            FROM (
                SELECT 
                    CAST(id AS TEXT) as idStr, * 
                FROM signals 
                WHERE status IN ('WIN', 'LOSS', 'BREAKEVEN', 'WIN_PARTIAL')
            )
            """
            df = pd.read_sql_query(query, conn)

        if df.empty:
            print("No closed trades to sync.")
            return

        # 3. Filter for New Trades
        new_trades = df[~df['idStr'].isin(existing_tickets)]
        
        if new_trades.empty:
            print("✅ Sheet is up to date.")
            return

        # 4. Format Data for Upload
        # Row: Ticket, Symbol, Type, OpenTime, CloseTime, Entry, Exit, Pips, Status, Risk, Session
        rows_to_add = []
        for _, row in new_trades.iterrows():
            open_time = pd.to_datetime(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            # approx close time = open + 1h (placeholder)
            close_time = (pd.to_datetime(row['timestamp']) + pd.Timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            
            rows_to_add.append([
                row['idStr'],
                row['symbol'].replace('=X', ''),
                row['direction'],
                open_time,
                close_time,
                row['entry_price'],
                row['exit_price'],
                row['result_pips'],
                row['status'],
                row['risk_percent'] if 'risk_percent' in row else 1.0, # Default if missing
                row['session']
            ])

        # 5. Batch Append
        worksheet.append_rows(rows_to_add)
        print(f"🚀 Synced {len(rows_to_add)} new trades to '{self.sheet_name}'")

if __name__ == "__main__":
    syncer = GSheetsSyncer()
    syncer.sync()
