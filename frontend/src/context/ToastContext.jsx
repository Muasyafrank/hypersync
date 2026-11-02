import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Toast, ToastContainer } from 'react-bootstrap';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';

const ToastContext = createContext(null);

const ICONS = {
  success: <CheckCircle2 size={18} color="#16A34A" />,
  error: <XCircle size={18} color="#DC2626" />,
  info: <Info size={18} color="#0D9488" />,
  warning: <AlertTriangle size={18} color="#EAB308" />,
};

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, variant, duration = 4000) => {
    const id = ++idCounter;
    setToasts((prev) => [...prev, { id, message, variant, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Stable identity: consumers (and any effect that lists `toast` as a
  // dependency) must not see a new object every time a toast is added.
  const toast = useMemo(
    () => ({
      success: (message, duration) => showToast(message, 'success', duration),
      error: (message, duration) => showToast(message, 'error', duration),
      info: (message, duration) => showToast(message, 'info', duration),
      warning: (message, duration) => showToast(message, 'warning', duration),
    }),
    [showToast],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <ToastContainer position="top-end" className="p-3 hs-toast-container">
        {toasts.map((t) => (
          <Toast
            key={t.id}
            onClose={() => removeToast(t.id)}
            delay={t.duration}
            autohide
            className="hs-toast"
            role={t.variant === 'error' ? 'alert' : 'status'}
          >
            <Toast.Body className="d-flex align-items-center gap-2">
              {ICONS[t.variant]}
              <span className="hs-toast-text">{t.message}</span>
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (context === null) throw new Error('useToast must be used inside a <ToastProvider>');
  return context;
}
