import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os

# --- COSTANTI E FUNZIONI DI SISTEMA ---
USER_DATA_FILE = "profilo_utente.json"

def salva_dati_locali(dati):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(dati, f)

def carica_dati_locali():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                return json.load(f)
        except: return None
    return None

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Diabete AI Helper", layout="centered", page_icon="💉")

if 'user_data' not in st.session_state:
    st.session_state.user_data = carica_dati_locali()

if 'mostra_camera' not in st.session_state:
    st.session_state.mostra_camera = False

# --- SIDEBAR: CONFIGURAZIONE AI ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    st.divider()
    if st.session_state.user_data:
        st.write(f"Utente: **{st.session_state.user_data['nome']}**")
        if st.button("🗑️ Elimina e Resetta Profilo"):
            if os.path.exists(USER_DATA_FILE):
                os.remove(USER_DATA_FILE)
            st.session_state.user_data = None
            st.rerun()

# --- FLUSSO DELLE SCHERMATE ---

# 1. REGISTRAZIONE
if st.session_state.user_data is None:
    st.title("🥗 Benvenuto su AI Bolus")
    st.info("Inserisci i tuoi dati per iniziare. Verranno salvati solo sul tuo dispositivo.")
    
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome")
            eta = st.number_input("Età", min_value=1, value=30)
        with col2:
            peso = st.number_input("Peso (kg)", min_value=10.0, value=70.0)
            altezza = st.number_input("Altezza (cm)", min_value=50, value=170)
        
        rapporto_ic = st.number_input("Rapporto Insulina/Carboidrati (IC)", min_value=1.0, value=30.0, help="Quanti grammi di carboidrati copre 1 unità di insulina?")
        
        if st.form_submit_button("Salva Profilo e Inizia"):
            if nome:
                dati = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza, "ic": rapporto_ic}
                st.session_state.user_data = dati
                salva_dati_locali(dati)
                st.success("Profilo creato!")
                st.rerun()

# 2. DASHBOARD OPERATIVA
else:
    u = st.session_state.user_data
    st.title(f"Ciao {u['nome']}! 👋")
    
    # Input Glicemia
    glicemia_attuale = st.number_input("Inserisci la Glicemia (mg/dL)", min_value=20, max_value=600, value=100)
    
    st.write("---")
    
    # Pulsante Camera sotto la Glicemia
    if not st.session_state.mostra_camera:
        if st.button("📸 SCATTA FOTO AL PIATTO", use_container_width=True, type="primary"):
            st.session_state.mostra_camera = True
            st.rerun()
    else:
        if st.button("⬅️ Chiudi Fotocamera"):
            st.session_state.mostra_camera = False
            st.rerun()
        
        # Opzione Camera + Opzione Upload (per usare la posteriore)
        st.write("Usa la camera frontale o carica una foto fatta con la posteriore:")
        foto_cam = st.camera_input("Inquadra il piatto")
        foto_up = st.file_uploader("Oppure carica dalla galleria (scelta consigliata per camera posteriore)", type=["jpg", "jpeg", "png"])
        
        input_finale = foto_cam if foto_cam else foto_up
        
        if input_finale:
            image = Image.open(input_finale)
            st.image(image, caption="Piatto da analizzare", use_column_width=True)
            
            if st.button("🚀 CALCOLA BOLO", use_container_width=True):
                if not api_key:
                    st.error("Manca l'API Key nella sidebar!")
                else:
                    with st.spinner("Analisi nutrizionale in corso..."):
                        prompt = f"""
                        Analizza questa foto per un paziente diabetico (Rapporto IC: {u['ic']}).
                        1. Controlla qualità foto. Se pessima scrivi 'QUALITA_KO'.
                        2. Identifica carboidrati (CHO).
                        3. Restituisci una tabella Alimento | Peso stimato | CHO.
                        4. Indica il totale CHO e suggerisci il bolo (Totale CHO / {u['ic']}).
                        5. Sii sintetico e usa il grassetto per i numeri.
                        """
                        response = model.generate_content([prompt, image])
                        
                        if "QUALITA_KO" in response.text:
                            st.warning("Foto non chiara. Prova ad avvicinarti o ad aumentare la luce.")
                        else:
                            st.markdown("### 📊 Risultato Analisi")
                            st.markdown(response.text)
                            st.caption("Nota: verifica sempre i dati prima di iniettare insulina.")

