import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart3, CalendarDays, RefreshCw, Box, Layers, X } from 'lucide-react';

const Dashboard = () => {
    const getTodayDate = () => new Date().toISOString().split('T')[0];
    
    const [date, setDate] = useState(getTodayDate());
    const [hourlyData, setHourlyData] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    
    // --- NOWOŚĆ: Stan odpowiedzialny za otwarte okno modalne (null, '1F' lub '1P') ---
    const [activeModal, setActiveModal] = useState(null);

    // --- POBIERANIE DANYCH ---
    const fetchForecast = async () => {
        setIsLoading(true);
        try {
            const res = await axios.get(`/api/analytics/forecast/hourly?target_date=${date}`);
            setHourlyData(res.data || []);
        } catch (error) {
            console.error("Błąd pobierania forecastu:", error);
            setHourlyData([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchForecast();
    }, [date]);

    // --- OBLICZENIA STATYSTYK ---
    const total1F = hourlyData.reduce((sum, h) => sum + h.yf, 0);
    const total1P = hourlyData.reduce((sum, h) => sum + h.yp, 0);
    const totalAll = total1F + total1P;

    const maxVal = Math.max(...hourlyData.map(h => Math.max(h.yf, h.yp)), 100);

    return (
        <div className="space-y-6 animate-in fade-in duration-500 p-1">
            
            {/* PANEL KONTROLNY: TYTUŁ + KALENDARZ */}
            <div className="flex justify-between items-center bg-[#1e2433] rounded-xl p-3 shadow-sm text-white">
                <div className="flex items-center gap-3">
                    <BarChart3 className="text-indigo-400" size={18} />
                    <h2 className="text-xs font-black uppercase tracking-widest">Magazyn Live Dashboard</h2>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center bg-[#151923] p-1 rounded-lg border border-slate-700">
                        <CalendarDays size={14} className="text-indigo-400 ml-2" />
                        <input 
                            type="date" 
                            value={date} 
                            onChange={e => setDate(e.target.value)} 
                            className="bg-transparent text-[10px] font-black px-2 py-1 outline-none text-slate-300 [color-scheme:dark]" 
                        />
                    </div>
                    <button 
                        onClick={fetchForecast} 
                        className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                        title="Odśwież dane"
                    >
                        <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
                    </button>
                </div>
            </div>

            {/* KOMPAKTOWY PANEL FORECASTU GODZINOWEGO */}
            <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm grid grid-cols-1 lg:grid-cols-4 gap-6">
                
                {/* LEWA STRONA: PODSUMOWANIE WOLUMENU DIZENNNEGO */}
                <div className="flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-100 pb-4 lg:pb-0 lg:pr-6">
                    <div>
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Total Intake Forecast</p>
                        <h3 className="text-3xl font-black text-slate-800 tracking-tight">{totalAll.toLocaleString()} <span className="text-xs text-slate-400 font-normal">pcs</span></h3>
                    </div>
                    
                    {/* ZMIANA: Kafelki posiadają teraz właściwości przycisków (interakcja) */}
                    <div className="grid grid-cols-2 gap-2 mt-4">
                        <div 
                            onClick={() => setActiveModal('1F')}
                            className="bg-indigo-50/60 p-2 rounded-xl border border-indigo-100/80 cursor-pointer hover:bg-indigo-100/50 hover:scale-[1.02] active:scale-[0.98] transition-all select-none group"
                        >
                            <div className="flex items-center gap-1.5 text-indigo-600 mb-0.5">
                                <Box size={12} />
                                <span className="text-[9px] font-black uppercase tracking-wider group-hover:underline">Stream 1F</span>
                            </div>
                            <p className="text-sm font-bold text-slate-800">{total1F.toLocaleString()}</p>
                        </div>
                        
                        <div 
                            onClick={() => setActiveModal('1P')}
                            className="bg-amber-50/60 p-2 rounded-xl border border-amber-100/80 cursor-pointer hover:bg-amber-100/50 hover:scale-[1.02] active:scale-[0.98] transition-all select-none group"
                        >
                            <div className="flex items-center gap-1.5 text-amber-600 mb-0.5">
                                <Layers size={12} />
                                <span className="text-[9px] font-black uppercase tracking-wider group-hover:underline">Stream 1P</span>
                            </div>
                            <p className="text-sm font-bold text-slate-800">{total1P.toLocaleString()}</p>
                        </div>
                    </div>
                </div>

                {/* PRAWA STRONA: WYKRES SŁUPKOWY */}
                <div className="lg:col-span-3 flex flex-col justify-end">
                    {hourlyData.length === 0 ? (
                        <div className="h-28 flex items-center justify-center text-slate-400 text-xs font-medium border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                            Brak danych planistycznych na wybrany dzień.
                        </div>
                    ) : (
                        <div>
                            <div className="h-24 flex items-end gap-1 px-2 border-b border-slate-100 overflow-x-auto pb-1 custom-scrollbar">
                                {hourlyData.map((h) => {
                                    const h1F = (h.yf / maxVal) * 100;
                                    const h1P = (h.yp / maxVal) * 100;
                                    return (
                                        <div key={h.hour} className="flex-1 min-w-[32px] flex items-end justify-center gap-[2px] group relative h-full">
                                            <div style={{ height: `${h1F}%` }} className="w-3 bg-indigo-500 rounded-t-[2px] transition-all group-hover:bg-indigo-600 relative"></div>
                                            <div style={{ height: `${h1P}%` }} className="w-3 bg-amber-500 rounded-t-[2px] transition-all group-hover:bg-amber-600 relative"></div>

                                            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-[9px] p-1.5 rounded shadow-xl hidden group-hover:block z-30 whitespace-nowrap font-bold">
                                                <p className="text-indigo-400">1F: {h.yf.toLocaleString()} pcs</p>
                                                <p className="text-amber-400">1P: {h.yp.toLocaleString()} pcs</p>
                                                <p className="border-t border-slate-700 mt-0.5 pt-0.5 text-[8px] text-slate-400 font-normal">Godzina: {h.hour}</p>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="flex gap-1 px-2 pt-1 overflow-x-auto text-[8px] font-black text-slate-400 uppercase tracking-tighter">
                                {hourlyData.map((h) => (
                                    <div key={h.hour} className="flex-1 min-w-[32px] text-center">
                                        {h.hour.split(':')[0]}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

            </div>

            {/* --- NOWOŚĆ: OKNO MODALNE (PO-UP Z TABELĄ DANYCH) --- */}
            {activeModal && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
                    <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-150">
                        
                        {/* Nagłówek Modala */}
                        <div className={`p-4 text-white flex justify-between items-center ${activeModal === '1F' ? 'bg-indigo-600' : 'bg-amber-600'}`}>
                            <div className="flex items-center gap-2">
                                {activeModal === '1F' ? <Box size={16} /> : <Layers size={16} />}
                                <h3 className="text-xs font-black uppercase tracking-widest">
                                    Szczegóły godzinowe: Stream {activeModal} ({date})
                                </h3>
                            </div>
                            <button 
                                onClick={() => setActiveModal(null)}
                                className="hover:bg-black/20 p-1 rounded-lg transition-colors text-white"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        {/* Tabela danych (Z możliwością scrollowania pionowego) */}
                        <div className="overflow-y-auto flex-1 p-2 custom-scrollbar bg-slate-50">
                            {hourlyData.length === 0 ? (
                                <p className="text-center text-xs text-slate-500 py-8 font-medium">Brak danych do wyświetlenia.</p>
                            ) : (
                                <table className="w-full text-left border-collapse bg-white rounded-xl overflow-hidden border border-slate-100 shadow-xs">
                                    <thead>
                                        <tr className="bg-slate-100 text-slate-500 text-[10px] font-black uppercase tracking-wider border-b border-slate-200">
                                            <th className="px-4 py-2.5">Przedział Godzinowy</th>
                                            <th className="px-4 py-2.5 text-right">Prognoza (PCS Intake)</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 text-xs font-medium text-slate-700">
                                        {hourlyData.map((h) => {
                                            const currentPcs = activeModal === '1F' ? h.yf : h.yp;
                                            // Wyliczamy ładny przedział (np. 08:00 - 09:00)
                                            const startHour = h.hour;
                                            const endHour = `${String((parseInt(startHour.split(':')[0]) + 1) % 24).padStart(2, '0')}:00`;
                                            
                                            return (
                                                <tr key={h.hour} className="hover:bg-slate-50/80 transition-colors">
                                                    <td className="px-4 py-2 font-mono text-slate-500">{startHour} - {endHour}</td>
                                                    <td className="px-4 py-2 text-right font-bold text-slate-800">
                                                        {currentPcs > 0 ? currentPcs.toLocaleString() : <span className="text-slate-300 font-normal">0</span>}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                    {/* Stopka tabeli z podsumowaniem */}
                                    <tfoot>
                                        <tr className="bg-slate-50 border-t-2 border-slate-200 font-black text-slate-800 text-xs">
                                            <td className="px-4 py-3 uppercase tracking-wider text-slate-500">Suma doiobowa:</td>
                                            <td className="px-4 py-3 text-right text-base text-slate-900">
                                                {(activeModal === '1F' ? total1F : total1P).toLocaleString()} <span className="text-[10px] text-slate-400 font-normal">pcs</span>
                                            </td>
                                        </tr>
                                    </tfoot>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* SEKCOJA AI - MIEJSCE NA REKOMENDACJE OBSADY */}
            <div className="border border-dashed border-slate-200 rounded-2xl h-48 flex items-center justify-center bg-white/50 text-slate-400 text-xs font-semibold">
                Miejsce na sekcję rekomendacji obsady AI (Wkrótce)
            </div>

        </div>
    );
};

export default Dashboard;