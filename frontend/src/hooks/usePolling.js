import { useEffect, useRef } from 'react';

/**
 * Custom Hook do cichego odświeżania danych w tle.
 * @param {Function} callback - Funkcja, która ma się wykonać (np. pobieranie danych z API)
 * @param {number} delay - Czas w milisekundach (np. 10000 dla 10 sekund)
 */
export const usePolling = (callback, delay) => {
  const savedCallback = useRef();

  // 1. Zawsze zapamiętujemy najnowszą wersję funkcji callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // 2. Konfigurujemy interwał
  useEffect(() => {
    // Jeśli delay to null, wyłączamy odświeżanie
    if (delay === null) return;

    const tick = () => savedCallback.current();
    
    const id = setInterval(tick, delay);
    return () => clearInterval(id); // Czyszczenie po wyjściu z danej strony
  }, [delay]);
};