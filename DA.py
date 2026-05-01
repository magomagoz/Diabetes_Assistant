import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
from datetime import datetime
import pandas as pd
#import plotly.express as px
import plotly.graph_objects as go

# Prova a importare le utils (assicurati che il file utils.py esista)
try:
    from utils import (
        elabora_dati, calcola_metriche, genera_suggerimenti, 
        suggerisci_aggiustamento_ic 
    )
except ImportError:
    st.error("File utils.py non trovato. Alcune funzioni di analisi non saranno disponibili.")

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
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
    
    if st.session_state.user_data:
        st.write(f"Utente: **{st.session_state.user_data.get('nome')}**")
        st.write(f"Rapporto IC: **{st.session_state.user_data.get('ic')}**")
        if st.button("🗑️ Reset Totale Profilo"):
            if os.path.exists(USER_DATA_FILE): os.remove(USER_DATA_FILE)
            if os.path.exists(LOG_PASTI_FILE): os.remove(LOG_PASTI_FILE)
            st.session_state.user_data = None
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
            # Formula empirica basata su TDI (Total Daily Insulin) stimata dal peso
            tdi_stimato = peso * 0.45
            ic_val = round(500 / tdi_stimato, 1)
            st.info(f"IC stimato per il tuo peso: {ic_val}")

        if st.form_submit_button("Salva Profilo"):
            if nome:
                dati = {"nome": nome, "eta": eta, "peso": peso, "altezza": altezza, "ic": ic_val, "isf": round(1650/(peso*0.45),1)}
                st.session_state.user_data = dati
                salva_dati_locali(dati)
                st.rerun()

# --- 2. DASHBOARD PRINCIPALE ---
else:
    u = st.session_state.user_data
    st.image("banner.png")
    
    tab_dash, tab_pasti, tab_trend = st.tabs(["📊 Dashboard CGM", "🍽️ Calcolatore Pasti", "📈 Storico e Analisi"])

    # TAB DASHBOARD: Caricamento dati sensore
    with tab_dash:
        st.subheader("Carica dati Sensore (Libre/Dexcom)")
        uploaded_file = st.file_uploader("Seleziona file CSV del sensore", type="csv")
        if uploaded_file:
            df_sensor = elabora_dati(pd.read_csv(uploaded_file, skiprows=1))
            m = calcola_metriche(df_sensor, 70, 180)
            c1, c2, c3 = st.columns(3)
            c1.metric("Time in Range", f"{m['TIR']:.1f}%")
            c2.metric("Ipoglicemie", f"{m['IPO']:.1f}%")
            c3.metric("Iperglicemie", f"{m['IPER']:.1f}%")
            
            for s in genera_suggerimenti(df_sensor):
                st.info(s)

    # TAB PASTI: Il cuore dell'app (AI + Manuale)
    with tab_pasti:
        st.subheader("💉 Calcolo del Bolo")
        
        # Parametri in tempo reale
        col_g1, col_g2 = st.columns(2)
        glicemia_pre = col_g1.number_input("Glicemia attuale (mg/dL)", value=120)
        trend = col_g2.selectbox("Trend", ["➡️ Stabile", "↗️ Salita lenta", "⬆️ Salita veloce", "↘️ Discesa lenta", "⬇️ Discesa veloce"])
        
        scelta_metodo = st.radio("Come vuoi inserire il pasto?", ["📸 Foto AI", "🔍 Cerca nel Database"], horizontal=True)

        # --- METODO A: FOTO AI ---
        if scelta_metodo == "📸 Foto AI":
            img_file = st.file_uploader("Scatta o carica foto", type=["jpg", "png", "jpeg"])
            if img_file:
                image = Image.open(img_file)
                st.image(image, width=300)
                if st.button("🚀 ANALIZZA CON AI"):
                    with st.spinner("Gemini sta analizzando il piatto..."):
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        prompt = f"Analizza foto. Estrai Carboidrati totali. Paziente IC: {u['ic']}. Glicemia: {glicemia_pre}. Fornisci stima CHO e Bolo."
                        response = model.generate_content([prompt, image])
                        st.markdown(response.text)

        # --- METODO B: DATABASE MANUALE ---
        else:
            try:
                with open('alimenti.json', 'r') as f: db_alimenti = json.load(f)
            except: db_alimenti = {"Pane": 50, "Pasta": 70, "Mela": 15, "Pizza": 100}
            
            search = st.text_input("Cerca alimento...").lower()
            items = [{"Alimento": k, "CHO_100g": v} for k, v in db_alimenti.items() if search in k.lower()]
            
            df_db = pd.DataFrame(items)
            df_db.insert(0, "Seleziona", False)
            df_db["Peso_g"] = 100.0
            
            edited = st.data_editor(df_db, hide_index=True, use_container_width=True)
            
            if st.button("➕ Aggiungi al Pasto"):
                sel = edited[edited["Seleziona"] == True]
                st.session_state.pasti_correnti.extend(sel.to_dict('records'))
                st.rerun()

        # Riepilogo e Calcolo Finale
        if st.session_state.pasti_correnti:
            st.divider()
            st.write("📋 **Pasto Corrente:**")
            df_pasto = pd.DataFrame(st.session_state.pasti_correnti)
            st.table(df_pasto[["Alimento", "Peso_g", "CHO_100g"]])
            
            if st.button("💉 CALCOLA BOLO FINALE"):
                tot_cho = (df_pasto["CHO_100g"] * df_pasto["Peso_g"] / 100).sum()
                target = 120
                dose_cho = tot_cho / u['ic']
                correzione = (glicemia_pre - target) / u['isf'] if glicemia_pre > target else 0
                
                # Aggiustamento Trend
                adj = {"⬆️ Salita veloce": 1.0, "↗️ Salita lenta": 0.5, "↘️ Discesa lenta": -0.5, "⬇️ Discesa veloce": -1.0}.get(trend, 0)
                
                totale = max(0, round(dose_cho + correzione + adj, 1))
                
                st.success(f"### Dose Suggerita: {totale} U")
                st.info(f"Dettaglio: {round(dose_cho,1)}U (Cibo) + {round(correzione,1)}U (Corr) + {adj}U (Trend)")
                
                # Salvataggio su LOG
                new_row = pd.DataFrame([{"Data": datetime.now(), "CHO": tot_cho, "Glicemia": glicemia_pre, "Bolo": totale}])
                new_row.to_csv(LOG_PASTI_FILE, mode='a', header=not os.path.exists(LOG_PASTI_FILE), index=False)
                st.session_state.pasti_correnti = []

    # TAB TREND: Storico e grafici
    with tab_trend:
        st.subheader("📖 Diario Pasti")
        if os.path.exists(LOG_PASTI_FILE):
            df_log = pd.read_csv(LOG_PASTI_FILE)
            st.dataframe(df_log, use_container_width=True)
            
            fig = px.scatter(df_log, x="CHO", y="Bolo", size="Glicemia", title="Relazione Carboidrati / Insulina")
            st.plotly_chart(fig)
            
            if st.button("🗑️ Svuota Diario"):
                os.remove(LOG_PASTI_FILE)
                st.rerun()
        else:
            st.write("Nessun dato salvato.")
