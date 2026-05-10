import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (
    elabora_dati, calcola_metriche, genera_suggerimenti, 
    suggerisci_aggiustamento_ic 
)

# --- COSTANTI E FUNZIONI DI SISTEMA ---
# Unificato l'uso del file di salvataggio per evitare doppioni tra "profilo_utente.json" e "profilo.json"
USER_DATA_FILE = "profilo.json"

def salva_dati_locali(dati):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(dati, f)

def carica_dati_locali():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                return json.load(f)
        except: 
            return None
    return None

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Diabete AI Helper", layout="wide", page_icon="💉")

st.image("banner.png")

# Inizializzazione Session State
if 'user_data' not in st.session_state:
    st.session_state.user_data = carica_dati_locali()

if 'pasti_correnti' not in st.session_state:
    st.session_state.pasti_correnti = []

# CSS per bottoni uniformi
st.markdown("""
    <style>
    div.stButton > button, div.stDownloadButton > button, div.stFileUploader > section {
        background-color: #f0f2f6 !important;
        border: 1px solid #d3d3d3 !important;
        border-radius: 5px !important;
        color: #31333F !important;
        width: 100% !important;
        height: 45px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: CONFIGURAZIONE AI ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    api_key = st.secrets.get("API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
    
    st.divider()
    if st.session_state.user_data:
        st.write(f"Utente: **{st.session_state.user_data.get('nome', '')}**")
        if st.button("🗑️ Reset Rapido Profilo"):
            if os.path.exists(USER_DATA_FILE):
                os.remove(USER_DATA_FILE)
            st.session_state.user_data = None
            st.rerun()

# --- 1. REGISTRAZIONE ---
if st.session_state.user_data is None:
    #st.title("🥗 Benvenuto su AI Bolus")
    st.info("Inserisci i tuoi dati per iniziare. Verranno salvati solo sul tuo dispositivo.")
    
    with st.form("reg_form"):
        st.subheader("Dati Personali")
        colA, colB = st.columns(2)
        nome = colA.text_input("Nome")
        sesso = colB.selectbox("Sesso", ["Donna", "Uomo"])
        eta = colA.number_input("Età", min_value=1, value=30)
        peso = colB.number_input("Peso (kg)", min_value=10.0, value=70.0, step=0.5)
        altezza = colA.number_input("Altezza (cm)", min_value=50, value=170)
        basale = colB.number_input("Unità di Basale (es. Toujeo) che fai ora", min_value=1, value=33)
        
        st.subheader("Parametri Diabete")
        conosco_ic = st.radio("Conosci i tuoi parametri (IC e ISF)?", ["Sì", "No (Calcolali per me dal peso)"])
        
        if conosco_ic == "Sì":
            rapporto_ic = st.number_input("Rapporto IC (g/U)", min_value=1.0, value=10.0)
            isf = st.number_input("ISF (Sensibilità)", min_value=1.0, value=40.0)
        else:
            tdi_stimato = peso * 0.45
            rapporto_ic = 500 / tdi_stimato
            isf = 1650 / tdi_stimato
            st.info(f"Parametri stimati - **IC:** {rapporto_ic:.1f} | **ISF:** {isf:.1f}")
        
        if st.form_submit_button("Salva Profilo e Inizia"):
            if nome:
                dati = {
                    "nome": nome, "sesso": sesso, "eta": eta, "peso": peso, 
                    "altezza": altezza, "basale": basale, "ic": round(rapporto_ic, 1), 
                    "isf": round(isf, 1)
                }
                st.session_state.user_data = dati
                salva_dati_locali(dati)
                st.success("Profilo creato con successo!")
                st.rerun()

# --- 2. DASHBOARD OPERATIVA ---
else:
    u = st.session_state.user_data
    st.title(f"Ciao {u.get('nome', 'Utente')}! 👋")

    # TABS
    tab_profilo, tab1, tab2, tab3 = st.tabs(["👤 **Profilo**", "📊 **Dashboard**", "🍽️ **Calcolatore Pasti**", "📈 **Analisi Trend**"])

    with tab_profilo:
        st.subheader("👤 Il tuo Profilo Clinico")
        st.write("Aggiorna i tuoi dati. L'app li userà per suggerirti i parametri di partenza per i calcoli del bolo.")
        
        with st.form("form_profilo_edit"):
            colA, colB = st.columns(2)
            nome_edit = colA.text_input("Nome", value=u.get("nome", ""))
            sesso_edit = colB.selectbox("Sesso", ["Donna", "Uomo"], index=0 if u.get("sesso", "Donna") == "Donna" else 1)
            eta_edit = colA.number_input("Età", min_value=1, max_value=120, value=int(u.get("eta", 30)))
            peso_edit = colB.number_input("Peso (kg)", min_value=20.0, max_value=200.0, value=float(u.get("peso", 70.0)), step=0.5)
            altezza_edit = colA.number_input("Altezza (cm)", min_value=100, max_value=250, value=int(u.get("altezza", 170)))
            basale_edit = colB.number_input("Unità di Basale che fai ora", min_value=1, value=int(u.get("basale", 32)))
            
            ic_edit = colA.number_input("Rapporto I:C (es. 10 = 1U ogni 10g)", value=float(u.get("ic", 10.0)), step=0.5)
            isf_edit = colB.number_input("ISF (Sensibilità)", value=float(u.get("isf", 40.0)), step=1.0)
            
            salva_profilo = st.form_submit_button("💾 Aggiorna Profilo")
            
            if salva_profilo:
                nuovo_profilo = {
                    "nome": nome_edit, "sesso": sesso_edit, "eta": eta_edit, 
                    "peso": peso_edit, "altezza": altezza_edit, "basale": basale_edit, 
                    "ic": ic_edit, "isf": isf_edit
                }
                st.session_state.user_data = nuovo_profilo
                salva_dati_locali(nuovo_profilo)
                st.success(f"✅ Profilo di {nome_edit} aggiornato con successo!")
                st.rerun()

        st.markdown("---")
        st.subheader("⚠️ Area di Manutenzione")
                
        with st.expander("🗑️ Cancella tutti i dati dell'app (Hard Reset)"):
            st.warning("Questa operazione eliminerà permanentemente il tuo profilo e lo storico dei pasti.")
            conferma_text = st.text_input("Scrivi 'ELIMINA' per confermare", key="check_elimina")
                    
            if st.button("Procedi con la cancellazione", key="btn_elimina_definitivo"):
                if conferma_text == "ELIMINA":
                    files_da_eliminare = ["log_pasti.csv", USER_DATA_FILE]
                    for file in files_da_eliminare:
                        if os.path.exists(file):
                           os.remove(file)
                    st.session_state.user_data = None
                    st.success("✅ Dati cancellati. Ricarico l'app...")
                    st.rerun() 
                else:
                   st.error("⚠️ Digita esattamente 'ELIMINA' nel campo sopra per sbloccare il tasto.")

    with tab1:
        with st.expander("📂 Clicca per caricare il file CSV (Sensore)"):
            uploaded_file = st.file_uploader("Seleziona file", type="csv", label_visibility="collapsed")

        if uploaded_file:
            df = elabora_dati(pd.read_csv(uploaded_file, skiprows=1))
            m = calcola_metriche(df, 70, 180)
            col1, col2, col3 = st.columns(3)
            col1.metric("**TIME IN RANGE**", f"{m['TIR']:.1f}%")
            col2.metric("**IPOGLICEMIE**", f"{m['IPO']:.1f}%")
            col3.metric("**IPERGLICEMIE**", f"{m['IPER']:.1f}%")
            
            st.subheader("🩺 Suggerimenti Clinici")
            for s in genera_suggerimenti(df):
                st.info(s)
                
    with tab2:
        
        # Input Glicemia
        glicemia_attuale = st.number_input("Inserisci la Glicemia attuale (mg/dL)", min_value=20, max_value=600, value=100)
        
        st.write("---")

        # Pulsante per Foto/Galleria gestito nativamente
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
                            Paziente: {u.get('nome', 'Utente')}, Rapporto IC: {u.get('ic', 10.0):.1f}.
                            Glicemia attuale: {glicemia_attuale} mg/dL.
                            
                            Analizza l'immagine:
                            1. Identifica gli alimenti.
                            2. Stima i carboidrati (CHO) totali.
                            3. Se la foto è illeggibile, scrivi chiaramente che la qualità è bassa.
                            4. Calcola il bolo per i pasti suggerito: (CHO totali / {u.get('ic', 10.0):.1f}).
                            """
                            
                            model = genai.GenerativeModel('gemini-2.0-flash')
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
     
        st.subheader("🍽️ Calcolatore Insulina")

        # Recupera direttamente dal session state (eliminata ri-lettura JSON superflua)
        default_ic = u.get("ic", 10.0)
        default_isf = u.get("isf", 40.0)

        with st.expander("⚙️ Parametri Personalizzati (Dal Profilo)"):
            st.write("Questi valori sono precompilati in base al tuo profilo, ma puoi modificarli per questo pasto.")
            col_p1, col_p2 = st.columns(2)
            ic_calc = col_p1.number_input("Rapporto I:C", value=float(default_ic), step=0.5, key="ic_calc_pasto")
            isf_calc = col_p2.number_input("ISF (Fattore Sensibilità)", value=float(default_isf), step=1.0, key="isf_calc_pasto")
            target_glicemico = col_p1.number_input("Target Glicemia (mg/dL)", value=150)

        col_a, col_b, col_c, col_d = st.columns([2, 2, 3, 2])
        data_pasto = col_a.date_input("Data", datetime.now().date())
        ora_pasto = col_b.time_input("Ora", datetime.now().time())
        glicemia_pre = col_c.number_input("Glicemia attuale (mg/dL)", value=150, key="glicemia_pre_pasto")
        trend_libre = col_d.selectbox("Trend misurazione", ["➡️ Stabile", "↗️ Salita lenta", "⬆️ Salita veloce", "↘️ Discesa lenta", "⬇️ Discesa veloce"])

        tipo_pasto = st.selectbox("Momento della giornata", ["Colazione", "Pranzo", "Cena", "Spuntino"])

        try:
            with open('alimenti.json', 'r') as f:
                db_alimenti = json.load(f)
        except FileNotFoundError:
            db_alimenti = {"Pane": 50, "Pasta": 70, "Mela": 15}
        
        search_term = st.text_input("🔍 Cerca alimento nel database", "").lower()
        df_alimenti = pd.DataFrame(list(db_alimenti.items()), columns=["Alimento", "Carboidrati_Unitari"])
        
        if search_term:
            df_filtrato = df_alimenti[df_alimenti["Alimento"].str.lower().str.contains(search_term)]
        else:
            df_filtrato = df_alimenti
            
        df_display = df_filtrato.copy() 
        df_display.insert(0, "Seleziona", False)
        df_display["Quantità"] = 1.0 
        
        edited_df = st.data_editor(
            df_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Seleziona": st.column_config.CheckboxColumn("Seleziona", default=False),
                "Alimento": st.column_config.TextColumn("Alimento", disabled=True),
                "Quantità": st.column_config.NumberColumn("Quantità", min_value=0.1, step=0.5, format="%.1f"),
                "Carboidrati_Unitari": st.column_config.NumberColumn("Carboidrati unitari", disabled=True)
            }
        )
        
        if st.button("➕ Aggiungi alimento selezionato"):
            selezionati = edited_df[edited_df["Seleziona"] == True]
            if not selezionati.empty:
                st.session_state.pasti_correnti.extend(selezionati.to_dict('records'))
                st.rerun() 
            else:
                st.warning("Seleziona almeno un alimento nella tabella.")

        if st.session_state.pasti_correnti:
            df_accumulato = pd.DataFrame(st.session_state.pasti_correnti)
            st.write("📋 **Alimenti nel tuo pasto:**", df_accumulato)
            
            if st.button("💉 **Calcola Dose Finale e Salva**"):
                tot_carbs = (df_accumulato["Carboidrati_Unitari"] * df_accumulato["Quantità"]).sum()
                dose_carboidrati = tot_carbs / ic_calc
                
                modifica_trend = 0.0
                if trend_libre == "⬆️ Salita veloce": modifica_trend = 0.7
                elif trend_libre == "↗️ Salita lenta": modifica_trend = 0.3
                elif trend_libre == "↘️ Discesa lenta": modifica_trend = -0.3
                elif trend_libre == "⬇️ Discesa veloce": modifica_trend = -0.7
                    
                correzione = (glicemia_pre - target_glicemico) / isf_calc if glicemia_pre > target_glicemico else 0
                dose_totale = max(0, dose_carboidrati + correzione + modifica_trend)
                
                descrizione = ", ".join([f"{r['Alimento']} (x{r['Quantità']})" for _, r in df_accumulato.iterrows()])

                st.markdown("---")
                st.write(f"**Riepilogo {tipo_pasto}:**")
                st.write(f"📝 **Alimenti scelti:** {descrizione}")
                st.write(f"🍬 **Totale Carboidrati:** {tot_carbs} g")
                if correzione > 0:
                    st.write(f"✨ **Correzione glicemia:** +{correzione:.1f} U")
                
                st.markdown("---")
                st.success(f"💉 **Dose totale suggerita: {round(dose_totale, 1)} unità di Novorapid**")

                etichette = ['Carboidrati', 'Correzione Glicemia', 'Aggiustamento Trend']
                valori = [dose_carboidrati, correzione, max(0, modifica_trend)] 
                
                fig_bolo = go.Figure(data=[go.Pie(
                    labels=etichette, 
                    values=valori, 
                    hole=.4,
                    marker_colors=['#00CC96', '#EF553B', '#636EFA']
                )])
                
                fig_bolo.update_layout(
                    title_text="Ripartizione Unità Insulina",
                    annotations=[dict(text='Bolo', x=0.5, y=0.5, font_size=20, showarrow=False)],
                    showlegend=True,
                    height=350,
                    margin=dict(l=0, r=0, b=0, t=40)
                )
                st.plotly_chart(fig_bolo, use_container_width=True)
                    
                nuovo_record = pd.DataFrame([{
                    "Data_Ora": f"{data_pasto} {ora_pasto}",
                    "Glicemia_Pre": glicemia_pre,
                    "Trend": trend_libre,
                    "Tipo_Pasto": tipo_pasto,
                    "Alimenti": descrizione,
                    "Carboidrati_g": tot_carbs,
                    "Rapporto_IC": ic_calc,
                    "Dose_Suggerita_U": round(dose_totale, 1)
                }])
                    
                log_file = "log_pasti.csv"
                nuovo_record.to_csv(log_file, mode='a', header=not os.path.exists(log_file), index=False)
                st.info("💾 Pasto salvato con successo nel Diario!")

            if st.button("❌ Pulisci lista alimenti e fai un nuovo calcolo"):
                st.session_state.pasti_correnti = []
                st.rerun()
                
    with tab3:
        st.subheader("📈 Analisi Trend e Gestione Diario")
        col1, col2 = st.columns(2)

        with col1:
            uploaded_csv = st.file_uploader("📥 Importa CSV Diario", type="csv", label_visibility="collapsed")
            if uploaded_csv:
                with open("log_pasti.csv", "wb") as f:
                    f.write(uploaded_csv.getbuffer())
                st.rerun()
        
        with col2:
            if os.path.exists("log_pasti.csv"):
                with open("log_pasti.csv", "rb") as f:
                    st.download_button("📤 Esporta CSV", data=f, file_name="mio_diario.csv", mime="text/csv")
                
        if os.path.exists("log_pasti.csv"):
            df_log = pd.read_csv("log_pasti.csv")
            
            df_log.insert(0, "Azioni", False)
            
            st.write("**Il tuo storico pasti:**")
            edited_log = st.data_editor(
                df_log,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Azioni": st.column_config.CheckboxColumn("Elimina riga?", default=False)
                }
            )
                    
            if st.button("💾 Conferma eliminazione righe selezionate"):
                df_salvataggio = edited_log[edited_log["Azioni"] == False].drop(columns=["Azioni"])
                df_salvataggio.to_csv("log_pasti.csv", index=False)
                st.rerun()
                
            st.markdown("---")
            st.write("🔍 **Analizza l'impatto di un pasto**")
                
            df_analisi = pd.read_csv("log_pasti.csv")
            
            if not df_analisi.empty:
                opzioni_pasto = df_analisi['Data_Ora'] + " - " + df_analisi['Tipo_Pasto'] + " (" + df_analisi['Carboidrati_g'].astype(str) + "g carbs)"
                pasto_scelto = st.selectbox("Seleziona un pasto per vedere se il bolo ha funzionato:", opzioni_pasto)
                    
                if pasto_scelto and 'df' in locals() and not df.empty:
                    orario_str = pasto_scelto.split(" - ")[0]
                    orario_inizio = pd.to_datetime(orario_str)
                    orario_fine = orario_inizio + pd.Timedelta(hours=3)
                    
                    mask = (df['Timestamp'] >= orario_inizio) & (df['Timestamp'] <= orario_fine)
                    df_trend = df[mask]
                        
                    if not df_trend.empty:
                        fig = px.line(
                            df_trend, 
                            x='Timestamp', 
                            y='Glucosio', 
                            title=f"Curva Glicemica (3 ore) per {pasto_scelto.split(' - ')[1]}",
                            markers=True 
                        )
                            
                        fig.add_hline(y=180, line_dash="dash", line_color="red", annotation_text="Iper (180)")
                        fig.add_hline(y=70, line_dash="dash", line_color="orange", annotation_text="Ipo (70)")
                        fig.add_hrect(y0=70, y1=180, line_width=0, fillcolor="green", opacity=0.1)
                        
                        fig.update_layout(yaxis_title="Glucosio (mg/dL)", xaxis_title="Orario", hovermode="x unified")
                        st.plotly_chart(fig, use_container_width=True)
                            
                        picco_max = df_trend['Glucosio'].max()
                        orario_picco = df_trend.loc[df_trend['Glucosio'].idxmax(), 'Timestamp']
                            
                        colA, colB = st.columns(2)
                        colA.metric("Picco Glicemico Massimo", f"{picco_max} mg/dL")
                            
                        minuti_al_picco = int((orario_picco - orario_inizio).total_seconds() / 60)
                        colB.metric("Tempo per raggiungere il picco", f"{minuti_al_picco} min")
                        
                        if picco_max > 180:
                            st.warning(f"⚠️ Attenzione: Il picco ha superato il target di 180 mg/dL (è arrivato a {picco_max}).")
                            if minuti_al_picco < 60:
                                st.write("💡 **Analisi:** Il picco è avvenuto molto in fretta (meno di 1 ora). Probabilmente avevi bisogno di un **anticipo del bolo** (aspettare 15-20 min tra iniezione e pasto) o il cibo aveva un altissimo indice glicemico.")
                            else:
                                st.write("💡 **Analisi:** Il bolo (Novorapid) non è stato sufficiente a coprire i carboidrati. Valuta con il medico se ridurre il tuo rapporto I:C in questo orario della giornata.")
                        elif picco_max < 70:
                            st.error("🚨 Ipoglicemia post-prandiale rilevata. La dose di insulina era eccessiva per questo pasto.")
                        else:
                            st.success("✅ Ottimo lavoro! La glicemia è rimasta perfettamente nel target (Time in Range) dopo il pasto. La dose calcolata era esatta.")
                    else:
                        st.info("🕒 Nessun dato glicemico trovato nel sensore per le 3 ore successive a questo pasto. Assicurati che il CSV caricato copra questa data e orario.")
                elif 'df' not in locals() or df.empty:
                    st.error("Per visualizzare le curve dei pasti devi prima caricare il file CSV del sensore nel Tab 'Dashboard'.")
            
            st.markdown("---")
            st.write("🧠 **Analisi Intelligente del Rapporto I:C**")
            
            suggerimenti_ic = suggerisci_aggiustamento_ic(df_analisi)
            for s in suggerimenti_ic:
                st.warning(s)
        else:
            st.write("Nessun pasto registrato finora. Usa la tabella nel 'Calcolatore Pasti' per registrare il tuo primo pasto!")
