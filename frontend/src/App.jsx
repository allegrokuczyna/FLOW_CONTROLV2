import React, { useState } from 'react';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Sync from './components/Sync';
import AIAnalysis from './components/AIAnalysis';
import WorkPlan from './components/WorkPlan'; // <-- Dodany import planu pracy

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('dashboard');

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
  };

  const handleLoginSuccess = () => {
    setIsLoggedIn(true);
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex h-screen bg-[#0a0c10] text-white overflow-hidden">
      {/* GŁÓWNA TREŚĆ - PO LEWEJ */}
      <main className="flex-1 p-12 overflow-y-auto">
        {/* Renderowanie warunkowe komponentów */}
        {activeTab === 'dashboard' && <Dashboard />}
        
        {/* Widok planu pracy */}
        {activeTab === 'plan' && <WorkPlan />}
        
        {activeTab === 'sync' && <Sync />}

        {/* Sekcja AI - teraz w pełni aktywna */}
        {activeTab === 'ai' && <AIAnalysis />}

        {/* Placeholder dla Live Status */}
        {activeTab === 'live' && (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <h2 className="text-xl font-medium text-white/50">live status</h2>
            <p className="text-gray-700 text-xs mt-2 italic tracking-widest uppercase">
              moduł podglądu rzeczywistego w budowie...
            </p>
          </div>
        )}
      </main>

      {/* MENU - PO PRAWEJ STRONIE */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        onLogout={handleLogout} 
      />
    </div>
  );
}

export default App;