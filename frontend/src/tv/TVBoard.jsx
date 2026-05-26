import React, { useState, useEffect, useRef } from 'react';
import api from '../api'; 
import './TVBoard.css';

// ---------------------------------------------------------
// Komponent: Zegar Cyfrowy
// ---------------------------------------------------------
const DigitalClock = ({ time }) => {
  const pad = (num) => num.toString().padStart(2, '0');
  
  return (
    <div className="flex items-center text-5xl font-black font-mono text-white tracking-widest drop-shadow-lg">
      <span>{pad(time.getHours())}</span>
      <span className="text-slate-600 mx-1 mb-1 animate-pulse">:</span>
      <span>{pad(time.getMinutes())}</span>
      <span className="text-slate-600 mx-1 mb-1 animate-pulse">:</span>
      <span className="text-indigo-500">{pad(time.getSeconds())}</span>
    </div>
  );
};

// ---------------------------------------------------------
// Komponent: Główna Tablica TV
// ---------------------------------------------------------
const TVBoard = () => {
  const [activeScans, setActiveScans] = useState([]);
  const [time, setTime] = useState(new Date());

  const previousLogins = useRef(new Set());
  const isFirstLoad = useRef(true);

  // KONFIGURACJA
  const SHOW_FOR_MS = 3000; // Czas wyświetlania: 3 sekundy

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
        const response = await api.get('/plan/tv-board');
        const currentWorkers = response.data || [];

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

        // AKTUALIZACJA PAMIĘCI
        previousLogins.current = new Set(currentWorkers.map(w => w.login));

      } catch (error) {
        console.error('Błąd pobierania danych TV Board:', error);
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
        
        <div className="tv-clock-wrapper">
          <DigitalClock time={time} />
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