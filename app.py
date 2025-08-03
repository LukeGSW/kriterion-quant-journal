import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Diario di Bordo Quantitativo",
    page_icon="📈",
    layout="wide"
)

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

# Il widget di login viene renderizzato in una colonna centrale
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

    # QUI VERRÀ INSERITO IL RESTO DELL'APP (Dashboard, Form, Registro)
    st.header("Dashboard Riepilogo")
    st.warning("Sezione in costruzione...", icon="🚧")

    st.header("Aggiungi Nuova Operazione")
    st.warning("Sezione in costruzione...", icon="🚧")

    st.header("Registro Operazioni")
    st.warning("Sezione in costruzione...", icon="🚧")


elif authentication_status == False:
    _, col2, _ = st.columns(3)
    with col2:
        st.error('Username/password non corretti')

elif authentication_status == None:
    _, col2, _ = st.columns(3)
    with col2:
        st.warning('Per favore, inserisci username e password')
        # Abilitiamo la registrazione se necessario
        try:
            if authenticator.register_user('Registra nuovo utente', preauthorization=False):
                st.success('Utente registrato con successo. Effettua il login.')
        except Exception as e:
            st.error(e)
            
# --- Nascondiamo il footer di Streamlit e il menu ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
