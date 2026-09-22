import { useCallback, useState } from 'react';

/**
 * Minimal controlled-form helper. Replaces the
 * `setForm({ ...form, [e.target.name]: e.target.value })` handler that was
 * copy-pasted into every form page, and handles checkboxes correctly.
 */
export function useForm(initialValues) {
  const [values, setValues] = useState(initialValues);

  const handleChange = useCallback((event) => {
    const { name, value, type, checked } = event.target;
    setValues((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  }, []);

  const setField = useCallback((name, value) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const reset = useCallback(() => setValues(initialValues), [initialValues]);

  return { values, setValues, setField, handleChange, reset };
}
