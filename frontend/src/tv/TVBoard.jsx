import React, { useState, useEffect, useRef } from 'react';
import api from '../api'; 
import './TVBoard.css'; // Możesz zostawić, jeśli masz tam jakieś własne style bazowe

// ---------------------------------------------------------
// Komponent: Zegar Cyfrowy (Wersja Jasna)
// ---------------------------------------------------------
const DigitalClock = ({ time }) => {
  const pad = (num) => num.toString().padStart(2, '0');
  
  return (
    <div className="flex items-center text-6xl font-black font-mono text-slate-800 tracking-widest drop-shadow-sm">
      <span>{pad(time.getHours())}</span>
      <span className="text-slate-300 mx-1 mb-2 animate-pulse">:</span>
      <span>{pad(time.getMinutes())}</span>
      <span className="text-slate-300 mx-1 mb-2 animate-pulse">:</span>
      <span className="text-indigo-600">{pad(time.getSeconds())}</span>
    </div>
  );
};

// ---------------------------------------------------------
// Komponent: Główna Tablica TV (Tryb Kremowy / Jasny)
// ---------------------------------------------------------
const TVBoard = () => {
  const [gateScans, setGateScans] = useState({ 1: null, 2: null, 3: null });
  const [time, setTime] = useState(new Date());

  const previousLogins = useRef(new Set());
  const isFirstLoad = useRef(true);

  // 1. ZEGAR (Usunęliśmy stąd czyszczenie bramek - loginy zostają na stałe!)
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
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
          previousLogins.current = new Set(currentWorkers.map(w => w.worker_login || w.login));
          isFirstLoad.current = false;
          return;
        }

        // Szukamy nowych twarzy
        const newArrivals = currentWorkers.filter(w => {
          const login = w.worker_login || w.login;
          return !previousLogins.current.has(login);
        });

        // Jeśli ktoś nowy się odbił, aktualizujemy jego bramkę
        if (newArrivals.length > 0) {
          setGateScans(prev => {
            const next = { ...prev };
            newArrivals.forEach(w => {
              const gateNum = w.gate || 1; 
              if ([1, 2, 3].includes(gateNum)) {
                next[gateNum] = w; // Nadpisujemy poprzednią osobę na tej bramce
              }
            });
            return next;
          });
        }

        // AKTUALIZACJA PAMIĘCI
        previousLogins.current = new Set(currentWorkers.map(w => w.worker_login || w.login));

      } catch (error) {
        console.error('Błąd pobierania danych TV Board:', error);
      }
    };

    fetchBoardData(); // strzał na start
    const dataTimer = setInterval(fetchBoardData, 3000); // odpytywanie co 3 sekundy
    return () => clearInterval(dataTimer);
  }, []);

  const gates = [1, 2, 3];

  return (
    <div className="min-h-screen bg-[#fdfbf7] p-10 flex flex-col font-sans">
      
      {/* NAGŁÓWEK */}
      <div className="flex justify-between items-center mb-12 border-b-2 border-slate-200/70 pb-8">
        <div>
          <h1 className="text-6xl font-black tracking-tighter text-slate-800">Here We GO! pysiaczku</h1>
          <p className="text-xl font-bold text-slate-400 mt-2 uppercase tracking-widest">Magazyn ADM-01</p>
        </div>
        <div className="bg-white px-8 py-4 rounded-3xl shadow-sm border border-slate-100">
          <DigitalClock time={time} />
        </div>
      </div>

      {/* KAFELKI BRAMEK */}
      <div className="flex flex-1 gap-8">
        {gates.map((gateNum) => {
          const worker = gateScans[gateNum];
          
          return (
            <div key={gateNum} className="flex-1 bg-white rounded-[3rem] shadow-xl shadow-slate-200/50 border border-slate-100 p-12 flex flex-col items-center justify-center relative overflow-hidden">
              
              {/* Górny pasek dekoracyjny */}
              <div className={`absolute top-0 left-0 w-full h-4 ${worker ? 'bg-indigo-500' : 'bg-slate-200'}`}></div>
              
              <h2 className="text-4xl font-bold text-slate-400 mb-12 tracking-widest uppercase">BRAMKA {gateNum}</h2>
              
              {worker ? (
                // Klucz to teraz sam login (bez Date.now), dzięki czemu komponent mignie tylko raz przy zmianie osoby
                <div className="flex flex-col items-center animate-in zoom-in duration-300" key={worker.worker_login || worker.login}>
                  <p className="text-[6rem] leading-none font-black text-slate-800 mb-8 tracking-tight">
                    {worker.worker_login || worker.login}
                  </p>
                  <p className={`px-8 py-3 rounded-full text-3xl font-bold uppercase tracking-widest shadow-sm ${worker.task === 'unassigned' ? 'bg-rose-50 text-rose-600 border border-rose-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
                    {worker.task === 'unassigned' ? 'BRAK PRZYDZIAŁU' : worker.task}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center opacity-40">
                  <p className="text-[6rem] leading-none font-black text-slate-300 mb-8">---</p>
                  <p className="px-8 py-3 rounded-full text-2xl font-bold uppercase tracking-widest bg-slate-100 text-slate-500">
                    OCZEKIWANIE
                  </p>
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