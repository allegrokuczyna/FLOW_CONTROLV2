import React, { useState } from 'react';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('dashboard');

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={() => setIsLoggedIn(true)} />;
  }

  return (
    <div className="flex h-screen bg-[#0a0c10] text-white">
      {/* GŁÓWNA TREŚĆ */}
      <main className="flex-1 p-12 overflow-y-auto">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab !== 'dashboard' && (
          <div className="h-full flex items-center justify-center text-gray-700 italic">
            Moduł "{activeTab}" zostanie podpięty pod API Dynamics w kolejnym kroku.
          </div>
        )}
      </main>

      {/* MENU PO PRAWEJ */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        onLogout={handleLogout} 
      />
    </div>
  );
}

export default App;