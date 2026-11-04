import { useEffect, useState } from 'react';
import PasswordInput from '../PasswordInput';
import { FormField, FormModal } from '../ui';
import { useSubmit } from '../../hooks/useSubmit';
import { resetPassword } from '../../api/admin';
import { MIN_PASSWORD_LENGTH } from '../../utils/constants';

export default function ResetPasswordModal({ user, onHide, onReset }) {
  const [password, setPassword] = useState('');

  const { submit, submitting, error, setError } = useSubmit(
    async () => {
      await resetPassword(user.user_id, password);
      onReset(user.full_name);
    },
    { fallback: 'Could not reset password.' },
  );

  useEffect(() => {
    setPassword('');
    setError('');
  }, [user, setError]);

  return (
    <FormModal
      show={Boolean(user)}
      title="Reset password"
      description={`Set a new password for ${user?.full_name ?? ''}. Share it with them securely.`}
      error={error}
      submitLabel="Reset password"
      submittingLabel="Resetting…"
      submitting={submitting}
      onSubmit={submit}
      onHide={onHide}
    >
      <FormField id="reset-password" label="New password" hint={`At least ${MIN_PASSWORD_LENGTH} characters.`} className="mb-0">
        <PasswordInput
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={MIN_PASSWORD_LENGTH}
          autoComplete="new-password"
          required
        />
      </FormField>
    </FormModal>
  );
}
