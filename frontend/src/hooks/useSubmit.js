import { useCallback, useState } from 'react';
import { errorMessage } from '../utils/format';

/**
 * Wraps a form's submit handler with the state every form needs: a
 * `submitting` flag (to disable the button) and a user-safe `error` string.
 *
 * Replaces the identical `try { … } catch { setError } finally { setSubmitting }`
 * block that each form page and modal carried.
 *
 * @param handler  async (event) => void. Throw to report a failure; call
 *                 `setError(message)` to report a validation problem.
 * @param options.fallback  message when the error carries no server detail
 * @param options.onError   called with the message too (e.g. to show a toast)
 */
export function useSubmit(handler, { fallback, onError } = {}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const submit = useCallback(
    async (event) => {
      event?.preventDefault?.();
      setError('');
      setSubmitting(true);
      try {
        await handler(event);
      } catch (err) {
        const message = errorMessage(err, fallback);
        setError(message);
        onError?.(message, err);
      } finally {
        setSubmitting(false);
      }
    },
    [handler, fallback, onError],
  );

  return { submit, submitting, error, setError };
}
