import { createContext, useContext, useState, useCallback } from 'react';
import { ToastContainer, Toast } from 'react-bootstrap';
import { CheckCircle2, XCircle, Info, AlertTriangle } from 'lucide-react';

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

  const showToast = useCallback((message, variant = 'success', duration = 4000) => {
    const id = ++idCounter;
    setToasts((prev) => [...prev, { id, message, variant, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = {
    success: (msg, duration) => showToast(msg, 'success', duration),
    error: (msg, duration) => showToast(msg, 'error', duration),
    info: (msg, duration) => showToast(msg, 'info', duration),
    warning: (msg, duration) => showToast(msg, 'warning', duration),
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <ToastContainer position="top-end" className="p-3" style={{ position: 'fixed', zIndex: 2000 }}>
        {toasts.map((t) => (
          <Toast key={t.id} onClose={() => removeToast(t.id)} delay={t.duration} autohide className="hs-toast">
            <Toast.Body className="d-flex align-items-center gap-2">
              {ICONS[t.variant]}
              <span style={{ color: 'var(--hs-navy)', fontSize: '0.9rem', fontWeight: 500 }}>
                {t.message}
              </span>
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}