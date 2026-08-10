import { createContext, useContext, useState, useCallback, useRef } from 'react';
import { Modal, Button } from 'react-bootstrap';
import { AlertTriangle } from 'lucide-react';

const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [config, setConfig] = useState(null);
  const resolveRef = useRef(null);

  const confirm = useCallback((options) => {
    setConfig({
      title: options.title || 'Are you sure?',
      message: options.message || 'This action cannot be undone.',
      confirmLabel: options.confirmLabel || 'Confirm',
      cancelLabel: options.cancelLabel || 'Cancel',
      variant: options.variant || 'danger',
    });
    return new Promise((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  function handleClose(result) {
    setConfig(null);
    if (resolveRef.current) {
      resolveRef.current(result);
      resolveRef.current = null;
    }
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}

      <Modal show={!!config} onHide={() => handleClose(false)} centered>
        {config && (
          <>
            <Modal.Body className="p-4">
              <div className="d-flex align-items-start gap-3">
                <div
                  style={{
                    width: 40, height: 40, borderRadius: '50%',
                    backgroundColor: config.variant === 'danger' ? '#FEE2E2' : 'rgba(13,148,136,0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}
                >
                  <AlertTriangle size={20} color={config.variant === 'danger' ? '#DC2626' : '#0D9488'} />
                </div>
                <div>
                  <h5 className="hs-title mb-2">{config.title}</h5>
                  <p className="hs-subtitle mb-0">{config.message}</p>
                </div>
              </div>
            </Modal.Body>
            <Modal.Footer className="border-0 pt-0">
              <Button variant="outline-secondary" onClick={() => handleClose(false)}>
                {config.cancelLabel}
              </Button>
              <Button
                className={config.variant === 'danger' ? 'btn-hs-danger' : 'btn-hs-primary'}
                onClick={() => handleClose(true)}
              >
                {config.confirmLabel}
              </Button>
            </Modal.Footer>
          </>
        )}
      </Modal>
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  return useContext(ConfirmContext);
}