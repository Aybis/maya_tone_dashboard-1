import React, { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext();
export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "dark",
  );
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("theme", theme);
  }, [theme]);
  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      className="text-[10px] px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700"
      title="Toggle theme"
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
