import React, { useState, useEffect } from 'react';

import { motion, AnimatePresence } from 'framer-motion';

import { Users, Sparkles, Check, CheckCircle2, Save, ArrowRight } from 'lucide-react';

import api from '../api';



const WorkPlan = () => {

    const [workers, setWorkers] = useState([]);

    const [selectedShift, setSelectedShift] = useState('1');

    const [aiProposals, setAiProposals] = useState([]);

    const [isLoading, setIsLoading] = useState(true);

    const [isSaving, setIsSaving] = useState(false);

    const [isAiLoading, setIsAiLoading] = useState(false);



    // --- POBIERANIE DANYCH ---

    const loadData = async () => {

        setIsLoading(true);

        try {

            const resWorkers = await api.get(`/plan/workers/${selectedShift}`);

            const initialData = resWorkers.data.map(w => ({

                id: w.login,

                login: w.login,

                shift: w.shift,

                hours: w.hours,

                task: w.task || 'unassigned'

            }));

            setWorkers(initialData);

            setAiProposals([]); 

        } catch (err) {

            console.error("Błąd ładowania danych:", err);

        }

        setIsLoading(false);

    };



    useEffect(() => {

        loadData();

    }, [selectedShift]);



    // --- ZAPISYWANIE PLANU ---

    const savePlanToDatabase = async () => {

        setIsSaving(true);

        try {

            const dataToSave = workers.map(w => ({

                worker_login: w.login,

                shift: w.shift,

                task: w.task

            }));

            await api.post('/plan/save', dataToSave);

            alert("Plan został zapisany!");

        } catch (err) {

            alert("Błąd zapisu!");

        }

        setIsSaving(false);

    };



    // --- DRAG & DROP ---

    const onDragStart = (e, workerId) => {

        e.dataTransfer.setData("workerId", workerId);

    };



    const onDrop = (e, targetTask) => {

        const workerId = e.dataTransfer.getData("workerId");

        moveWorker(workerId, targetTask);

    };



    const moveWorker = (workerId, targetTask) => {

        setWorkers(prev => prev.map(w => w.login === workerId ? { ...w, task: targetTask } : w));

        setAiProposals(prev => prev.filter(p => p.workerId !== workerId));

    };



    // --- REALNA ANALIZA AI (LLAMA 3) ---

    const generateAiPlan = async () => {

        if (getWorkersByTask('unassigned').length === 0) return;

        

        setIsAiLoading(true);

        try {

            // KLUCZOWA ZMIANA: Wysyłamy wybraną zmianę do backendu

            const res = await api.post('/plan/ai_suggest', { shift: selectedShift });

            if (res.data && Array.isArray(res.data)) {

                setAiProposals(res.data);

            }

        } catch (err) {

            console.error("Błąd AI:", err);

            alert("Błąd połączenia z modułem AI.");

        }

        setIsAiLoading(false);

    };



    const acceptAllAiProposals = () => {

        setWorkers(prev => {

            let newWorkers = [...prev];

            aiProposals.forEach(prop => {

                const index = newWorkers.findIndex(w => w.login === prop.workerId);

                if (index !== -1) {

                    newWorkers[index] = { ...newWorkers[index], task: prop.suggestedZone };

                }

            });

            return newWorkers;

        });

        setAiProposals([]);

    };



    const getWorkersByTask = (taskName) => workers.filter(w => w.task === taskName);



    if (isLoading) return <div className="h-full flex items-center justify-center italic text-gray-500 tracking-widest uppercase text-[10px]">Inicjalizacja grafiku...</div>;



    return (

        <div className="space-y-8 max-w-[1800px] mx-auto">

            <header className="flex justify-between items-end">

                <div>

                    <h1 className="text-2xl font-semibold tracking-tight text-white/90 italic">Warehouse Flow Control</h1>

                    <p className="text-gray-500 text-[10px] uppercase tracking-widest mt-1">Status: Dane zsynchronizowane z Grafik 2026</p>

                </div>

                

                <div className="flex items-center gap-4">

                    <button 

                        onClick={savePlanToDatabase}

                        disabled={isSaving}

                        className="flex items-center gap-2 bg-green-600/10 hover:bg-green-600/20 text-green-400 border border-green-500/20 px-5 py-2.5 rounded-xl text-[10px] font-bold tracking-[0.2em] uppercase transition-all"

                    >

                        {isSaving ? 'Zapisywanie...' : 'Zatwierdź Plan'}

                        <Save size={14} />

                    </button>



                    <button 

                        onClick={generateAiPlan}

                        disabled={isAiLoading || selectedShift === 'all' || getWorkersByTask('unassigned').length === 0}

                        className="flex items-center gap-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 px-5 py-2.5 rounded-xl text-[10px] font-bold tracking-[0.2em] uppercase transition-all disabled:opacity-20"

                    >

                        {isAiLoading ? 'Analiza...' : 'Magazynowy Mózg AI'}

                        <Sparkles size={14} />

                    </button>



                    <div className="flex gap-1.5 bg-black/20 p-1.5 rounded-xl border border-white/5">

                        {['all', '1', '2', '3'].map(id => (

                            <button

                                key={id}

                                onClick={() => setSelectedShift(id)}

                                className={`px-4 py-2 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${selectedShift === id ? 'bg-white/10 text-white border border-white/10' : 'text-gray-500 hover:text-gray-300'}`}

                            >

                                {id === 'all' ? 'Wszyscy' : `Zmiana ${id}`}

                            </button>

                        ))}

                    </div>

                </div>

            </header>



            <div className="grid grid-cols-1 xl:grid-cols-7 gap-4">

                

                <div 

                    onDragOver={e => e.preventDefault()} 

                    onDrop={e => onDrop(e, 'unassigned')} 

                    className="xl:col-span-1 p-5 rounded-[2rem] bg-white/[0.01] border border-white/5 flex flex-col h-[750px]"

                >

                    <div className="flex items-center gap-2 mb-6 px-2 text-gray-500">

                        <Users size={12} />

                        <h2 className="text-[9px] uppercase tracking-[0.3em] font-black">Dostępni</h2>

                    </div>

                    <div className="space-y-2 overflow-y-auto pr-2 flex-1 custom-scrollbar">

                        {getWorkersByTask('unassigned').map(w => (

                            <WorkerCard key={w.login} worker={w} onDragStart={onDragStart} />

                        ))}

                    </div>

                </div>

                

                <div className="xl:col-span-5 grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">

                     <Zone title="Picking" task="picking" workers={getWorkersByTask('picking')} onDrop={onDrop} onDragStart={onDragStart} color="border-blue-500/10" accent="bg-blue-500" />

                     <Zone title="Putaway" task="putaway" workers={getWorkersByTask('putaway')} onDrop={onDrop} onDragStart={onDragStart} color="border-purple-500/10" accent="bg-purple-500" />

                     <Zone title="Inbound" task="inbound" workers={getWorkersByTask('inbound')} onDrop={onDrop} onDragStart={onDragStart} color="border-green-500/10" accent="bg-green-500" />

                     <Zone title="Packing" task="packing" workers={getWorkersByTask('packing')} onDrop={onDrop} onDragStart={onDragStart} color="border-orange-500/10" accent="bg-orange-500" />

                     <Zone title="Sorting" task="sorting" workers={getWorkersByTask('sorting')} onDrop={onDrop} onDragStart={onDragStart} color="border-yellow-500/10" accent="bg-yellow-500" />

                </div>



                <div className="xl:col-span-1 p-5 rounded-[2rem] bg-blue-500/[0.03] border border-blue-500/10 flex flex-col h-[750px]">

                    <div className="flex flex-col mb-6 px-2 gap-4">

                        <div className="flex items-center gap-2 text-blue-400">

                            <Sparkles size={12} />

                            <h2 className="text-[9px] uppercase tracking-[0.3em] font-black">Sugestie AI</h2>

                        </div>

                        {aiProposals.length > 0 && (

                            <button 

                                onClick={acceptAllAiProposals}

                                className="flex items-center justify-center gap-2 w-full py-2 bg-blue-500/20 hover:bg-blue-500 text-white text-[9px] uppercase tracking-widest font-bold rounded-xl transition-all border border-blue-500/30"

                            >

                                Akceptuj <CheckCircle2 size={12} />

                            </button>

                        )}

                    </div>

                    

                    <div className="space-y-3 overflow-y-auto pr-2 flex-1 custom-scrollbar">

                        <AnimatePresence>

                            {aiProposals.map((prop) => (

                                <motion.div 

                                    key={prop.workerId}

                                    initial={{ opacity: 0, y: 10 }}

                                    animate={{ opacity: 1, y: 0 }}

                                    className="p-3 rounded-2xl bg-white/[0.03] border border-blue-500/20 group hover:border-blue-500/50 transition-all"

                                >

                                    <div className="flex justify-between items-start">

                                        <div>

                                            <p className="text-[11px] font-bold text-white/90">{prop.login}</p>

                                            <div className="flex items-center gap-1.5 mt-1 text-blue-400">

                                                <ArrowRight size={10} />

                                                <span className="text-[9px] uppercase font-black tracking-tighter">{prop.suggestedZone}</span>

                                            </div>

                                        </div>

                                        <button 

                                            onClick={() => moveWorker(prop.workerId, prop.suggestedZone)}

                                            className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white transition-all"

                                        >

                                            <Check size={12} />

                                        </button>

                                    </div>

                                </motion.div>

                            ))}

                        </AnimatePresence>

                        {aiProposals.length === 0 && !isAiLoading && (

                            <div className="h-full flex items-center justify-center text-center p-4">

                                <p className="text-[9px] text-gray-600 uppercase tracking-widest leading-loose">Brak nowych sugestii. Przenieś pracowników do listy dostępnych i uruchom AI.</p>

                            </div>

                        )}

                    </div>

                </div>



            </div>

        </div>

    );

};



