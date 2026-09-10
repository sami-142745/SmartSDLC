import { useCallback, useEffect, useState } from 'react';

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });

  const refetch = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    return fn().then(
      (data) => setState({ data, loading: false, error: null }),
      (err) =>
        setState({
          data: null,
          loading: false,
          error: (err as { message?: string }).message ?? 'Something went wrong.',
        }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data: state.data, loading: state.loading, error: state.error, refetch };
}