import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../api';

const Sync = () => {
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState(null);

    const handleSync = async (endpoint) => {
        setLoading(true);
        setStatus(null);
        try {
            await api.post(endpoint);
            setStatus({ type: 'success', msg: 'synchronizacja zakończona pomyślnie' });
        } catch (err) {
            setStatus({ type: 'error', msg: 'błąd połączenia z serwerem dynamics' });
        }
        setLoading(false);
    };

    return (
        <div className="max-w-2xl space-y-8">
            <header>
                <h1 className="text-2xl font-semibold tracking-tight text-white/90">centrum synchronizacji</h1>
                <p className="text-gray-500 text-sm mt-1">zarządzaj przepływem danych między dynamics 365 a bazą lokalną.</p>
            </header>

            <div className="grid grid-cols-1 gap-4">
                <SyncCard 
                    title="aktualizacja prac (live)" 
                    desc="pobiera aktualny stan prac otwartych i w toku (whsworktable)"
                    icon={<RefreshCw size={18} className={loading ? "animate-spin" : ""} />}
                    onClick={() => handleSync('/sync/active_status')}
                    loading={loading}
                />
                
                <SyncCard 
                    title="archiwum główne" 
                    desc="pełna synchronizacja historii eksportu prac"
                    icon={<RefreshCw size={18} />}
                    onClick={() => handleSync('/sync/works')}
                    loading={loading}
                />
            </div>

            {status && (
                <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`p-4 rounded-xl border flex items-center gap-3 text-xs uppercase tracking-widest ${
                        status.type === 'success' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
                    }`}
                >
                    {status.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                    {status.msg}
                </motion.div>
            )}
        </div>
    );
};

const SyncCard = ({ title, desc, icon, onClick, loading }) => (
    <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 flex items-center justify-between group hover:border-white/10 transition-all">
        <div>
            <h3 className="text-sm font-medium text-white/80">{title}</h3>
            <p className="text-gray-600 text-xs mt-1">{desc}</p>
        </div>
        <button 
            disabled={loading}
            onClick={onClick}
            className="p-3 rounded-xl bg-blue-600/10 text-blue-500 hover:bg-blue-600 hover:text-white transition-all disabled:opacity-50"
        >
            {icon}
        </button>
    </div>
);

export default Sync;