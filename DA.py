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
st.set_page_config(page_title="Diabete AI Helper", layout="wide", page_icon="💉")

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
        model = genai.GenerativeModel('gemini-2.5-flash')
    
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
                    st.error("Inserisci l'API Key nella barra laterale!")
                elif input_finale is None:
                    st.warning("Per favore, scatta una foto o carica un'immagine prima di procedere.")
                else:
                    with st.spinner("Analisi nutrizionale in corso..."):
                        try:
                            # Carichiamo l'immagine
                            image = Image.open(input_finale)
                            
                            # Definiamo il prompt per Gemini
                            prompt = f"""
                            Agisci come un esperto nutrizionista per diabetici. 
                            Paziente: {u['nome']}, Rapporto IC: {u['ic']}.
                            Analizza l'immagine:
                            1. Identifica gli alimenti (es. Peperoni grigliati).
                            2. Stima i carboidrati (CHO) totali.
                            3. Se la foto è illeggibile, scrivi chiaramente che la qualità è bassa.
                            4. Calcola il bolo suggerito: (CHO totali / {u['ic']}).
                            """
                            
                            # CHIAMATA AL MODELLO (Uso il nome completo del modello per evitare il NotFound)
                            # Proviamo con 'gemini-1.5-flash', se fallisce darà un errore specifico
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            
                            response = model.generate_content([prompt, image])
                            
                            # Visualizzazione del risultato
                            st.markdown("### 📊 Risultato Analisi")
                            st.markdown(response.text)
                            
                        except Exception as e:
                            # Se c'è un errore, lo catturiamo e lo spieghiamo
                            errore_str = str(e)
                            if "404" in errore_str or "not found" in errore_str.lower():
                                st.error("❌ Errore: Il modello 'gemini-1.5-flash' non è stato trovato. Prova a scrivere 'models/gemini-1.5-flash' nel codice.")
                            elif "API_KEY_INVALID" in errore_str:
                                st.error("❌ Errore: La tua API Key non è valida. Controllala in Google AI Studio.")
                            else:
                                st.error(f"❌ Si è verificato un errore inaspettato: {errore_str}")
