import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import api from '../api';

const Dashboard = () => {
    const [stats, setStats] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.get('/analytics/workpools');
                const data = response.data.workpools || {};
                setStats(data);
                setLoading(false);
            } catch (err) {
                console.error("Błąd pobierania danych:", err);
                setLoading(false);
            }
        };
        fetchStats();
    }, []);

    const getTotalWorks = () => {
        return Object.values(stats).reduce((acc, curr) => {
            const val = typeof curr === 'number' ? curr : (curr?.count || 0);
            return acc + Number(val);
        }, 0);
    };

    const getVal = (key) => {
        const entry = stats[key];
        if (typeof entry === 'number') return entry;
        if (typeof entry === 'object' && entry !== null) return entry.count || 0;
        return 0;
    };

    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-2xl font-semibold tracking-tight text-white/90">witaj w systemie, adrian.</h1>
                <p className="text-gray-500 text-sm mt-1">aktualny stan operacyjny magazynu.</p>
            </header>

            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5 animate-pulse">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-32 bg-white/5 rounded-2xl border border-white/5" />
                    ))}
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    <StatCard 
                        label="suma wszystkich prac" 
                        val={getTotalWorks()} 
                        color="border-blue-500/10" 
                    />
                    <StatCard 
                        label="strefa sortowania" 
                        val={getVal('SORT')} 
                        color="border-purple-500/10" 
                    />
                    <StatCard 
                        label="strefa kompletacji" 
                        val={getVal('PICK')} 
                        color="border-green-500/10" 
                    />
                </div>
            )}
            
            <div className="p-10 border border-white/5 rounded-2xl bg-white/[0.01] text-[10px] text-gray-700 text-center uppercase tracking-widest">
                dane zsynchronizowane z Dynamics 365: {new Date().toLocaleTimeString()}
            </div>
        </div>
    );
};

const StatCard = ({ label, val, color }) => (
    <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`p-6 rounded-2xl bg-white/[0.02] border ${color} backdrop-blur-sm`}
    >
        <p className="text-gray-500 text-[10px] uppercase tracking-[0.2em] font-medium">{label}</p>
        <h2 className="text-2xl font-bold mt-2 text-white/80">{val}</h2>
    </motion.div>
);

export default Dashboard;