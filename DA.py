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

# --- SIDEBAR: CONFIGURAZIONE AI ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
    
    st.divider()
    if st.session_state.user_data:
        st.write(f"Utente: **{st.session_state.user_data['nome']}**")
        if st.button("🗑️ Elimina e Resetta Profilo"):
            if os.path.exists(USER_DATA_FILE):
                os.remove(USER_DATA_FILE)
            st.session_state.user_data = None
            st.rerun()

# --- 1. REGISTRAZIONE ---
if st.session_state.user_data is None:
    st.title("🥗 Benvenuto su AI Bolus")
    st.info("Inserisci i tuoi dati per iniziare. Verranno salvati solo sul tuo dispositivo.")
    
    with st.form("reg_form"):
        st.subheader("Dati Personali")
        nome = st.text_input("Nome")
        eta = st.number_input("Età", min_value=1, value=30)
        peso = st.number_input("Peso (kg)", min_value=10.0, value=70.0)
        altezza = st.number_input("Altezza (cm)", min_value=50, value=170)
        
        st.subheader("Parametri Diabete")
        conosco_ic = st.radio("Conosci il tuo rapporto IC?", ["Sì", "No (Calcolalo per me)"])
        
        if conosco_ic == "Sì":
            rapporto_ic = st.number_input("Inserisci il tuo rapporto IC (g/U)", min_value=1.0, value=10.0)
        else:
            tdd = st.number_input("Unità totali di insulina al giorno (Basale + Boli)", min_value=1.0, value=40.0)
            rapporto_ic = 500 / tdd
            st.info(f"Il tuo IC stimato è: **{rapporto_ic:.1f}**")
        
        if st.form_submit_button("Salva Profilo e Inizia"):
            if nome:
                dati = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza, "ic": rapporto_ic}
                st.session_state.user_data = dati
                salva_dati_locali(dati)
                st.success("Profilo creato!")
                st.rerun()

# --- 2. DASHBOARD OPERATIVA ---
else:
    u = st.session_state.user_data
    st.title(f"Ciao {u['nome']}! 👋")
    
    # Input Glicemia
    glicemia_attuale = st.number_input("Inserisci la Glicemia attuale (mg/dL)", min_value=20, max_value=600, value=100)
    
    st.write("---")
    
    # Pulsante per Foto/Galleria gestito nativamente dal sistema operativo
    st.subheader("📸 Scatta o carica foto del piatto")
    input_finale = st.file_uploader("", type=["jpg", "jpeg", "png"])
    
    if input_finale:
        image = Image.open(input_finale)
        st.image(image, caption="Piatto da analizzare", use_column_width=True)
        
        if st.button("🚀 CALCOLA BOLO", use_container_width=True, type="primary"):
            if not api_key:
                st.error("⚠️ Manca l'API Key nella sidebar!")
            else:
                with st.spinner("Analisi nutrizionale in corso..."):
                    try:
                        prompt = f"""
                        Agisci come un esperto nutrizionista per diabetici. 
                        Paziente: {u['nome']}, Rapporto IC: {u['ic']:.1f}.
                        Glicemia attuale: {glicemia_attuale} mg/dL.
                        
                        Analizza l'immagine:
                        1. Identifica gli alimenti.
                        2. Stima i carboidrati (CHO) totali.
                        3. Se la foto è illeggibile, scrivi chiaramente che la qualità è bassa.
                        4. Calcola il bolo per i pasti suggerito: (CHO totali / {u['ic']:.1f}).
                        """
                        
                        # Chiamata al modello
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        response = model.generate_content([prompt, image])
                        
                        st.markdown("### 📊 Risultato Analisi")
                        st.markdown(response.text)
                        st.caption("Nota: verifica sempre i dati prima di iniettare insulina.")
                        
                    except Exception as e:
                        errore_str = str(e)
                        if "404" in errore_str or "not found" in errore_str.lower():
                            st.error("❌ Errore: Il modello non è stato trovato. Controlla il nome del modello nel codice.")
                        elif "API_KEY_INVALID" in errore_str:
                            st.error("❌ Errore: La tua API Key non è valida. Controllala in Google AI Studio.")
                        else:
                            st.error(f"❌ Si è verificato un errore inaspettato: {errore_str}")
