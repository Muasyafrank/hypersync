import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { Button, Modal } from 'react-bootstrap';
import { AlertTriangle } from 'lucide-react';

const ConfirmContext = createContext(null);

const DEFAULTS = {
  title: 'Are you sure?',
  message: 'This action cannot be undone.',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  variant: 'danger',
};

export function ConfirmProvider({ children }) {
  const [config, setConfig] = useState(null);
  const resolveRef = useRef(null);

  /** Resolves true if the user confirms, false if they cancel or dismiss. */
  const confirm = useCallback((options) => {
    setConfig({ ...DEFAULTS, ...options });
    return new Promise((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  function handleClose(result) {
    setConfig(null);
    resolveRef.current?.(result);
    resolveRef.current = null;
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}

      <Modal show={Boolean(config)} onHide={() => handleClose(false)} centered>
        {config && (
          <>
            <Modal.Body className="p-4">
              <div className="d-flex align-items-start gap-3">
                <div className={`hs-confirm-icon hs-confirm-icon-${config.variant}`}>
                  <AlertTriangle size={20} aria-hidden="true" />
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
  const context = useContext(ConfirmContext);
  if (context === null) throw new Error('useConfirm must be used inside a <ConfirmProvider>');
  return context;
}
