import { useEffect } from 'react';
import { Form } from 'react-bootstrap';
import PasswordInput from '../PasswordInput';
import { FormField, FormModal } from '../ui';
import { useForm } from '../../hooks/useForm';
import { useSubmit } from '../../hooks/useSubmit';
import { updateUser } from '../../api/admin';
import { MIN_PASSWORD_LENGTH } from '../../utils/constants';
import { capitalize } from '../../utils/format';

const ROLES = ['patient', 'clinician', 'admin'];

export default function EditUserModal({ user, currentUserId, onHide, onSaved }) {
  const { values, setValues, handleChange } = useForm({ full_name: '', email: '', role: 'patient', password: '' });

  const { submit, submitting, error, setError } = useSubmit(
    async () => {
      const payload = { full_name: values.full_name, email: values.email, role: values.role };
      if (values.password) payload.password = values.password;
      await updateUser(user.user_id, payload);
      onSaved();
    },
    { fallback: 'Could not update user.' },
  );

  // Refill the form whenever a different user is opened.
  useEffect(() => {
    if (!user) return;
    setValues({ full_name: user.full_name, email: user.email, role: user.role, password: '' });
    setError('');
  }, [user, setValues, setError]);

  const isSelf = user?.user_id === currentUserId;

  return (
    <FormModal
      show={Boolean(user)}
      title="Edit user"
      error={error}
      submitLabel="Save changes"
      submittingLabel="Saving…"
      submitting={submitting}
      onSubmit={submit}
      onHide={onHide}
    >
      <FormField id="edit-name" label="Full name" name="full_name" value={values.full_name} onChange={handleChange} required />
      <FormField id="edit-email" label="Email" type="email" name="email" value={values.email} onChange={handleChange} required />
      <FormField id="edit-role" label="Role" hint={isSelf ? "You can't change your own role." : undefined}>
        <Form.Select name="role" value={values.role} onChange={handleChange} disabled={isSelf}>
          {ROLES.map((role) => (
            <option key={role} value={role}>{capitalize(role)}</option>
          ))}
        </Form.Select>
      </FormField>
      <FormField id="edit-password" label="New password" hint="Leave blank to keep the current password." className="mb-0">
        <PasswordInput
          name="password"
          value={values.password}
          onChange={handleChange}
          minLength={MIN_PASSWORD_LENGTH}
          autoComplete="new-password"
        />
      </FormField>
    </FormModal>
  );
}
