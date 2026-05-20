import requests
from requests_ntlm import HttpNtlmAuth
import pandas as pd
import io
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPORT_URL = "https://poz-sql-111.allegrogroup.internal/ReportServer?/rogvisio/we-wy%20magazyn%20adamow&rs:Command=Render&rs:Format=CSV"

# ==========================================
# WPISZ SWOJE DANE LOGOWANIA DO SIECI FIRMOWEJ
# ==========================================
DOMAIN = "allegrogroup" 
USERNAME = "adrian.kuczynski"
PASSWORD = "Mojehaslojestok00!"
# ==========================================

def fetch_gate_data():
    print("⏳ Logowanie do serwera raportów (NTLM)...")
    
    try:
        # Używamy jawnego logowania NTLM (Domena\Użytkownik + Hasło)
        auth = HttpNtlmAuth(f"{DOMAIN}\\{USERNAME}", PASSWORD)
        
        response = requests.get(REPORT_URL, auth=auth, verify=False)
        
        if response.status_code == 200:
            print("✅ Udało się! Jesteśmy w środku.")
            
            # Wrzucamy pobrany tekst CSV bezpośrednio do tabeli Pandas
            df = pd.read_csv(io.StringIO(response.text))
            
            print("\nOto podgląd Twoich danych z bramek:")
            print(df.head())
            print(f"\nŁączna liczba wierszy w raporcie: {len(df)}")
            
        elif response.status_code == 401:
            print("❌ Błąd 401: Serwer nadal odrzuca logowanie. Sprawdź, czy nazwa domeny, login i hasło są w 100% poprawne.")
        elif response.status_code == 404:
            print("❌ Błąd 404: Raport nie istnieje pod tym adresem (zła ścieżka).")
        else:
            print(f"❌ Inny błąd. Kod HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Błąd w kodzie: {e}")

if __name__ == "__main__":
    fetch_gate_data()