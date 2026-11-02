import { Alert, Button, Form } from 'react-bootstrap';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../components/AuthCard';
import PasswordInput from '../components/PasswordInput';
import { FormField } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useForm } from '../hooks/useForm';
import { useSubmit } from '../hooks/useSubmit';
import { roleHome } from '../utils/format';

// Deliberately generic: don't reveal whether the email exists.
const BAD_CREDENTIALS = 'Incorrect email or password.';

export default function Login() {
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const toast = useToast();
  const { values, handleChange } = useForm({ email: '', password: '' });

  const { submit, submitting, error } = useSubmit(
    async () => {
      const user = await signIn(values);
      toast.success(`Welcome back, ${user.full_name}!`);
      navigate(roleHome(user.role), { replace: true });
    },
    { fallback: BAD_CREDENTIALS, onError: (message) => toast.error(message) },
  );

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Log in to continue monitoring your blood pressure"
      footer={<>Don&apos;t have an account? <Link to="/register" className="hs-link">Register</Link></>}
    >
      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <Form onSubmit={submit} noValidate>
        <FormField
          id="login-email"
          label="Email"
          type="email"
          name="email"
          value={values.email}
          onChange={handleChange}
          placeholder="you@example.com"
          autoComplete="email"
          required
        />

        <FormField id="login-password" label="Password" className="mb-4">
          <PasswordInput value={values.password} onChange={handleChange} required />
        </FormField>

        <Button type="submit" className="btn-hs-primary w-100" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </Button>
      </Form>
    </AuthCard>
  );
}
