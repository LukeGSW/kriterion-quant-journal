import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# Colonne operazioni (Foglio1)
COLS = [
    "username", "date", "ticker", "type",
    "premioIncassato", "premioReinvestito", "btdStandard", "btdBoost",
    "notes"
]

# Colonne tickers (worksheet "Tickers")
TICKER_COLS = [
    "username", "ticker", "capitaleIniziale", "descrizione",
    "attivo", "created_at", "notes"
]

# --------------------------------------------------------------------------------------
# Connessioni
# --------------------------------------------------------------------------------------
@st.cache_resource(ttl=600)
def _get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

def get_google_sheet(spreadsheet_name: str, worksheet_title: str = "Foglio1"):
    """Ritorna il worksheet delle operazioni."""
    try:
        gc = _get_gspread_client()
        ss = gc.open(spreadsheet_name)
        return ss.worksheet(worksheet_title)
    except Exception as e:
        st.error(f"Errore apertura worksheet '{worksheet_title}': {e}")
        return None

def get_tickers_sheet(spreadsheet_name: str, worksheet_title: str = "Tickers"):
    """Ritorna (o crea se possibile) il worksheet dei tickers."""
    try:
        gc = _get_gspread_client()
        ss = gc.open(spreadsheet_name)
        try:
            return ss.worksheet(worksheet_title)
        except gspread.WorksheetNotFound:
            # Prova a crearlo (richiede permessi di scrittura)
            try:
                ws = ss.add_worksheet(title=worksheet_title, rows=1000, cols=20)
                # intestazioni
                set_with_dataframe(ws, pd.DataFrame(columns=TICKER_COLS), include_index=False, resize=True)
                return ws
            except Exception as ce:
                st.warning(f"Worksheet '{worksheet_title}' non trovato e non creato: {ce}")
                return None
    except Exception as e:
        st.error(f"Errore apertura spreadsheet '{spreadsheet_name}': {e}")
        return None

# --------------------------------------------------------------------------------------
# Lettura/Scrittura Operazioni
# Nota: i parametri worksheet/worksheet_tickers sono _nominali (iniziano con _)
# per evitare problemi di hashing in @st.cache_data.
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_all_data(_ws):
    """Legge tutte le operazioni."""
    if _ws is None:
        return pd.DataFrame(columns=COLS)

    df = get_as_dataframe(_ws, evaluate_formulas=True)

    # Assicura colonne
    for c in COLS:
        if c not in df.columns:
            df[c] = pd.NA

    # Tipi
    num_cols = ["premioIncassato", "premioReinvestito", "btdStandard", "btdBoost"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["type"] = df["type"].astype(str).str.strip()
    df["username"] = df["username"].astype(str)
    df["notes"] = df["notes"].astype(str)

    return df[COLS]

def save_all_data(_ws, df: pd.DataFrame):
    """Scrive l’intero DataFrame operazioni sul worksheet."""
    if _ws is None:
        return
    df_copy = df.copy()
    # serializza date
    df_copy["date"] = pd.to_datetime(df_copy["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    set_with_dataframe(_ws, df_copy[COLS], include_index=False, resize=True)
    # pulisci cache per ricarichi coerenti
    st.cache_data.clear()

# --------------------------------------------------------------------------------------
# Lettura/Scrittura Tickers
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_all_tickers(_ws_tickers):
    """Legge la tabella Tickers."""
    if _ws_tickers is None:
        return pd.DataFrame(columns=TICKER_COLS)

    df = get_as_dataframe(_ws_tickers, evaluate_formulas=True)

    for c in TICKER_COLS:
        if c not in df.columns:
            df[c] = pd.NA

    df["capitaleIniziale"] = pd.to_numeric(df["capitaleIniziale"], errors="coerce").fillna(0.0)
    df["attivo"] = df["attivo"].map(lambda x: bool(x) if pd.notna(x) else True)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["username"] = df["username"].astype(str)
    df["descrizione"] = df["descrizione"].astype(str)
    df["notes"] = df["notes"].astype(str)

    return df[TICKER_COLS]

def save_all_tickers(_ws_tickers, df: pd.DataFrame):
    """Scrive l’intero DataFrame tickers sul worksheet."""
    if _ws_tickers is None:
        return
    df_copy = df.copy()
    df_copy["created_at"] = pd.to_datetime(df_copy["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    set_with_dataframe(_ws_tickers, df_copy[TICKER_COLS], include_index=False, resize=True)
    st.cache_data.clear()
