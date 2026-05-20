import React, { useState } from 'react';
import { Bot } from 'lucide-react';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import WorkPlan from './components/WorkPlan';
import SystemData from './components/SystemData';
import ScheduleGrid from './components/ScheduleGrid';
import ProductivityGrid from './components/ProductivityGrid';

// 1. DODANY IMPORT TABLICY TV Z NOWEGO FOLDERU
import TVBoard from './tv/TVBoard'; 

function App() {
  // =========================================================================

  // =========================================================================
  if (window.location.pathname === '/tv') {
    return <TVBoard />;
  }

  // Stan autoryzacji - sprawdza token w localStorage
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  
  // Stan nawigacji - 'dashboard' jest widokiem startowym
  const [activeTab, setActiveTab] = useState('dashboard');
  

  // Jeśli użytkownik nie jest zalogowany, pokazujemy TYLKO ekran logowania
  if (!isLoggedIn) {
    return <Login onLoginSuccess={() => setIsLoggedIn(true)} />;
  }

  // Funkcja pomocnicza do renderowania nagłówka
  const renderHeaderTitle = () => {
    switch (activeTab) {
      case 'dashboard': return 'System Overview';
      case 'plan':      return 'Warehouse Flow Control | Plan';
      case 'schedule':  return 'Full Weekly Schedule';
      case 'dane':      return 'AI Configuration | System Data';
      case 'live':      return 'Live Operations Status';
      case 'sync':      return 'D365 Data Synchronization';
      case 'productivity': return 'Productivity Metrics';
      default:          return 'Adamów Operational Node';
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 font-sans text-slate-900 overflow-hidden">
      
      {/* 1. MENU BOCZNE (SIDEBAR) */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      {/* 2. GŁÓWNY KONTENER (Prawa strona) */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        
        {/* NAGŁÓWEK (HEADER) */}
        <header className="h-14 border-b border-slate-200 flex items-center justify-between px-8 shrink-0 bg-white z-10 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-black uppercase tracking-widest text-[#8b5cf6] bg-purple-50 px-2 py-1 rounded border border-purple-100">
              Active
            </span>
            <h1 className="text-sm font-bold uppercase tracking-tight text-slate-700">
              {renderHeaderTitle()}
            </h1>
          </div>
          <div className="text-[10px] text-slate-400 font-black uppercase tracking-widest">
            Node: ADM-01
          </div>
        </header>

        {/* GŁÓWNY OBSZAR ROBOCZY (MAIN CONTENT) */}
        <main className="flex-1 relative overflow-hidden">
          
          {/* Widok: DASHBOARD */}
          {activeTab === 'dashboard' && (
            <div className="absolute inset-0 overflow-auto p-8 animate-in fade-in duration-300">
               <Dashboard />
            </div>
          )}

          {/* Widok: PLAN PRACY (WORK PLAN) */}
          {activeTab === 'plan' && (
            <div className="absolute inset-0 overflow-hidden p-8 animate-in fade-in duration-300">
               <WorkPlan />
            </div>
          )}

          {/* Widok: PEŁNY GRAFIK (SCHEDULE GRID) */}
          {activeTab === 'schedule' && (
            <div className="absolute inset-0 overflow-hidden p-8 animate-in fade-in duration-300">
               <ScheduleGrid />
            </div>
          )}

          {/* Widok: SYSTEM DATA (TABELA KONFIGURACJI AI) */}
          {activeTab === 'dane' && (
            <div className="absolute inset-0 overflow-auto p-8 bg-slate-50/50 animate-in fade-in duration-300">
               <SystemData />
            </div>
          )}

          {/* Widok: PRODUCTIVITY (TABELA METRYK PRODUCTIVITY) */}
          {activeTab === 'productivity' && (
            <div className="absolute inset-0 overflow-auto p-8 bg-slate-50/50 animate-in fade-in duration-300">
               <ProductivityGrid />
            </div>
          )}

          {/* EKRAN DLA MODUŁÓW W BUDOWIE */}
          {activeTab !== 'dashboard' && activeTab !== 'plan' && activeTab !== 'dane' && activeTab !== 'schedule' && activeTab !== 'productivity' && (
            <div className="flex flex-col items-center justify-center h-full text-slate-300 bg-white/50">
              <Bot size={64} className="mb-4 opacity-10" />
              <h2 className="text-2xl font-black uppercase tracking-widest opacity-20">
                Module Under Construction
              </h2>
              <p className="text-xs font-bold mt-2 text-slate-400">
                Current ID: <span className="text-[#8b5cf6]">{activeTab}</span>
              </p>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}

export default App;