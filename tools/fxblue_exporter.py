import sqlite3
import pandas as pd
import argparse
import os
from datetime import datetime

class FXBlueExporter:
    def __init__(self, db_path="database/signals.db"):
        self.db_path = db_path

    def export(self, output_file="fxblue_history.csv"):
        """Exports verified signals to FX Blue compatible CSV"""
        print(f"Reading from {self.db_path}...")
        
        with sqlite3.connect(self.db_path) as conn:
            # Select only closed trades (WIN/LOSS/BE)
            query = """
            SELECT 
                id as 'Ticket',
                symbol as 'Symbol',
                direction as 'Type',
                timestamp as 'OpenTime',
                entry_price as 'OpenPrice',
                result_pips as 'Profit',
                status as 'Comment'
            FROM signals 
            WHERE status IN ('WIN', 'LOSS', 'BREAKEVEN')
            """
            df = pd.read_sql_query(query, conn)

        if df.empty:
            print("No closed trades found to export.")
            # Create empty dummy file for structure verification
            pd.DataFrame(columns=['Ticket', 'Symbol', 'Type', 'Size', 'OpenTime', 'OpenPrice', 'CloseTime', 'ClosePrice', 'Commission', 'Swap', 'Profit', 'Comment']).to_csv(output_file, index=False)
            return

        # Transformation for FX Blue Compatibility
        
        # 1. Clean Symbols (EURUSD=X -> EURUSD)
        df['Symbol'] = df['Symbol'].str.replace('=X', '')
        
        # 2. Format Dates (ISO -> yyyy-MM-dd HH:mm:ss)
        df['OpenTime'] = pd.to_datetime(df['OpenTime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 3. Derive CloseTime (Approximation)
        df['CloseTime'] = pd.to_datetime(df['OpenTime']) + pd.Timedelta(hours=1)
        df['CloseTime'] = df['CloseTime'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # 4. Standardize Type (BUY/SELL)
        df['Type'] = df['Type'].str.upper()

        # 5. Calculate Close Price
        # Buy: Close = Open + (Pips * PipSize)
        # Sell: Close = Open - (Pips * PipSize)
        # Assuming standard forex pips (0.0001 or 0.01 for JPY)
        def calc_close(row):
            is_jpy = 'JPY' in row['Symbol'] or 'Gold' in row['Symbol'] or 'GC' in row['Symbol']
            pip_size = 0.01 if is_jpy else 0.0001
            
            pips = row['Profit']
            # Note: result_pips in DB is likely raw pips (e.g., 20.5)
            
            if row['Type'] == 'BUY':
                return row['OpenPrice'] + (pips * pip_size)
            else:
                return row['OpenPrice'] - (pips * pip_size)

        df['ClosePrice'] = df.apply(calc_close, axis=1)

        # 5. Lots (Default to 0.1 if not stored, or derive from risk)
        df['Size'] = 0.1 

        # 6. Commission/Swap (Default 0)
        df['Commission'] = 0.0
        df['Swap'] = 0.0

        # Select and Reorder Columns for FX Blue (Custom CSV format)
        # Ticket, Symbol, Type, Size, OpenTime, OpenPrice, CloseTime, ClosePrice, Commission, Swap, Profit, Comment
        export_df = df[[
            'Ticket', 'Symbol', 'Type', 'Size', 
            'OpenTime', 'OpenPrice', 'CloseTime', 'ClosePrice', 
            'Commission', 'Swap', 'Profit', 'Comment'
        ]]

        export_df.to_csv(output_file, index=False)
        print(f"✅ Successfully exported {len(df)} trades to {output_file}")
        print("Upload this file to FX Blue > Analysis > Data Import")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export trading history for FX Blue")
    parser.add_argument("--db", default="database/signals.db", help="Path to database")
    parser.add_argument("--out", default="fxblue_history.csv", help="Output CSV file")
    
    args = parser.parse_args()
    
    exporter = FXBlueExporter(args.db)
    exporter.export(args.out)
