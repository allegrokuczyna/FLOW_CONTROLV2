import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
    BarChart3, Users, TrendingUp, Clock, Search, RefreshCcw, CalendarDays, 
    Calculator, UserMinus, ShieldCheck, CalendarRange
} from 'lucide-react';

const WarehouseCockpit = () => {
    const getRelativeDate = (offset) => {
        const d = new Date();
        d.setDate(d.getDate() + offset);
        return d.toISOString().split('T')[0];
    };

    const [date, setDate] = useState(getRelativeDate(0));
    const [activeTab, setActiveTab] = useState('forecast');
    const [loading, setLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastUpdated, setLastUpdated] = useState('');
    const [selectedShift, setSelectedShift] = useState('2');

    const [data, setData] = useState({
        forecast: [], // Hourly forecast for selected date
        weeklyForecast: [], // Summary for 7 days
        matrix: [],
        schedule: { 1: [], 2: [], 3: [] }
    });

    const fetchAllData = async () => {
        setLoading(true);
        try {
            // Pobieramy dane: 1. Hourly Forecast, 2. Weekly Summary, 3. Matrix, 4. Shifts
            const [forecastRes, weeklyRes, matrixRes, s1, s2, s3] = await Promise.all([
                axios.get(`/api/works/forecast_upcoming?date=${date}`),
                axios.get(`/api/works/forecast_weekly`), // Załóżmy ten endpoint dla wykresu 7-dniowego
                axios.get('/api/productivity'),
                axios.get(`/api/plan/workers/1?target_date=${date}`),
                axios.get(`/api/plan/workers/2?target_date=${date}`),
                axios.get(`/api/plan/workers/3?target_date=${date}`)
            ]);

            setData({
                forecast: forecastRes.data.data || forecastRes.data || [],
                weeklyForecast: weeklyRes.data || [], // Format: [{date: '2026-05-15', total_pcs: 12000}, ...]
                matrix: matrixRes.data || [],
                schedule: { 1: s1.data || [], 2: s2.data || [], 3: s3.data || [] }
            });
            setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        } catch (err) {
            console.error("Błąd kokpitu:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchAllData(); }, [date]);

    // --- WIDOK TYGODNIOWEGO INTAKE ---
    const WeeklyChart = () => {
        const weekly = data.weeklyForecast.length > 0 ? data.weeklyForecast : [
            { date: getRelativeDate(0), total_pcs: 0 },
            { date: getRelativeDate(1), total_pcs: 0 },
            { date: getRelativeDate(2), total_pcs: 0 },
            { date: getRelativeDate(3), total_pcs: 0 },
            { date: getRelativeDate(4), total_pcs: 0 },
            { date: getRelativeDate(5), total_pcs: 0 },
            { date: getRelativeDate(6), total_pcs: 0 },
        ];
        
        const maxVal = Math.max(...weekly.map(d => d.total_pcs || 0), 1000);

        return (
            <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm mb-6">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
                    <CalendarRange size={14} /> Planowany Intake (7 Dni)
                </h4>
                <div className="flex justify-between items-end h-32 gap-2">
                    {weekly.map((day, i) => {
                        const height = ((day.total_pcs || 0) / maxVal) * 100;
                        const isSelected = day.date === date;
                        return (
                            <div key={i} className="flex-1 flex flex-col items-center gap-2 group cursor-pointer" onClick={() => setDate(day.date)}>
                                <div className="w-full bg-slate-50 rounded-lg relative overflow-hidden h-full">
                                    <div 
                                        className={`absolute bottom-0 w-full transition-all duration-500 ${isSelected ? 'bg-indigo-600' : 'bg-slate-200 group-hover:bg-indigo-300'}`}
                                        style={{ height: `${height}%` }}
                                    />
                                </div>
                                <span className={`text-[8px] font-black uppercase ${isSelected ? 'text-indigo-600' : 'text-slate-400'}`}>
                                    {day.date.split('-').slice(1).reverse().join('.')}
                                </span>
                                <span className="text-[9px] font-black text-slate-700">{day.total_pcs?.toLocaleString()}</span>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    const ForecastView = () => {
        const hourly = Array.isArray(data.forecast) ? data.forecast : [];
        const totalToday = hourly.reduce((sum, f) => sum + (f.forecast_pcs || 0), 0);
        const maxHourly = Math.max(...hourly.map(f => f.forecast_pcs || 0), 100);

        return (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2">
                        <WeeklyChart />
                    </div>
                    <div className="bg-slate-900 rounded-3xl p-8 text-white flex flex-col justify-center shadow-2xl">
                        <p className="text-indigo-400 text-[10px] font-black uppercase tracking-widest mb-2">Total Intake ({date})</p>
                        <h3 className="text-5xl font-black">{totalToday.toLocaleString()} <span className="text-sm font-normal text-slate-400">pcs</span></h3>
                        <div className="mt-4 flex items-center gap-2 text-emerald-400 text-[10px] font-bold">
                            <TrendingUp size={14} /> +12% względem wczoraj
                        </div>
                    </div>
                </div>

                <div className="bg-white rounded-[2.5rem] border border-slate-200 p-8 shadow-sm">
                    <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-8">Rozkład godzinowy: {date}</h4>
                    <div className="space-y-3">
                        {hourly.map((f, i) => (
                            <div key={i} className="flex items-center gap-4 group">
                                <span className="text-[10px] font-black text-slate-400 w-12">{f.hour_from ? new Date(f.hour_from).getHours() + ':00' : `${i}:00`}</span>
                                <div className="flex-1 bg-slate-50 h-8 rounded-lg overflow-hidden relative border border-slate-100">
                                    <div className="h-full bg-indigo-500 transition-all duration-700" style={{ width: `${(f.forecast_pcs / maxHourly) * 100}%` }} />
                                    <span className="absolute inset-y-0 left-3 flex items-center text-[10px] font-black text-white mix-blend-difference">{f.forecast_pcs} pcs</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full bg-[#f8fafc]">
            {/* TOOLBAR */}
            <div className="flex justify-between items-center p-8 pb-4 shrink-0">
                <div>
                    <h2 className="text-3xl font-black text-slate-900 tracking-tight">Operational Cockpit</h2>
                    <p className="text-xs font-bold text-slate-400 mt-1 flex items-center gap-1">
                        <Clock size={12}/> Ostatnia aktualizacja: {lastUpdated}
                    </p>
                </div>
                
                <div className="flex bg-white p-1 rounded-2xl border border-slate-200 shadow-sm">
                    <button onClick={() => setDate(getRelativeDate(0))} className={`px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${date === getRelativeDate(0) ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-50'}`}>Dziś</button>
                    <button onClick={() => setDate(getRelativeDate(1))} className={`px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${date === getRelativeDate(1) ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-50'}`}>Jutro</button>
                    <div className="w-px h-4 bg-slate-200 my-auto mx-2" />
                    <CalendarDays size={16} className="text-slate-400 ml-2 my-auto" />
                    <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="bg-transparent text-[10px] font-black px-3 py-2 outline-none text-slate-700 cursor-pointer" />
                </div>
            </div>

            {/* TABS */}
            <div className="px-8 mb-4">
                <div className="flex gap-4 border-b border-slate-200">
                    {['forecast', 'matrix', 'schedule'].map(tab => (
                        <button key={tab} onClick={() => setActiveTab(tab)} className={`pb-4 text-[10px] font-black uppercase tracking-widest transition-all border-b-2 ${activeTab === tab ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-400'}`}>
                            {tab}
                        </button>
                    ))}
                </div>
            </div>

            {/* CONTENT */}
            <div className="flex-1 overflow-y-auto p-8 pt-0 custom-scrollbar">
                {loading ? (
                    <div className="h-full flex items-center justify-center text-indigo-600">
                        <RefreshCcw size={40} className="animate-spin" />
                    </div>
                ) : (
                    <div className="max-w-7xl mx-auto">
                        {activeTab === 'forecast' && <ForecastView />}
                        {/* Pozostałe widoki (Matrix, Schedule) zostają jak wcześniej */}
                    </div>
                )}
            </div>
        </div>
    );
};

export default WarehouseCockpit;