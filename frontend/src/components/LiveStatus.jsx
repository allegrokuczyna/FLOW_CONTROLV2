import React, { useState, useEffect } from 'react';
import api from '../api';
import { 
    Activity, 
    Layers, 
    RefreshCw, 
    Package, 
    Truck, 
    Boxes 
} from 'lucide-react';
import { usePolling } from '../hooks/usePolling';

// --- KONFIGURACJA WIDOKU D365 ---
const D365_PROCESS_CONFIG = [
    { id: 'receiving', label: 'Przyjęcia (Inbound)', icon: Package, color: 'text-blue-600', bg: 'bg-blue-50' },
    { id: 'putaway', label: 'Rozkładanie (Putaway)', icon: Layers, color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { id: 'picking', label: 'Kompletacja (Picking)', icon: Boxes, color: 'text-amber-600', bg: 'bg-amber-50' },
    { id: 'packing', label: 'Pakowanie (w trakcie)', icon: Activity, color: 'text-slate-400', bg: 'bg-slate-50' },
    { id: 'sorting', label: 'Sortowanie (w trakcie)', icon: Truck, color: 'text-slate-400', bg: 'bg-slate-50' }
];

const LiveStatus = () => {
    const [liveD365Data, setLiveD365Data] = useState(null);
    const [lastD365Update, setLastD365Update] = useState('--:--:--');
    const [isLoading, setIsLoading] = useState(false);

    const fetchLiveD365 = async () => {
        setIsLoading(true);
        try {
            const res = await api.get('/sync/live-view'); 
            if (res.data && res.data.status === 'success') {
                setLiveD365Data(res.data.data);
                setLastD365Update(res.data.timestamp);
            }
        } catch (error) {
            console.error("❌ Błąd pobierania danych D365 Live View:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // Odświeżanie w tle co 10 sekund
    usePolling(fetchLiveD365, 10000);


    useEffect(() => {
        fetchLiveD365();
    }, []);

    return (
        <div className="p-2 animate-in fade-in duration-500">
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
                
                {/* NAGŁÓWEK */}
                <div className="p-6 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <div className="bg-indigo-600 p-2.5 rounded-xl shadow-sm shadow-indigo-200">
                            <Activity size={24} className="text-white animate-pulse" />
                        </div>
                        <div>
                            <h2 className="text-base font-black uppercase tracking-widest text-slate-800">Magazyn D365 (Live)</h2>
                            <p className="text-xs font-bold text-slate-400 mt-1">Ostatnia aktualizacja: <span className="text-slate-500">{lastD365Update}</span></p>
                        </div>
                    </div>
                    <button 
                        onClick={fetchLiveD365} 
                        className="px-4 py-2 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all flex items-center gap-2 border border-transparent hover:border-indigo-100"
                        title="Odśwież dane"
                    >
                        <span className="text-xs font-bold uppercase tracking-wider hidden sm:block">Odśwież</span>
                        <RefreshCw size={16} className={isLoading ? 'animate-spin text-indigo-600' : ''} />
                    </button>
                </div>

                {/* TABELA DANYCH */}
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead className="bg-white">
                            <tr className="text-xs font-black uppercase tracking-widest text-slate-400 border-b border-slate-100">
                                <th className="p-5 pl-8">Główny Proces</th>
                                <th className="p-5 text-center">Otwarte Prace</th>
                                <th className="p-5 text-right pr-8">Ilość Sztuk (Backlog)</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {D365_PROCESS_CONFIG.map((process) => {
                                const Icon = process.icon;
                                const data = liveD365Data ? liveD365Data[process.id] : { works: 0, qty: 0 };
                                
                                // Wyszarzanie procesów w budowie
                                const isPending = process.id === 'packing' || process.id === 'sorting';

                                return (
                                    <tr key={process.id} className={`hover:bg-slate-50 transition-colors ${isPending ? 'opacity-40 grayscale' : ''}`}>
                                        <td className="p-5 pl-8 flex items-center gap-4">
                                            <div className={`p-3 rounded-xl ${process.bg}`}>
                                                <Icon size={20} className={process.color} />
                                            </div>
                                            <span className="text-sm font-bold text-slate-700">{process.label}</span>
                                        </td>
                                        <td className="p-5 text-center">
                                            <span className="font-mono font-black text-slate-600 text-lg bg-slate-100/50 px-3 py-1 rounded-lg">
                                                {data.works}
                                            </span>
                                        </td>
                                        <td className="p-5 pr-8 text-right">
                                            <span className={`text-xl font-black ${data.qty > 0 ? 'text-slate-800' : 'text-slate-300'}`}>
                                                {data.qty.toLocaleString()}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default LiveStatus;