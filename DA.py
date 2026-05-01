import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
from datetime import datetime
import pandas as pd
import plotly.express as px

# --- GESTIONE IMPORTAZIONI SICURA ---
# Se utils.py manca, creiamo funzioni vuote per non far crashare l'app
try:
    from utils import (
        elabora_dati, calcola_metriche, genera_suggerimenti, 
        suggerisci_aggiustamento_ic 
    )
    utils_presente = True
except ImportError:
    utils_presente = False
    # Fallback fittizi
    def elabora_dati(df): return df
    def calcola_metriche(df, a, b): return {"TIR": 0.0, "IPO": 0.0, "IPER": 0.0}
    def genera_suggerimenti(df): return ["Attenzione: File utils.py non trovato. Analisi disabilitata."]
    def suggerisci_aggiustamento_ic(df): return []

# --- COSTANTI E FUNZIONI DI SISTEMA ---
USER_DATA_FILE = "profilo_utente.json"
LOG_PASTI_FILE = "log_pasti.csv"

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

# --- CONFIGURAZIONE STREAMLIT ---
st.set_page_config(page_title="AI Bolus - Diabete Helper", layout="wide", page_icon="💉")

if not utils_presente:
    st.sidebar.warning("⚠️ File utils.py mancante. Le analisi avanzate del sensore non funzioneranno.")

# Inizializzazione Session State
if 'user_data' not in st.session_state:
    st.session_state.user_data = carica_dati_locali()
if 'pasti_correnti' not in st.session_state:
    st.session_state.pasti_correnti = []

