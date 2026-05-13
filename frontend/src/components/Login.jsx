import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Lock, ArrowRight, Cpu, Loader2 } from 'lucide-react';
import api from '../api'; // Upewnij się, że ścieżka do Twojego api.js jest poprawna

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
            // FastAPI OAuth2 wymaga formatu x-www-form-urlencoded
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const res = await api.post('/auth/login', formData, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });

            if (res.data.access_token) {
                localStorage.setItem('token', res.data.access_token);
                // Funkcja przekazana z App.jsx, która zmienia stan na zalogowany
                if (onLoginSuccess) onLoginSuccess();
                else window.location.reload(); // Fallback
            }
        } catch (err) {
            setError('Niepoprawny login lub hasło.');
        } finally {
            setIsLoading(false);
        }
    };

    // --- ANIMACJE (Framer Motion) ---
    const containerVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: { 
            opacity: 1, 
            y: 0,
            transition: { duration: 0.6, staggerChildren: 0.1 }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, x: -20 },
        visible: { opacity: 1, x: 0 }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-[#0a0c10]">
            
            {/* BAJER: Animowane tło (Pływające poświaty) */}
            <motion.div 
                animate={{ 
                    x: [0, 100, -100, 0], 
                    y: [0, -100, 100, 0],
                    scale: [1, 1.2, 0.8, 1]
                }}
                transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                className="absolute w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[120px] top-[-10%] left-[-10%]"
            />
            <motion.div 
                animate={{ 
                    x: [0, -150, 150, 0], 
                    y: [0, 150, -150, 0],
                    scale: [1, 1.5, 0.9, 1]
                }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="absolute w-[500px] h-[500px] bg-amber-600/10 rounded-full blur-[100px] bottom-[-10%] right-[-10%]"
            />

            {/* GŁÓWNA KARTA LOGOWANIA */}
            <motion.div 
                variants={containerVariants}
                initial="hidden"
                animate="visible"
                className="w-full max-w-md p-8 md:p-10 rounded-[2rem] bg-white/[0.02] border border-white/10 shadow-2xl backdrop-blur-xl relative z-10 mx-4"
            >
                {/* Logo / Nagłówek */}
                <motion.div variants={itemVariants} className="flex flex-col items-center justify-center mb-10">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-amber-600/20 border border-white/10 flex items-center justify-center mb-4 shadow-lg shadow-blue-900/20">
                        <Cpu className="text-gray-300" size={32} />
                    </div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Flow Control</h1>
                    <p className="text-xs text-gray-500 uppercase tracking-[0.3em] mt-2 font-semibold">Autoryzacja Systemu</p>
                </motion.div>

                {/* Formularz */}
                <form onSubmit={handleLogin} className="space-y-6">
                    <motion.div variants={itemVariants} className="space-y-4">
                        
                        {/* Input: Login */}
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-blue-400 transition-colors">
                                <User size={18} />
                            </div>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="Identyfikator / Login"
                                required
                                className="w-full pl-12 pr-4 py-4 bg-black/40 border border-white/5 rounded-xl text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all text-sm font-medium"
                            />
                        </div>

                        {/* Input: Hasło */}
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-amber-400 transition-colors">
                                <Lock size={18} />
                            </div>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Hasło dostępu"
                                required
                                className="w-full pl-12 pr-4 py-4 bg-black/40 border border-white/5 rounded-xl text-gray-300 placeholder-gray-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all text-sm font-medium"
                            />
                        </div>

                    </motion.div>

                    {/* Błędy */}
                    <AnimatePresence>
                        {error && (
                            <motion.div 
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="text-red-400 text-xs text-center font-medium bg-red-500/10 py-2 rounded-lg border border-red-500/20"
                            >
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Przycisk Submit */}
                    <motion.div variants={itemVariants} className="pt-2">
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="group relative w-full flex items-center justify-center gap-3 bg-white/10 hover:bg-white/15 text-white py-4 rounded-xl font-bold tracking-widest uppercase text-xs transition-all overflow-hidden border border-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {/* Efekt najechania (Hover Sweep) */}
                            <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-in-out" />
                            
                            {isLoading ? (
                                <>
                                    <Loader2 className="animate-spin" size={16} />
                                    Autoryzacja...
                                </>
                            ) : (
                                <>
                                    Rozpocznij Sesję
                                    <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </motion.div>
                </form>
            </motion.div>
        </div>
    );
};

export default Login;