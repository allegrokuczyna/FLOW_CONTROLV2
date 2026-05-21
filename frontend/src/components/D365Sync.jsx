import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Database, RefreshCcw, ShieldCheck, Clock, User, AlertCircle, Cpu } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';

const D365Sync = () => {
    const [syncState, setSyncState] = useState({ last_sync_time: null, triggered_by: '', status: '' });
    const [isSyncing, setIsSyncing] = useState(false);
    const [msg, setMsg] = useState(null);

    // Pobieranie logów z bazy danych
    const fetchSyncStatus = async () => {
        try {
            const res = await axios.get('/api/sync/status');
            setSyncState(res.data);
        } catch (err) {
            console.error("Nie udało się pobrać statusu synchronizacji", err);
        }
    };

    useEffect(() => { fetchSyncStatus(); }, []);

    // Ciche sprawdzanie statusu logów w tle co 10 sekund
    usePolling(fetchSyncStatus, 10000);

    // Obsługa ręcznego kliknięcia w guzik
    const handleManualSync = async () => {
        setIsSyncing(true);
        setMsg(null);
        try {
            const res = await axios.post('/api/sync/trigger');
            if (res.status === 200) {
                setMsg({ type: 'success', text: 'Ręczna synchronizacja zakończona pełnym sukcesem!' });
                fetchSyncStatus(); // Odśwież dane na ekranie od razu
            }
        } catch (err) {
            setMsg({ type: 'error', text: err.response?.data?.detail || 'Błąd połączenia ze środowiskiem D365.' });
        } finally {
            setIsSyncing(false);
        }
    };

    const isError = String(syncState.status).includes('ERROR');
    const isAuto = syncState.triggered_by === 'Automatycznie';

    return (
        <div className="flex flex-col h-full bg-[#f8fafc] p-6 animate-in fade-in duration-300">
            {/* NAGŁÓWEK MODUŁU */}
            <div className="flex items-center gap-4 mb-8 bg-white p-6 rounded-3xl border border-slate-200 shadow-sm shrink-0">
                <div className="bg-indigo-600 p-3 rounded-2xl text-white shadow-lg shadow-indigo-100">
                    <Database size={24} />
                </div>
                <div>
                    <h2 className="text-xl font-black uppercase tracking-wider text-slate-800">D365 Data Synchronization</h2>
                    <p className="text-xs font-bold text-slate-400 mt-0.5">Integracja zasobów D365 z panelem ADM-01</p>
                </div>
            </div>

            {/* GŁÓWNY PANEL STATUSU */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 max-h-[350px]">
                
                {/* LEWA STRONA: MONITOR STANU */}
                <div className="bg-white border border-slate-200 rounded-[2.5rem] p-8 shadow-xs flex flex-col justify-between lg:col-span-2">
                    <div className="space-y-6">
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 block">Aktualny Stan Synchronizacji</span>
                        
                        <div className="flex items-center gap-6">
                            {isSyncing ? (
                                <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center text-indigo-600 border border-indigo-100">
                                    <RefreshCcw size={32} className="animate-spin" />
                                </div>
                            ) : isError ? (
                                <div className="w-16 h-16 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-600 border border-rose-100">
                                    <AlertCircle size={32} />
                                </div>
                            ) : (
                                <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-600 border border-emerald-100">
                                    <ShieldCheck size={32} />
                                </div>
                            )}

                            <div>
                                <h4 className="text-2xl font-black text-slate-800">
                                    {isSyncing ? 'Trwa pobieranie danych...' : isError ? 'Wykryto błędy integracji' : 'Połączenie stabilne'}
                                </h4>
                                <p className="text-xs font-bold text-slate-400 mt-1">
                                    {isSyncing ? 'Model podmienia paczki Open/InProcess w bazie.' : 'Wszystkie tabele ActiveWork oraz WorkExport działają prawidłowo.'}
                                </p>
                            </div>
                        </div>

                        {/* STATYSTYKI CZASU I INICJATORA */}
                        <div className="grid grid-cols-2 gap-4 border-t border-slate-100 pt-6 mt-6">
                            <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 flex items-center gap-3">
                                <Clock size={18} className="text-slate-400 shrink-0" />
                                <div>
                                    <span className="text-[9px] font-black uppercase text-slate-400 block leading-none mb-1">Czas Ostatniego Syncu</span>
                                    <span className="text-xs font-black text-slate-700 font-mono">{syncState.last_sync_time || 'Brak danych'}</span>
                                </div>
                            </div>

                            <div className={`p-4 rounded-2xl border flex items-center gap-3 ${isAuto ? 'bg-purple-50/50 border-purple-100' : 'bg-amber-50/50 border-amber-100'}`}>
                                {isAuto ? <Cpu size={18} className="text-purple-500 shrink-0" /> : <User size={18} className="text-amber-500 shrink-0" />}
                                <div>
                                    <span className="text-[9px] font-black uppercase text-slate-400 block leading-none mb-1">Inicjator Operacji</span>
                                    <span className={`text-xs font-black uppercase tracking-tight ${isAuto ? 'text-purple-700' : 'text-amber-700'}`}>
                                        {syncState.triggered_by}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {msg && (
                        <div className={`mt-4 p-3 rounded-xl text-xs font-bold flex items-center gap-2 border animate-in slide-in-from-bottom-2 ${msg.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-rose-50 border-rose-200 text-rose-800'}`}>
                            <AlertCircle size={14} /> {msg.text}
                        </div>
                    )}
                </div>

                {/* PRAWA STRONA: PRZYCISK RĘCZNY (GŁĘBOKA CZERŃ) */}
                <div className="bg-slate-950 text-white rounded-[2.5rem] p-8 flex flex-col justify-between shadow-xl relative overflow-hidden group">
                    <div>
                        <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 block mb-2">Wymuszenie systemu</span>
                        <h3 className="text-xl font-black leading-tight">Zażądaj natychmiastowej aktualizacji</h3>
                        <p className="text-xs font-medium text-slate-400 mt-3 leading-relaxed">
                            Jeżeli w D365 powstały zamówienia, nie czekaj na 10-minutowy harmonogram automatyczny. Zaktualizuj bazę natychmiast.
                        </p>
                    </div>

                    <button 
                        onClick={handleManualSync}
                        disabled={isSyncing}
                        className="w-full bg-white hover:bg-indigo-50 text-slate-900 py-4 rounded-2xl text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 shadow-lg transition-all active:scale-[0.98] disabled:opacity-40"
                    >
                        <RefreshCcw size={14} className={isSyncing ? "animate-spin" : ""} />
                        {isSyncing ? 'Synchronizuję...' : 'Uruchom ręcznie'}
                    </button>
                </div>
            </div>
            <div className="flex-1"></div>
        </div>
    );
};

export default D365Sync;