import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import { useDataSources } from './useDataSources';

type ActiveDataSourceContextValue = {
  sources: { key: string; label: string }[];
  activeSourceKey: string | null;
  setActiveSourceKey: (key: string | null) => void;
  loading: boolean;
  error: string | null;
};

const ActiveDataSourceContext = createContext<ActiveDataSourceContextValue | undefined>(undefined);

type ProviderProps = {
  children: ReactNode;
};

export const DataSourceProvider = ({ children }: ProviderProps) => {
  const { sources, active, loading, error } = useDataSources();
  const [activeSourceKey, setActiveSourceKey] = useState<string | null>(null);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!sources.length) {
      setActiveSourceKey(null);
      return;
    }
    setActiveSourceKey((previous) => {
      if (previous && sources.some((source) => source.key === previous)) {
        return previous;
      }
      const preferred = sources.find((source) => source.key === 'drivehud');
      if (preferred) {
        return preferred.key;
      }
      if (active && sources.some((source) => source.key === active)) {
        return active;
      }
      return sources[0]?.key ?? null;
    });
  }, [loading, sources, active]);

  const value: ActiveDataSourceContextValue = useMemo(
    () => ({
      sources,
      activeSourceKey,
      setActiveSourceKey,
      loading,
      error,
    }),
    [sources, activeSourceKey, loading, error],
  );

  return <ActiveDataSourceContext.Provider value={value}>{children}</ActiveDataSourceContext.Provider>;
};

export const useActiveDataSource = (): ActiveDataSourceContextValue => {
  const context = useContext(ActiveDataSourceContext);
  if (!context) {
    throw new Error('useActiveDataSource must be used within a DataSourceProvider');
  }
  return context;
};
