import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Cpu, Sparkles, BrainCircuit, History, User, Clock, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '../api';

const AIAnalysis = () => {
    const [report, setReport] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    // Pobieranie historii logów
    const fetchHistory = async () => {
        try {
            const res = await api.get('/ai/manager_report/history');
            setHistory(res.data.slice(0, 10)); // Tylko ostatnie 10
        } catch (err) {
            console.error("Błąd pobierania historii", err);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, []);

    const generateReport = async () => {
        setLoading(true);
        try {
            const response = await api.get('/ai/manager_report');
            setReport(response.data);
            fetchHistory(); // Odśwież historię po wygenerowaniu nowego
        } catch (err) {
            setReport({ ai_analysis: 'Błąd podczas generowania raportu przez silnik AI.' });
        }
        setLoading(false);
    };

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-8">
            <header>
                <h1 className="text-2xl font-semibold tracking-tight text-white/90 underline decoration-blue-500/40 underline-offset-8">analiza ai</h1>
                <p className="text-gray-500 text-sm mt-2">inteligentna interpretacja obciążenia magazynu i wydajności.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                
                {/* LEWA KOLUMNA: GENERATOR I AKTUALNY RAPORT */}
                <div className="lg:col-span-2 relative">
                    <AnimatePresence mode="wait">
                        {!report ? (
                            <motion.div 
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 1.05 }}
                                className="p-12 border border-white/5 rounded-[2rem] bg-white/[0.01] flex flex-col items-center text-center space-y-6 shadow-2xl"
                            >
                                <div className="p-4 rounded-full bg-blue-500/10 text-blue-500 animate-pulse">
                                    <BrainCircuit size={40} />
                                </div>
                                <div className="space-y-2">
                                    <h3 className="text-sm font-medium text-gray-300 italic">gotowy do analizy, pysiaczku?</h3>
                                    <p className="text-gray-600 text-xs max-w-xs mx-auto font-light leading-relaxed">
                                        AI przeanalizuje aktualne workpoole i zasugeruje optymalizację składu na podstawie skilli.
                                    </p>
                                </div>
                                <button 
                                    onClick={generateReport}
                                    disabled={loading}
                                    className="flex items-center gap-3 bg-blue-600 hover:bg-blue-500 px-8 py-4 rounded-2xl text-[10px] text-white font-bold tracking-[0.2em] uppercase transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20"
                                >
                                    {loading ? 'analizowanie...' : 'generuj raport'}
                                    <Sparkles size={16} />
                                </button>
                            </motion.div>
                        ) : (
                            <motion.div 
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="p-8 border border-blue-500/10 rounded-[2rem] bg-blue-500/[0.02] backdrop-blur-md relative overflow-hidden"
                            >
                                <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                                    <Cpu size={150} />
                                </div>
                                
                                <div className="flex items-center justify-between mb-8">
                                    <div className="flex items-center gap-2 text-blue-400">
                                        <Sparkles size={16} />
                                        <span className="text-[10px] uppercase tracking-[0.3em] font-bold">raport live</span>
                                    </div>
                                    <span className="text-[10px] text-gray-500 font-mono italic">{report.time}</span>
                                </div>

                                <div className="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed font-light">
                                    <ReactMarkdown>
                                        {report.ai_analysis}
                                    </ReactMarkdown>
                                </div>

                                <button 
                                    onClick={() => setReport(null)}
                                    className="mt-12 text-[10px] text-gray-600 uppercase tracking-widest hover:text-white transition-colors flex items-center gap-2"
                                >
                                    [ wyczyść raport ]
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* PRAWA KOLUMNA: LOGI / HISTORIA */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 px-2 text-gray-400 mb-4">
                        <History size={16} className="text-blue-500" />
                        <span className="text-[10px] uppercase tracking-widest font-bold">ostatnie logi AI (bufor 10)</span>
                    </div>

                    <div className="space-y-3 overflow-y-auto max-h-[500px] pr-2 scrollbar-hide">
                        {history.length > 0 ? history.map((log) => (
                            <motion.div 
                                key={log.id}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="p-4 border border-white/5 rounded-2xl bg-white/[0.01] hover:bg-white/[0.03] transition-colors group cursor-default"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2 text-xs text-blue-400">
                                        <User size={12} />
                                        <span className="font-medium text-[10px] uppercase">{log.username}</span>
                                    </div>
                                    <div className="flex items-center gap-1 text-[9px] text-gray-600">
                                        <Clock size={10} />
                                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                </div>
                                <p className="text-[11px] text-gray-500 line-clamp-2 italic leading-snug group-hover:text-gray-400 transition-colors">
                                    {log.report_text.replace(/[#*]/g, '')}
                                </p>
                                <div className="mt-3 flex justify-between items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                    <span className="text-[9px] text-gray-700 uppercase tracking-tighter">Załoga: {log.workers_count}</span>
                                    <ChevronRight size={12} className="text-blue-500" />
                                </div>
                            </motion.div>
                        )) : (
                            <div className="text-center py-8 text-[10px] text-gray-700 uppercase tracking-widest border border-dashed border-white/5 rounded-2xl">
                                brak wpisów w historii
                            </div>
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
};

export default AIAnalysis;