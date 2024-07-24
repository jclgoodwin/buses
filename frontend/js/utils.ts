import { useState, useEffect } from "react";

export const useDarkMode = () => {
  const query = window.matchMedia("(prefers-color-scheme: dark)");

  const [darkMode, setDarkMode] = useState(query.matches);

  useEffect(() => {
    const handleChange = (e: MediaQueryListEvent) => {
      setDarkMode(e.matches);
    };

    query.addEventListener("change", handleChange);

    return () => {
      query.removeEventListener("change", handleChange);
    };
  }, [query]);

  return darkMode
};
