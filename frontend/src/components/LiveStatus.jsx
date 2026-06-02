import React, { useState, useEffect } from 'react';
import api from '../api';
import { 
    Activity, 
    Layers, 
    Box, 
    RefreshCw, 
    Inbox, 
    ArrowRightLeft, 
    PackageSearch, 
    Clock, 
    User, 
    Search,
    ListFilter
} from 'lucide-react';
import { usePolling } from '../hooks/usePolling'; // Zakładam, że masz ten hook w projekcie

// --- MAPOWANIE KATEGORII PRAC NA ENDPOINTY ---
const WORK_CATEGORIES = [
    { id: 'inbound', title: 'Inbound (W toku)', icon: <Inbox size={20} />, endpoint: '/works/inbound/inprocess', color: 'text-emerald-600', bg: 'bg-emerald-100', border: 'border-emerald-200' },
    { id: 'sorting', title: 'Sorting (Otwarte)', icon: <ArrowRightLeft size={20} />, endpoint: '/works/sorting/open', color: 'text-amber-600', bg: 'bg-amber-100', border: 'border-amber-200' },
    { id: 'replenishment', title: 'Replenishment', icon: <RefreshCw size={20} />, endpoint: '/works/replenishment/open', color: 'text-blue-600', bg: 'bg-blue-100', border: 'border-blue-200' },
    { id: 'zone_1m0b1', title: 'Zone Pick 1M0B1', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M0B1', color: 'text-indigo-600', bg: 'bg-indigo-100', border: 'border-indigo-200' },
    { id: 'zone_1m0b2', title: 'Zone Pick 1M0B2', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M0B2', color: 'text-indigo-600', bg: 'bg-indigo-100', border: 'border-indigo-200' },
    { id: 'zone_1m1b1', title: 'Zone Pick 1M1B1', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M1B1', color: 'text-purple-600', bg: 'bg-purple-100', border: 'border-purple-200' },
    { id: 'zone_1m1b2', title: 'Zone Pick 1M1B2', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M1B2', color: 'text-purple-600', bg: 'bg-purple-100', border: 'border-purple-200' },
    { id: 'zone_1m2b1', title: 'Zone Pick 1M2B1', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M2B1', color: 'text-pink-600', bg: 'bg-pink-100', border: 'border-pink-200' },
    { id: 'zone_1m2b2', title: 'Zone Pick 1M2B2', icon: <PackageSearch size={20} />, endpoint: '/works/zonepick/open-1M2B2', color: 'text-pink-600', bg: 'bg-pink-100', border: 'border-pink-200' },
];

const LiveStatus = () => {
    // Stany nawigacji
    const [activeTab, setActiveTab] = useState('prace');
    const [expandedCategory, setExpandedCategory] = useState(null); // ID klikniętego kafelka
    const [searchQuery, setSearchQuery] = useState('');

    // Stany danych
    const [counts, setCounts] = useState({});
    const [worksData, setWorksData] = useState({});
    const [isLoading, setIsLoading] = useState(false);

    // 1. Funkcja pobierająca zsumowane dane dla KAFELKÓW
    const fetchAllCounts = async () => {
        setIsLoading(true);
        try {
            const promises = WORK_CATEGORIES.map(cat => api.get(cat.endpoint));
            const responses = await Promise.allSettled(promises);
            
            const newCounts = {};
            const newData = {};
            
            responses.forEach((res, index) => {
                const cat = WORK_CATEGORIES[index];
                
                if (res.status === 'fulfilled') {
                    // Magia bezpiecznego odpakowywania - wspiera zarówno czystego Axios'a jak i interceptory
                    const payload = res.value.data || res.value; 
                    
                    // --- ODKOMENTUJ TO, JEŚLI CHCESZ ZOBACZYĆ SUROWE DANE W KONSOLI (F12) ---
                    // console.log(`[LIVE STATUS] Odpowiedź z ${cat.endpoint}:`, payload);

                    if (payload && payload.status === 'success') {
                        newCounts[cat.id] = payload.total_count || 0;
                        newData[cat.id] = payload.data || [];
                    } 
                    // Fallback w razie gdyby backend zwrócił samą listę (zamiast obiektu ze statusem)
                    else if (Array.isArray(payload)) {
                        newCounts[cat.id] = payload.length;
                        newData[cat.id] = payload;
                    } 
                    else {
                        newCounts[cat.id] = 0;
                        newData[cat.id] = [];
                    }
                } else {
                    console.error(`❌ [LIVE STATUS] Błąd pobierania dla ${cat.endpoint}:`, res.reason);
                    newCounts[cat.id] = 0;
                    newData[cat.id] = [];
                }
            });
            
            setCounts(newCounts);
            setWorksData(newData);
        } catch (error) {
            console.error("❌ Błąd krytyczny pobierania danych Live Status:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // Odświeżanie danych w tle (co 10 sekund) - o ile masz zaimplementowany hook usePolling
    usePolling(fetchAllCounts, 10000);

    // Pobranie danych na start
    useEffect(() => {
        fetchAllCounts();
    }, []);

    // Helper do formatowania daty z bazy (usuwa 'T' i ucina ułamki sekund)
    const formatDate = (dateString) => {
        if (!dateString) return '---';
        const date = new Date(dateString);
        return date.toLocaleString('pl-PL', { 
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' 
        });
    };

    // Filtrowanie prac w otwartej tabeli
    const displayedWorks = (expandedCategory && worksData[expandedCategory]) 
        ? worksData[expandedCategory].filter(w => 
            w.workid?.toLowerCase().includes(searchQuery.toLowerCase()) || 
            w.ordernum?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            w.lockeduser?.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : [];

    return (
        <div className="space-y-6 animate-in fade-in duration-500 p-2">
            
            {/* PASEK GÓRNY I NAWIGACJA (TABS) */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="flex items-center gap-3 p-4 border-b border-slate-100 bg-slate-50">
                    <Activity className="text-indigo-600" size={20} />
                    <h2 className="text-sm font-black uppercase tracking-widest text-slate-800">Live Status Monitor</h2>
                    
                    <button 
                        onClick={fetchAllCounts} 
                        className="ml-auto flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-indigo-600 transition-colors"
                    >
                        <RefreshCw size={14} className={isLoading ? "animate-spin text-indigo-600" : ""} />
                        Odśwież
                    </button>
                </div>
                
                <div className="flex p-2 gap-2 bg-white overflow-x-auto custom-scrollbar">
                    {['prace', 'zamówienia sprzedaży', 'zamówienia zakupu', 'uzupełnienia zapasu'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => { setActiveTab(tab); setExpandedCategory(null); }}
                            className={`px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${
                                activeTab === tab 
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200' 
                                : 'bg-slate-50 text-slate-500 hover:bg-slate-100 border border-slate-200'
                            }`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>
            </div>

            {/* ZAWWARTOŚĆ ZAKŁADKI "PRACE" */}
            {activeTab === 'prace' && (
                <div className="space-y-6">
                    
                    {/* KAFELKI KATEGORII PRAC */}
                    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                        {WORK_CATEGORIES.map((cat) => {
                            const isExpanded = expandedCategory === cat.id;
                            const count = counts[cat.id] !== undefined ? counts[cat.id] : '...';
                            
                            return (
                                <div 
                                    key={cat.id}
                                    onClick={() => setExpandedCategory(isExpanded ? null : cat.id)}
                                    className={`cursor-pointer rounded-2xl p-4 transition-all duration-200 border-2 group ${
                                        isExpanded 
                                        ? `bg-white border-indigo-500 shadow-lg shadow-indigo-100 ring-4 ring-indigo-50` 
                                        : `bg-white hover:bg-slate-50 border-slate-200 shadow-sm hover:border-indigo-300`
                                    }`}
                                >
                                    <div className="flex justify-between items-start mb-4">
                                        <div className={`p-2 rounded-xl ${cat.bg} ${cat.color}`}>
                                            {cat.icon}
                                        </div>
                                        <div className={`px-2.5 py-1 rounded-lg text-lg font-black ${
                                            count > 0 ? 'bg-rose-100 text-rose-600 border border-rose-200' : 'bg-slate-100 text-slate-400 border border-slate-200'
                                        }`}>
                                            {count}
                                        </div>
                                    </div>
                                    <h3 className="text-xs font-black text-slate-700 uppercase tracking-wider">{cat.title}</h3>
                                    <p className="text-[10px] font-bold text-slate-400 mt-1 uppercase">
                                        {count === 0 ? 'Brak otwartych prac' : 'Kliknij, aby zobaczyć szczegóły'}
                                    </p>
                                </div>
                            );
                        })}
                    </div>

                    {/* ROZWIJANA TABELA SZCZEGÓŁÓW (Tylko jeśli wybrano kategorię) */}
                    {expandedCategory && (
                        <div className="bg-white rounded-2xl shadow-lg border border-indigo-100 overflow-hidden animate-in slide-in-from-top-4 duration-300">
                            
                            {/* Nagłówek Tabeli z Wyszukiwarką */}
                            <div className="p-4 border-b border-slate-100 bg-indigo-50/50 flex flex-col md:flex-row justify-between items-center gap-4">
                                <div className="flex items-center gap-3">
                                    <ListFilter className="text-indigo-600" size={20} />
                                    <div>
                                        <h3 className="text-sm font-black text-slate-800 uppercase tracking-widest">
                                            Szczegóły: {WORK_CATEGORIES.find(c => c.id === expandedCategory)?.title}
                                        </h3>
                                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                                            Wyświetlam {displayedWorks.length} rekordów
                                        </p>
                                    </div>
                                </div>

                                <div className="relative w-full md:w-72">
                                    <input 
                                        type="text" 
                                        placeholder="Szukaj po ID pracy, zamówieniu lub loginie..." 
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="w-full pl-9 pr-4 py-2 bg-white border border-slate-300 rounded-xl text-xs font-bold outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-slate-700"
                                    />
                                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                </div>
                            </div>

                            {/* Płaściwa Tabela Danych */}
                            <div className="overflow-x-auto max-h-[60vh] custom-scrollbar">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-white shadow-sm z-10">
                                        <tr className="text-[9px] font-black uppercase tracking-widest text-slate-500 border-b-2 border-slate-200">
                                            <th className="p-4">ID Pracy</th>
                                            <th className="p-4">Nr Zamówienia</th>
                                            <th className="p-4">Status</th>
                                            <th className="p-4">Przypisany (Locked)</th>
                                            <th className="p-4 text-right">Ilość PCS</th>
                                            <th className="p-4 text-right">Linie</th>
                                            <th className="p-4">LP Docelowe</th>
                                            <th className="p-4">Utworzono</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 text-xs font-medium text-slate-700 bg-slate-50/20">
                                        {displayedWorks.length === 0 ? (
                                            <tr>
                                                <td colSpan="8" className="p-8 text-center text-slate-400 font-bold">
                                                    {counts[expandedCategory] === 0 ? 'Brak otwartych prac w tej kategorii.' : 'Nie znaleziono prac pasujących do wyszukiwania.'}
                                                </td>
                                            </tr>
                                        ) : (
                                            displayedWorks.map((work) => (
                                                <tr key={work.workid} className="hover:bg-indigo-50/50 transition-colors">
                                                    <td className="p-4 font-mono font-bold text-indigo-700">{work.workid}</td>
                                                    <td className="p-4 font-bold">{work.ordernum || '---'}</td>
                                                    <td className="p-4">
                                                        <span className={`px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-wider ${
                                                            work.workstatus?.toLowerCase() === 'open' ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' :
                                                            work.workstatus?.toLowerCase() === 'in process' ? 'bg-amber-100 text-amber-700 border border-amber-200' :
                                                            'bg-slate-100 text-slate-600 border border-slate-200'
                                                        }`}>
                                                            {work.workstatus || 'Nieznany'}
                                                        </span>
                                                    </td>
                                                    <td className="p-4">
                                                        {work.lockeduser ? (
                                                            <div className="flex items-center gap-1.5 text-indigo-600 bg-indigo-50 px-2 py-1 rounded-md border border-indigo-100 w-max">
                                                                <User size={12} />
                                                                <span className="font-bold">{work.lockeduser}</span>
                                                            </div>
                                                        ) : (
                                                            <span className="text-slate-400">---</span>
                                                        )}
                                                    </td>
                                                    <td className="p-4 text-right font-black">{work.whasalesitemqty || 0}</td>
                                                    <td className="p-4 text-right text-slate-500">{work.whasalesitemcount || 0}</td>
                                                    <td className="p-4 font-mono text-[10px] text-slate-500">{work.targetlicenseplateid || '---'}</td>
                                                    <td className="p-4 text-[10px] text-slate-500">{formatDate(work.workcreateddatetime)}</td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ZAŚLEPKA NA POZOSTAŁE ZAKŁADKI */}
            {activeTab !== 'prace' && (
                <div className="h-64 flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-2xl bg-white/50">
                    <Layers className="text-slate-300 mb-4" size={48} />
                    <h3 className="text-sm font-black text-slate-500 uppercase tracking-widest">Moduł {activeTab}</h3>
                    <p className="text-xs text-slate-400 mt-2 font-bold">W trakcie dewelopmentu...</p>
                </div>
            )}

        </div>
    );
};

export default LiveStatus;