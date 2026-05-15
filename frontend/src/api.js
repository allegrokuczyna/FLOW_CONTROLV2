import axios from 'axios';

const api = axios.create({
  // DODANO /api NA KOŃCU ADRESU
  baseURL: 'http://localhost:8002/api', 
});

// Dodawanie tokena do każdego zapytania
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default api;