import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
from yaml.loader import SafeLoader
import data_manager as dm # Importa il nostro nuovo modulo

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Diario di Bordo Quantitativo",
    page_icon="📈",
    layout="wide"
)

# --- GESTIONE SECRETS E CONNESSIONE AL FOGLIO ---
# Nota: Questa parte verrà eseguita solo se i secrets sono configurati correttamente
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
    # Mostra l'interfaccia principale solo se l'utente è loggato
    
    # Header
    st.sidebar.success(f"Benvenuto *{name}*")
    authenticator.logout('Logout', 'sidebar')

    st.title("📈 Diario di Bordo Quantitativo")
    st.markdown("---")

    # Carica e filtra i dati per l'utente corrente
    all_data_df = dm.get_all_data(worksheet)
    user_data_df = all_data_df[all_data_df['username'] == username].copy()
    user_data_df = user_data_df.sort_values(by="date", ascending=False)


    # --- SEZIONI DELL'APP ---
    st.header("Dashboard Riepilogo")
    st.warning("Sezione in costruzione...", icon="🚧")

    st.header("Aggiungi Nuova Operazione")
    st.warning("Sezione in costruzione...", icon="🚧")

    st.header("Registro Operazioni")
    if worksheet is None:
        st.error("Connessione al database non riuscita. Controlla la configurazione.")
    else:
        st.dataframe(user_data_df.drop(columns=['username'])) # Mostra il registro senza la colonna username

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
