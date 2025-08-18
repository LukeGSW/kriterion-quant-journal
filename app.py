# app.py
# ======================================================================================
# Kriterion Quant Journal - Streamlit App
# - Autenticazione con streamlit-authenticator (credenziali in .streamlit/secrets.toml)
# - Gestione operazioni su Google Sheets (Foglio1)
# - Gestione Tickers & Capitale Iniziale (worksheet "Tickers")
# - Tab:
#   1) Portafoglio: Impostazioni Tickers + Panoramica configurata
#   2) Journal: Dashboard Riepilogo + Aggiungi Operazione + Registro Operazioni
#   3) Metriche: KPI di portafoglio e per singolo ticker (+ trend mensile)
# ======================================================================================

from __future__ import annotations

import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
from datetime import datetime
import data_manager as dm

# --------------------------------------------------------------------------------------
# Config pagina
# --------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Diario di Bordo Quantitativo - Kriterion Quant",
    page_icon="📈",
    layout="wide",
)

# --------------------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------------------
def load_css() -> None:
    st.markdown("""
    <style>
      :root {
        --slate-50:#f8fafc; --slate-100:#f1f5f9; --slate-200:#e2e8f0; --slate-700:#334155;
        --slate-800:#1e293b; --slate-900:#0f172a;
      }
      .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
      h1{ font-weight:800; color:var(--slate-900); }
      h2{ font-weight:700; color:var(--slate-800); border-bottom:1px solid var(--slate-200);
          padding-bottom:.5rem; margin-top:2rem; margin-bottom:1rem; }
      .stDataFrame { border:1px solid var(--slate-200); border-radius:.75rem; background:#fff;
                     box-shadow:0 1px 2px 0 rgb(0 0 0 / .05); }
      thead th{ background:var(--slate-50); color:#475569; text-transform:uppercase; font-size:.75rem !important; }
      tbody tr:hover{ background:var(--slate-100) !important; }
      #MainMenu, footer, header { visibility:hidden; }
    </style>
    """, unsafe_allow_html=True)

def format_money_or_dash(value) -> str:
    """Formatta importi in USD con due decimali; zero/NaN → '-'."""
    try:
        if pd.isna(value) or float(value) == 0.0:
            return "-"
        return f"${float(value):,.2f}"
    except Exception:
        return "-"

def format_pct_or_dash(value) -> str:
    """Formatta percentuali; NaN → '-'."""
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value)*100:.2f}%"
    except Exception:
        return "-"

# Carica CSS
load_css()

# --------------------------------------------------------------------------------------
# Connessione ai worksheet
# --------------------------------------------------------------------------------------
SHEET_NAME = "KriterionJournalData"
WORKSHEET_TITLE = "Foglio1"
TICKERS_SHEET_TITLE = "Tickers"

worksheet = dm.get_google_sheet(SHEET_NAME, WORKSHEET_TITLE) if "gcp_service_account" in st.secrets else None
ws_tickers = dm.get_tickers_sheet(SHEET_NAME, TICKERS_SHEET_TITLE) if "gcp_service_account" in st.secrets else None

# --------------------------------------------------------------------------------------
# Autenticazione
# --------------------------------------------------------------------------------------
try:
    usernames = st.secrets["credentials"]["usernames"]  # dict utenti
    credentials = {"usernames": {}}
    for username, user_data in usernames.items():
        credentials["usernames"][username] = {
            "name": user_data["name"],
            "email": user_data["email"],
            "password": user_data["password"],  # hash generato con stauth.Hasher
        }

    cookie_conf = st.secrets["cookies"]
    authenticator = stauth.Authenticate(
        credentials,
        cookie_conf["cookie_name"],
        cookie_conf["key"],
        cookie_conf["expiry_days"],
    )