# CSS Bottoni
st.markdown("""
    <style>
    div.stButton > button { width: 100% !important; height: 45px !important; border-radius: 5px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    
    # Gestione sicura API Key
    try:
        api_key = st.secrets["API_KEY"]
        genai.configure(api_key=api_key)
    except:
        api_key = ""
        st.warning("🔑 API_KEY non trovata nei secrets.")
    
    if st.session_state.user_data:
        st.divider()
        st.write(f"👤 Utente: **{st.session_state.user_data.get('nome')}**")
        st.write(f"⚖️ Rapporto IC: **{st.session_state.user_data.get('ic')}** g/U")
        st.write(f"🩸 ISF: **{st.session_state.user_data.get('isf')}** mg/dL/U")
        
        if st.button("🗑️ Reset Totale Profilo"):
            if os.path.exists(USER_DATA_FILE): os.remove(USER_DATA_FILE)
            if os.path.exists(LOG_PASTI_FILE): os.remove(LOG_PASTI_FILE)
            st.session_state.user_data = None
            st.session_state.pasti_correnti = []
            st.rerun()

# --- 1. SCHERMATA REGISTRAZIONE (Se profilo manca) ---
if st.session_state.user_data is None:
    st.title("🥗 Benvenuto su AI Bolus")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome")
        eta = col1.number_input("Età", min_value=1, value=30)
        peso = col2.number_input("Peso (kg)", min_value=10.0, value=70.0)
        altezza = col2.number_input("Altezza (cm)", min_value=50, value=170)
        
        st.subheader("Parametri Insulina")
        metodo_ic = st.radio("Come vuoi impostare il rapporto I:C?", ["Calcolo Automatico (basato su peso)", "Inserimento Manuale"])
        
        if metodo_ic == "Inserimento Manuale":
            ic_val = st.number_input("Rapporto IC (g/U)", min_value=1.0, value=10.0)
        else:
            tdi_stimato = peso * 0.45
            ic_val = round(500 / tdi_stimato, 1)
            st.info(f"IC stimato per il tuo peso: **{ic_val}**")

        if st.form_submit_button("Salva Profilo"):
            if nome:
                # Calcolo ISF standard (Regola del 1800 o 1650 a seconda della terapia)
                isf_val = round(1650 / (peso * 0.45), 1)
                dati = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza, "ic": ic_val, "isf": isf_val}
                st.session_state.user_data = dati
                salva_dati_locali(dati)
                st.rerun()

# --- 2. DASHBOARD PRINCIPALE ---
else:
    u = st.session_state.user_data
    try:
        st.image("banner.png")
    except:
        st.title(f"Benvenuto nella tua Dashboard, {u['nome']}! 👋")
    
    tab_dash, tab_pasti, tab_trend = st.tabs(["📊 Dashboard CGM", "🍽️ Calcolatore Pasti", "📈 Storico e Analisi"])

    # --- TAB 1: DASHBOARD SENSORE ---
    with tab_dash:
        st.subheader("Carica dati Sensore (Libre/Dexcom)")
        uploaded_file = st.file_uploader("Seleziona file CSV del sensore", type="csv")
        if uploaded_file and utils_presente:
            try:
                df_sensor = elabora_dati(pd.read_csv(uploaded_file, skiprows=1))
                m = calcola_metriche(df_sensor, 70, 180)
                c1, c2, c3 = st.columns(3)
                c1.metric("Time in Range", f"{m['TIR']:.1f}%")
                c2.metric("Ipoglicemie", f"{m['IPO']:.1f}%")
                c3.metric("Iperglicemie", f"{m['IPER']:.1f}%")
                
                for s in genera_suggerimenti(df_sensor):
                    st.info(s)
            except Exception as e:
                st.error(f"Errore nella lettura del file: {e}")

    # --- TAB 2: CALCOLATORE PASTI ---
    with tab_pasti:
        st.subheader("💉 Calcolo del Bolo")
        
        # Parametri in tempo reale
        col_g1, col_g2 = st.columns(2)
        glicemia_pre = col_g1.number_input("Glicemia attuale (mg/dL)", min_value=20, max_value=600, value=120)
        trend = col_g2.selectbox("Trend Glicemico", ["➡️ Stabile", "↗️ Salita lenta", "⬆️ Salita veloce", "↘️ Discesa lenta", "⬇️ Discesa veloce"])
        
        st.divider()
        scelta_metodo = st.radio("Come vuoi inserire il pasto?", ["📸 Foto AI", "🔍 Cerca nel Database"], horizontal=True)

        # METODO A: FOTO AI
        if scelta_metodo == "📸 Foto AI":
            img_file = st.file_uploader("Scatta o carica foto del pasto", type=["jpg", "png", "jpeg"])
            if img_file:
                image = Image.open(img_file)
                st.image(image, width=400, caption="Piatto da analizzare")
                if st.button("🚀 ANALIZZA CON AI", type="primary"):
                    if not api_key:
                        st.error("Devi configurare la tua API_KEY nei secrets per usare l'intelligenza artificiale.")
                    else:
                        with st.spinner("Gemini sta analizzando il piatto..."):
                            try:
                                model = genai.GenerativeModel('gemini-2.0-flash')
                                prompt = f"""
                                Sei un nutrizionista esperto. Analizza questo pasto per un diabetico.
                                Paziente: IC={u['ic']} g/U, Glicemia={glicemia_pre} mg/dL.
                                1. Elenca gli ingredienti visibili.
                                2. Stima i carboidrati totali (CHO).
                                3. Calcola il bolo per i carboidrati (CHO / {u['ic']}).
                                Sii conciso e preciso.
                                """
                                response = model.generate_content([prompt, image])
                                st.markdown("### 🤖 Analisi AI:")
                                st.info(response.text)
                                st.caption("Usa la stima dei carboidrati qui sopra e inseriscila manualmente per sicurezza, oppure aggiungi gli alimenti dal database.")
                            except Exception as e:
                                st.error(f"Errore di connessione a Gemini: {e}")

        # METODO B: DATABASE MANUALE
        else:
            # Caricamento sicuro del DB
            try:
                with open('alimenti.json', 'r') as f: 
                    db_alimenti = json.load(f)
            except: 
                # Database di emergenza se il file manca
                db_alimenti = {"Pane comune": 50, "Pasta scondita": 70, "Mela": 15, "Pizza margherita": 33, "Riso bianco": 78}
            
            search = st.text_input("🔍 Cerca alimento...").lower()
            items = [{"Alimento": k, "CHO_100g": v} for k, v in db_alimenti.items() if search in k.lower()]
            
            df_db = pd.DataFrame(items)
            
            if not df_db.empty:
                df_db.insert(0, "Seleziona", False)
                df_db["Peso_g"] = 100.0 # Valore di default
                
                # Tabella interattiva corretta (Permette la modifica del peso)
                edited = st.data_editor(
                    df_db, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Seleziona": st.column_config.CheckboxColumn("Aggiungi", default=False),
                        "Alimento": st.column_config.TextColumn("Alimento", disabled=True),
                        "CHO_100g": st.column_config.NumberColumn("CHO (per 100g)", disabled=True),
                        "Peso_g": st.column_config.NumberColumn("La tua porzione (g)", min_value=1.0, step=10.0)
                    }
                )
                
                if st.button("➕ Aggiungi al Pasto Corrente"):
                    sel = edited[edited["Seleziona"] == True]
                    if not sel.empty:
                        st.session_state.pasti_correnti.extend(sel.to_dict('records'))
                        st.rerun()
                    else:
                        st.warning("Seleziona almeno un alimento spuntando la casella.")
            else:
                st.info("Nessun alimento trovato con questo nome.")

        # RIEPILOGO E CALCOLO FINALE (Visibile per entrambi i metodi se ci sono cibi)
        if st.session_state.pasti_correnti:
            st.markdown("---")
            st.subheader("📋 Il tuo pasto attuale:")
            df_pasto = pd.DataFrame(st.session_state.pasti_correnti)
            
            # Calcolo carboidrati per porzione e visualizzazione tabella pulita
            df_pasto["CHO_Porzione"] = (df_pasto["CHO_100g"] * df_pasto["Peso_g"] / 100).round(1)
            st.table(df_pasto[["Alimento", "Peso_g", "CHO_Porzione"]])
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("🗑️ Svuota Vassoio", key="clear_tray"):
                    st.session_state.pasti_correnti = []
                    st.rerun()
            
            with col_btn2:
                if st.button("💉 CALCOLA BOLO FINALE E SALVA", type="primary"):
                    tot_cho = df_pasto["CHO_Porzione"].sum()
                    target = 120
                    
                    # Calcoli
                    dose_cho = tot_cho / u['ic']
                    correzione = (glicemia_pre - target) / u['isf'] if glicemia_pre > target else 0
                    adj = {"⬆️ Salita veloce": 1.0, "↗️ Salita lenta": 0.5, "↘️ Discesa lenta": -0.5, "⬇️ Discesa veloce": -1.0}.get(trend, 0)
                    
                    totale = max(0, round(dose_cho + correzione + adj, 1))
                    
                    st.success(f"### 💉 Dose Suggerita: {totale} Unità")
                    st.write(f"**Dettaglio:** {round(dose_cho,1)}U (Cibo) + {round(correzione,1)}U (Correzione) + {adj}U (Trend)")
                    
                    # Salvataggio nel log
                    ora_attuale = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_row = pd.DataFrame([{
                        "Data_Ora": ora_attuale, 
                        "CHO_Totali": tot_cho, 
                        "Glicemia_Pre": glicemia_pre, 
                        "Dose_U": totale,
                        "Trend": trend
                    }])
                    new_row.to_csv(LOG_PASTI_FILE, mode='a', header=not os.path.exists(LOG_PASTI_FILE), index=False)
                    
                    # Pulizia dopo il calcolo
                    st.session_state.pasti_correnti = []
                    st.balloons()

    # --- TAB 3: STORICO E TREND ---
    with tab_trend:
        st.subheader("📖 Diario Iniezioni")
        if os.path.exists(LOG_PASTI_FILE):
            df_log = pd.read_csv(LOG_PASTI_FILE)
            st.dataframe(df_log, use_container_width=True)
            
            # Grafico a dispersione per vedere la relazione Carboidrati / Bolo
            try:
                fig = px.scatter(
                    df_log, 
                    x="CHO_Totali", 
                    y="Dose_U", 
                    color="Glicemia_Pre",
                    size="Dose_U", 
                    title="Relazione Carboidrati / Unità di Insulina",
                    labels={"CHO_Totali": "Carboidrati Mangiati (g)", "Dose_U": "Insulina Iniettata (U)", "Glicemia_Pre": "Glicemia"}
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.write("Dati insufficienti per generare il grafico. Inserisci altri pasti!")
            
            if st.button("🗑️ Svuota Diario Pasti"):
                os.remove(LOG_PASTI_FILE)
                st.rerun()
        else:
            st.info("Nessun bolo salvato nel diario finora. Fai il tuo primo calcolo nella scheda 'Calcolatore Pasti'!")
