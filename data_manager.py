# data_manager.py
# ======================================================================================
# Gestione dati per Kriterion Quant Journal
# - Connessione a Google Sheets tramite gspread
# - Lettura/scrittura del worksheet principale (operazioni)
# - Gestione worksheet "Tickers" per configurare capitale iniziale per ticker/utente
# - Caching con Streamlit (resource/data)
# ======================================================================================

from __future__ import annotations

import streamlit as st
import gspread
import pandas as pd
from typing import Optional
from datetime import datetime
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# --------------------------------------------------------------------------------------
# Schema del foglio OPERAZIONI (worksheet "Foglio1")
# --------------------------------------------------------------------------------------
COLS = [
    "username", "date", "ticker", "type",
    "premioIncassato", "premioReinvestito", "btdStandard", "btdBoost",
    "notes"
]

NUMERIC_COLS = ["premioIncassato", "premioReinvestito", "btdStandard", "btdBoost"]

# --------------------------------------------------------------------------------------
# Schema del foglio TICKERS (worksheet "Tickers")
# --------------------------------------------------------------------------------------
TICKERS_COLS = [
    "username", "ticker", "capitaleIniziale", "descrizione", "attivo", "created_at", "notes"
]


# --------------------------------------------------------------------------------------
# Client gspread e apertura Spreadsheet/Worksheet
# --------------------------------------------------------------------------------------
@st.cache_resource(ttl=300)
def _get_gspread_client() -> gspread.client.Client:
    """
    Istanzia il client gspread usando le credenziali del service account
    presenti in st.secrets["gcp_service_account"].
    """
    try:
        creds = st.secrets["gcp_service_account"]
    except Exception as e:
        st.error(f"Credenziali GCP mancanti in st.secrets['gcp_service_account']: {e}")
        raise
    return gspread.service_account_from_dict(creds)


@st.cache_resource(ttl=300)
def get_spreadsheet(spreadsheet_name: str) -> Optional[gspread.Spreadsheet]:
    """
    Restituisce l'oggetto Spreadsheet aperto per nome, oppure None in caso di errore.
    """
    try:
        gc = _get_gspread_client()
        return gc.open(spreadsheet_name)
    except Exception as e:
        st.error(f"Errore apertura spreadsheet '{spreadsheet_name}': {e}")
        return None


def get_or_create_worksheet(spreadsheet: gspread.Spreadsheet,
                            title: str,
                            header: list[str]) -> Optional[gspread.Worksheet]:
    """
    Restituisce il worksheet con 'title'. Se non esiste, lo crea con intestazioni 'header'.
    """
    if spreadsheet is None:
        return None
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(len(header), 10))
            # Scrive intestazioni alla prima riga
            ws.update("A1", [header])
            return ws
        except Exception as e:
            st.error(f"Impossibile creare worksheet '{title}': {e}")
            return None


@st.cache_resource(ttl=300)
def get_google_sheet(spreadsheet_name: str, worksheet_title: str = "Foglio1") -> Optional[gspread.Worksheet]:
    """
    Restituisce il worksheet principale (default 'Foglio1').
    """
    ss = get_spreadsheet(spreadsheet_name)
    if ss is None:
        return None
    try:
        return ss.worksheet(worksheet_title)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_title}' non trovato nello spreadsheet '{spreadsheet_name}'.")
        return None
    except Exception as e:
        st.error(f"Errore nell'apertura del worksheet '{worksheet_title}': {e}")
        return None


@st.cache_resource(ttl=300)
def get_tickers_sheet(spreadsheet_name: str = "KriterionJournalData",
                      title: str = "Tickers") -> Optional[gspread.Worksheet]:
    """
    Restituisce il worksheet 'Tickers', creandolo se non esiste (con intestazioni TICKERS_COLS).
    """
    ss = get_spreadsheet(spreadsheet_name)
    if ss is None:
        return None
    return get_or_create_worksheet(ss, title, TICKERS_COLS)


# --------------------------------------------------------------------------------------
# Lettura/Scrittura OPERAZIONI
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_all_data(_ws: Optional[gspread.Worksheet]) -> pd.DataFrame:
    """
    Legge tutte le operazioni dal worksheet in un DataFrame tipizzato, con colonne garantite.
    Nota: il parametro è prefissato con underscore per evitare hashing (Worksheet non hashabile).
    """
    if _ws is None:
        return pd.DataFrame(columns=COLS)

    try:
        df = get_as_dataframe(_ws, evaluate_formulas=True, header=0)
    except Exception as e:
        st.error(f"Errore lettura dati da worksheet: {e}")
        return pd.DataFrame(columns=COLS)

    # Drop righe completamente vuote
    df = df.dropna(how="all")

    # Garantisce tutte le colonne e l'ordine
    for col in COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLS]

    # Tipizzazione
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["type"] = df["type"].astype(str).str.strip()
    df["notes"] = df["notes"].astype(str).fillna("")
    df["username"] = df["username"].astype(str)

    return df


def save_all_data(_ws: Optional[gspread.Worksheet], df: pd.DataFrame) -> None:
    """
    Scrive l'intero DataFrame OPERAZIONI nel worksheet e invalida le cache.
    (Funzione non cached → nessun problema ad accettare Worksheet come parametro.)
    """
    if _ws is None:
        st.error("Worksheet operazioni non disponibile.")
        return

    try:
        out = df.copy()

        # Serializza date in formato YYYY-MM-DD per compatibilità con Sheets
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")

        set_with_dataframe(_ws, out, include_index=False, resize=True)
        # Invalida cache dopo scrittura
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Errore scrittura dati su worksheet operazioni: {e}")


# --------------------------------------------------------------------------------------
# Lettura/Scrittura TICKERS
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_all_tickers(_ws_tickers: Optional[gspread.Worksheet]) -> pd.DataFrame:
    """
    Legge tutti i tickers configurati in un DataFrame tipizzato, con colonne garantite.
    Nota: parametro prefissato con underscore per evitare hashing (Worksheet non hashabile).
    """
    if _ws_tickers is None:
        return pd.DataFrame(columns=TICKERS_COLS)

    try:
        df = get_as_dataframe(_ws_tickers, evaluate_formulas=True, header=0)
    except Exception as e:
        st.error(f"Errore lettura dati da worksheet Tickers: {e}")
        return pd.DataFrame(columns=TICKERS_COLS)

    df = df.dropna(how="all")

    for c in TICKERS_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[TICKERS_COLS]

    df["username"] = df["username"].astype(str)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["capitaleIniziale"] = pd.to_numeric(df["capitaleIniziale"], errors="coerce").fillna(0.0)
    df["descrizione"] = df["descrizione"].astype(str).fillna("")
    # Interpreta booleani comuni (true/1/yes/y/t)
    df["attivo"] = df["attivo"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "t"])
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["notes"] = df["notes"].astype(str).fillna("")

    return df


def save_all_tickers(_ws_tickers: Optional[gspread.Worksheet], df: pd.DataFrame) -> None:
    """
    Scrive l'intera tabella TICKERS nel worksheet e invalida le cache.
    (Funzione non cached → nessun problema ad accettare Worksheet come parametro.)
    """
    if _ws_tickers is None:
        st.error("Worksheet Tickers non disponibile.")
        return

    try:
        out = df.copy()
        # Serializza created_at
        if "created_at" in out.columns:
            out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        set_with_dataframe(_ws_tickers, out, include_index=False, resize=True)
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Errore scrittura dati su worksheet Tickers: {e}")
