import pandas as pd
import json
import os

def elabora_dati(df):
    # Il file Libre richiede attenzione alle date e alla pulizia delle celle vuote
    df['Timestamp'] = pd.to_datetime(df['Timestamp del dispositivo'], dayfirst=True)
    df = df.sort_values('Timestamp')
    df['Glucosio'] = pd.to_numeric(df['Storico del glucosio mg/dL'], errors='coerce')
    df['Carboidrati (grammi)'] = pd.to_numeric(df['Carboidrati (grammi)'], errors='coerce').fillna(0)
    return df

def suggerisci_aggiustamento_ic(df_log):
    suggerimenti = []
    
    # Controllo di sicurezza: la colonna esiste?
    if 'Rapporto_IC' not in df_log.columns:
        return ["⚠️ Dati insufficienti per l'analisi: la colonna 'Rapporto_IC' manca nel diario."]
    
    # Raggruppiamo per tipo di pasto
    for tipo in df_log['Tipo_Pasto'].unique():
        subset = df_log[df_log['Tipo_Pasto'] == tipo]
        if len(subset) >= 3: 
            # Prendiamo l'ultimo rapporto usato per quel pasto
            ultimo_ic = subset['Rapporto_IC'].iloc[-1]
            suggerimenti.append(f"💡 Analisi per {tipo}: Stai usando un rapporto I:C di 1:{ultimo_ic}. Se noti iperglicemia costante post-pasto, valuta con il tuo medico una riduzione (es. 1:{int(ultimo_ic)-1}).")
    
    if not suggerimenti:
        return ["Registra almeno 3 pasti per ogni categoria per attivare i suggerimenti."]
    return suggerimenti

def calcola_iob(df, ora_attuale, durata_azione_insulina=4):
    """
    Calcola l'insulina ancora attiva (IOB) basandosi sull'ultima dose.
    """
    # Filtra solo i boli di Novorapid nelle ultime 'durata_azione_insulina' ore
    tempo_limite = ora_attuale - pd.Timedelta(hours=durata_azione_insulina)
    boli_recenti = df[(df['Timestamp'] > tempo_limite) & (df['Insulina ad azione rapida (unità)'] > 0)]
    
    iob = 0
    for _, bolo in boli_recenti.iterrows():
        tempo_trascorso = (ora_attuale - bolo['Timestamp']).total_seconds() / 3600
        # Decadimento lineare semplificato (più sicuro e facile da gestire)
        frazione_rimanente = 1 - (tempo_trascorso / durata_azione_insulina)
        iob += bolo['Insulina ad azione rapida (unità)'] * max(0, frazione_rimanente)
        
    return iob

def calcola_metriche(df, target_min, target_max):
    valori = df['Glucosio'].dropna()
    totale = len(valori)
    tir = (len(valori[(valori >= target_min) & (valori <= target_max)]) / totale) * 100
    ipo = (len(valori[valori < target_min]) / totale) * 100
    iper = (len(valori[valori > target_max]) / totale) * 100
    return {"TIR": tir, "IPO": ipo, "IPER": iper}

def genera_suggerimenti(df):
    notte = df[df['Timestamp'].dt.hour.isin([0, 1, 2, 3, 4, 5])]
    media_notte = notte['Glucosio'].mean()
    suggerimenti = []
    if media_notte > 140:
        suggerimenti.append("📈 Basale: Media notturna alta. Valutare aumento Toujeo.")
    elif media_notte < 80:
        suggerimenti.append("📉 Basale: Media notturna bassa. Valutare riduzione Toujeo.")
    return suggerimenti

# Carica il database alimenti
def get_carbs(nome_alimento):
    with open('alimenti.json', 'r') as f:
        db = json.load(f)
    return db.get(nome_alimento, 0)

def calcola_bolo_suggerito(alimento, rapporto_ic):
    carbs = get_carbs(alimento)
    # Esempio: se rapporto_ic è 1:10, significa 1 unità ogni 10g di carboidrati
    dose = carbs / rapporto_ic
    return dose

def analisi_notturna(df):
    # Identifica le ore notturne tipiche per la Toujeo (es. 00:00 - 06:00)
    notte = df[df['Timestamp'].dt.hour.isin([0, 1, 2, 3, 4, 5])]
    media_notturna = notte['Glucosio'].mean()
    
    return media_notturna

def analizza_efficacia_bolo(df, soglia_iper=180):
    """
    Analizza cosa succede dopo l'assunzione di carboidrati.
    """
    # Filtra solo i momenti in cui hai mangiato
    pasti = df[df['Carboidrati (grammi)'] > 0]
    
    report = []
    for index, pasto in pasti.iterrows():
        # Prendi i dati glicemici nelle 2 ore successive
        time_limit = pasto['Timestamp'] + pd.Timedelta(hours=2)
        trend_post_pasto = df[(df['Timestamp'] > pasto['Timestamp']) & 
                              (df['Timestamp'] <= time_limit)]
        
        max_glicemia = trend_post_pasto['Glucosio'].max()
        
        if max_glicemia > soglia_iper:
            report.append(f"Attenzione: dopo il pasto delle {pasto['Timestamp'].time()}, la glicemia è salita a {max_glicemia} mg/dL.")
            
    return report

