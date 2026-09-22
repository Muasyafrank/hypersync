import { useState } from 'react';
import { Alert, Button, Form, Modal } from 'react-bootstrap';
import PasswordInput from '../PasswordInput';
import { useForm } from '../../hooks/useForm';
import { createClinician } from '../../api/admin';
import { errorMessage } from '../../utils/format';

const EMPTY = { full_name: '', email: '', password: '' };
const MIN_PASSWORD_LENGTH = 8;

export default function ClinicianModal({ show, onHide, onCreated }) {
  const { values, handleChange, reset } = useForm(EMPTY);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function close() {
    reset();
    setError('');
    onHide();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await createClinician(values);
      onCreated(values.full_name);
      close();
    } catch (err) {
      setError(errorMessage(err, 'Could not create clinician account.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal show={show} onHide={close} centered>
      <Modal.Body className="p-4">
        <h5 className="hs-title mb-1">Create clinician account</h5>
        <p className="hs-subtitle hs-panel-description mb-3">
          Clinician accounts can&apos;t be self-registered — they&apos;re provisioned here.
        </p>

        {error && <Alert variant="danger" role="alert">{error}</Alert>}

        <Form onSubmit={handleSubmit} noValidate>
          <Form.Group className="mb-3" controlId="clinician-name">
            <Form.Label className="hs-form-label">Full name</Form.Label>
            <Form.Control name="full_name" value={values.full_name} onChange={handleChange} required />
          </Form.Group>
          <Form.Group className="mb-3" controlId="clinician-email">
            <Form.Label className="hs-form-label">Email</Form.Label>
            <Form.Control type="email" name="email" value={values.email} onChange={handleChange} required />
          </Form.Group>
          <Form.Group className="mb-4" controlId="clinician-password">
            <Form.Label className="hs-form-label">Temporary password</Form.Label>
            <PasswordInput
              name="password"
              value={values.password}
              onChange={handleChange}
              minLength={MIN_PASSWORD_LENGTH}
              autoComplete="new-password"
              required
            />
            <Form.Text className="text-muted">At least {MIN_PASSWORD_LENGTH} characters.</Form.Text>
          </Form.Group>

          <div className="d-flex justify-content-end gap-2">
            <Button variant="outline-secondary" onClick={close} disabled={submitting}>Cancel</Button>
            <Button type="submit" className="btn-hs-primary" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}
