import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Search, RefreshCcw, AlertTriangle, SlidersHorizontal, Check, Zap } from 'lucide-react';
import { usePolling } from '../hooks/usePolling'; // <-- IMPORT HOOKA

const ProductivityGrid = () => {
    const [performanceData, setPerformanceData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [error, setError] = useState(null);

    const [selectedZones, setSelectedZones] = useState([]);
    const [showZoneMenu, setShowZoneMenu] = useState(false);

    // Główne pobieranie
    const fetchProductivity = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get('/api/productivity');
            if (Array.isArray(res.data)) {
                setPerformanceData(res.data);
            } else {
                throw new Error("Nieprawidłowy format danych z serwera matrycy");
            }
        } catch (err) {
            setError(err.response?.data?.detail || err.message || "Wystąpił błąd");
        } finally {
            setLoading(false);
        }
    };

    // Ciche pobieranie w tle
    const fetchProductivitySilent = async () => {
        try {
            const res = await axios.get('/api/productivity');
            if (Array.isArray(res.data)) {
                setPerformanceData(res.data);
            }
        } catch (err) {
            console.warn("Background productivity sync failed");
        }
    };

    useEffect(() => { fetchProductivity(); }, []);

    // Odświeżaj tabelę w tle co 15 sekund
    usePolling(fetchProductivitySilent, 15000);

    const safePerformances = useMemo(() => {
        return Array.isArray(performanceData) ? performanceData : [];
    }, [performanceData]);

    const IGNORED_KEYS = ['id', 'login', 'worker_login', 'full_name', 'worker_name', 'updated_at', 'created_at', 'timestamp', 'date'];

    const allColumns = useMemo(() => {
        if (safePerformances.length === 0) return [];
        const cols = new Set();
        safePerformances.forEach(worker => {
            Object.keys(worker).forEach(key => {
                if (!IGNORED_KEYS.includes(key.toLowerCase()) && worker[key] !== null && typeof worker[key] !== 'object') {
                    cols.add(key);
                }
            });
        });
        return Array.from(cols).sort();
    }, [safePerformances]);

    const visibleColumns = useMemo(() => {
        if (selectedZones.length === 0) return allColumns;
        return allColumns.filter(col => selectedZones.includes(col));
    }, [allColumns, selectedZones]);

    const toggleZoneFilter = (zone) => {
        setSelectedZones(prev => prev.includes(zone) ? prev.filter(z => z !== zone) : [...prev, zone]);
    };

    const filteredWorkers = useMemo(() => {
        return safePerformances.filter(w => {
            const name = String(w.full_name || "").toLowerCase();
            const login = String(w.login || w.worker_login || "").toLowerCase();
            const searchLower = search.toLowerCase();
            return name.includes(searchLower) || login.includes(searchLower);
        });
    }, [safePerformances, search]);

    const getSkillClass = (val) => {
        const num = Number(val);
        if (isNaN(num) || num === 0) return 'bg-slate-50 text-slate-300 font-normal border border-slate-100'; 
        if (num >= 5) return 'bg-emerald-50 text-emerald-700 font-black border border-emerald-200/50 shadow-sm'; 
        if (num >= 3) return 'bg-indigo-50 text-indigo-700 font-bold border border-indigo-200/50'; 
        return 'bg-amber-50 text-amber-700 font-semibold border border-amber-200/50'; 
    };

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-purple-600 bg-white rounded-[2rem] shadow-sm border border-slate-200">
                <RefreshCcw size={40} className="animate-spin mb-4" />
                <span className="text-[10px] uppercase font-black tracking-widest text-slate-400">Ładowanie matrycy skilli...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-red-500 bg-white rounded-[2rem] shadow-sm border border-slate-200">
                <AlertTriangle size={48} className="mb-4 text-red-400" />
                <h3 className="text-sm font-black uppercase tracking-widest mb-2">Błąd ładowania danych</h3>
                <p className="text-xs text-slate-500 font-bold">{error}</p>
                <button onClick={fetchProductivity} className="mt-6 bg-slate-900 text-white px-6 py-2 rounded-xl text-xs font-black uppercase">Spróbuj ponownie</button>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-white rounded-[2rem] shadow-sm border border-slate-200 overflow-hidden animate-in fade-in duration-300">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 shrink-0">
                <div className="flex items-center gap-4">
                    <div className="bg-purple-600 p-2 rounded-xl text-white shadow-md shadow-purple-200">
                        <Zap size={20} />
                    </div>
                    <div className="flex flex-col">
                        <h2 className="text-sm font-black uppercase tracking-widest text-slate-700">Matryca Umiejętności</h2>
                        <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Skill Level (0-6)</span>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                        <input 
                            type="text" 
                            placeholder="Szukaj loginu..." 
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all w-64 shadow-xs"
                        />
                    </div>

                    <div className="relative">
                        <button 
                            onClick={() => setShowZoneMenu(!showZoneMenu)}
                            className={`flex items-center gap-2 px-4 py-2 border rounded-xl text-xs font-bold transition-all shadow-xs ${selectedZones.length > 0 ? 'bg-purple-50 border-purple-200 text-purple-700' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}
                        >
                            <SlidersHorizontal size={16} />
                            <span>Procesy {selectedZones.length > 0 && `(${selectedZones.length})`}</span>
                        </button>

                        {showZoneMenu && (
                            <>
                                <div className="fixed inset-0 z-40" onClick={() => setShowZoneMenu(false)}></div>
                                <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-200 shadow-xl rounded-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100 p-2">
                                    <div className="flex justify-between items-center p-2 border-b border-slate-100 mb-2">
                                        <span className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Wyświetl procesy</span>
                                        {selectedZones.length > 0 && (
                                            <button onClick={() => setSelectedZones([])} className="text-[10px] font-bold text-red-500 hover:text-red-600 transition-colors">
                                                Wszystkie
                                            </button>
                                        )}
                                    </div>
                                    <div className="max-h-60 overflow-y-auto custom-scrollbar flex flex-col gap-1">
                                        {allColumns.map(zone => (
                                            <label key={zone} className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors group">
                                                <div className="relative flex items-center justify-center">
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedZones.includes(zone)}
                                                        onChange={() => toggleZoneFilter(zone)}
                                                        className="peer appearance-none w-4 h-4 border-2 border-slate-300 rounded cursor-pointer checked:bg-purple-600 checked:border-purple-600 transition-all"
                                                    />
                                                    <Check className="absolute text-white opacity-0 peer-checked:opacity-100 pointer-events-none w-3 h-3" strokeWidth={3} />
                                                </div>
                                                <span className="text-xs font-bold text-slate-700 group-hover:text-purple-600 transition-colors uppercase">{zone}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    <button onClick={fetchProductivity} className="p-2 hover:bg-slate-200 rounded-lg transition-all text-slate-500" title="Odśwież matrycę">
                        <RefreshCcw size={18} />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar">
                <table className="w-full border-collapse">
                    <thead className="sticky top-0 z-20 bg-white shadow-xs">
                        <tr>
                            <th className="p-4 bg-slate-50 border-b border-r border-slate-100 text-[10px] font-black uppercase text-slate-400 w-48 sticky left-0 z-30">
                                Pracownicy ({filteredWorkers.length})
                            </th>
                            {visibleColumns.map(colName => (
                                <th key={colName} className="p-4 bg-slate-50 border-b border-slate-100 text-[10px] font-black uppercase text-slate-600 text-center min-w-[90px]">
                                    {colName}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="text-[11px]">
                        {filteredWorkers.length === 0 ? (
                            <tr>
                                <td colSpan={visibleColumns.length + 1} className="p-8 text-center text-slate-400 font-medium bg-slate-50/30">
                                    Brak pracowników w bazie.
                                </td>
                            </tr>
                        ) : (
                            filteredWorkers.map((worker) => (
                                <tr key={worker.login || worker.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors group">
                                    <td className="p-4 border-r border-slate-100 sticky left-0 bg-white group-hover:bg-slate-50 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.02)]">
                                        <span className="font-black text-slate-700 tracking-wider text-xs">
                                            {worker.login || worker.worker_login || `ID: ${worker.id}`}
                                        </span>
                                    </td>
                                    
                                    {visibleColumns.map(colName => {
                                        const skillLvl = worker[colName];
                                        return (
                                            <td key={colName} className="p-4 text-center border-r border-slate-50 last:border-r-0">
                                                <span className={`px-2.5 py-1.5 rounded-lg text-[11px] inline-block min-w-[32px] ${getSkillClass(skillLvl)}`}>
                                                    {Number(skillLvl) > 0 ? skillLvl : '-'}
                                                </span>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default ProductivityGrid;