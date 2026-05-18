import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Database, CalendarDays, Save, RefreshCcw } from 'lucide-react';

const SystemData = () => {
    const getTodayDate = () => new Date().toISOString().split('T')[0];

    // --- STANY ---
    const [date, setDate] = useState(getTodayDate());
    const [shift, setShift] = useState('1');
    const [totalWorkers, setTotalWorkers] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const initialConstraints = [
        { zone_name: 'Rozładunek', category: 'INBOUND', priority: 'P1', s1_min: 0, s1_max: 0, s2_min: 1, s2_max: 2, s3_min: 0, s3_max: 0 },
        { zone_name: 'Przyjęcie', category: 'INBOUND', priority: 'P3', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Putaway', category: 'INBOUND', priority: 'P4', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Sprzątanie', category: 'INBOUND', priority: 'P2', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Nieproduktywne', category: 'INBOUND', priority: 'P5', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Pick', category: 'OUTBOUND', priority: 'P2', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Pack', category: 'OUTBOUND', priority: 'P3', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Sort', category: 'OUTBOUND', priority: 'P4', s1_min: 0, s1_max: 0, s2_min: 0, s2_max: 0, s3_min: 0, s3_max: 0 },
        { zone_name: 'Załadunki', category: 'OUTBOUND', priority: 'P1', s1_min: 0, s1_max: 0, s2_min: 1, s2_max: 3, s3_min: 0, s3_max: 0 }
    ];

    const [constraints, setConstraints] = useState(initialConstraints);

    // --- 1. POBIERANIE KONFIGURACJI Z BAZY (ZALEŻNE OD DATY!) ---
    const loadConstraints = async () => {
        try {
            // Zmiana: Odpytujemy o konkretny dzień
            const res = await axios.get(`/api/settings/constraints/${date}`);
            
            if (res.data && res.data.length > 0) {
                // Konwertujemy priorytety z liczb na format wizualny "P1"
                const mappedData = res.data.map(item => ({
                    ...item,
                    priority: String(item.priority).includes('P') ? item.priority : `P${item.priority}`
                }));
                setConstraints(mappedData);
            } else {
                // Zmiana: Jeśli w bazie na ten dzień nic nie ma, wracamy do czystego szablonu
                setConstraints(initialConstraints);
            }
        } catch (e) {
            console.error("Błąd ładowania z DB, używam domyślnych.");
            setConstraints(initialConstraints);
        }
    };

    // --- 2. POBIERANIE SUMY LUDZI Z GRAFIKU ---
    const fetchWorkersCount = async () => {
        setIsLoading(true);
        try {
            const res = await axios.get(`/api/plan/workers/${shift}?target_date=${date}`);
            setTotalWorkers(res.data.length || 0);
        } catch (error) {
            setTotalWorkers(0);
        } finally {
            setIsLoading(false);
        }
    };

    // Zmiana: Nasłuchujemy zmiany daty, by odświeżyć tabelę z regułami
    useEffect(() => { loadConstraints(); }, [date]);
    useEffect(() => { fetchWorkersCount(); }, [date, shift]);

    // --- 3. LOGIKA KALKULATORA ---
    const activeMinKey = `s${shift}_min`;
    const totalAssignedMin = constraints.reduce((sum, item) => sum + (Number(item[activeMinKey]) || 0), 0);
    const remainingWorkers = totalWorkers - totalAssignedMin;

    const handleInputChange = (zoneName, field, value) => {
        const numValue = parseInt(value) || 0;
        setConstraints(prev => prev.map(c => 
            c.zone_name === zoneName ? { ...c, [field]: numValue < 0 ? 0 : numValue } : c
        ));
    };

    // --- 4. ZAPIS DO BAZY ---
    const handleSave = async () => {
        setIsSaving(true);
        try {
            // Zmiana: Wysyłamy dane z priorytetem jako string "P1", "P2" (tak, jak oczekuje tego Pydantic)
            const dataToSave = constraints.map(c => ({
                ...c,
                priority: String(c.priority).includes('P') ? String(c.priority) : `P${c.priority}`
            }));

            const payload = {
                target_date: date,
                constraints: dataToSave
            };

            await axios.post('/api/settings/constraints', payload);
            alert(`✅ Konfiguracja AI zapisana pomyślnie dla dnia: ${date}`);
            loadConstraints(); // Odświeżamy dane
        } catch (error) {
            console.error(error);
            alert("❌ Błąd zapisu! Sprawdź logi backendu.");
        } finally {
            setIsSaving(false);
        }
    };

    const getPriorityBadge = (p) => {
        const pValue = String(p).includes('P') ? p : `P${p}`;
        const styles = { P1: 'bg-red-500', P2: 'bg-orange-500', P3: 'bg-amber-400', P4: 'bg-slate-300', P5: 'bg-slate-400' };
        return <span className={`px-1.5 py-0.5 rounded text-[9px] font-black text-white ${styles[pValue] || 'bg-slate-200'}`}>{pValue}</span>;
    };

    return (
        <div className="flex flex-col h-full bg-[#f8fafc] overflow-hidden p-4">
            
            {/* PANEL GÓRNY (PASEK CZARNY) */}
            <div className="bg-[#1e2433] rounded-t-xl p-3 flex justify-between items-center shadow-md shrink-0">
                <div className="flex items-center gap-3">
                    <Database className="text-indigo-400" size={18} />
                    <h2 className="text-xs font-black text-white tracking-widest uppercase">AI Constraints Manager</h2>
                </div>

                <div className="flex items-center gap-3">
                    <div className="flex bg-[#151923] p-1 rounded-lg border border-slate-700">
                        {['1', '2', '3'].map(s => (
                            <button 
                                key={s} 
                                onClick={() => setShift(s)} 
                                className={`px-4 py-1.5 rounded text-[10px] font-black transition-all ${shift === s ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                Shift {s}
                            </button>
                        ))}
                    </div>
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
                        onClick={handleSave} 
                        disabled={isSaving} 
                        className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 rounded-lg text-[10px] font-black uppercase flex items-center gap-2 transition-all disabled:opacity-50"
                    >
                        {isSaving ? <RefreshCcw size={12} className="animate-spin" /> : <Save size={12} />} Zapisz
                    </button>
                </div>
            </div>

            {/* PRZELICZNIK (MAŁY PASEK POD NAGŁÓWKIEM) */}
            <div className="bg-white border-x border-b border-slate-200 rounded-b-xl p-2.5 mb-4 shadow-sm flex items-center gap-6 text-[10px] font-bold shrink-0">
                <div className="flex items-center gap-2 pl-2">
                    <span className="text-slate-400 uppercase tracking-tighter">Suma grafik:</span>
                    <span className="text-slate-900 font-black text-xs">{totalWorkers}</span>
                </div>
                <div className="text-slate-300 font-light">|</div>
                <div className="flex items-center gap-2">
                    <span className="text-amber-500 uppercase tracking-tighter">Zablokowani (Min Staff):</span>
                    <span className="text-amber-600 font-black text-xs">{totalAssignedMin}</span>
                </div>
                <div className="text-slate-300 font-light">|</div>
                <div className="bg-indigo-50 px-4 py-1.5 rounded-md flex items-center gap-2">
                    <span className="text-indigo-500 uppercase tracking-tighter">Dostępni dla AI:</span>
                    <span className={`font-black text-sm ${remainingWorkers < 0 ? 'text-red-600' : 'text-indigo-700'}`}>
                        {remainingWorkers}
                    </span>
                </div>
            </div>

            {/* TABELA (KOMPAKTOWA) */}
            <div className="flex-1 overflow-y-auto custom-scrollbar bg-white border border-slate-200 rounded-xl shadow-sm">
                <table className="w-full text-left border-collapse table-fixed">
                    <thead className="bg-[#2D3748] text-white text-[9px] uppercase tracking-widest sticky top-0 z-20 shadow-sm">
                        <tr>
                            <th className="px-4 py-3 w-1/3">Strefa Operacyjna</th>
                            <th className="px-4 py-3 text-center w-20">Prio</th>
                            <th className="px-4 py-3 text-center bg-[#252d3a] w-28">Min (S{shift})</th>
                            <th className="px-4 py-3 text-center bg-[#1e2433] w-28">Max (S{shift})</th>
                        </tr>
                    </thead>
                    <tbody className="text-[11px]">
                        {['INBOUND', 'OUTBOUND'].map(cat => (
                            <React.Fragment key={cat}>
                                <tr className="bg-slate-800 text-slate-400">
                                    <td colSpan="4" className="text-[8px] font-black uppercase tracking-[0.2em] px-4 py-1">{cat}</td>
                                </tr>
                                {constraints.filter(c => c.category === cat).map((row) => (
                                    <tr key={row.zone_name} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                        <td className="px-4 py-2 font-bold text-slate-700 truncate">{row.zone_name}</td>
                                        <td className="px-4 py-2 text-center">{getPriorityBadge(row.priority)}</td>
                                        <td className="px-4 py-2 text-center bg-slate-50/30">
                                            <input 
                                                type="number" 
                                                value={row[`s${shift}_min`] ?? 0} 
                                                onChange={e => handleInputChange(row.zone_name, `s${shift}_min`, e.target.value)}
                                                className="w-12 text-center font-black border border-slate-200 rounded py-0.5 outline-none focus:border-indigo-500"
                                            />
                                        </td>
                                        <td className="px-4 py-2 text-center">
                                            <input 
                                                type="number" 
                                                value={row[`s${shift}_max`] ?? 0} 
                                                onChange={e => handleInputChange(row.zone_name, `s${shift}_max`, e.target.value)}
                                                className="w-12 text-center font-black border border-slate-200 rounded py-0.5 outline-none focus:border-indigo-500"
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </React.Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default SystemData;