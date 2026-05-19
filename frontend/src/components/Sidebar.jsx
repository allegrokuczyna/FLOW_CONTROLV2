import React from 'react';
import { LayoutDashboard, Calendar, Activity, Database, Server, Cpu, Settings, LogOut , Table, Zap} from 'lucide-react';

const Sidebar = ({ activeTab, setActiveTab }) => {
  // Tutaj definiujemy TYLKO przyciski menu
  const menu = [
    { id: 'dashboard', icon: <LayoutDashboard size={20} />, title: 'Dashboard' },
    { id: 'plan', icon: <Calendar size={20} />, title: 'Work Plan' },
    { id: 'live', icon: <Activity size={20} />, title: 'Live Status' },
    { id: 'sync', icon: <Database size={20} />, title: 'D365 Sync' },
    { id: 'dane', icon: <Server size={20} />, title: 'System Data' },
    { id: 'ai', icon: <Cpu size={20} />, title: 'AI Engine' },
    { id: 'schedule', icon: <Table size={20} />, title: 'Full Schedule' },
    { id: 'productivity', icon: <Zap size={20} />, title: 'Productivity' }
  ];

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.reload();
  };

  return (
    <div className="w-16 h-full bg-white border-r border-slate-200 flex flex-col items-center py-6 shrink-0 z-50 shadow-sm">
      
      {/* Logo ADM */}
      <div className="w-10 h-10 bg-[#8b5cf6] text-white font-black text-[10px] flex items-center justify-center rounded-xl mb-8 shadow-md">
        ADM
      </div>

      {/* Nawigacja - ikony */}
      <nav className="flex-1 w-full flex flex-col items-center space-y-4">
        {menu.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)} // To zmienia zakładkę w App.jsx
            title={item.title}
            className={`p-3 rounded-xl transition-all duration-200 ${
              activeTab === item.id
                ? 'bg-[#8b5cf6]/10 text-[#8b5cf6]'
                : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'
            }`}
          >
            {item.icon}
          </button>
        ))}
      </nav>

      {/* Dolna sekcja (Ustawienia/Wyloguj) */}
      <div className="mt-auto pt-4 flex flex-col gap-2 border-t border-slate-100 w-full items-center">
         <button className="p-3 text-slate-400 hover:bg-slate-100 rounded-xl transition-all">
            <Settings size={20} />
         </button>
         <button onClick={handleLogout} className="p-3 text-slate-400 hover:bg-red-50 hover:text-red-500 rounded-xl transition-all">
            <LogOut size={20} />
         </button>
      </div>
    </div>
  );
};

export default Sidebar;