import React, { useState, useEffect, useRef } from 'react';
import './TVBoard.css';

// ---------------------------------------------------------
// Komponent: Klasyczny Zegar Analogowy (Wskazówkowy)
// ---------------------------------------------------------
const AnalogClock = ({ time }) => {
  // Obliczenia kątów dla wskazówek
  const secondsDegrees = time.getSeconds() * 6; // 360 stopni / 60 sekund
  const minutesDegrees = time.getMinutes() * 6 + time.getSeconds() * 0.1;
  const hoursDegrees = (time.getHours() % 12) * 30 + time.getMinutes() * 0.5;

  return (
    <svg width="80" height="80" viewBox="0 0 100 100" style={{ filter: 'drop-shadow(0px 4px 6px rgba(0,0,0,0.5))' }}>
      {/* Tło i ramka zegara */}
      <circle cx="50" cy="50" r="48" stroke="#27272a" strokeWidth="4" fill="#09090b" />
      
      {/* Główne znaczniki godzin (12, 3, 6, 9) */}
      <line x1="50" y1="8" x2="50" y2="16" stroke="#a855f7" strokeWidth="4" strokeLinecap="round" />
      <line x1="50" y1="84" x2="50" y2="92" stroke="#52525b" strokeWidth="4" strokeLinecap="round" />
      <line x1="8" y1="50" x2="16" y2="50" stroke="#52525b" strokeWidth="4" strokeLinecap="round" />
      <line x1="84" y1="50" x2="92" y2="50" stroke="#52525b" strokeWidth="4" strokeLinecap="round" />

      {/* Wskazówka GODZINNA (Gruba, biała) */}
      <line 
        x1="50" y1="50" x2="50" y2="28" 
        stroke="#ffffff" strokeWidth="5" strokeLinecap="round" 
        transform={`rotate(${hoursDegrees} 50 50)`} 
      />
      
      {/* Wskazówka MINUTOWA (Średnia, szara) */}
      <line 
        x1="50" y1="50" x2="50" y2="15" 
        stroke="#a1a1aa" strokeWidth="4" strokeLinecap="round" 
        transform={`rotate(${minutesDegrees} 50 50)`} 
      />
      
      {/* Wskazówka SEKUNDOWA (Cienka, czerwona) */}
      <line 
        x1="50" y1="60" x2="50" y2="10" 
        stroke="#ef4444" strokeWidth="2" strokeLinecap="round" 
        transform={`rotate(${secondsDegrees} 50 50)`} 
      />
      
      {/* Środek zegara (Kropeczka) */}
      <circle cx="50" cy="50" r="4" fill="#ef4444" />
    </svg>
  );
};

// ---------------------------------------------------------
// Komponent: Główna Tablica TV
// ---------------------------------------------------------
const TVBoard = () => {
  // Lista osób aktualnie wyświetlanych na ekranie
  const [activeScans, setActiveScans] = useState([]);
  const [time, setTime] = useState(new Date());

  // previousLogins zamiast knownLogins - zapomina tych, co wyszli
  const previousLogins = useRef(new Set());
  const isFirstLoad = useRef(true);

  // KONFIGURACJA
  const API_URL = 'http://127.0.0.1:8002/api/plan/tv-board';
  const SHOW_FOR_MS = 3000; // ZMIANA: Czas wyświetlania skrócony do 3 sekund

  // 1. ZEGAR i USUWANIE STARYCH ODBIĆ Z EKRANU
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
      
      // Co sekundę sprawdzamy, czy czyjś czas na ekranie już minął
      setActiveScans((prev) => prev.filter(scan => scan.hideAt > Date.now()));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 2. POBIERANIE DANYCH I WYKRYWANIE "NOWYCH" ODBIĆ
  useEffect(() => {
    const fetchBoardData = async () => {
      try {
        const response = await fetch(API_URL);
        if (!response.ok) return;
        
        const currentWorkers = await response.json();

        // Pierwsze uruchomienie TV -> robimy zdjęcie bazy i nie wyzwalamy animacji
        if (isFirstLoad.current) {
          previousLogins.current = new Set(currentWorkers.map(w => w.login));
          isFirstLoad.current = false;
          return;
        }

        // Szukamy nowych twarzy (tych, których nie było na poprzednim "zdjęciu")
        const newArrivals = currentWorkers.filter(w => !previousLogins.current.has(w.login));

        if (newArrivals.length > 0) {
          const hideTime = Date.now() + SHOW_FOR_MS;
          const newScans = newArrivals.map(w => ({ worker: w, hideAt: hideTime }));
          
          // Dodajemy ich na początek kolejki na ekranie
          setActiveScans(prev => [...newScans, ...prev]);
        }

        // AKTUALIZACJA PAMIĘCI: Nadpisujemy starą pamięć nową listą.
        previousLogins.current = new Set(currentWorkers.map(w => w.login));

      } catch (error) {
        console.error('Błąd pobierania danych:', error);
      }
    };

    fetchBoardData(); // strzał na start
    const dataTimer = setInterval(fetchBoardData, 3000); // odpytywanie co 3 sekundy
    return () => clearInterval(dataTimer);
  }, []);

  // Wyciągamy maksymalnie 3 osoby, które aktualnie są na ekranie
  const currentDisplayWorkers = activeScans.map(s => s.worker).slice(0, 3);
  const slots = [0, 1, 2];

  return (
    <div className="tv-board-container">
      <div className="tv-header">
        <h1 className="tv-title">STATUS OPERACYJNY</h1>
        
        {/* Zamieniony zegar cyfrowy na analogowy */}
        <div className="tv-clock-wrapper">
          <AnalogClock time={time} />
        </div>
        
      </div>

      <div className="tv-gates-container animate-fade">
        {slots.map((index) => {
          const worker = currentDisplayWorkers[index];
          
          return (
            <div className={`tv-gate ${index !== 2 ? 'tv-border-right' : ''}`} key={index}>
              <h2 className="tv-gate-title">BRAMKA {index + 1}</h2>
              
              {worker ? (
                <div className="tv-worker-info animate-fade" key={worker.login + Date.now()}>
                  <p className="tv-login">{worker.login}</p>
                  <p className={`tv-task ${worker.task === 'unassigned' ? 'unassigned' : ''}`}>
                    {worker.task === 'unassigned' ? 'BRAK PRZYDZIAŁU' : worker.task}
                  </p>
                </div>
              ) : (
                <div className="tv-worker-empty">
                  <p>---</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TVBoard;