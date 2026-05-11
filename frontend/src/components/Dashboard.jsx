import React from 'react';
import { motion } from 'framer-motion';

const Dashboard = () => {
    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-2xl font-semibold tracking-tight text-white/90">witaj w systemie, adrian.</h1>
                <p className="text-gray-500 text-sm mt-1">aktualny stan operacyjny magazynu.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {[
                    { label: 'oczekujące prace', val: '42', color: 'border-blue-500/10' },
                    { label: 'wydajność średnia', val: '88%', color: 'border-green-500/10' },
                    { label: 'pracownicy online', val: '12', color: 'border-purple-500/10' },
                ].map((stat, i) => (
                    <motion.div 
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className={`p-6 rounded-2xl bg-white/[0.02] border ${stat.color} backdrop-blur-sm`}
                    >
                        <p className="text-gray-500 text-[10px] uppercase tracking-[0.2em] font-medium">{stat.label}</p>
                        <h2 className="text-2xl font-bold mt-2 text-white/80">{stat.val}</h2>
                    </motion.div>
                ))}
            </div>
            
            <div className="p-10 border border-white/5 rounded-2xl bg-white/[0.01] text-xs text-gray-600 text-center italic">
                oczekiwanie na dane telemetryczne z dynamics 365...
            </div>
        </div>
    );
};

export default Dashboard;