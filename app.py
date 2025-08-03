import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
from datetime import datetime
import data_manager as dm

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Diario di Bordo Quantitativo - Kriterion Quant",
    page_icon="📈",
    layout="wide"
)

# --- INIEZIONE CSS PERSONALIZZATO ---
def load_css():
    """Carica e inietta il CSS per replicare lo stile dell'app originale."""
    st.markdown("""
        <style>
            :root {
                --slate-50: #f8fafc; --slate-100: #f1f5f9; --slate-200: #e2e8f0; --slate-300: #cbd5e1;
                --slate-500: #64748b; --slate-600: #475569; --slate-700: #334155; --slate-800: #1e293b; --slate-900: #0f172a;
                --blue-600: #2563eb; --blue-700: #1d4ed8;
                --green-600: #16a34a; --green-700: #15803d;
                --red-600: #dc2626; --red-700: #b91c1c;
                --orange-500: #f97316;
            }
            .main .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            h1 { font-weight: 800; color: var(--slate-900); }
            h2 { font-weight: 700; color: var(--slate-800); border-bottom: 1px solid var(--slate-200); padding-bottom: 0.5rem; margin-top: 2rem; margin-bottom: 1rem;}
            .stDataFrame {
                border: none;
                border-radius: 0.75rem;
                background-color: white;
                box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                border: 1px solid var(--slate-200);
            }
            thead th {
                background-color: var(--slate-50);
                color: var(--slate-700);
                text-transform: uppercase;
                font-size: 0.75rem !important;
            }
            tbody tr:hover {
                background-color: var(--slate-50) !important;
            }
            /* Nasconde il menu di Streamlit e il footer */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI DI UTILITÀ ---
def format_currency(value):
    """Formatta un numero come valuta in USD."""
    if pd.isna(value) or value == 0:
        return "-"
    return f"${value:,.2f}"

# --- CARICAMENTO STILE E CONNESSIONE AL DB ---
load_css()
SHEET_NAME = "KriterionJournalData" # Assicurati che il nome del tuo Google Sheet corrisponda
if "gcp_service_account" in st.secrets:
    worksheet = dm.get_google_sheet(SHEET_NAME)
else:
    worksheet = None

# --- AUTENTICAZIONE ---
try:
    # CORREZIONE: Creiamo una copia modificabile (un dict standard) della configurazione
    # letta dai secrets di sola lettura di Streamlit.
    config = {
        'credentials': dict(st.secrets['credentials']),
        'cookies': dict(st.secrets['cookies']),
        'preauthorized': dict(st.secrets['preauthorized'])
    }

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookies']['cookie_name'],
        config['cookies']['key'],
        config['cookies']['expiry_days'],
        config['preauthorized']
    )
except KeyError as e:
    st.error(f"🚨 Errore di configurazione nei Secrets: Manca la chiave {e}. Controlla il file dei secrets su Streamlit Cloud.")
    st.stop()


# --- GESTIONE LOGIN ---
# Il widget di login viene renderizzato in una colonna centrale per estetica
_, col2, _ = st.columns(3)
with col2:
    name, authentication_status, username = authenticator.login('main')

# --- LOGICA PRINCIPALE DELL'APP ---
if authentication_status:
    # --- Interfaccia utente dopo il login ---
    st.sidebar.title(f"Benvenuto, *{name}*")
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.markdown("---")

    st.title("📈 Diario di Bordo Quantitativo")

    if worksheet is None:
        st.error("🚨 Connessione al database non riuscita. Controlla la configurazione dei Secrets di Google.")
        st.stop()
        
    all_data_df = dm.get_all_data(worksheet)
    user_data_df = all_data_df[all_data_df['username'] == username].copy()
    user_data_df = user_data_df.sort_values(by="date", ascending=False, ignore_index=True)

    # 1. DASHBOARD RIEPILOGO
    st.header("Dashboard Riepilogo")
    if user_data_df.empty:
        st.info("Nessuna operazione registrata. Aggiungi la prima operazione dal form qui sotto.")
    else:
        summary = user_data_df.groupby('ticker').agg(
            incassati=('premioIncassato', 'sum'),
            reinvestiti=('premioReinvestito', 'sum'),
            standard=('btdStandard', 'sum'),
            boost=('btdBoost', 'sum')
        ).reset_index()
        summary['liquidi'] = summary['incassati'] - summary['reinvestiti']
        summary['totale_investito'] = summary['reinvestiti'] + summary['standard'] + summary['boost']
        
        summary_display = summary.rename(columns={
            'ticker': 'Asset', 'incassati': 'Premi Incassati', 'reinvestiti': 'Premi Reinvestiti',
            'liquidi': 'Premi Liquidi', 'standard': 'BTD Standard', 'boost': 'BTD Boost',
            'totale_investito': 'Inv. Totale'
        })
        
        styled_summary = summary_display.style.format(format_currency, subset=summary_display.columns[1:])\
            .set_properties(**{'text-align': 'right'}, subset=summary_display.columns[1:])\
            .set_properties(**{'font-weight': 'bold'}, subset=['Asset'])\
            .hide(axis="index")
        st.dataframe(styled_summary, use_container_width=True, height=len(summary_display)*36+38)

    # 2. AGGIUNGI NUOVA OPERAZIONE
    st.header("Aggiungi Nuova Operazione")
    with st.form("new_op_form", clear_on_submit=True, border=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            op_date = st.date_input("Data", value=datetime.now(), format="DD/MM/YYYY")
        with col2:
            op_ticker = st.text_input("Ticker", placeholder="es. SPY").upper()
        with col3:
            op_type = st.selectbox("Tipo Operazione", ["Incasso Premio", "Reinvestimento Premio", "Investimento BTD"])
        with col4:
            op_notes = st.text_input("Note")
        
        op_premio_incassato, op_premio_reinvestito, op_btd_standard, op_btd_boost = 0.0, 0.0, 0.0, 0.0
        if op_type == "Incasso Premio":
            op_premio_incassato = st.number_input("Premio Incassato", min_value=0.0, step=0.01, format="%.2f")
        elif op_type == "Reinvestimento Premio":
            op_premio_reinvestito = st.number_input("Premio Reinvestito", min_value=0.0, step=0.01, format="%.2f")
        elif op_type == "Investimento BTD":
            btd_col1, btd_col2 = st.columns(2)
            with btd_col1:
                op_btd_standard = st.number_input("BTD Standard", min_value=0.0, step=0.01, format="%.2f")
            with btd_col2:
                op_btd_boost = st.number_input("BTD Boost", min_value=0.0, step=0.01, format="%.2f")

        submitted = st.form_submit_button("✓ Registra Operazione")

        if submitted:
            if not op_ticker:
                st.error("Il campo Ticker è obbligatorio.")
            else:
                new_op_data = {
                    'username': username, 'date': pd.to_datetime(op_date), 'ticker': op_ticker,
                    'type': op_type, 'premioIncassato': op_premio_incassato, 'premioReinvestito': op_premio_reinvestito,
                    'btdStandard': op_btd_standard, 'btdBoost': op_btd_boost, 'notes': op_notes
                }
                new_op_df = pd.DataFrame([new_op_data])
                updated_df = pd.concat([all_data_df, new_op_df], ignore_index=True)
                dm.save_all_data(worksheet, updated_df)
                st.success("Operazione registrata con successo!")
                st.rerun()

    # 3. REGISTRO OPERAZIONI CON CANCELLAZIONE
    st.header("Registro Operazioni")
    if not user_data_df.empty:
        user_data_df.insert(0, "delete", False)
        
        edited_df = st.data_editor(
            user_data_df, hide_index=True, use_container_width=True,
            column_config={
                "delete": st.column_config.CheckboxColumn("Cancella", default=False),
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "username": None
            },
            disabled=user_data_df.columns.drop('delete')
        )
        
        if st.button("🗑️ Conferma Cancellazione Selezionate", type="primary"):
            rows_to_delete = edited_df[edited_df['delete']]
            if not rows_to_delete.empty:
                indices_to_drop = all_data_df.index[
                    (all_data_df['username'] == username) & 
                    (all_data_df.index.isin(rows_to_delete.index))
                ]
                final_df = all_data_df.drop(indices_to_drop)
                dm.save_all_data(worksheet, final_df)
                st.success(f"{len(rows_to_delete)} operazione/i cancellata/e con successo.")
                st.rerun()
            else:
                st.warning("Nessuna operazione selezionata per la cancellazione.")

elif authentication_status is False:
    _, col2, _ = st.columns(3)
    with col2:
        st.error('Username/password non corretti')

elif authentication_status is None:
    _, col2, _ = st.columns(3)
    with col2:
        st.warning('Per favore, inserisci username e password')
        # Abilita la registrazione se necessario
        try:
            if authenticator.register_user('Registra nuovo utente', preauthorization=False):
                st.success('Utente registrato con successo. Effettua il login.')
        except Exception as e:
            st.error(e)
