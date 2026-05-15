import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Calendar, Search, RefreshCcw, AlertTriangle } from 'lucide-react';

const ScheduleGrid = () => {
    // Domyślny, bezpieczny stan
    const [schedule, setSchedule] = useState({ dates: [], workers: [] });
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [error, setError] = useState(null);

    const fetchWeekly = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get('/api/plan/weekly');
            // Upewniamy się, że to co przyszło to faktycznie obiekt z tablicami
            if (res.data && Array.isArray(res.data.workers) && Array.isArray(res.data.dates)) {
                setSchedule(res.data);
            } else {
                throw new Error("Nieprawidłowy format danych z serwera");
            }
        } catch (err) {
            console.error("Błąd pobierania grafiku tygodniowego:", err);
            setError(err.response?.data?.detail || err.message || "Wystąpił błąd");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchWeekly(); }, []);

    // PANCERNE FILTROWANIE: Zabezpieczone przed null, undefined i liczbami
    const safeWorkers = Array.isArray(schedule.workers) ? schedule.workers : [];
    const safeDates = Array.isArray(schedule.dates) ? schedule.dates : [];

    const filteredWorkers = safeWorkers.filter(w => {
        const name = String(w.full_name || "").toLowerCase();
        const login = String(w.login || "").toLowerCase();
        const searchLower = search.toLowerCase();
        return name.includes(searchLower) || login.includes(searchLower);
    });

    const getDayName = (dateStr) => {
        if (!dateStr) return "";
        return new Date(dateStr).toLocaleDateString('pl-PL', { weekday: 'short', day: '2-digit', month: '2-digit' });
    };

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-indigo-600 bg-white rounded-[2rem] shadow-sm border border-slate-200">
                <RefreshCcw size={40} className="animate-spin mb-4" />
                <span className="text-[10px] uppercase font-black tracking-widest text-slate-400">Ładowanie grafiku...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-red-500 bg-white rounded-[2rem] shadow-sm border border-slate-200">
                <AlertTriangle size={48} className="mb-4 text-red-400" />
                <h3 className="text-sm font-black uppercase tracking-widest mb-2">Błąd pobierania danych</h3>
                <p className="text-xs text-slate-500 font-bold">{error}</p>
                <button onClick={fetchWeekly} className="mt-6 bg-slate-900 text-white px-6 py-2 rounded-xl text-xs font-black uppercase">Spróbuj ponownie</button>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-white rounded-[2rem] shadow-sm border border-slate-200 overflow-hidden">
            {/* Header / Search */}
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 shrink-0">
                <div className="flex items-center gap-4">
                    <div className="bg-indigo-600 p-2 rounded-xl text-white">
                        <Calendar size={20} />
                    </div>
                    <h2 className="text-sm font-black uppercase tracking-widest text-slate-700">Tygodniowy Plan Pracy</h2>
                </div>
                
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                        <input 
                            type="text" 
                            placeholder="Szukaj pracownika..." 
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-indigo-500 transition-all w-64"
                        />
                    </div>
                    <button onClick={fetchWeekly} className="p-2 hover:bg-slate-200 rounded-lg transition-all text-slate-500">
                        <RefreshCcw size={18} />
                    </button>
                </div>
            </div>

            {/* Macierz grafiku */}
            <div className="flex-1 overflow-auto custom-scrollbar">
                <table className="w-full border-collapse">
                    <thead className="sticky top-0 z-20 bg-white shadow-sm">
                        <tr>
                            <th className="p-4 bg-slate-50 border-b border-r border-slate-100 text-[10px] font-black uppercase text-slate-400 w-64 sticky left-0 z-30">
                                Pracownik ({filteredWorkers.length})
                            </th>
                            {safeDates.map(date => (
                                <th key={date} className="p-4 bg-slate-50 border-b border-slate-100 text-[10px] font-black uppercase text-slate-600 text-center min-w-[100px]">
                                    {getDayName(date)}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="text-[11px]">
                        {filteredWorkers.map((worker) => (
                            <tr key={worker.login} className="border-b border-slate-50 hover:bg-slate-50 transition-colors group">
                                <td className="p-4 border-r border-slate-100 sticky left-0 bg-white group-hover:bg-slate-50 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.02)]">
                                    <div className="flex flex-col">
                                        <span className="font-black text-slate-800 uppercase leading-none mb-1">{worker.full_name}</span>
                                        <span className="text-[9px] font-bold text-slate-400 tracking-tighter">{worker.login}</span>
                                    </div>
                                </td>
                                {safeDates.map(date => {
                                    // Upewniamy się, że sprawdzamy po pełnej dacie (bez czasu)
                                    const dateKey = date.split('T')[0];
                                    const shift = worker.days ? worker.days[dateKey] : null;
                                    const isWeekend = new Date(date).getDay() === 0 || new Date(date).getDay() === 6;
                                    
                                    return (
                                        <td key={date} className={`p-4 text-center border-r border-slate-50 last:border-r-0 ${isWeekend ? 'bg-slate-50/30' : ''}`}>
                                            {shift ? (
                                                <span className={`px-2 py-1 rounded-md font-black text-[10px] ${
                                                    String(shift).includes('6-14') ? 'bg-amber-100 text-amber-700' : 
                                                    String(shift).includes('14-22') ? 'bg-indigo-100 text-indigo-700' :
                                                    String(shift).includes('22-06') ? 'bg-slate-800 text-white' : 
                                                    'bg-emerald-100 text-emerald-700'
                                                }`}>
                                                    {shift}
                                                </span>
                                            ) : (
                                                <span className="text-slate-200 font-bold">-</span>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ScheduleGrid;