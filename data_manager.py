# --- AGGIUNGE/INCORPORA IN data_manager.py ---

from datetime import datetime

TICKERS_COLS = [
    "username", "ticker", "capitaleIniziale", "descrizione", "attivo", "created_at", "notes"
]

@st.cache_resource(ttl=300)
def get_spreadsheet(spreadsheet_name: str):
    """Restituisce l'oggetto Spreadsheet gspread."""
    try:
        gc = _get_gspread_client()
        return gc.open(spreadsheet_name)
    except Exception as e:
        st.error(f"Errore apertura spreadsheet '{spreadsheet_name}': {e}")
        return None

def get_or_create_worksheet(spreadsheet, title: str, header: list[str]):

    if spreadsheet is None:
        return None
    try:
        ws = spreadsheet.worksheet(title)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(header))
            # scrivi intestazioni
            ws.update("A1", [header])
            return ws
        except Exception as e:
            st.error(f"Impossibile creare worksheet '{title}': {e}")
            return None

@st.cache_resource(ttl=300)
def get_tickers_sheet(spreadsheet_name: str = "KriterionJournalData", title: str = "Tickers"):
    """Restituisce il worksheet 'Tickers', creandolo se manca."""
    ss = get_spreadsheet(spreadsheet_name)
    return get_or_create_worksheet(ss, title, TICKERS_COLS)

@st.cache_data(ttl=60)
def get_all_tickers(ws_tickers) -> pd.DataFrame:
    """Legge tutti i tickers configurati."""
    if ws_tickers is None:
        return pd.DataFrame(columns=TICKERS_COLS)
    df = get_as_dataframe(ws_tickers, evaluate_formulas=True, header=0).dropna(how="all")
    for c in TICKERS_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[TICKERS_COLS]
    df["username"] = df["username"].astype(str)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["capitaleIniziale"] = pd.to_numeric(df["capitaleIniziale"], errors="coerce").fillna(0.0)
    df["descrizione"] = df["descrizione"].astype(str).fillna("")
    df["attivo"] = df["attivo"].astype(str).str.lower().isin(["true", "1", "yes", "y", "t"])
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["notes"] = df["notes"].astype(str).fillna("")
    return df

def save_all_tickers(ws_tickers, df: pd.DataFrame) -> None:
    """Scrive l'intera tabella Tickers e invalida cache."""
    if ws_tickers is None:
        st.error("Worksheet Tickers non disponibile.")
        return
    out = df.copy()
    out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    set_with_dataframe(ws_tickers, out, include_index=False, resize=True)
    st.cache_data.clear()
    st.cache_resource.clear()
