import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Calendar, TrendingUp, Star, CalendarClock, Loader2, Search, Filter } from 'lucide-react';
import api from '../api';

const SystemData = () => {
    const [activeTab, setActiveTab] = useState(null);
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // --- NOWE STANY DLA FILTRÓW ---
    const [filters, setFilters] = useState({
        login: '',
        shift: '',
        hours: '',
        task: ''
    });

    const tabs = {
        grafik_dzis: {
            title: "Grafik Pracowników - Dzisiaj",
            icon: <Calendar size={16} />,
            endpoint: '/plan/daily',
            showFilters: true, // Flaga: pokazuj filtry dla tej zakładki
            columns: [
                { key: 'work_date', label: 'Data' },
                { key: 'login', label: 'Pracownik' },
                { key: 'hours', label: 'Godziny' },
                { key: 'shift', label: 'Zmiana' },
                { key: 'task', label: 'Zadanie / Strefa' }
            ]
        },
        grafik_jutro: {
            title: "Grafik Pracowników - Jutro",
            icon: <CalendarClock size={16} />,
            endpoint: () => {
                const tomorrow = new Date();
                tomorrow.setDate(tomorrow.getDate() + 1);
                return `/plan/daily?target_date=${tomorrow.toISOString().split('T')[0]}`;
            },
            showFilters: true,
            columns: [
                { key: 'work_date', label: 'Data' },
                { key: 'login', label: 'Pracownik' },
                { key: 'hours', label: 'Godziny' },
                { key: 'shift', label: 'Zmiana' },
                { key: 'task', label: 'Zadanie / Strefa' }
            ]
        },
        forecast: {
            title: "Prognoza Spływu (Forecast)",
            icon: <TrendingUp size={16} />,
            endpoint: '/works/forecast_upcoming',
            columns: [
                { key: 'forecast_date', label: 'Data' },
                { key: 'hour_from', label: 'Godzina', format: (val) => new Date(val).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) },
                { key: 'forecast_pcs', label: 'Prognozowane Sztuki' }
            ]
        },
        productivity: {
            title: "Matryca Kompetencji",
            icon: <Star size={16} />,
            endpoint: '/productivity',
            columns: [
                { key: 'login', label: 'Pracownik' },
                { key: 'picking', label: 'Picking' },
                { key: 'packing', label: 'Packing' },
                { key: 'putaway', label: 'Putaway' },
                { key: 'forklift', label: 'Forklift' }
            ]
        }
    };

    // Resetowanie filtrów przy zmianie zakładki
    useEffect(() => {
        setFilters({ login: '', shift: '', hours: '', task: '' });
    }, [activeTab]);

    useEffect(() => {
        if (!activeTab) return;
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const url = typeof tabs[activeTab].endpoint === 'function' ? tabs[activeTab].endpoint() : tabs[activeTab].endpoint;
                const response = await api.get(url);
                const resultData = response.data.data || response.data.results || response.data;
                setData(Array.isArray(resultData) ? resultData : []);
            } catch (err) {
                setError("Błąd pobierania danych.");
            }
            setLoading(false);
        };
        fetchData();
    }, [activeTab]);

    // --- LOGIKA FILTROWANIA ---
    const filteredData = useMemo(() => {
        return data.filter(item => {
            const matchLogin = item.login?.toLowerCase().includes(filters.login.toLowerCase());
            const matchShift = filters.shift === '' || String(item.shift) === filters.shift;
            const matchHours = filters.hours === '' || item.hours === filters.hours;
            const matchTask = filters.task === '' || item.task === filters.task;
            return matchLogin && matchShift && matchHours && matchTask;
        });
    }, [data, filters]);

    // Wyciąganie unikalnych wartości dla selectów (tylko z aktualnych danych)
    const uniqueValues = useMemo(() => {
        return {
            shifts: [...new Set(data.map(i => String(i.shift)))].filter(v => v && v !== 'undefined').sort(),
            hours: [...new Set(data.map(i => i.hours))].filter(v => v && v !== 'undefined').sort(),
            tasks: [...new Set(data.map(i => i.task))].filter(v => v && v !== 'undefined').sort()
        };
    }, [data]);

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-8 relative text-gray-200">
            <header className="space-y-6 border-b border-white/5 pb-6">
                <div>
                    <h1 className="text-2xl font-semibold tracking-tight text-white/90 underline decoration-blue-500/40 underline-offset-8">
                        baza danych systemowych
                    </h1>
                    <p className="text-gray-500 text-sm mt-2">zarządzanie grafikami, skryptami i forecastem.</p>
                </div>

                <div className="flex flex-wrap gap-2">
                    {Object.entries(tabs).map(([key, tab]) => (
                        <button
                            key={key}
                            onClick={() => setActiveTab(key)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-[10px] font-bold uppercase tracking-widest transition-all ${
                                activeTab === key 
                                ? 'bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-500/20' 
                                : 'bg-white/[0.02] text-gray-500 border-white/5 hover:border-white/20 hover:text-gray-300'
                            }`}
                        >
                            {tab.icon}
                            {tab.title.split(' - ')[0]}
                        </button>
                    ))}
                </div>
            </header>

            {/* --- PASEK FILTRÓW (TYLKO DLA GRAFIKU) --- */}
            <AnimatePresence>
                {activeTab && tabs[activeTab]?.showFilters && data.length > 0 && (
                    <motion.div 
                        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                        className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-2xl"
                    >
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" size={14} />
                            <input 
                                type="text"
                                placeholder="Szukaj loginu..."
                                value={filters.login}
                                onChange={(e) => setFilters({...filters, login: e.target.value})}
                                className="w-full bg-black/20 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-xs focus:border-blue-500 outline-none transition-colors"
                            />
                        </div>

                        <select 
                            value={filters.shift}
                            onChange={(e) => setFilters({...filters, shift: e.target.value})}
                            className="bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-xs focus:border-blue-500 outline-none appearance-none"
                        >
                            <option value="">Wszystkie zmiany</option>
                            {uniqueValues.shifts.map(v => <option key={v} value={v}>Zmiana {v}</option>)}
                        </select>

                        <select 
                            value={filters.hours}
                            onChange={(e) => setFilters({...filters, hours: e.target.value})}
                            className="bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-xs focus:border-blue-500 outline-none appearance-none"
                        >
                            <option value="">Wszystkie godziny</option>
                            {uniqueValues.hours.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>

                        <select 
                            value={filters.task}
                            onChange={(e) => setFilters({...filters, task: e.target.value})}
                            className="bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-xs focus:border-blue-500 outline-none appearance-none"
                        >
                            <option value="">Wszystkie zadania</option>
                            {uniqueValues.tasks.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* OBSZAR WYŚWIETLANIA DANYCH */}
            <div className="relative min-h-[400px] border border-white/5 rounded-[2rem] bg-white/[0.01] backdrop-blur-sm overflow-hidden p-6">
                {!activeTab && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 space-y-4">
                        <Database size={48} className="opacity-20" />
                        <p className="text-sm font-light tracking-widest uppercase">Wybierz kategorię z menu powyżej</p>
                    </div>
                )}

                <AnimatePresence mode="wait">
                    {loading ? (
                        <motion.div key="loader" className="absolute inset-0 flex items-center justify-center bg-[#0a0a0a]/50 z-10">
                            <Loader2 size={32} className="text-blue-500 animate-spin" />
                        </motion.div>
                    ) : (
                        <motion.div key="content" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                            {activeTab && (
                                <div className="flex items-center gap-3 text-blue-400 mb-2">
                                    <h2 className="text-sm font-medium text-white/70 uppercase tracking-widest">{tabs[activeTab].title}</h2>
                                    <span className="text-[10px] text-gray-600 font-mono ml-auto">Wyniki: {filteredData.length} / {data.length}</span>
                                </div>
                            )}

                            <div className="overflow-x-auto rounded-xl border border-white/10 bg-black/20">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-[10px] text-gray-500 uppercase bg-white/5 tracking-tighter">
                                        <tr>
                                            {activeTab && tabs[activeTab].columns.map((col, idx) => (
                                                <th key={idx} className="px-6 py-3 font-semibold">{col.label}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {filteredData.length > 0 ? filteredData.map((row, rIndex) => (
                                            <tr key={rIndex} className="hover:bg-white/[0.02] transition-colors">
                                                {tabs[activeTab].columns.map((col, cIndex) => (
                                                    <td key={cIndex} className="px-6 py-3 whitespace-nowrap text-gray-400 font-light text-xs">
                                                        {col.format ? col.format(row[col.key]) : (row[col.key] || '-')}
                                                    </td>
                                                ))}
                                            </tr>
                                        )) : activeTab && (
                                            <tr>
                                                <td colSpan={tabs[activeTab].columns.length} className="px-6 py-12 text-center text-gray-600 italic text-xs">
                                                    Nie znaleziono pracowników spełniających kryteria.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default SystemData;