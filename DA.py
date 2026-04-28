import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os

# --- COSTANTI ---
USER_DATA_FILE = "profilo_utente.json"

# --- FUNZIONI DI SERVIZIO PER IL SALVATAGGIO ---
def salva_dati_locali(dati):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(dati, f)

def carica_dati_locali():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return None

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="AI Bolus Helper", layout="centered")

# Inizializzazione session_state caricando dal file (se esiste)
if 'user_data' not in st.session_state:
    st.session_state.user_data = carica_dati_locali()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configurazione")
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    if st.session_state.user_data:
        if st.button("🗑️ Elimina Profilo"):
            if os.path.exists(USER_DATA_FILE):
                os.remove(USER_DATA_FILE)
            st.session_state.user_data = None
            st.rerun()

# --- SCHERMATA REGISTRAZIONE ---
if st.session_state.user_data is None:
    st.title("📝 Crea il tuo Profilo")
    with st.form("form_registrazione"):
        nome = st.text_input("Nome")
        eta = st.number_input("Età", min_value=1, max_value=120)
        peso = st.number_input("Peso (kg)", min_value=10.0, step=0.1)
        altezza = st.number_input("Altezza (cm)", min_value=50, step=1)
        
        # Tasto per salvare e scrivere su file
        if st.form_submit_button("Salva Dati Permanente"):
            if nome:
                nuovi_dati = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza}
                st.session_state.user_data = nuovi_dati
                salva_dati_locali(nuovi_dati) # Scrittura su file JSON
                st.success("Dati salvati correttamente!")
                st.rerun()
            else:
                st.error("Per favore, inserisci almeno il nome.")

# --- SCHERMATA PRINCIPALE ---
else:
    u = st.session_state.user_data
    st.title(f"Bentornato, {u['nome']}! 👋")
    
    # Campo Glicemia
    glicemia = st.number_input("Glicemia attuale (mg/dL)", min_value=20, max_value=600, value=100)
    
    st.divider()
    
    # Sezione Fotocamera
    st.subheader("📸 Analisi Pasto")
    foto = st.camera_input("Scatta una foto al piatto")

    if foto:
        image = Image.open(foto)
        if st.button('🚀 Calcola Carboidrati e Bolo', use_container_width=True):
            if not api_key:
                st.warning("Inserisci l'API Key nella barra laterale!")
            else:
                with st.spinner('L\'intelligenza artificiale sta analizzando...'):
                    # Prompt arricchito con i dati dell'utente
                    prompt = f"""
                    Agisci come assistente medico per diabetici di tipo 1.
                    Dati Utente: {u['nome']}, {u['eta']} anni, {u['peso']}kg.
                    Glicemia attuale: {glicemia} mg/dL.
                    
                    Analizza la foto:
                    1. Se la foto è sfocata o poco chiara, scrivi: "QUALITÀ_INSUFFICIENTE: [motivo]".
                    2. Altrimenti, elenca gli alimenti, stima le porzioni e i CHO totali.
                    3. Suggerisci se è necessario un bolo correttivo basandoti sulla glicemia.
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    if "QUALITÀ_INSUFFICIENTE" in response.text:
                        st.error("La foto non è chiara. Prova a scattare di nuovo con più luce o da un'altra angolazione.")
                    else:
                        st.markdown(response.text)

