import React from 'react';
import { Activity, Box, Users, Zap } from 'lucide-react';

const Dashboard = () => {
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            
            {/* GÓRNY PASEK WIDGETÓW */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Główny licznik */}
                <div className="md:col-span-2 bg-white border border-slate-200 rounded-2xl p-8 shadow-sm flex flex-col justify-between">
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-[#8b5cf6] rounded-full animate-pulse"></div>
                            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">Live System Load</h3>
                        </div>
                    </div>
                    <div className="flex items-end gap-4">
                        <span className="text-6xl font-black text-slate-800 tracking-tighter">7,432</span>
                        <span className="text-green-500 font-bold text-sm mb-2">+12.4% vs wczoraj</span>
                    </div>
                </div>
                
                {/* Status Systemu */}
                <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm flex flex-col justify-between">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-6">Status Węzła ADM-01</h3>
                    <div className="flex items-center gap-4">
                        <div className="p-3.5 bg-green-50 text-green-600 rounded-xl">
                            <Zap size={24} />
                        </div>
                        <div>
                            <p className="text-base font-bold text-slate-800">Systemy w normie</p>
                            <p className="text-xs text-slate-500 font-medium mt-1">Brak opóźnień (24ms)</p>
                        </div>
                    </div>
                </div>

            </div>

            {/* SIATKA MNIEJSZYCH WIDGETÓW */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <MiniCard label="Picking" val="2.4k" icon={<Box size={18}/>} />
                <MiniCard label="Putaway" val="1.1k" icon={<Zap size={18}/>} />
                <MiniCard label="Sorting" val="843" icon={<Activity size={18}/>} />
                <MiniCard label="Active Workers" val="142" icon={<Users size={18}/>} />
            </div>

        </div>
    );
};

// Pomocniczy mini-komponent dla małych kart
const MiniCard = ({ label, val, icon }) => (
    <div className="bg-white border border-slate-200 rounded-xl p-6 flex justify-between items-center shadow-sm hover:border-[#8b5cf6]/50 transition-colors cursor-default group">
        <div>
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">{label}</p>
            <p className="text-2xl font-bold text-slate-800">{val}</p>
        </div>
        <div className="p-3 bg-slate-50 rounded-xl text-slate-400 group-hover:text-[#8b5cf6] transition-colors">
            {icon}
        </div>
    </div>
);

export default Dashboard;