const WorkerCard = ({ worker, onDragStart }) => (

    <motion.div

        draggable onDragStart={(e) => onDragStart(e, worker.login)}

        whileHover={{ x: 3 }}

        className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/5 cursor-grab active:cursor-grabbing hover:bg-white/[0.06] hover:border-white/10 transition-all flex justify-between items-center group"

    >

        <span className="text-xs font-bold text-gray-300 group-hover:text-white transition-colors">{worker.login}</span>

        <div className="px-2 py-0.5 rounded-md bg-black/20 border border-white/5">

            <span className="text-[8px] text-gray-500 font-mono">{worker.hours}</span>

        </div>

    </motion.div>

);



const Zone = ({ title, task, workers, onDrop, onDragStart, color, accent }) => (

    <div 

        onDragOver={e => e.preventDefault()}

        onDrop={(e) => onDrop(e, task)}

        className={`p-5 rounded-[2.5rem] border ${color} bg-white/[0.01] flex flex-col transition-all hover:bg-white/[0.02] h-[750px]`}

    >

        <div className="flex justify-between items-center mb-6 pb-3 border-b border-white/5">

            <div className="flex items-center gap-2.5">

                <div className={`w-1.5 h-1.5 rounded-full ${accent} shadow-[0_0_10px_rgba(255,255,255,0.2)]`} />

                <h3 className="text-[10px] uppercase tracking-[0.3em] font-black text-gray-400">{title}</h3>

            </div>

            <div className="px-2 py-1 rounded-lg bg-white/5 border border-white/5">

                <span className="text-[10px] font-mono text-gray-400">{workers.length}</span>

            </div>

        </div>

        <div className="space-y-2 overflow-y-auto custom-scrollbar pr-1 flex-1">

            {workers.map(w => <WorkerCard key={w.login} worker={w} onDragStart={onDragStart} />)}

            {workers.length === 0 && (

                <div className="h-full flex items-center justify-center border-2 border-dashed border-white/[0.02] rounded-[2rem]">

                    <span className="text-[8px] uppercase tracking-[0.2em] text-gray-700">Upuść tutaj</span>

                </div>

            )}

        </div>

    </div>

);



export default WorkPlan;

