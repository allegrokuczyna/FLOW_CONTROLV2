import React from 'react';
import { motion } from 'framer-motion';
import { LayoutDashboard, Database, Cpu, Activity, LogOut, Calendar } from 'lucide-react';

const Sidebar = ({ activeTab, setActiveTab, onLogout }) => {
    const menuItems = [
        { id: 'dashboard', label: 'panel główny', icon: <LayoutDashboard size={18} /> },
        { id: 'plan', label: 'plan pracy', icon: <Calendar size={18} /> },
        { id: 'sync', label: 'synchronizacja', icon: <Database size={18} /> },
        { id: 'ai', label: 'analiza ai', icon: <Cpu size={18} /> },
        { id: 'live', label: 'live status', icon: <Activity size={18} /> },
    ];

    return (
        <motion.div 
            initial={{ x: 50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="w-64 h-screen bg-[#0d0f14] border-l border-white/5 p-6 flex flex-col"
        >
            <div className="mb-10 px-2">
                <h2 className="text-blue-500 font-medium text-lg tracking-tight">flow control</h2>
            </div>

            <nav className="flex-1 space-y-1">
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center gap-3 px-4 py-2 rounded-xl transition-all text-sm ${
                            activeTab === item.id 
                            ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' 
                            : 'text-gray-500 hover:bg-white/5 hover:text-gray-300'
                        }`}
                    >
                        {item.icon}
                        <span className="font-normal">{item.label}</span>
                    </button>
                ))}
            </nav>

            <button 
                onClick={onLogout}
                className="flex items-center gap-3 px-4 py-2 text-gray-600 hover:text-red-400 text-sm transition-all mt-auto"
            >
                <LogOut size={18} />
                <span>wyloguj się</span>
            </button>
        </motion.div>
    );
};

export default Sidebar;