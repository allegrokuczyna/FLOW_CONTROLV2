import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Lock, User, ShieldCheck } from 'lucide-react';
import api from '../api';

const Login = ({ onLoginSuccess }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        try {
            const response = await api.post('/auth/login', formData);
            localStorage.setItem('token', response.data.access_token);
            onLoginSuccess();
        } catch (err) {
            setError('Nieautoryzowany dostęp. Sprawdź poświadczenia.');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#0a0c10] relative overflow-hidden">
            {/* Dekoracyjne kule w tle */}
            <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-blue-600/20 rounded-full blur-[120px]" />
            <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-purple-600/20 rounded-full blur-[120px]" />

            <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-2xl shadow-2xl z-10"
            >
                <div className="text-center mb-10">
                    <div className="inline-flex p-4 rounded-2xl bg-blue-600/20 mb-4">
                        <ShieldCheck className="text-blue-500" size={32} />
                    </div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Flow Control V2</h1>
                    <p className="text-gray-400 text-sm mt-2">Wpisz dane, aby wejść do systemu</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    {error && <div className="text-red-400 text-sm text-center bg-red-400/10 py-2 rounded-lg">{error}</div>}
                    
                    <div className="relative">
                        <User className="absolute left-3 top-3 text-gray-500" size={20} />
                        <input 
                            type="text" placeholder="Użytkownik"
                            className="w-full bg-black/20 border border-white/10 rounded-xl py-3 pl-10 pr-4 text-white focus:outline-none focus:border-blue-500 transition-all"
                            onChange={(e) => setUsername(e.target.value)}
                        />
                    </div>

                    <div className="relative">
                        <Lock className="absolute left-3 top-3 text-gray-500" size={20} />
                        <input 
                            type="password" placeholder="Hasło"
                            className="w-full bg-black/20 border border-white/10 rounded-xl py-3 pl-10 pr-4 text-white focus:outline-none focus:border-blue-500 transition-all"
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>

                    <motion.button 
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-4 rounded-xl shadow-lg shadow-blue-600/20 transition-all"
                    >
                        Zaloguj
                    </motion.button>
                </form>
            </motion.div>
        </div>
    );
};

export default Login;