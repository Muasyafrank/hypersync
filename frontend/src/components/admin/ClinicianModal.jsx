import PasswordInput from '../PasswordInput';
import { FormField, FormModal } from '../ui';
import { useForm } from '../../hooks/useForm';
import { useSubmit } from '../../hooks/useSubmit';
import { createClinician } from '../../api/admin';
import { MIN_PASSWORD_LENGTH } from '../../utils/constants';

const EMPTY = { full_name: '', email: '', password: '' };

export default function ClinicianModal({ show, onHide, onCreated }) {
  const { values, handleChange, reset } = useForm(EMPTY);

  const { submit, submitting, error, setError } = useSubmit(
    async () => {
      await createClinician(values);
      onCreated(values.full_name);
      close();
    },
    { fallback: 'Could not create clinician account.' },
  );

  function close() {
    reset();
    setError('');
    onHide();
  }

  return (
    <FormModal
      show={show}
      title="Create clinician account"
      description="Clinician accounts can't be self-registered — they're provisioned here."
      error={error}
      submitLabel="Create account"
      submittingLabel="Creating…"
      submitting={submitting}
      onSubmit={submit}
      onHide={close}
    >
      <FormField id="clinician-name" label="Full name" name="full_name" value={values.full_name} onChange={handleChange} required />
      <FormField id="clinician-email" label="Email" type="email" name="email" value={values.email} onChange={handleChange} required />
      <FormField id="clinician-password" label="Temporary password" hint={`At least ${MIN_PASSWORD_LENGTH} characters.`} className="mb-0">
        <PasswordInput
          name="password"
          value={values.password}
          onChange={handleChange}
          minLength={MIN_PASSWORD_LENGTH}
          autoComplete="new-password"
          required
        />
      </FormField>
    </FormModal>
  );
}
