import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bot, CheckCircle2, CalendarDays, Clock, RefreshCcw, Loader2, Award } from 'lucide-react';

const ZONES = [
    { id: 'receiving', label: 'Receiving' },
    { id: 'putaway', label: 'Putaway' },
    { id: 'picking', label: 'Picking' },
    { id: 'packing', label: 'Packing' },
    { id: 'sorting', label: 'Sorting' }
];

const WorkPlan = () => {
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [shift, setShift] = useState('1'); 
    const [isLoading, setIsLoading] = useState(false);
    const [isDraft, setIsDraft] = useState(false);
    
    const [pool, setPool] = useState([]);
    const [zones, setZones] = useState({
        receiving: [], putaway: [], picking: [], packing: [], sorting: []
    });

    // --- HELPER: NAJLEPSZY SKILL ---
    const getBestSkill = (worker) => {
        const skills = [
            { id: 'receiving', label: 'Rec', val: worker.receiving || 0 },
            { id: 'putaway', label: 'Put', val: worker.putaway || 0 },
            { id: 'picking', label: 'Pick', val: worker.picking || 0 },
            { id: 'packing', label: 'Pack', val: worker.packing || 0 },
            { id: 'sorting', label: 'Sort', val: worker.sorting || 0 }
        ];
        const best = skills.reduce((prev, current) => (prev.val > current.val) ? prev : current);
        return best.val > 0 ? best : { label: 'Newbie', val: 0 };
    };

    // --- POBIERANIE DANYCH ---
    const fetchData = async () => {
        setIsLoading(true);
        try {
            console.log(`📡 Pobieram plan: Shift ${shift}, Data ${date}`);
            const response = await axios.get(`/api/plan/workers/${shift}?target_date=${date}`);
            const allWorkers = response.data;

            const newZones = { receiving: [], putaway: [], picking: [], packing: [], sorting: [] };
            const newPool = [];

            if (allWorkers && Array.isArray(allWorkers)) {
                allWorkers.forEach(worker => {
                    const currentTask = worker.task ? worker.task.toLowerCase().trim() : 'unassigned';
                    
                    if (currentTask !== 'unassigned' && newZones[currentTask]) {
                        newZones[currentTask].push(worker);
                    } else {
                        newPool.push(worker);
                    }
                });
            }

            setPool(newPool);
            setZones(newZones);
            setIsDraft(false); 
        } catch (error) {
            console.error("❌ Błąd pobierania danych:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [date, shift]);

    // --- DRAG & DROP LOGIKA ---
    const handleDragStart = (e, workerId, sourceZone) => {
        e.dataTransfer.setData('workerId', workerId);
        e.dataTransfer.setData('sourceZone', sourceZone);
    };

    const handleDrop = (e, targetZone) => {
        const workerId = e.dataTransfer.getData('workerId');
        const sourceZone = e.dataTransfer.getData('sourceZone');

        if (!workerId || sourceZone === targetZone) return;

        let worker;
        if (sourceZone === 'pool') {
            worker = pool.find(w => String(w.worker_login) === String(workerId));
            if (!worker) return;
            setPool(prev => prev.filter(w => String(w.worker_login) !== String(workerId)));
        } else {
            worker = zones[sourceZone].find(w => String(w.worker_login) === String(workerId));
            if (!worker) return;
            setZones(prev => ({ 
                ...prev, 
                [sourceZone]: prev[sourceZone].filter(w => String(w.worker_login) !== String(workerId)) 
            }));
        }

        const updatedWorker = { ...worker, task: targetZone };

        if (targetZone === 'pool') {
            setPool(prev => [...prev, { ...updatedWorker, task: 'unassigned' }]);
        } else {
            setZones(prev => ({ 
                ...prev, 
                [targetZone]: [...prev[targetZone], updatedWorker] 
            }));
        }
        setIsDraft(true);
    };

    // --- AI/OPTIMIZER SUGGESTION ---
    const handleAISuggestion = async () => {
        setIsLoading(true);
        try {
            // 1. Zbieramy loginy osób, które już są rozpisane na strefach (zablokowane)
            const assignedLogins = Object.values(zones)
                .flat()
                .map(w => String(w.worker_login));

            const response = await axios.post('/api/plan/ai_suggest', { 
                shift: shift,
                target_date: date,
                locked_logins: assignedLogins // <--- Wysyłamy zablokowanych do backendu
            });
            const suggestions = response.data; 

            // 2. Klonujemy aktualny stan stref (żeby nie ruszać tych już przypisanych)
            const newZones = { ...zones };
            const newPool = [];

            // 3. Iterujemy TYLKO po pracownikach, którzy są obecnie w "Unassigned Pool"
            pool.forEach(w => {
                const suggestedTask = suggestions[String(w.worker_login)];
                if (suggestedTask && newZones[suggestedTask]) {
                    // Jeśli AI znalazło dla niego miejsce, dodajemy go do strefy
                    newZones[suggestedTask] = [...newZones[suggestedTask], { ...w, task: suggestedTask }];
                } else {
                    // Jeśli dalej nie ma miejsca, zostaje w puli
                    newPool.push(w);
                }
            });

            setZones(newZones);
            setPool(newPool);
            setIsDraft(true);
        } catch (error) {
            console.error("❌ AI Error:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // --- POTWIERDZENIE I ZAPIS ---
    const handleConfirm = async () => {
        setIsLoading(true);
        try {
            const assignments = [];
            Object.keys(zones).forEach(zoneId => {
                zones[zoneId].forEach(worker => {
                    assignments.push({
                        worker_login: String(worker.worker_login),
                        shift: shift,
                        task: zoneId
                    });
                });
            });

            pool.forEach(worker => {
                assignments.push({
                    worker_login: String(worker.worker_login),
                    shift: shift,
                    task: 'unassigned'
                });
            });

            await axios.post(`/api/plan/save?target_date=${date}`, assignments);
            setIsDraft(false);
            alert("Plan został pomyślnie zapisany!");
        } catch (error) {
            console.error("❌ Błąd zapisu:", error);
            alert("Błąd zapisu! Sprawdź konsolę backendu.");
        } finally {
            setIsLoading(false);
        }
    };

    // --- KARTA PRACOWNIKA ---
    const WorkerCard = ({ worker, sourceZone }) => {
        const topSkill = getBestSkill(worker);
        
        // Zabezpieczenie: jeśli imię to po prostu "pracownik", nie pokazujemy go
        const nameToDisplay = worker.full_name?.toLowerCase() === 'pracownik' ? null : worker.full_name;

        return (
            <div
                draggable
                onDragStart={(e) => handleDragStart(e, worker.worker_login, sourceZone)}
                className={`p-3 rounded-xl border mb-2 cursor-grab active:cursor-grabbing shadow-sm transition-all hover:border-indigo-400 ${
                    isDraft ? 'bg-indigo-50/50 border-indigo-200' : 'bg-white border-slate-200'
                }`}
            >
                <div className="flex justify-between items-start mb-2">
                    <div className="flex flex-col gap-1 w-full overflow-hidden">
                        {/* SAM LOGIN - ZROBIONY NA GŁÓWNY PUNKT KARTY */}
                        <span className="text-[13px] font-black text-slate-800 tracking-tight leading-none uppercase">
                            {worker.worker_login}
                        </span>
                        
                        {/* Imię pokazuje się TYLKO jeśli to faktyczne imię, a nie domyślne "PRACOWNIK" */}
                        {nameToDisplay && (
                            <span className="text-[9px] font-bold text-slate-400 leading-none uppercase truncate" title={nameToDisplay}>
                                {nameToDisplay}
                            </span>
                        )}

                        <div className={`flex items-center w-fit gap-1 px-1.5 py-0.5 mt-1 rounded-md text-[8px] font-black uppercase tracking-tighter border ${
                            topSkill.val >= 5 ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-slate-50 border-slate-200 text-slate-500'
                        }`}>
                            {topSkill.val >= 5 && <Award size={10} className="text-amber-500" />}
                            {topSkill.label}: {topSkill.val}
                        </div>
                    </div>
                    <div className="flex gap-0.5 pt-0.5 shrink-0">
                        {[1, 2, 3, 4, 5, 6].map(i => (
                            <div key={i} className={`w-1 h-3 rounded-full ${worker.picking >= i ? 'bg-indigo-500' : 'bg-slate-100'}`} />
                        ))}
                    </div>
                </div>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-50">
                    <div className="flex items-center gap-1 text-[9px] font-bold text-slate-400 uppercase">
                        <Clock size={10} /> {worker.hours || '8h'}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full bg-[#f8fafc] relative">
            {/* TOOLBAR */}
            <div className="flex justify-between items-center p-6 bg-white border-b border-slate-200 shrink-0 shadow-sm z-10">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 bg-slate-50 p-1 rounded-2xl border border-slate-200 shadow-sm">
                        <CalendarDays size={16} className="text-slate-400 ml-3" />
                        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="bg-transparent text-xs font-black p-2 outline-none text-slate-700 cursor-pointer" />
                        <div className="w-px h-4 bg-slate-200 mx-2" />
                        <Clock size={16} className="text-slate-400" />
                        <select value={shift} onChange={(e) => setShift(e.target.value)} className="bg-transparent text-xs font-black p-2 outline-none cursor-pointer text-slate-700 uppercase">
                            <option value="1">Shift I</option>
                            <option value="2">Shift II</option>
                            <option value="3">Shift III</option>
                        </select>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button onClick={fetchData} className="p-2.5 text-slate-400 hover:bg-slate-50 rounded-xl transition-all">
                        <RefreshCcw size={18} className={`${isLoading ? 'animate-spin' : ''}`} />
                    </button>
                    <button onClick={handleAISuggestion} className="bg-slate-900 text-white px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center gap-2 shadow-lg hover:bg-indigo-600 transition-all hover:-translate-y-0.5">
                        <Bot size={14} /> AI Suggestion
                    </button>
                    <button disabled={!isDraft} onClick={handleConfirm} className="bg-emerald-600 text-white px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center gap-2 shadow-lg disabled:opacity-30 transition-all hover:bg-emerald-700 hover:-translate-y-0.5">
                        <CheckCircle2 size={14} /> Confirm Plan
                    </button>
                </div>
            </div>

            {/* MAIN WORKSPACE */}
            <div className="flex flex-1 overflow-hidden p-6 gap-6">
                {/* Pula nieprzypisanych */}
                <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => handleDrop(e, 'pool')} className="w-72 bg-slate-200/30 border-2 border-dashed border-slate-300 rounded-[2.5rem] flex flex-col overflow-hidden shadow-inner shrink-0">
                    <div className="p-5 bg-white/50 border-b border-slate-200 flex justify-between items-center backdrop-blur-sm">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Unassigned Pool</span>
                        <span className="bg-white text-slate-900 text-[10px] font-black px-3 py-1 rounded-full border border-slate-200 shadow-sm">{pool.length}</span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                        {pool.map(worker => <WorkerCard key={worker.worker_login} worker={worker} sourceZone="pool" />)}
                    </div>
                </div>

                {/* Kolumny stref */}
                <div className="flex-1 flex gap-4 overflow-x-auto pb-4 custom-scrollbar">
                    {ZONES.map(zone => (
                        <div key={zone.id} onDragOver={(e) => e.preventDefault()} onDrop={(e) => handleDrop(e, zone.id)} className="bg-white border border-slate-200 rounded-[2rem] flex flex-col min-w-[220px] max-w-[260px] flex-1 shadow-sm overflow-hidden hover:border-indigo-200 transition-all group">
                            <div className="p-4 border-b border-slate-50 flex justify-between items-center bg-slate-50/50 group-hover:bg-indigo-50/30 transition-colors">
                                <h3 className="text-[10px] font-black text-slate-400 group-hover:text-indigo-600 uppercase tracking-widest transition-colors">{zone.label}</h3>
                                <span className="text-[10px] font-black text-indigo-600 bg-white px-2 py-1 rounded-lg border border-indigo-100">{zones[zone.id]?.length || 0}</span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3 custom-scrollbar">
                                {zones[zone.id]?.map(worker => <WorkerCard key={worker.worker_login} worker={worker} sourceZone={zone.id} />)}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* LOADER OVERLAY */}
            {isLoading && (
                <div className="absolute inset-0 bg-slate-900/10 backdrop-blur-[2px] z-50 flex items-center justify-center">
                    <div className="bg-white p-8 rounded-3xl shadow-2xl flex flex-col items-center border border-slate-200 animate-in zoom-in duration-200">
                        <Loader2 className="animate-spin text-indigo-600 mb-4" size={40} />
                        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-800">Processing Data...</span>
                    </div>
                </div>
            )}
        </div>
    );
};

export default WorkPlan;