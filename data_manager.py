import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# Colonne previste nel nostro foglio di calcolo
COLS = ['username', 'date', 'ticker', 'type', 'premioIncassato', 
        'premioReinvestito', 'btdStandard', 'btdBoost', 'notes']

@st.cache_resource(ttl=60) # Cache per 60 secondi per non sovraccaricare le API
def get_google_sheet(sheet_name: str):
    """Si connette a Google Sheets usando le credenziali nei secrets e restituisce un worksheet."""
    try:
        # Utilizza le credenziali di Streamlit Secrets per l'autenticazione
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        # Apri il foglio di calcolo per nome e seleziona il primo foglio
        spreadsheet = gc.open(sheet_name)
        return spreadsheet.worksheet("Foglio1") # Assicurati che il nome del foglio sia "Foglio1"
    except Exception as e:
        st.error(f"Errore di connessione a Google Sheets: {e}")
        return None

@st.cache_data(ttl=60) # Cache per 60 secondi
def get_all_data(_worksheet):
    """Recupera tutti i dati dal worksheet e li restituisce come DataFrame, gestendo i tipi di dato."""
    if _worksheet is None:
        return pd.DataFrame(columns=COLS)
        
    df = get_as_dataframe(_worksheet, evaluate_formulas=True)

    # Assicura che tutte le colonne esistano, anche se il foglio è vuoto
    for col in COLS:
        if col not in df.columns:
            df[col] = pd.NA

    # Assicura il corretto tipo di dato per le colonne numeriche
    numeric_cols = ['premioIncassato', 'premioReinvestito', 'btdStandard', 'btdBoost']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Assicura che la colonna 'date' sia in formato data
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    return df[COLS] # Riordina le colonne per sicurezza

def save_all_data(_worksheet, df):
    """Salva l'intero DataFrame nel worksheet, sovrascrivendo i dati esistenti."""
    if _worksheet is not None:
        # Converte la colonna data in stringa prima di salvare per evitare problemi di formato
        df_copy = df.copy()
        df_copy['date'] = df_copy['date'].dt.strftime('%Y-%m-%d')
        set_with_dataframe(_worksheet, df_copy, include_index=False, resize=True)
        # Pulisci le cache per forzare il ricaricamento dei dati al prossimo accesso
        st.cache_data.clear()
        st.cache_resource.clear()
