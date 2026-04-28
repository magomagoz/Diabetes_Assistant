import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Diabete AI Assistant", layout="centered")

# --- GESTIONE PERSISTENZA (PROFILO UTENTE) ---
# Inizializziamo le variabili di stato se non esistono
if 'user_data' not in st.session_state:
    st.session_state.user_data = None

# --- FUNZIONE RESET ---
def reset_profile():
    st.session_state.user_data = None
    st.rerun()

# --- SIDEBAR PER API KEY ---
with st.sidebar:
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    if st.session_state.user_data:
        if st.button("🗑️ Reset Profilo / Cambia Utente"):
            reset_profile()

# --- LOGICA SCHERMATE ---

# SCHERMATA 1: REGISTRAZIONE (Se non c'è un utente)
if st.session_state.user_data is None:
    st.title("👋 Benvenuto! Crea il tuo profilo")
    with st.form("registration_form"):
        nome = st.text_input("Nome")
        eta = st.number_input("Età", min_value=1, max_value=120)
        peso = st.number_input("Peso (kg)", min_value=10.0, step=0.1)
        altezza = st.number_input("Altezza (cm)", min_value=50, step=1)
        
        submit = st.form_submit_input("Salva Profilo")
        if submit and nome:
            st.session_state.user_data = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza}
            st.rerun()

# SCHERMATA 2: DASHBOARD (Se l'utente è loggato)
else:
    u = st.session_state.user_data
    st.title(f"Ciao, {u['nome']}! 😊")
    
    # Input Glicemia
    glicemia = st.number_input("Inserisci la glicemia attuale (mg/dL)", min_value=20, max_value=600, step=1)
    
    st.divider()
    
    # Sezione Foto
    st.subheader("📸 Analisi del Pasto")
    foto_piatto = st.camera_input("Scatta una foto al tuo piatto")

    if foto_piatto:
        image = Image.open(foto_piatto)
        
        if st.button('🚀 Analizza e Calcola Bolo', use_container_width=True):
            if not api_key:
                st.error("Inserisci l'API Key nella sidebar per continuare.")
            else:
                with st.spinner('Analisi in corso...'):
                    # Prompt avanzato che chiede anche un controllo qualità
                    prompt = f"""
                    Agisci come un esperto di nutrizione per diabetici. 
                    L'utente è {u['nome']}, {u['eta']} anni, {u['peso']}kg. 
                    La sua glicemia attuale è {glicemia} mg/dL.
                    
                    1. Valuta la qualità della foto: se è troppo mossa, buia o se gli alimenti non sono identificabili, scrivi come prima riga 'ERRORE_QUALITA: ' seguita dal motivo.
                    2. Se la foto è chiara, identifica gli alimenti e stima i grammi di carboidrati (CHO).
                    3. Restituisci una tabella Markdown con: Alimento, Quantità stimata, CHO (g).
                    4. Calcola il totale CHO.
                    5. Se possibile, dai un consiglio rapido basato sulla glicemia inserita ({glicemia}).
                    """
                    
                    response = model.generate_content([prompt, image])
                    testo_risposta = response.text
                    
                    if "ERRORE_QUALITA" in testo_risposta:
                        st.warning("⚠️ La foto non è abbastanza chiara.")
                        st.info(testo_risposta.replace("ERRORE_QUALITA:", ""))
                        st.button("Riprova lo scatto")
                    else:
                        st.success("Analisi completata!")
                        st.markdown(testo_risposta)

