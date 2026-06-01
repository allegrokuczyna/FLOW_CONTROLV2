import React, { useState, useEffect, useRef } from 'react';
import api from '../api'; 
import './TVBoard.css';

// ---------------------------------------------------------
// Komponent: Zegar Cyfrowy
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
// Komponent: Główna Tablica TV (Tryb 3 Sloty / 7 Sekund / PIONOWO)
// ---------------------------------------------------------
const TVBoard = () => {
  const [gateScans, setGateScans] = useState({ 
    1: { slots: [null, null, null], pointer: 0 }, 
    2: { slots: [null, null, null], pointer: 0 }, 
    3: { slots: [null, null, null], pointer: 0 } 
  });
  
  const [time, setTime] = useState(new Date());

  const previousLogins = useRef(new Set());
  const isFirstLoad = useRef(true);

  const SHOW_FOR_MS = 7000; // 7 sekund widoczności

  const formatTaskName = (taskId) => {
    if (!taskId || taskId === 'unassigned') return 'ODPRAWA LIDERA';
    const taskMap = {
      'receiving': 'RECEIVING', 'putaway': 'PUTAWAY',
      'picking_mezz_m0': 'PICKING - MEZZ M0', 'picking_mezz_m1': 'PICKING - MEZZ M1',
      'picking_mezz_m2': 'PICKING - MEZZ M2', 'picking_rack': 'PICKING - RACK',
      'packing': 'PACKING', 'sorting': 'SORTING', 'task_cleaning': 'SPRZĄTANIE',
      'task_filler': 'WYPEŁNIACZ', 'task_waterspider': 'WATER-SPIDER',
      'task_training': 'SZKOLENIE', 'task_relocation': 'RELOKACJA'
    };
    return taskMap[taskId] || taskId.toUpperCase().replace(/_/g, ' ');
  };

  // 1. ZEGAR I CZYSZCZENIE PO 7 SEKUNDACH
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setTime(new Date(now));

      setGateScans(prev => {
        let changed = false;
        const next = { 
          1: { slots: [...prev[1].slots], pointer: prev[1].pointer },
          2: { slots: [...prev[2].slots], pointer: prev[2].pointer },
          3: { slots: [...prev[3].slots], pointer: prev[3].pointer }
        };

        [1, 2, 3].forEach(gateNum => {
          next[gateNum].slots.forEach((slot, idx) => {
            if (slot && slot.hideAt <= now) {
              next[gateNum].slots[idx] = null; 
              changed = true;
            }
          });
        });

        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 2. BŁYSKAWICZNE POBIERANIE DANYCH (CO 1 SEKUNDĘ)
  useEffect(() => {
    const fetchBoardData = async () => {
      try {
        const response = await api.get('/plan/tv-board');
        const currentWorkers = response.data || [];

        if (isFirstLoad.current) {
          previousLogins.current = new Set(currentWorkers.map(w => w.worker_login || w.login));
          isFirstLoad.current = false;
          
          if (currentWorkers.length > 0) {
            setGateScans(prev => {
              const next = { 
                1: { slots: [null, null, null], pointer: 0 },
                2: { slots: [null, null, null], pointer: 0 },
                3: { slots: [null, null, null], pointer: 0 }
              };

              currentWorkers.forEach(w => {
                const gateNum = parseInt(w.gate, 10) || 1; 
                if ([1, 2, 3].includes(gateNum)) {
                  const gateData = next[gateNum];
                  gateData.slots[gateData.pointer] = { ...w, hideAt: Date.now() + SHOW_FOR_MS };
                  gateData.pointer = (gateData.pointer + 1) % 3; 
                }
              });
              return next;
            });
          }
          return;
        }

        const newArrivals = currentWorkers.filter(w => {
          const login = w.worker_login || w.login;
          return !previousLogins.current.has(login);
        });

        if (newArrivals.length > 0) {
          setGateScans(prev => {
            const next = { 
              1: { slots: [...prev[1].slots], pointer: prev[1].pointer },
              2: { slots: [...prev[2].slots], pointer: prev[2].pointer },
              3: { slots: [...prev[3].slots], pointer: prev[3].pointer }
            };

            newArrivals.forEach(w => {
              const gateNum = parseInt(w.gate, 10) || 1; 
              if ([1, 2, 3].includes(gateNum)) {
                const gateData = next[gateNum];
                gateData.slots[gateData.pointer] = { ...w, hideAt: Date.now() + SHOW_FOR_MS };
                gateData.pointer = (gateData.pointer + 1) % 3; 
              }
            });
            return next;
          });
        }

        previousLogins.current = new Set(currentWorkers.map(w => w.worker_login || w.login));

      } catch (error) {
        console.error('Błąd pobierania danych TV Board:', error);
      }
    };

    fetchBoardData(); 
    const dataTimer = setInterval(fetchBoardData, 1000); 
    return () => clearInterval(dataTimer);
  }, []);

  const gates = [1, 2, 3];

  return (
    <div className="min-h-screen bg-[#fdfbf7] p-12 flex flex-col font-sans">
      
      {/* NAGŁÓWEK */}
      <div className="flex justify-between items-center mb-12 border-b-2 border-slate-200/70 pb-8">
        <div>
          <h1 className="text-7xl font-black tracking-tighter text-slate-800">Here We GO! pysiaczku</h1>
          <p className="text-2xl font-bold text-slate-400 mt-4 uppercase tracking-widest">Magazyn ADM-01</p>
        </div>
        <div className="bg-white px-10 py-5 rounded-3xl shadow-sm border border-slate-100">
          <DigitalClock time={time} />
        </div>
      </div>

      {/* KAFELKI BRAMEK */}
      <div className="flex flex-1 gap-10">
        {gates.map((gateNum) => {
          const gateData = gateScans[gateNum];
          
          return (
            <div key={gateNum} className="flex-1 bg-white rounded-[3rem] shadow-xl shadow-slate-200/50 border border-slate-100 p-8 xl:p-10 flex flex-col relative overflow-hidden">
              
              <div className={`absolute top-0 left-0 w-full h-4 ${gateData.slots.some(s => s !== null) ? 'bg-indigo-500' : 'bg-slate-200'}`}></div>
              
              <h2 className="text-5xl font-bold text-slate-400 mb-10 tracking-widest uppercase text-center mt-2">BRAMKA {gateNum}</h2>
              
              {/* LISTA 3 OSTATNICH ODBIĆ */}
              <div className="flex flex-col gap-8 flex-1 justify-start">
                {gateData.slots.map((worker, idx) => (
                  <div 
                    key={idx} 
                    // ZMIANA: flex-col (pionowo) zamiast justify-between, wyśrodkowanie (items-center) i większy padding
                    className={`w-full flex flex-col items-center justify-center py-8 px-4 rounded-[2rem] transition-all duration-300 gap-6 ${
                      worker ? 'bg-white border-2 border-indigo-100 shadow-lg scale-100' : 'bg-slate-50/30 border-2 border-dashed border-slate-200 opacity-40 scale-95'
                    }`}
                  >
                    {worker ? (
                      <>
                        <span 
                          // ZMIANA: text-6xl (duży login), wyśrodkowany, zawijający się, jeśli jest ekstremalnie długi
                          className="text-6xl font-black text-slate-800 tracking-tight animate-in zoom-in duration-500 text-center break-words w-full" 
                          key={"login-" + (worker.worker_login || worker.login) + worker.hideAt}
                        >
                          {worker.worker_login || worker.login}
                        </span>
                        
                        <span 
                          // ZMIANA: Pigułka na dole, wyśrodkowana
                          className={`px-8 py-3 rounded-full text-2xl font-black uppercase tracking-widest animate-in slide-in-from-bottom-4 duration-500 text-center ${
                            (!worker.task || worker.task === 'unassigned') 
                              ? 'bg-rose-50 text-rose-600 border border-rose-200 shadow-sm' 
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-sm'
                          }`} 
                          key={"task-" + (worker.worker_login || worker.login) + worker.hideAt}
                        >
                          {formatTaskName(worker.task)}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-6xl font-black text-slate-300 tracking-tight leading-tight">---</span>
                        <span className="px-8 py-3 rounded-full text-2xl font-bold uppercase tracking-widest bg-slate-100 text-slate-400">
                          OCZEKIWANIE
                        </span>
                      </>
                    )}
                  </div>
                ))}
              </div>
              
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TVBoard;