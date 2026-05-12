import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Cpu, Sparkles, Send, BrainCircuit } from 'lucide-react';
import api from '../api';

const AIAnalysis = () => {
    const [report, setReport] = useState('');
    const [loading, setLoading] = useState(false);

    const generateReport = async () => {
        setLoading(true);
        try {
            const response = await api.get('/ai/manager_report');
            setReport(response.data); // Zakładam, że backend zwraca stringa lub obiekt z polem report
        } catch (err) {
            setReport('błąd podczas generowania raportu przez silnik gemini.');
        }
        setLoading(false);
    };

    return (
        <div className="max-w-3xl space-y-8">
            <header>
                <h1 className="text-2xl font-semibold tracking-tight text-white/90">analiza ai</h1>
                <p className="text-gray-500 text-sm mt-1">inteligentna interpretacja obciążenia magazynu i wydajności.</p>
            </header>

            <div className="relative">
                <AnimatePresence mode="wait">
                    {!report ? (
                        <motion.div 
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="p-12 border border-white/5 rounded-[2rem] bg-white/[0.01] flex flex-col items-center text-center space-y-6"
                        >
                            <div className="p-4 rounded-full bg-blue-500/10 text-blue-500">
                                <BrainCircuit size={32} />
                            </div>
                            <div className="space-y-2">
                                <h3 className="text-sm font-medium text-gray-300">gotowy do analizy?</h3>
                                <p className="text-gray-600 text-xs max-w-xs mx-auto">
                                    gemini przeanalizuje aktualne workpoole i zasugeruje optymalizację składu.
                                </p>
                            </div>
                            <button 
                                onClick={generateReport}
                                disabled={loading}
                                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl text-xs font-bold tracking-widest uppercase transition-all disabled:opacity-50"
                            >
                                {loading ? 'analizowanie...' : 'generuj raport'}
                                <Sparkles size={14} />
                            </button>
                        </motion.div>
                    ) : (
                        <motion.div 
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-8 border border-blue-500/10 rounded-[2rem] bg-blue-500/[0.02] backdrop-blur-md relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 p-4 opacity-10">
                                <Cpu size={120} />
                            </div>
                            
                            <div className="flex items-center gap-2 mb-6 text-blue-400">
                                <Sparkles size={16} />
                                <span className="text-[10px] uppercase tracking-[0.3em] font-bold">raport gemini ai</span>
                            </div>

                            <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap font-light">
                                {typeof report === 'object' ? JSON.stringify(report, null, 2) : report}
                            </div>

                            <button 
                                onClick={() => setReport('')}
                                className="mt-8 text-[10px] text-gray-600 uppercase tracking-widest hover:text-white transition-colors"
                            >
                                [ wyczyść raport ]
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default AIAnalysis;