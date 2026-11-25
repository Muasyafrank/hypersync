import { useId } from 'react';
import { Alert, Button, Form, Modal } from 'react-bootstrap';

/**
 * Modal shell for a single form: title, optional description, error banner,
 * the fields (children) and the Cancel / Submit footer. The three admin
 * dialogs previously each repeated all of this markup.
 */
export default function FormModal({
  show,
  title,
  description,
  error,
  submitLabel,
  submittingLabel,
  submitting,
  onSubmit,
  onHide,
  children,
}) {
  const titleId = useId();
  const descriptionId = useId();

  return (
    <Modal
      show={show}
      onHide={onHide}
      centered
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
    >
      <Modal.Body className="p-4">
        <h2 id={titleId} className={`hs-title hs-modal-title ${description ? 'mb-1' : 'mb-3'}`}>{title}</h2>
        {description && <p id={descriptionId} className="hs-subtitle hs-panel-description mb-3">{description}</p>}

        {error && <Alert variant="danger" role="alert">{error}</Alert>}

        <Form onSubmit={onSubmit} noValidate>
          {children}
          <div className="d-flex justify-content-end gap-2 mt-4">
            <Button variant="outline-secondary" onClick={onHide} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" className="btn-hs-primary" disabled={submitting}>
              {submitting ? submittingLabel : submitLabel}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}
