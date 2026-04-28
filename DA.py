import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="AI Bolus Helper", layout="wide")

# Inizializziamo lo stato della camera se non esiste
if 'camera_attiva' not in st.session_state:
    st.session_state.camera_attiva = False

# --- SIDEBAR PER API KEY ---
with st.sidebar:
    api_key = st.secrets.get("API_KEY", "")

    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

st.title("🥗 Calcolo CHO Istantaneo")

# --- LOGICA DEL PULSANTE ---
if not st.session_state.camera_attiva:
    # Se la camera è spenta, mostra il pulsante per attivarla
    if st.button("📸 Apri Fotocamera", use_container_width=True):
        st.session_state.camera_attiva = True
        st.rerun() # Ricarica la pagina per mostrare la camera
else:
    # Se la camera è attiva, mostra il widget e un tasto per chiuderla
    if st.button("❌ Chiudi Fotocamera"):
        st.session_state.camera_attiva = False
        st.rerun()

    foto_piatto = st.camera_input("Inquadra il cibo")

    if foto_piatto:
        image = Image.open(foto_piatto)
        
        if st.button('🚀 Analizza Piatto', use_container_width=True):
            if not api_key:
                st.error("Inserisci l'API Key nella sidebar!")
            else:
                with st.spinner('Gemini sta calcolando...'):
                    prompt = "Analizza l'immagine, identifica gli alimenti e stima i grammi totali di carboidrati (CHO). Rispondi con una tabella e un totale finale."
                    response = model.generate_content([prompt, image])
                    st.markdown(response.text)
