import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
from datetime import datetime
from yaml.loader import SafeLoader
import data_manager as dm # Importa il nostro nuovo modulo

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Diario di Bordo Quantitativo",
    page_icon="📈",
    layout="wide"
)

# --- FUNZIONI DI UTILITÀ ---
def format_currency(value):
    """Formatta un numero come valuta in USD."""
    if value == 0:
        return "-"
    return f"${value:,.2f}"

# --- GESTIONE SECRETS E CONNESSIONE AL FOGLIO ---
SHEET_NAME = "KriterionJournalData" # Assicurati che il nome corrisponda
if "gcp_service_account" in st.secrets:
    worksheet = dm.get_google_sheet(SHEET_NAME)
else:
    st.error("Credenziali Google non configurate nei secrets di Streamlit.")
    worksheet = None

# --- AUTENTICAZIONE ---
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookies']['cookie_name'],
    config['cookies']['key'],
    config['cookies']['expiry_days'],
    config['preauthorized']
)

_, col2, _ = st.columns(3)
with col2:
    name, authentication_status, username = authenticator.login('main')

# --- LOGICA PRINCIPALE DELL'APP ---
if authentication_status:
    st.sidebar.success(f"Benvenuto *{name}*")
    authenticator.logout('Logout', 'sidebar')

    st.title("📈 Diario di Bordo Quantitativo")
    st.markdown("---")

    # Carica e filtra i dati per l'utente corrente
    all_data_df = dm.get_all_data(worksheet)
    user_data_df = all_data_df[all_data_df['username'] == username].copy()
    user_data_df = user_data_df.sort_values(by="date", ascending=False)


    # --- SEZIONI DELL'APP ---

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
        
        # Calcolo totali per il footer
        total_row = pd.DataFrame({
            'ticker': ['**TOTALE**'],
            'incassati': [summary['incassati'].sum()],
            'reinvestiti': [summary['reinvestiti'].sum()],
            'liquidi': [summary['liquidi'].sum()],
            'standard': [summary['standard'].sum()],
            'boost': [summary['boost'].sum()],
            'totale_investito': [summary['totale_investito'].sum()]
        })
        
        # Applica formattazione
        summary_display = summary.style\
            .format(format_currency, subset=['incassati', 'reinvestiti', 'liquidi', 'standard', 'boost', 'totale_investito'])\
            .set_properties(**{'text-align': 'right'}, subset=['incassati', 'reinvestiti', 'liquidi', 'standard', 'boost', 'totale_investito'])\
            .set_properties(**{'font-weight': 'bold'}, subset=['ticker'])\
            .hide(axis="index")\
            .set_table_styles([
                {'selector': 'th', 'props': [('text-transform', 'uppercase'), ('font-size', '0.8rem')]},
                {'selector': '.col5, .col6', 'props': [('font-weight', 'bold')]},
            ])

        st.dataframe(summary_display, use_container_width=True)
        st.dataframe(total_row.style.format(format_currency).hide(axis="index").set_properties(**{'font-weight': 'bold'}), use_container_width=True, hide_headers=True)


    st.markdown("---")

    # 2. AGGIUNGI NUOVA OPERAZIONE
    st.header("Aggiungi Nuova Operazione")
    with st.form("new_op_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            op_date = st.date_input("Data", value=datetime.now(), format="DD/MM/YYYY")
        with col2:
            op_ticker = st.text_input("Ticker", placeholder="es. SPY").upper()
        with col3:
            op_type = st.selectbox("Tipo Operazione", ["Incasso Premio", "Reinvestimento Premio", "Investimento BTD"])
        with col4:
            op_notes = st.text_input("Note")
        
        # Campi condizionali
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

        submitted = st.form_submit_button("Registra Operazione")

        if submitted:
            if not op_ticker:
                st.error("Il campo Ticker è obbligatorio.")
            else:
                new_op_data = {
                    'username': username,
                    'date': pd.to_datetime(op_date),
                    'ticker': op_ticker,
                    'type': op_type,
                    'premioIncassato': op_premio_incassato if op_type == "Incasso Premio" else 0,
                    'premioReinvestito': op_premio_reinvestito if op_type == "Reinvestimento Premio" else 0,
                    'btdStandard': op_btd_standard if op_type == "Investimento BTD" else 0,
                    'btdBoost': op_btd_boost if op_type == "Investimento BTD" else 0,
                    'notes': op_notes
                }
                new_op_df = pd.DataFrame([new_op_data])
                updated_df = pd.concat([all_data_df, new_op_df], ignore_index=True)
                
                dm.save_all_data(worksheet, updated_df)
                st.success("Operazione registrata con successo!")

    st.markdown("---")

    # 3. REGISTRO OPERAZIONI
    st.header("Registro Operazioni")
    if worksheet is None:
        st.error("Connessione al database non riuscita. Controlla la configurazione.")
    else:
        # Formattazione per la visualizzazione
        display_df = user_data_df.copy()
        for col in ['premioIncassato', 'premioReinvestito', 'btdStandard', 'btdBoost']:
            display_df[col] = display_df[col].apply(format_currency)
        
        display_df['date'] = display_df['date'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(display_df.drop(columns=['username']), use_container_width=True)


elif authentication_status is False:
    _, col2, _ = st.columns(3)
    with col2:
        st.error('Username/password non corretti')

elif authentication_status is None:
    _, col2, _ = st.columns(3)
    with col2:
        st.warning('Per favore, inserisci username e password')
        try:
            if authenticator.register_user('Registra nuovo utente', preauthorization=False):
                st.success('Utente registrato con successo. Effettua il login.')
        except Exception as e:
            st.error(e)
            
# --- Stile ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
