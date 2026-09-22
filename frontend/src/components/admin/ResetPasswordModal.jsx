import { useEffect, useState } from 'react';
import { Alert, Button, Form, Modal } from 'react-bootstrap';
import PasswordInput from '../PasswordInput';
import { resetPassword } from '../../api/admin';
import { errorMessage } from '../../utils/format';

const MIN_PASSWORD_LENGTH = 8;

export default function ResetPasswordModal({ user, onHide, onReset }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setPassword('');
    setError('');
  }, [user]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await resetPassword(user.user_id, password);
      onReset(user.full_name);
    } catch (err) {
      setError(errorMessage(err, 'Could not reset password.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal show={Boolean(user)} onHide={onHide} centered>
      <Modal.Body className="p-4">
        <h5 className="hs-title mb-1">Reset password</h5>
        <p className="hs-subtitle hs-panel-description mb-3">
          Set a new password for {user?.full_name}. Share it with them securely.
        </p>

        {error && <Alert variant="danger" role="alert">{error}</Alert>}

        <Form onSubmit={handleSubmit} noValidate>
          <Form.Group className="mb-4" controlId="reset-password">
            <Form.Label className="hs-form-label">New password</Form.Label>
            <PasswordInput
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={MIN_PASSWORD_LENGTH}
              autoComplete="new-password"
              required
            />
            <Form.Text className="text-muted">At least {MIN_PASSWORD_LENGTH} characters.</Form.Text>
          </Form.Group>

          <div className="d-flex justify-content-end gap-2">
            <Button variant="outline-secondary" onClick={onHide} disabled={submitting}>Cancel</Button>
            <Button type="submit" className="btn-hs-primary" disabled={submitting}>
              {submitting ? 'Resetting…' : 'Reset password'}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}
