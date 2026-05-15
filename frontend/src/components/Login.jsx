import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Lock, ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import api from '../api';

const Login = ({ onLoginSuccess }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const handleLogin = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');

        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const res = await api.post('/auth/login', formData, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });

            if (res.data.access_token) {
                localStorage.setItem('token', res.data.access_token);
                if (onLoginSuccess) onLoginSuccess();
                else window.location.reload();
            }
        } catch (err) {
            setError('Autoryzacja odrzucona. Sprawdź poświadczenia.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center bg-slate-50 relative overflow-hidden font-sans p-4">
            
            {/* SZEROKI PANEL LOGOWANIA */}
            <motion.div 
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="w-full max-w-4xl bg-white border border-slate-200 rounded-3xl shadow-xl relative z-10 flex flex-col md:flex-row p-8 md:p-10 gap-8 md:gap-12 items-center"
            >
                {/* LEWA STRONA - LOGO I TYTUŁ */}
                <div className="flex flex-col justify-center gap-4 w-full md:w-1/2">
                    <div className="w-16 h-16 rounded-2xl bg-[#8b5cf6] flex items-center justify-center shadow-lg text-white font-black text-sm font-mono tracking-tighter">
                        ADM
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-slate-800 tracking-tight mb-2">Dostęp do Systemu</h1>
                        <p className="text-sm text-slate-500 font-medium leading-relaxed max-w-xs">
                            Zaloguj się, aby uzyskać dostęp do panelu sterowania Adamów Flow Control.
                        </p>
                    </div>
                    <div className="flex items-center gap-2 text-slate-400 mt-4">
                        <ShieldCheck size={16} />
                        <span className="text-[10px] uppercase tracking-widest font-bold">Magazyn ADM-01</span>
                    </div>
                </div>

                {/* SEPARATOR (Tylko na dużych ekranach) */}
                <div className="hidden md:block w-px h-48 bg-slate-100 shrink-0"></div>

                {/* PRAWA STRONA - FORMULARZ (Pionowy) */}
                <div className="w-full md:w-1/2">
                    <form onSubmit={handleLogin} className="flex flex-col gap-4">
                        
                        {/* Pole: Login */}
                        <div className="relative group w-full">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-[#8b5cf6] transition-colors">
                                <User size={18} />
                            </div>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="Identyfikator użytkownika"
                                required
                                className="w-full pl-11 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#8b5cf6] focus:ring-1 focus:ring-[#8b5cf6] transition-all text-sm font-medium"
                            />
                        </div>

                        {/* Pole: Hasło */}
                        <div className="relative group w-full">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-[#8b5cf6] transition-colors">
                                <Lock size={18} />
                            </div>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Hasło dostępowe"
                                required
                                className="w-full pl-11 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#8b5cf6] focus:ring-1 focus:ring-[#8b5cf6] transition-all text-sm font-medium"
                            />
                        </div>

                        {/* Komunikat o błędzie */}
                        <AnimatePresence>
                            {error && (
                                <motion.div 
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="overflow-hidden"
                                >
                                    <div className="text-red-500 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2 bg-red-50 py-3 px-4 rounded-xl border border-red-100">
                                        <div className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse shrink-0"></div>
                                        {error}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Przycisk Logowania */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full h-[52px] mt-2 flex items-center justify-center gap-2.5 bg-[#8b5cf6] hover:bg-[#7c3aed] text-white rounded-xl font-bold tracking-widest uppercase text-[11px] transition-all shadow-md hover:shadow-lg disabled:opacity-60 group"
                        >
                            {isLoading ? (
                                <Loader2 className="animate-spin" size={18} />
                            ) : (
                                <>
                                    Autoryzuj dostęp
                                    <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </form>
                </div>

            </motion.div>
        </div>
    );
};

export default Login;