except KeyError as e:
    st.error(f"🚨 Errore di configurazione nei Secrets: manca la chiave {e}. Controlla .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    st.error(f"🚨 Errore inizializzazione autenticazione: {e}")
    st.stop()

authenticator.login()

name = st.session_state.get("name")
authentication_status = st.session_state.get("authentication_status")
username = st.session_state.get("username")

# --------------------------------------------------------------------------------------
# Funzioni di metrica (pure, senza side-effect)
# --------------------------------------------------------------------------------------
def compute_aggregates(user_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Aggrega le operazioni per ticker (incassati, reinvestiti, btd std/boost).
    """
    if user_ops.empty:
        return pd.DataFrame(columns=["ticker", "inc", "reinv", "std", "bst"])
    agg = (
        user_ops.groupby("ticker")
        .agg(
            inc=("premioIncassato", "sum"),
            reinv=("premioReinvestito", "sum"),
            std=("btdStandard", "sum"),
            bst=("btdBoost", "sum"),
        )
        .reset_index()
    )
    for c in ["inc", "reinv", "std", "bst"]:
        agg[c] = pd.to_numeric(agg[c], errors="coerce").fillna(0.0)
    return agg

def compute_kpi_tables(user_ops: pd.DataFrame, user_tickers_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Restituisce:
    - kpi_ticker: KPI per ticker attivo (Capitale Iniziale, inc/reinv/std/bst, Investito Totale, Cash Residuo,
                  Tasso Reinvestimento, Utilization, Operazioni per tipo, prime/ultime date, giorni attivi)
    - kpi_port: KPI aggregati di portafoglio
    """
    # Config tickers
    k_cfg = user_tickers_df.copy()
    k_cfg = k_cfg.rename(columns={"capitaleIniziale": "Capitale Iniziale"})
    k_cfg["Capitale Iniziale"] = pd.to_numeric(k_cfg["Capitale Iniziale"], errors="coerce").fillna(0.0)

    # Aggregati operazioni
    agg = compute_aggregates(user_ops)

    # Join per mostrare anche tickers senza operazioni
    kpi = k_cfg.merge(agg, how="left", left_on="ticker", right_on="ticker")
    for c in ["inc", "reinv", "std", "bst"]:
        kpi[c] = pd.to_numeric(kpi[c], errors="coerce").fillna(0.0)

    # Investito, cash, tassi
    kpi["Investito Totale"] = kpi["reinv"] + kpi["std"] + kpi["bst"]
    kpi["Entrate Totali"] = kpi["inc"]
    kpi["Base Finanziata"] = kpi["Capitale Iniziale"] + kpi["Entrate Totali"]
    # Evita divisione per zero
    kpi["Tasso Reinvestimento"] = kpi.apply(lambda r: (r["reinv"] / r["inc"]) if r["inc"] > 0 else pd.NA, axis=1)
    kpi["Utilization"] = kpi.apply(lambda r: (r["Investito Totale"] / r["Base Finanziata"]) if r["Base Finanziata"] > 0 else pd.NA, axis=1)
    kpi["Cash Residuo"] = kpi["Base Finanziata"] - kpi["Investito Totale"]

    # Conteggio operazioni per tipo
    if user_ops.empty:
        counts = pd.DataFrame(columns=["ticker","n_ops","n_inc","n_reinv","n_btd_std","n_btd_bst"])
    else:
        cnt_all = user_ops.groupby("ticker").size().rename("n_ops")
        cnt_inc = user_ops[user_ops["type"]=="Incasso Premio"].groupby("ticker").size().rename("n_inc")
        cnt_rei = user_ops[user_ops["type"]=="Reinvestimento Premio"].groupby("ticker").size().rename("n_reinv")
        cnt_std = (user_ops[user_ops["btdStandard"].fillna(0.0)>0.0].groupby("ticker").size().rename("n_btd_std"))
        cnt_bst = (user_ops[user_ops["btdBoost"].fillna(0.0)>0.0].groupby("ticker").size().rename("n_btd_bst"))
        counts = pd.concat([cnt_all, cnt_inc, cnt_rei, cnt_std, cnt_bst], axis=1).fillna(0.0).reset_index()

    kpi = kpi.merge(counts, how="left", on="ticker")
    for c in ["n_ops","n_inc","n_reinv","n_btd_std","n_btd_bst"]:
        if c in kpi.columns:
            kpi[c] = pd.to_numeric(kpi[c], errors="coerce").fillna(0).astype(int)
        else:
            kpi[c] = 0

    # Prime/ultime date e giorni attivi
    if user_ops.empty:
        span = pd.DataFrame(columns=["ticker","first_date","last_date","giorni_attivi"])
    else:
        span = user_ops.groupby("ticker").agg(first_date=("date","min"), last_date=("date","max")).reset_index()
        span["giorni_attivi"] = (span["last_date"] - span["first_date"]).dt.days.clip(lower=0).fillna(0).astype("Int64")

    kpi = kpi.merge(span, how="left", on="ticker")

    # Selezione e rinomina colonne per presentazione
    kpi_ticker = kpi.loc[kpi["attivo"], [
        "ticker",
        "Capitale Iniziale",
        "Entrate Totali",
        "reinv","std","bst",
        "Investito Totale",
        "Cash Residuo",
        "Tasso Reinvestimento",
        "Utilization",
        "n_ops","n_inc","n_reinv","n_btd_std","n_btd_bst",
        "first_date","last_date","giorni_attivi"
    ]].rename(columns={
        "ticker": "Asset",
        "reinv": "Premi Reinvestiti",
        "std": "BTD Standard",
        "bst": "BTD Boost",
        "n_ops": "N. Operazioni",
        "n_inc": "N. Incassi",
        "n_reinv": "N. Reinvestimenti",
        "n_btd_std": "N. BTD Std",
        "n_btd_bst": "N. BTD Boost",
        "first_date": "Primo Movimento",
        "last_date": "Ultimo Movimento",
        "giorni_attivi": "Giorni Attivi",
    }).copy()

    # KPI di portafoglio (solo tickers attivi)
    if kpi_ticker.empty:
        kpi_port = pd.DataFrame([{
            "Tickers Attivi": 0,
            "Capitale Iniziale Totale": 0.0,
            "Entrate Totali": 0.0,
            "Investito Totale": 0.0,
            "Cash Residuo Totale": 0.0,
            "Tasso Reinvestimento Portafoglio": pd.NA,
            "Utilization Portafoglio": pd.NA,
            "Operazioni Totali": 0
        }])
    else:
        cap0 = kpi_ticker["Capitale Iniziale"].sum()
        entr = kpi_ticker["Entrate Totali"].sum()
        invt = kpi_ticker["Investito Totale"].sum()
        cash = kpi_ticker["Cash Residuo"].sum()
        nops = kpi_ticker["N. Operazioni"].sum()
        # Tasso di reinvestimento e utilization a livello portafoglio
        t_rei = (kpi_ticker["Premi Reinvestiti"].sum() / entr) if entr > 0 else pd.NA
        base_fin = cap0 + entr
        utilz = (invt / base_fin) if base_fin > 0 else pd.NA

        kpi_port = pd.DataFrame([{
            "Tickers Attivi": int((kpi_ticker["Asset"].nunique())),
            "Capitale Iniziale Totale": cap0,
            "Entrate Totali": entr,
            "Investito Totale": invt,
            "Cash Residuo Totale": cash,
            "Tasso Reinvestimento Portafoglio": t_rei,
            "Utilization Portafoglio": utilz,
            "Operazioni Totali": int(nops)
        }])

    return kpi_ticker, kpi_port

def compute_monthly_trend(user_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Restituisce un pivot mensile (ultimi 12 mesi) per colonne: Incassi, Reinvestimenti, BTD Std, BTD Boost, Investito Totale.
    """
    if user_ops.empty:
        return pd.DataFrame(columns=["month","Incassi","Reinvestimenti","BTD Standard","BTD Boost","Investito Totale"])
    df = user_ops.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    grp = df.groupby("month").agg(
        Incassi=("premioIncassato","sum"),
        Reinvestimenti=("premioReinvestito","sum"),
        BTD_Standard=("btdStandard","sum"),
        BTD_Boost=("btdBoost","sum")
    ).reset_index()
    grp["Investito Totale"] = grp["Reinvestimenti"] + grp["BTD_Standard"] + grp["BTD_Boost"]
    grp = grp.sort_values("month")
    if len(grp) > 12:
        grp = grp.tail(12)
    grp = grp.rename(columns={"BTD_Standard":"BTD Standard","BTD_Boost":"BTD Boost"})
    return grp

# --------------------------------------------------------------------------------------
# Logica applicativa
# --------------------------------------------------------------------------------------
if authentication_status:
    st.sidebar.title(f"Benvenuto, *{name}*")
    authenticator.logout("Logout", "sidebar")
    st.sidebar.markdown("---")

    st.title("📈 Diario di Bordo Quantitativo")

    # Verifica worksheet
    if worksheet is None or ws_tickers is None:
        st.error("🚨 Connessione ai worksheet non riuscita. Verifica le credenziali GCP in secrets.")
        st.stop()

    # Carica dataset operazioni e tickers (tutti gli utenti)
    all_data_df = dm.get_all_data(worksheet)
    all_tickers_df = dm.get_all_tickers(ws_tickers)

    # Filtra dati per utente corrente
    user_data_df = (
        all_data_df.loc[all_data_df["username"] == username]
        .copy()
        .sort_values(by="date", ascending=False, ignore_index=True)
    )
    user_tickers_df = all_tickers_df.loc[all_tickers_df["username"] == username].copy()

    # Tabs principali
    tab_port, tab_journal, tab_metrics = st.tabs(["💼 Portafoglio", "📒 Journal", "📊 Metriche"])

    # ----------------------------------------------------------------------------------
    # TAB 1) Portafoglio
    # ----------------------------------------------------------------------------------
    with tab_port:
        st.header("Impostazioni Portafoglio — Tickers & Capitale Iniziale")

        with st.expander("➕ Aggiungi o aggiorna ticker", expanded=True):
            c1, c2 = st.columns([1, 1])
            with c1:
                new_ticker = st.text_input("Ticker", placeholder="es. SPY").upper().strip()
                new_descr = st.text_input("Descrizione (opzionale)")
            with c2:
                new_cap = st.number_input("Capitale iniziale", min_value=0.0, step=100.0, format="%.2f")
                new_active = st.checkbox("Attivo", value=True)

            if st.button("Salva ticker"):
                if not new_ticker:
                    st.error("Inserisci un ticker.")
                else:
                    now = pd.Timestamp.now()
                    # Se esiste già (username+ticker) → update; altrimenti append
                    mask = (all_tickers_df["username"] == username) & (all_tickers_df["ticker"] == new_ticker)
                    if mask.any():
                        # Update dei campi modificabili
                        all_tickers_df.loc[mask, ["capitaleIniziale", "descrizione", "attivo"]] = [
                            float(new_cap), new_descr, bool(new_active)
                        ]
                    else:
                        new_row = pd.DataFrame([{
                            "username": username,
                            "ticker": new_ticker,
                            "capitaleIniziale": float(new_cap),
                            "descrizione": new_descr,
                            "attivo": bool(new_active),
                            "created_at": now,
                            "notes": ""
                        }])
                        all_tickers_df = pd.concat([all_tickers_df, new_row], ignore_index=True)

                    dm.save_all_tickers(ws_tickers, all_tickers_df)
                    st.success("Ticker salvato.")
                    st.rerun()

        # Editor tickers utente con cancellazione e salvataggio modifiche
        st.subheader("Tickers configurati")
        if not user_tickers_df.empty:
            view_tk = user_tickers_df.copy()
            view_tk.insert(0, "delete", False)

            edited_tk = st.data_editor(
                view_tk,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "delete": st.column_config.CheckboxColumn("Cancella", default=False),
                    "capitaleIniziale": st.column_config.NumberColumn("Capitale Iniziale", step=100.0, format="%.2f"),
                    "attivo": st.column_config.CheckboxColumn("Attivo", default=True),
                    "created_at": None,
                    "notes": None,
                    "username": None,
                },
                disabled=[c for c in view_tk.columns if c not in ["delete", "capitaleIniziale", "descrizione", "attivo", "notes"]],
            )

            cdel, csave = st.columns([1, 1])

            with cdel:
                if st.button("🗑️ Cancella selezionati"):
                    to_del = edited_tk[edited_tk["delete"]].drop(columns=["delete"], errors="ignore")
                    if to_del.empty:
                        st.warning("Nessun ticker selezionato.")
                    else:
                        # Cancella per match su (username, ticker)
                        mask = pd.Series(False, index=all_tickers_df.index)
                        for _, r in to_del.iterrows():
                            mask |= ((all_tickers_df["username"] == r["username"]) &
                                     (all_tickers_df["ticker"] == r["ticker"]))
                        kept = all_tickers_df[~mask]
                        dm.save_all_tickers(ws_tickers, kept)
                        st.success(f"Cancellati {mask.sum()} ticker.")
                        st.rerun()

            with csave:
                if st.button("💾 Salva modifiche"):
                    # Applica modifiche per l'utente corrente unendo su (username, ticker)
                    upd = edited_tk.drop(columns=["delete"], errors="ignore")
                    base = all_tickers_df.copy()
                    base = base[~((base["username"] == username) & (base["ticker"].isin(upd["ticker"])))]
                    merged = pd.concat([base, upd], ignore_index=True)
                    dm.save_all_tickers(ws_tickers, merged)
                    st.success("Modifiche salvate.")
                    st.rerun()
        else:
            st.info("Nessun ticker configurato. Aggiungi i tuoi ticker per iniziare.")

        # Panoramica configurata
        st.subheader("Panoramica Portafoglio (configurato)")
        agg = compute_aggregates(user_data_df)
        k_cfg = user_tickers_df.copy().rename(columns={"capitaleIniziale":"Capitale Iniziale"})
        kpi = k_cfg.merge(agg, how="left", on="ticker")
        for c in ["inc","reinv","std","bst"]:
            kpi[c] = pd.to_numeric(kpi[c], errors="coerce").fillna(0.0)
        kpi["Investito Totale"] = kpi["reinv"] + kpi["std"] + kpi["bst"]
        kpi["Cash Residuo"] = kpi["Capitale Iniziale"] + kpi["inc"] - kpi["Investito Totale"]

        kpi_display = kpi.loc[kpi["attivo"], ["ticker","Capitale Iniziale","inc","reinv","std","bst","Investito Totale","Cash Residuo"]]\
                         .rename(columns={
                             "ticker":"Asset","inc":"Premi Incassati","reinv":"Premi Reinvestiti",
                             "std":"BTD Standard","bst":"BTD Boost"
                         })
        if kpi_display.empty:
            st.info("Nessun dato da mostrare.")
        else:
            styled_kpi = (
                kpi_display.style
                .format({c: format_money_or_dash for c in kpi_display.columns if c != "Asset"})
                .set_properties(**{"text-align":"right"}, subset=[c for c in kpi_display.columns if c != "Asset"])
                .set_properties(**{"font-weight":"bold"}, subset=["Asset"])
                .hide(axis="index")
            )
            st.dataframe(styled_kpi, use_container_width=True, height=len(kpi_display)*36+38)

    # ----------------------------------------------------------------------------------
    # TAB 2) Journal
    # ----------------------------------------------------------------------------------
    with tab_journal:
        # 3) Dashboard Riepilogo
        st.header("Dashboard Riepilogo")
        if user_data_df.empty:
            st.info("Nessuna operazione registrata. Aggiungi la prima operazione dal form qui sotto.")
        else:
            summary = (
                user_data_df.groupby("ticker")
                .agg(
                    incassati=("premioIncassato", "sum"),
                    reinvestiti=("premioReinvestito", "sum"),
                    standard=("btdStandard", "sum"),
                    boost=("btdBoost", "sum"),
                )
                .reset_index()
            )
            summary["liquidi"] = summary["incassati"] - summary["reinvestiti"]
            summary["totale_investito"] = summary["reinvestiti"] + summary["standard"] + summary["boost"]

            summary_display = summary.rename(columns={
                "ticker": "Asset",
                "incassati": "Premi Incassati",
                "reinvestiti": "Premi Reinvestiti",
                "liquidi": "Premi Liquidi",
                "standard": "BTD Standard",
                "boost": "BTD Boost",
                "totale_investito": "Inv. Totale",
            })

            styled_summary = (
                summary_display.style
                .format({c: format_money_or_dash for c in summary_display.columns if c != "Asset"})
                .set_properties(**{"text-align": "right"}, subset=[c for c in summary_display.columns if c != "Asset"])
                .set_properties(**{"font-weight": "bold"}, subset=["Asset"])
                .hide(axis="index")
            )
            st.dataframe(styled_summary, use_container_width=True, height=len(summary_display) * 36 + 38)

        # 4) Aggiungi Nuova Operazione (Ticker con menu a tendina condizionale)
        st.header("Aggiungi Nuova Operazione")

        # Costruisci lista ticker validi: capitaleIniziale > 0 e attivo = True
        valid_tickers = []
        if not user_tickers_df.empty:
            tmp = user_tickers_df.copy()
            tmp["capitaleIniziale"] = pd.to_numeric(tmp["capitaleIniziale"], errors="coerce").fillna(0.0)
            tmp["ticker"] = tmp["ticker"].astype(str).str.upper().str.strip()
            valid_tickers = sorted(
                tmp.loc[(tmp["attivo"] == True) & (tmp["capitaleIniziale"] > 0.0), "ticker"]
                .dropna().unique().tolist()
            )

        if not valid_tickers:
            st.warning("Nessun ticker disponibile: configura almeno un ticker **attivo** con **capitale iniziale > 0** nella tab **Portafoglio**.")

        op_type_selection = st.selectbox(
            "Tipo Operazione",
            ["Incasso Premio", "Reinvestimento Premio", "Investimento BTD"],
            key="op_type_selector",
        )

        with st.form("new_op_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                op_date = st.date_input("Data", value=datetime.now(), format="DD/MM/YYYY")
            with c2:
                op_ticker = st.selectbox(
                    "Ticker",
                    options=valid_tickers,
                    index=None if valid_tickers else 0,
                    placeholder="Seleziona un ticker",
                )
            with c3:
                op_notes = st.text_input("Note")

            if op_type_selection == "Incasso Premio":
                st.number_input("Premio Incassato", min_value=0.0, step=0.01, format="%.2f", key="premio_incassato_input")
            elif op_type_selection == "Reinvestimento Premio":
                st.number_input("Premio Reinvestito", min_value=0.0, step=0.01, format="%.2f", key="premio_reinvestito_input")
            else:
                b1, b2 = st.columns(2)
                with b1:
                    st.number_input("BTD Standard", min_value=0.0, step=0.01, format="%.2f", key="btd_standard_input")
                with b2:
                    st.number_input("BTD Boost", min_value=0.0, step=0.01, format="%.2f", key="btd_boost_input")

            submitted = st.form_submit_button("✓ Registra Operazione", disabled=(len(valid_tickers) == 0))

            if submitted:
                if not op_ticker:
                    st.error("Seleziona un ticker (menu a tendina).")
                else:
                    sel = st.session_state.op_type_selector
                    premio_incassato_val = float(st.session_state.get("premio_incassato_input", 0.0)) if sel == "Incasso Premio" else 0.0
                    premio_reinvestito_val = float(st.session_state.get("premio_reinvestito_input", 0.0)) if sel == "Reinvestimento Premio" else 0.0
                    btd_standard_val = float(st.session_state.get("btd_standard_input", 0.0)) if sel == "Investimento BTD" else 0.0
                    btd_boost_val = float(st.session_state.get("btd_boost_input", 0.0)) if sel == "Investimento BTD" else 0.0

                    new_row = {
                        "username": username,
                        "date": pd.to_datetime(op_date),
                        "ticker": str(op_ticker).upper().strip(),
                        "type": sel,
                        "premioIncassato": premio_incassato_val,
                        "premioReinvestito": premio_reinvestito_val,
                        "btdStandard": btd_standard_val,
                        "btdBoost": btd_boost_val,
                        "notes": op_notes,
                    }

                    updated_df = pd.concat([all_data_df, pd.DataFrame([new_row])], ignore_index=True)
                    dm.save_all_data(worksheet, updated_df)
                    st.success("Operazione registrata con successo!")
                    st.rerun()

        # 5) Registro Operazioni
        st.header("Registro Operazioni")
        if not user_data_df.empty:
            view_df = user_data_df.copy()
            view_df.insert(0, "delete", False)

            edited_df = st.data_editor(
                view_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "delete": st.column_config.CheckboxColumn("Cancella", default=False),
                    "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "username": None,
                },
                disabled=[c for c in view_df.columns if c != "delete"],
            )

            if st.button("🗑️ Conferma Cancellazione Selezionate", type="primary"):
                to_delete = edited_df[edited_df["delete"]].drop(columns=["delete"], errors="ignore")
                if to_delete.empty:
                    st.warning("Nessuna operazione selezionata per la cancellazione.")
                else:
                    # Normalizzazione & chiave di confronto
                    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
                        out = df.copy()
                        out["date"] = pd.to_datetime(out["date"], errors="coerce")
                        for c in ["premioIncassato", "premioReinvestito", "btdStandard", "btdBoost"]:
                            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
                        out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
                        out["type"] = out["type"].astype(str).str.strip()
                        out["notes"] = out["notes"].astype(str)
                        out["username"] = out["username"].astype(str)
                        return out

                    base_norm = _normalize(all_data_df)
                    del_norm  = _normalize(to_delete)

                    def _make_key(df: pd.DataFrame) -> pd.Series:
                        return (
                            df["username"].astype(str) + "|" +
                            df["date"].dt.strftime("%Y-%m-%d").astype(str) + "|" +
                            df["ticker"].astype(str) + "|" +
                            df["type"].astype(str) + "|" +
                            df["premioIncassato"].astype(str) + "|" +
                            df["premioReinvestito"].astype(str) + "|" +
                            df["btdStandard"].astype(str) + "|" +
                            df["btdBoost"].astype(str) + "|" +
                            df["notes"].astype(str)
                        )

                    base_norm["_rk"] = _make_key(base_norm)
                    del_norm["_rk"]  = _make_key(del_norm)

                    indices_to_drop = base_norm.index[base_norm["_rk"].isin(set(del_norm["_rk"]))]
                    final_df = all_data_df.drop(index=indices_to_drop)

                    dm.save_all_data(worksheet, final_df)
                    st.success(f"{len(indices_to_drop)} operazione/i cancellata/e con successo.")
                    st.rerun()

    # ----------------------------------------------------------------------------------
    # TAB 3) Metriche
    # ----------------------------------------------------------------------------------
    with tab_metrics:
        st.header("Metriche di Portafoglio e per Ticker")

        # Costruzione tabelle KPI
        kpi_ticker, kpi_port = compute_kpi_tables(user_data_df, user_tickers_df)

        # KPI di Portafoglio (metriche sintetiche)
        st.subheader("KPI di Portafoglio")
        if not kpi_port.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tickers Attivi", int(kpi_port.iloc[0]["Tickers Attivi"]))
            c2.metric("Operazioni Totali", int(kpi_port.iloc[0]["Operazioni Totali"]))
            c3.metric("Capitale Iniziale Totale", format_money_or_dash(kpi_port.iloc[0]["Capitale Iniziale Totale"]))
            c4.metric("Cash Residuo Totale", format_money_or_dash(kpi_port.iloc[0]["Cash Residuo Totale"]))

            c5, c6, c7 = st.columns(3)
            c5.metric("Entrate Totali", format_money_or_dash(kpi_port.iloc[0]["Entrate Totali"]))
            c6.metric("Investito Totale", format_money_or_dash(kpi_port.iloc[0]["Investito Totale"]))
            c6.caption("Somma di Reinvestimenti + BTD Standard + BTD Boost")
            c7.metric("Utilization Portafoglio", format_pct_or_dash(kpi_port.iloc[0]["Utilization Portafoglio"]))
            st.caption(f"Tasso Reinvestimento Portafoglio: {format_pct_or_dash(kpi_port.iloc[0]['Tasso Reinvestimento Portafoglio'])}")

        # KPI per Ticker (tabella dettagliata)
        st.subheader("KPI per Ticker (attivi)")
        if kpi_ticker.empty:
            st.info("Nessun ticker attivo o nessuna operazione registrata.")
        else:
            kpi_show = kpi_ticker.copy()
            money_cols = ["Capitale Iniziale","Entrate Totali","Premi Reinvestiti","BTD Standard","BTD Boost","Investito Totale","Cash Residuo"]
            pct_cols   = ["Tasso Reinvestimento","Utilization"]
            for c in money_cols:
                if c not in kpi_show.columns:
                    kpi_show[c] = 0.0
            if "Primo Movimento" in kpi_show.columns:
                kpi_show["Primo Movimento"] = pd.to_datetime(kpi_show["Primo Movimento"], errors="coerce").dt.strftime("%Y-%m-%d")
            if "Ultimo Movimento" in kpi_show.columns:
                kpi_show["Ultimo Movimento"] = pd.to_datetime(kpi_show["Ultimo Movimento"], errors="coerce").dt.strftime("%Y-%m-%d")

            styled = (
                kpi_show.style
                .format({c: format_money_or_dash for c in money_cols})
                .format({c: format_pct_or_dash for c in pct_cols})
                .set_properties(**{"text-align":"right"}, subset=[c for c in kpi_show.columns if c not in ["Asset","Primo Movimento","Ultimo Movimento"]])
                .set_properties(**{"font-weight":"bold"}, subset=["Asset"])
                .hide(axis="index")
            )
            st.dataframe(styled, use_container_width=True, height=min(600, len(kpi_show)*36+38))

        # Trend mensile (ultimi 12 mesi)
        st.subheader("Trend Mensile (ultimi 12 mesi)")
        monthly = compute_monthly_trend(user_data_df)
        if monthly.empty:
            st.info("Nessun dato mensile disponibile.")
        else:
            st.dataframe(
                monthly.rename(columns={"month":"Mese"}),
                use_container_width=True,
                height=min(600, len(monthly)*36+38)
            )
            st.line_chart(
                data=monthly.set_index("month")[["Investito Totale"]],
                use_container_width=True
            )

elif authentication_status is False:
    st.error("Username/password non corretti")
else:
    st.warning("Per favore, inserisci username e password")
    # Registrazione runtime sconsigliata in produzione (manca persistenza esterna).
    # Se necessario, implementare uno storage per nuove credenziali.
