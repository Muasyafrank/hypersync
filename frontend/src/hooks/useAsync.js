import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Runs an async loader and tracks { data, loading, error }.
 *
 * Replaces the useState/useEffect/.then/.finally boilerplate that was
 * duplicated in nearly every page, and — importantly — ignores results
 * that arrive after the component unmounts or after the dependencies
 * change, which the original pages only did in some places.
 *
 * @param loader      async function returning the data
 * @param deps        re-run when these change
 * @param initialData value for `data` before the first load resolves
 */
export function useAsync(loader, deps = [], initialData = null) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestId = useRef(0);

  const run = useCallback(() => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);

    return Promise.resolve()
      .then(loader)
      .then((result) => {
        if (id === requestId.current) setData(result);
        return result;
      })
      .catch((err) => {
        if (id === requestId.current) setError(err);
        return undefined;
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    return () => { requestId.current += 1; }; // invalidate in-flight results
  }, [run]);

  return { data, loading, error, reload: run, setData };
}
