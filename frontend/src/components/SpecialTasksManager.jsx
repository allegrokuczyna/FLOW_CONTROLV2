import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Wrench, Plus, Trash2, RefreshCcw, AlertTriangle, User, Layers, Briefcase, CheckCircle } from 'lucide-react';

const SpecialTasksManager = () => {
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [msg, setMsg] = useState(null);
    
    // Słownik przechowujący przypisania { "a123": "Outbound", "b456": "Inbound" }
    const [workersMap, setWorkersMap] = useState({});

    const [formData, setFormData] = useState({
        login: '',
        process: '',
        task_name: '' 
    });

    const fetchTasks = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/plan/special-tasks');
            if (res.data && res.data.status === 'success') {
                setTasks(Array.isArray(res.data.data) ? res.data.data : []);
            }
        } catch (err) {
            console.error("Błąd pobierania ról specjalnych:", err);
            setMsg({ type: 'error', text: 'Nie udało się pobrać danych z serwera.' });
        } finally {
            setLoading(false);
        }
    };

    const fetchWorkersMap = async () => {
        try {
            const res = await axios.get('/api/plan/weekly');
            if (res.data && res.data.workers) {
                const map = {};
                res.data.workers.forEach(w => {
                    if (w.login && w.process && w.process !== 'nan') {
                        map[w.login.toLowerCase()] = w.process;
                    }
                });
                setWorkersMap(map);
            }
        } catch (err) {
            console.error("Błąd pobierania słownika pracowników dla autouzupełniania", err);
        }
    };

    useEffect(() => {
        fetchTasks();
        fetchWorkersMap();
    }, []);

    const handleChange = (e) => {
        const { name, value } = e.target;
        
        setFormData(prev => {
            const updated = { ...prev, [name]: value };
            
            if (name === 'login') {
                const processAuto = workersMap[value.toLowerCase().trim()];
                if (processAuto) {
                    updated.process = processAuto;
                }
            }
            
            return updated;
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setMsg(null);

        if (!formData.login || !formData.process || !formData.task_name) {
            setMsg({ type: 'error', text: 'Wszystkie pola są wymagane! Wybierz zadanie z listy.' });
            return;
        }

        try {
            const res = await axios.post('/api/plan/special-tasks', formData);
            if (res.data.status === 'success') {
                setMsg({ type: 'success', text: 'Pracownik przypisany pomyślnie!' });
                setFormData({ login: '', process: '', task_name: '' }); 
                fetchTasks();
            }
        } catch (err) {
            setMsg({ type: 'error', text: err.response?.data?.detail || 'Wystąpił błąd podczas zapisu.' });
        }
    };

    const handleDelete = async (login) => {
        if (!window.confirm(`Czy na pewno chcesz usunąć rolę specjalną dla pracownika: ${login}?`)) return;
        
        try {
            const res = await axios.delete(`/api/plan/special-tasks/${login}`);
            if (res.data.status === 'success') {
                setMsg({ type: 'success', text: 'Rola usunięta pomyślnie.' });
                fetchTasks();
            }
        } catch (err) {
            setMsg({ type: 'error', text: 'Błąd podczas usuwania roli.' });
        }
    };

    const handleEditClick = (task) => {
        setFormData({
            login: task.login,
            process: task.process,
            task_name: task.task_name
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const safeTasks = Array.isArray(tasks) ? tasks : [];

    return (
        <div className="flex flex-col min-h-full bg-white rounded-[2rem] shadow-sm border border-slate-200 overflow-visible animate-in fade-in duration-300">
            
            <div className="p-6 border-b border-slate-100 bg-slate-50/50 shrink-0">
                <div className="flex items-center gap-4 mb-2">
                    <div className="bg-indigo-600 p-2.5 rounded-xl text-white shadow-md shadow-indigo-100">
                        <Wrench size={22} />
                    </div>
                    <div>
                        <h2 className="text-lg font-black uppercase tracking-widest text-slate-800">Role Specjalne (Indirects)</h2>
                        <p className="text-xs font-bold text-slate-400 mt-0.5">Zarządzanie pracami nieproduktywnymi (np. Water spider, Rozładunek)</p>
                    </div>
                </div>
            </div>

            <div className="p-6 flex flex-col xl:flex-row gap-8 items-start">
                
                {/* LEWA STRONA: FORMULARZ DODAWANIA */}
                <div className="w-full xl:w-1/3 xl:sticky xl:top-6">
                    <div className="bg-slate-50 p-6 rounded-3xl border border-slate-200 shadow-sm">
                        <h3 className="text-sm font-black uppercase tracking-widest text-slate-700 mb-6 flex items-center gap-2">
                            <Plus size={18} className="text-indigo-600" />
                            Dodaj / Edytuj Rolę
                        </h3>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block mb-1.5 ml-1">Login pracownika</label>
                                <div className="relative">
                                    <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                    <input 
                                        type="text"
                                        name="login"
                                        value={formData.login}
                                        onChange={handleChange}
                                        placeholder="np. A1234"
                                        className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-indigo-500 transition-all text-slate-700"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block mb-1.5 ml-1">Proces bazowy</label>
                                <div className="relative">
                                    <Layers size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                    <input 
                                        type="text"
                                        name="process"
                                        value={formData.process}
                                        onChange={handleChange}
                                        placeholder="Uzupełni się automatycznie..."
                                        className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-indigo-500 transition-all text-slate-700"
                                    />
                                </div>
                            </div>

                            {/* ZMIANA: Wartości "value" w select dopasowane 1:1 do subZones z WorkPlan */}
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block mb-1.5 ml-1">Zadanie Specjalne</label>
                                <div className="relative">
                                    <Briefcase size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                                    <select
                                        name="task_name"
                                        value={formData.task_name}
                                        onChange={handleChange}
                                        className="w-full pl-10 pr-10 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-indigo-500 transition-all text-slate-700 appearance-none cursor-pointer"
                                    >
                                        <option value="" disabled>Wybierz zadanie z listy...</option>
                                        <option value="rozładunek">Rozładunek(Przyjęcia)</option>
                                        <option value="water spider">Water Spider(Pakowanie)</option>
                                        <option value="produkcja wypełniacza">Wypełniacz(Pakowanie)</option>
                                        <option value="załadunki">Załadunki(Wysyłka)</option>
                                        <option value="sprzątanie">Sprzątanie(Przyjęcia)</option>
                                    </select>
                                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
                                    </div>
                                </div>
                            </div>

                            <button 
                                type="submit" 
                                className="w-full mt-4 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 shadow-lg shadow-indigo-200 transition-all active:scale-[0.98]"
                            >
                                <CheckCircle size={16} /> Zapisz Przypisanie
                            </button>
                        </form>

                        {msg && (
                            <div className={`mt-4 p-3 rounded-xl text-xs font-bold flex items-center gap-2 border animate-in slide-in-from-top-2 ${msg.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-rose-50 border-rose-200 text-rose-800'}`}>
                                <AlertTriangle size={16} /> {msg.text}
                            </div>
                        )}
                    </div>
                </div>

                {/* PRAWA STRONA: TABELA PRZYPISAŃ */}
                <div className="w-full xl:w-2/3 flex flex-col">
                    <div className="flex justify-between items-end mb-4">
                        <div>
                            <h3 className="text-sm font-black uppercase tracking-widest text-slate-700">Aktywne Przypisania ({safeTasks.length})</h3>
                            <p className="text-[10px] font-bold text-slate-400 mt-1">
                                Ci pracownicy zostaną automatycznie wykluczeni z ogólnej puli przez AI.
                            </p>
                        </div>
                        <button onClick={fetchTasks} className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-all">
                            <RefreshCcw size={18} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
                        <table className="w-full text-left border-collapse">
                            <thead className="bg-slate-50 border-b border-slate-100">
                                <tr className="text-[9px] font-black uppercase tracking-widest text-slate-400">
                                    <th className="p-4">Login</th>
                                    <th className="p-4">Proces</th>
                                    <th className="p-4">Zadanie Specjalne</th>
                                    <th className="p-4 text-right">Akcje</th>
                                </tr>
                            </thead>
                            <tbody className="text-xs font-medium text-slate-700 divide-y divide-slate-50">
                                {loading && safeTasks.length === 0 ? (
                                    <tr>
                                        <td colSpan="4" className="p-8 text-center text-slate-400 font-bold">Wczytywanie danych...</td>
                                    </tr>
                                ) : safeTasks.length === 0 ? (
                                    <tr>
                                        <td colSpan="4" className="p-8 text-center text-slate-400 font-bold bg-slate-50/50">
                                            Brak przypisanych ról specjalnych. Użyj formularza, aby dodać pracownika.
                                        </td>
                                    </tr>
                                ) : (
                                    safeTasks.map((task) => (
                                        <tr key={task.login} className="hover:bg-slate-50/80 transition-colors group cursor-pointer" onClick={() => handleEditClick(task)}>
                                            <td className="p-4 font-mono font-bold text-indigo-700">{task.login}</td>
                                            <td className="p-4 font-black text-slate-600">{task.process}</td>
                                            <td className="p-4">
                                                <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-amber-100 text-amber-700 border border-amber-200">
                                                    {task.task_name}
                                                </span>
                                            </td>
                                            <td className="p-4 text-right">
                                                <button 
                                                    onClick={(e) => { e.stopPropagation(); handleDelete(task.login); }}
                                                    className="p-2 bg-rose-50 text-rose-500 hover:bg-rose-500 hover:text-white rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                                                    title="Usuń rolę"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default SpecialTasksManager;