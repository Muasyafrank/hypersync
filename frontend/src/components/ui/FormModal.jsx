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
  return (
    <Modal show={show} onHide={onHide} centered>
      <Modal.Body className="p-4">
        <h5 className={`hs-title ${description ? 'mb-1' : 'mb-3'}`}>{title}</h5>
        {description && <p className="hs-subtitle hs-panel-description mb-3">{description}</p>}

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
