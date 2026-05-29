import pandas as pd
import os

# File locali
OP_FILE = "operazioni_journal.csv"
TICKER_FILE = "tickers_journal.csv"

COLS = ["username", "date", "ticker", "type", "premioIncassato", "premioReinvestito", "btdStandard", "btdBoost", "notes"]
TICKER_COLS = ["username", "ticker", "capitaleIniziale", "descrizione", "attivo", "created_at", "notes"]

def get_all_data(_ws=None):
    if not os.path.exists(OP_FILE):
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(OP_FILE)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df[COLS]

def save_all_data(_ws, df: pd.DataFrame):
    df_copy = df.copy()
    df_copy["date"] = pd.to_datetime(df_copy["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df_copy[COLS].to_csv(OP_FILE, index=False)

def get_all_tickers(_ws_tickers=None):
    if not os.path.exists(TICKER_FILE):
        return pd.DataFrame(columns=TICKER_COLS)
    df = pd.read_csv(TICKER_FILE)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["attivo"] = df["attivo"].astype(bool)
    return df[TICKER_COLS]

def save_all_tickers(_ws_tickers, df: pd.DataFrame):
    df_copy = df.copy()
    df_copy["created_at"] = pd.to_datetime(df_copy["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    df_copy[TICKER_COLS].to_csv(TICKER_FILE, index=False)

# Funzioni fittizie per non rompere i riferimenti in app.py
def get_google_sheet(spreadsheet_name, worksheet_title): return "dummy"
def get_tickers_sheet(spreadsheet_name, worksheet_title): return "dummy"
