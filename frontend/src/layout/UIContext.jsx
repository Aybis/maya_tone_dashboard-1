import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

const UIContext = createContext(null);
export const useUI = () => useContext(UIContext);

export function UIProvider({ children }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("sidebar_collapsed") === "1",
  );
  const [sidebarAutoHidden, setSidebarAutoHidden] = useState(false); // hides fully when canvas open
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem("sidebar_collapsed", sidebarCollapsed ? "1" : "0");
  }, [sidebarCollapsed]);

  const toggleSidebar = useCallback(() => setSidebarCollapsed((c) => !c), []);
  const openSearch = useCallback(() => setSearchOpen(true), []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);

  const value = {
    sidebarCollapsed,
    toggleSidebar,
    setSidebarCollapsed,
    sidebarAutoHidden,
    setSidebarAutoHidden,
    searchOpen,
    openSearch,
    closeSearch,
  };
  return <UIContext.Provider value={value}>{children}</UIContext.Provider>;
}
