import os
import asyncio
import requests
from requests_ntlm import HttpNtlmAuth
import pandas as pd
import io
import urllib3
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 1. KONFIGURACJA POŁĄCZENIA SSRS
# =====================================================================
SSRS_USERNAME = os.getenv("SSRS_USERNAME")
SSRS_PASSWORD = os.getenv("SSRS_PASSWORD")
REPORT_URL = "https://poz-sql-111.allegrogroup.internal/ReportServer?/rogvisio/we-wy%20magazyn%20adamow&rs:Command=Render&rs:Format=CSV"

async def poll_gates_and_update(db: AsyncSession):
    print("🚀 [BRAMKA] Uruchamiam Agenta SSRS dla 'wejscie-magazyn'...")

    if not SSRS_USERNAME or not SSRS_PASSWORD:
        print("❌ [BRAMKA] Brak SSRS_USERNAME lub Password Agent zasypia.")
        while True:
            await asyncio.sleep(3600)

    auth = HttpNtlmAuth(SSRS_USERNAME, SSRS_PASSWORD)
    
    last_check_time = pd.Timestamp.now()

    while True:
        try:
            response = await asyncio.to_thread(requests.get, REPORT_URL, auth=auth, verify=False)
            
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                
                # ZABEZPIECZENIE 1: Usuwamy niewidoczne spacje z nazw kolumn
                df.columns = df.columns.str.strip()
                
                df = df.dropna(subset=['PersonNumber', 'LoggedOn'])
                df['LoggedOn'] = pd.to_datetime(df['LoggedOn'], format='%m/%d/%Y %I:%M:%S %p')
                
                # Zostawiamy WSZYSTKIE odbicia od ostatniego sprawdzenia (zarówno wejścia, jak i wyjścia)
                new_entries = df[df['LoggedOn'] > last_check_time]
                
                if not new_entries.empty:
                    print(f"🚨 [BRAMKA] Wykryto nowe ruchy: {len(new_entries)} odbić!")
                    
                    # Sortujemy po dacie, żeby najświeższe odbicie było na końcu
                    # i grupujemy po pracowniku, biorąc tylko jego OSTATNI ruch z tej paczki
                    latest_status = new_entries.sort_values('LoggedOn').groupby('PersonNumber').last().reset_index()
                    
                    for index, row in latest_status.iterrows():
                        worker_login = str(int(float(row['PersonNumber']))).strip()
                        
                        # Jeśli ostatnie odbicie to wejście -> True, w każdym innym wypadku (np. wyjscie) -> False
                        is_present = bool(row['LocationID'] == 'wejscie-magazyn')
                        
                        # --- KULOODPORNA LOGIKA ROZPOZNAWANIA BRAMEK ---
                        # ZMIANA: Szukamy kolumny 'Reader_Name' (z podkreślnikiem)
                        reader_name = str(row.get('Reader_Name', '')).strip().upper()
                        gate = 1  # Domyślny fallback w razie totalnego braku dopasowania
                        
                        if is_present:
                            # Szukamy tylko kluczowych fragmentów
                            if 'P1' in reader_name:
                                gate = 1
                            elif 'P2' in reader_name:
                                gate = 2
                            elif 'P3' in reader_name:
                                gate = 3
                            
                            # DEBUG do terminala
                            print(f"🔍 DEBUG ODBICIA: Login {worker_login} -> Czytnik: '{reader_name}' -> Przypisano BRAMKĘ: {gate}")
                        else:
                            gate = None  # Reset przy wyjściu
                        
                        update_stmt = text("""
                            UPDATE schedules 
                            SET is_present = :is_present,
                                gate = :gate
                            WHERE login = :login AND work_date = CURRENT_DATE
                        """)
                        
                        await db.execute(update_stmt, {
                            "is_present": is_present, 
                            "gate": gate, 
                            "login": worker_login
                        })
                    
                    await db.commit()
                    print(f"✅ [BRAMKA] Zaktualizowano statusy oraz numery bramek w bazie.")
                    
                    last_check_time = new_entries['LoggedOn'].max()

            else:
                print(f"❌ [BRAMKA] Błąd serwera raportów HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ [BRAMKA] Błąd podczas przetwarzania: {e}")
        
        await asyncio.sleep(15) # Skrócony czas dla płynności