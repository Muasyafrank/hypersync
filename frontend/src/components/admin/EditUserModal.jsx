import { useEffect, useState } from 'react';
import { Alert, Button, Form, Modal } from 'react-bootstrap';
import PasswordInput from '../PasswordInput';
import { useForm } from '../../hooks/useForm';
import { updateUser } from '../../api/admin';
import { errorMessage } from '../../utils/format';

const ROLES = ['patient', 'clinician', 'admin'];
const MIN_PASSWORD_LENGTH = 8;

export default function EditUserModal({ user, currentUserId, onHide, onSaved }) {
  const { values, setValues, handleChange } = useForm({ full_name: '', email: '', role: 'patient', password: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Refill the form whenever a different user is opened.
  useEffect(() => {
    if (!user) return;
    setValues({ full_name: user.full_name, email: user.email, role: user.role, password: '' });
    setError('');
  }, [user, setValues]);

  const isSelf = user?.user_id === currentUserId;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const payload = { full_name: values.full_name, email: values.email, role: values.role };
      if (values.password) payload.password = values.password;
      await updateUser(user.user_id, payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err, 'Could not update user.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal show={Boolean(user)} onHide={onHide} centered>
      <Modal.Body className="p-4">
        <h5 className="hs-title mb-3">Edit user</h5>
        {error && <Alert variant="danger" role="alert">{error}</Alert>}

        <Form onSubmit={handleSubmit} noValidate>
          <Form.Group className="mb-3" controlId="edit-name">
            <Form.Label className="hs-form-label">Full name</Form.Label>
            <Form.Control name="full_name" value={values.full_name} onChange={handleChange} required />
          </Form.Group>
          <Form.Group className="mb-3" controlId="edit-email">
            <Form.Label className="hs-form-label">Email</Form.Label>
            <Form.Control type="email" name="email" value={values.email} onChange={handleChange} required />
          </Form.Group>
          <Form.Group className="mb-3" controlId="edit-role">
            <Form.Label className="hs-form-label">Role</Form.Label>
            <Form.Select name="role" value={values.role} onChange={handleChange} disabled={isSelf}>
              {ROLES.map((role) => (
                <option key={role} value={role}>{role.charAt(0).toUpperCase() + role.slice(1)}</option>
              ))}
            </Form.Select>
            {isSelf && <Form.Text className="text-muted">You can&apos;t change your own role.</Form.Text>}
          </Form.Group>
          <Form.Group className="mb-4" controlId="edit-password">
            <Form.Label className="hs-form-label">New password</Form.Label>
            <PasswordInput
              name="password"
              value={values.password}
              onChange={handleChange}
              minLength={MIN_PASSWORD_LENGTH}
              autoComplete="new-password"
            />
            <Form.Text className="text-muted">Leave blank to keep the current password.</Form.Text>
          </Form.Group>

          <div className="d-flex justify-content-end gap-2">
            <Button variant="outline-secondary" onClick={onHide} disabled={submitting}>Cancel</Button>
            <Button type="submit" className="btn-hs-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </Form>
      </Modal.Body>
    </Modal>
  );
}
