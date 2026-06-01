import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bot, CheckCircle2, CalendarDays, Clock, RefreshCcw, Loader2, Briefcase } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';

// ZMIANA: Zaktualizowana struktura ZONES o nową grupę zadań menadżerskich
const ZONES = [
    { id: 'receiving', label: 'Receiving' },
    { id: 'putaway', label: 'Putaway' },
    { 
        id: 'picking_group', 
        label: 'Picking', 
        subZones: [
            { id: 'picking_mezz_m0', label: 'MEZZ M0' },
            { id: 'picking_mezz_m1', label: 'MEZZ M1' },
            { id: 'picking_mezz_m2', label: 'MEZZ M2' },
            { id: 'picking_rack', label: 'RACK' }
        ]
    },
    { id: 'packing', label: 'Packing' },
    { id: 'sorting', label: 'Sorting' },
    { 
        id: 'manager_group', 
        label: 'Manager Tasks',
        subZones: [
            { id: 'task_cleaning', label: 'Sprzątanie' },
            { id: 'task_filler', label: 'Wypełniacz' },
            { id: 'task_waterspider', label: 'Water-spider' },
            { id: 'task_training', label: 'Szkolenie' },
            { id: 'task_relocation', label: 'Relokacja' }
        ]
    }
];

const WorkPlan = () => {
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [shift, setShift] = useState('1'); 
    const [isLoading, setIsLoading] = useState(false);
    const [isDraft, setIsDraft] = useState(false);
    
    const [pool, setPool] = useState([]);
    
    // ZMIANA: Zaktualizowany stan początkowy o 5 nowych stref i usunięto starą
    const [zones, setZones] = useState({
        receiving: [], putaway: [], packing: [], sorting: [], 
        picking_mezz_m0: [], picking_mezz_m1: [], picking_mezz_m2: [], picking_rack: [],
        task_cleaning: [], task_filler: [], task_waterspider: [], task_training: [], task_relocation: []
    });

    const getBestSkill = (worker) => {
        const skills = [
            { id: 'receiving', label: 'Rec', val: worker.receiving || 0 },
            { id: 'putaway', label: 'Put', val: worker.putaway || 0 },
            { id: 'picking', label: 'Pick', val: worker.picking || 0 },
            { id: 'packing', label: 'Pack', val: worker.packing || 0 },
            { id: 'sorting', label: 'Sort', val: worker.sorting || 0 }
        ];
        const best = skills.reduce((prev, current) => (prev.val > current.val) ? prev : current);
        return best.val > 0 ? best : { label: 'New', val: 0 };
    };

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const response = await axios.get(`/api/plan/workers/${shift}?target_date=${date}`);
            const allWorkers = response.data;

            const newZones = { 
                receiving: [], putaway: [], packing: [], sorting: [], 
                picking_mezz_m0: [], picking_mezz_m1: [], picking_mezz_m2: [], picking_rack: [],
                task_cleaning: [], task_filler: [], task_waterspider: [], task_training: [], task_relocation: []
            };
            const newPool = [];

            if (allWorkers && Array.isArray(allWorkers)) {
                allWorkers.forEach(worker => {
                    let currentTask = worker.task ? worker.task.toLowerCase().trim() : 'unassigned';
                    
                    // Bezpieczna migracja starych rekordów
                    if (currentTask === 'picking') currentTask = 'picking_mezz_m0';
                    if (currentTask === 'manager_tasks') currentTask = 'task_cleaning';

                    if (currentTask !== 'unassigned' && newZones[currentTask] !== undefined) {
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

    useEffect(() => { fetchData(); }, [date, shift]);

    const fetchLiveUpdates = async () => {
        try {
            const response = await axios.get(`/api/plan/workers/${shift}?target_date=${date}`);
            const freshWorkers = response.data;
            const freshLookup = {};
            freshWorkers.forEach(w => freshLookup[w.worker_login] = w);

            setPool(prevPool => prevPool.map(worker => {
                const freshData = freshLookup[worker.worker_login];
                return (freshData && freshData.is_present !== worker.is_present) 
                    ? { ...worker, is_present: freshData.is_present } : worker;
            }));

            setZones(prevZones => {
                const updatedZones = { ...prevZones };
                let hasChanges = false;
                Object.keys(updatedZones).forEach(zoneId => {
                    updatedZones[zoneId] = updatedZones[zoneId].map(worker => {
                        const freshData = freshLookup[worker.worker_login];
                        if (freshData && freshData.is_present !== worker.is_present) {
                            hasChanges = true;
                            return { ...worker, is_present: freshData.is_present };
                        }
                        return worker;
                    });
                });
                return hasChanges ? updatedZones : prevZones;
            });
        } catch (error) {
            console.warn("Background sync failed:", error.message);
        }
    };

    usePolling(fetchLiveUpdates, 10000);

    const handlePresenceChange = async (workerLogin, currentStatus) => {
        const newStatus = !currentStatus; 
        try {
            const response = await axios.post('/api/plan/update-presence', {
                login: String(workerLogin),
                is_present: newStatus
            });
            if (response.status === 200) {
                setPool(prev => prev.map(w => String(w.worker_login) === String(workerLogin) ? { ...w, is_present: newStatus } : w));
                setZones(prev => {
                    const newZones = { ...prev };
                    Object.keys(newZones).forEach(zoneId => {
                        newZones[zoneId] = newZones[zoneId].map(w => String(w.worker_login) === String(workerLogin) ? { ...w, is_present: newStatus } : w);
                    });
                    return newZones;
                });
            }
        } catch (error) {
            console.error("❌ Błąd:", error);
        }
    };

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
            setZones(prev => ({ ...prev, [sourceZone]: prev[sourceZone].filter(w => String(w.worker_login) !== String(workerId)) }));
        }

        const updatedWorker = { ...worker, task: targetZone };

        if (targetZone === 'pool') {
            setPool(prev => [...prev, { ...updatedWorker, task: 'unassigned' }]);
        } else {
            setZones(prev => ({ ...prev, [targetZone]: [...prev[targetZone], updatedWorker] }));
        }
        setIsDraft(true);
    };

    const handleAISuggestion = async () => {
        setIsLoading(true);
        try {
            const assignedLogins = Object.values(zones).flat().map(w => String(w.worker_login));
            const response = await axios.post('/api/plan/ai_suggest', { shift: shift, target_date: date, locked_logins: assignedLogins });
            const suggestions = response.data; 

            const newZones = { ...zones };
            const newPool = [];

            pool.forEach(w => {
                let suggestedTask = suggestions[String(w.worker_login)];
                
                // Migracja AI
                if (suggestedTask && suggestedTask.toLowerCase().trim() === 'picking') {
                    suggestedTask = 'picking_mezz_m0';
                }
                if (suggestedTask && suggestedTask.toLowerCase().trim() === 'manager_tasks') {
                    suggestedTask = 'task_cleaning';
                }

                if (suggestedTask && newZones[suggestedTask] !== undefined) {
                    newZones[suggestedTask] = [...newZones[suggestedTask], { ...w, task: suggestedTask }];
                } else {
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

    const handleConfirm = async () => {
        setIsLoading(true);
        try {
            const assignments = [];
            Object.keys(zones).forEach(zoneId => {
                zones[zoneId].forEach(worker => {
                    assignments.push({ worker_login: String(worker.worker_login), shift: shift, task: zoneId });
                });
            });
            pool.forEach(worker => {
                assignments.push({ worker_login: String(worker.worker_login), shift: shift, task: 'unassigned' });
            });

            await axios.post(`/api/plan/save?target_date=${date}`, assignments);
            setIsDraft(false);
            alert("Plan został pomyślnie zapisany!");
        } catch (error) {
            alert("Błąd zapisu! Sprawdź konsolę.");
        } finally {
            setIsLoading(false);
        }
    };

    // --- MIKRO-KARTA PRACOWNIKA ---
    const WorkerCard = ({ worker, sourceZone }) => {
        const topSkill = getBestSkill(worker);
        const isPresent = !!worker.is_present;
        const presenceClasses = isPresent 
            ? 'bg-emerald-50 border-emerald-300 text-emerald-900 shadow-emerald-100/50' 
            : 'bg-rose-50 border-rose-200 text-rose-900 opacity-70';         

        return (
            <div
                draggable
                onDragStart={(e) => handleDragStart(e, worker.worker_login, sourceZone)}
                className={`flex flex-col gap-0.5 p-1 rounded-md border cursor-grab active:cursor-grabbing shadow-sm hover:scale-105 transition-transform ${presenceClasses}`}
                title={worker.full_name || 'Brak danych'}
            >
                <div className="flex justify-between items-center w-full gap-0.5">
                    <span className="text-[9px] font-black tracking-tighter truncate leading-none">{worker.worker_login}</span>
                    <input 
                        type="checkbox"
                        checked={isPresent}
                        onChange={() => handlePresenceChange(worker.worker_login, isPresent)}
                        className="w-2 h-2 rounded cursor-pointer accent-emerald-600 shrink-0 border-slate-300 m-0"
                        title="Obecność"
                    />
                </div>
                <div className={`text-[7px] font-black uppercase tracking-widest text-center rounded-[3px] py-[2px] leading-none ${topSkill.val >= 5 ? 'bg-amber-200/70 text-amber-900' : 'bg-white/60 text-slate-500'}`}>
                    {topSkill.label} {topSkill.val}
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full bg-[#f8fafc] relative">
            {/* TOOLBAR */}
            <div className="flex justify-between items-center px-4 py-3 bg-white border-b border-slate-200 shrink-0 shadow-sm z-10">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 bg-slate-50 p-1 rounded-xl border border-slate-200 shadow-sm">
                        <CalendarDays size={14} className="text-slate-400 ml-2" />
                        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="bg-transparent text-xs font-black p-1.5 outline-none text-slate-700 cursor-pointer" />
                        <div className="w-px h-4 bg-slate-200 mx-1" />
                        <Clock size={14} className="text-slate-400" />
                        <select value={shift} onChange={(e) => setShift(e.target.value)} className="bg-transparent text-xs font-black p-1.5 outline-none cursor-pointer text-slate-700 uppercase">
                            <option value="1">Shift I</option>
                            <option value="2">Shift II</option>
                            <option value="3">Shift III</option>
                        </select>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button onClick={fetchData} className="p-2 text-slate-400 hover:bg-slate-50 rounded-lg transition-all">
                        <RefreshCcw size={16} className={`${isLoading ? 'animate-spin' : ''}`} />
                    </button>
                    <button onClick={handleAISuggestion} className="bg-slate-900 text-white px-4 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest flex items-center gap-1.5 shadow-md hover:bg-indigo-600 transition-all hover:-translate-y-0.5">
                        <Bot size={12} /> AI Suggestion
                    </button>
                    <button disabled={!isDraft} onClick={handleConfirm} className="bg-emerald-600 text-white px-4 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest flex items-center gap-1.5 shadow-md disabled:opacity-30 transition-all hover:bg-emerald-700 hover:-translate-y-0.5">
                        <CheckCircle2 size={12} /> Confirm Plan
                    </button>
                </div>
            </div>

            {/* MAIN WORKSPACE */}
            <div className="flex flex-1 overflow-hidden p-3 gap-2">
                
                {/* POOL */}
                <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => handleDrop(e, 'pool')} className="w-[16%] min-w-[140px] bg-slate-200/30 border-2 border-dashed border-slate-300 rounded-2xl flex flex-col overflow-hidden shadow-inner shrink-0">
                    <div className="p-3 bg-white/50 border-b border-slate-200 flex justify-between items-center backdrop-blur-sm">
                        <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest truncate">Unassigned</span>
                        <span className="bg-white text-slate-900 text-[9px] font-black px-2 py-0.5 rounded-full border border-slate-200">{pool.length}</span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 custom-scrollbar grid grid-cols-3 gap-1 content-start">
                        {pool.map(worker => <WorkerCard key={worker.worker_login} worker={worker} sourceZone="pool" />)}
                    </div>
                </div>

                {/* ZONES */}
                <div className="flex-1 flex gap-2 overflow-hidden">
                    {ZONES.map(zone => {
                        
                        // Renderowanie GRUP z kolumnami (np. Picking lub Manager Tasks)
                        if (zone.subZones) {
                            const totalWorkersInGroup = zone.subZones.reduce((sum, sz) => sum + (zones[sz.id]?.length || 0), 0);
                            
                            // Dynamiczne style (Niebieski dla Picking, Bursztynowy dla Managera)
                            const isManager = zone.id === 'manager_group';
                            const bgClass = isManager ? 'bg-amber-50/40 border-amber-200' : 'bg-indigo-50/40 border-indigo-200';
                            const headerBgClass = isManager ? 'bg-amber-100/60 border-amber-200' : 'bg-indigo-100/60 border-indigo-200';
                            const headerTextClass = isManager ? 'text-amber-800' : 'text-indigo-800';
                            const badgeBgClass = isManager ? 'text-amber-700 border-amber-200' : 'text-indigo-700 border-indigo-200';
                            const subZoneHoverClass = isManager ? 'hover:border-amber-300' : 'hover:border-indigo-300';
                            const subZoneBadgeClass = isManager ? 'text-amber-600' : 'text-indigo-600';

                            return (
                                <div key={zone.id} className={`${bgClass} border-2 rounded-2xl flex flex-col flex-[1.2] min-w-[240px] shadow-sm overflow-hidden transition-all`}>
                                    
                                    {/* Nagłówek grupy */}
                                    <div className={`p-2 border-b ${headerBgClass} flex justify-between items-center shadow-sm z-10`}>
                                        <div className="flex items-center">
                                            {isManager && <Briefcase size={10} className="text-amber-500 shrink-0 mr-1.5" />}
                                            <h3 className={`text-[10px] font-black uppercase tracking-widest ${headerTextClass}`}>{zone.label}</h3>
                                        </div>
                                        <span className={`text-[9px] font-black bg-white px-1.5 py-0.5 rounded-md border shadow-sm ${badgeBgClass}`}>{totalWorkersInGroup}</span>
                                    </div>
                                    
                                    {/* Kolumna przewijana pionowo z kwadratami */}
                                    <div className="flex-1 flex flex-col gap-2 p-2 bg-slate-100/50 overflow-y-auto custom-scrollbar">
                                        {zone.subZones.map(subZone => (
                                            <div key={subZone.id} onDragOver={(e) => e.preventDefault()} onDrop={(e) => handleDrop(e, subZone.id)} className={`bg-white border border-slate-200 rounded-xl flex flex-col shrink-0 min-h-[160px] overflow-hidden transition-colors shadow-sm ${subZoneHoverClass}`}>
                                                <div className="p-1.5 border-b border-slate-50 bg-slate-50 flex justify-between items-center">
                                                    <h4 className="text-[9px] font-black uppercase tracking-widest text-slate-500 truncate">{subZone.label}</h4>
                                                    <span className={`text-[9px] font-black bg-white px-1.5 py-[1px] rounded border border-slate-200 leading-none ${subZoneBadgeClass}`}>{zones[subZone.id]?.length || 0}</span>
                                                </div>
                                                <div className="flex-1 overflow-y-auto p-1.5 custom-scrollbar grid grid-cols-3 gap-1 content-start bg-slate-50/30">
                                                    {zones[subZone.id]?.map(worker => <WorkerCard key={worker.worker_login} worker={worker} sourceZone={subZone.id} />)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        }

                        // Renderowanie standardowej, pojedynczej strefy
                        return (
                            <div key={zone.id} onDragOver={(e) => e.preventDefault()} onDrop={(e) => handleDrop(e, zone.id)} className="bg-white border border-slate-200 rounded-2xl flex flex-col flex-1 min-w-0 shadow-sm overflow-hidden transition-all hover:border-indigo-200">
                                <div className="p-2.5 border-b border-slate-50 bg-slate-50/50 flex justify-between items-center transition-colors">
                                    <div className="flex items-center gap-1.5 truncate">
                                        <h3 className="text-[9px] font-black uppercase tracking-widest truncate text-slate-500">{zone.label}</h3>
                                    </div>
                                    <span className="text-[9px] font-black bg-white px-1.5 py-0.5 rounded-md border shrink-0 text-indigo-600 border-indigo-100">{zones[zone.id]?.length || 0}</span>
                                </div>
                                <div className="flex-1 overflow-y-auto p-1.5 custom-scrollbar grid grid-cols-3 gap-1 content-start">
                                    {zones[zone.id]?.map(worker => <WorkerCard key={worker.worker_login} worker={worker} sourceZone={zone.id} />)}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

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