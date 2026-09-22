import { useState } from 'react';
import { Alert, Button, Form } from 'react-bootstrap';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../components/AuthCard';
import PasswordInput from '../components/PasswordInput';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useForm } from '../hooks/useForm';
import { getCurrentUser, loginUser } from '../api/auth';
import { setTokens } from '../api/tokenStorage';
import { roleHome } from '../utils/format';

const GENERIC_ERROR = 'Incorrect email or password.';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const toast = useToast();
  const { values, handleChange } = useForm({ email: '', password: '' });

  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      const tokens = await loginUser(values);
      setTokens(tokens);
      const user = await getCurrentUser();
      login(tokens, user);
      toast.success(`Welcome back, ${user.full_name}!`);
      navigate(roleHome(user.role), { replace: true });
    } catch {
      // Deliberately generic: don't reveal whether the email exists.
      setError(GENERIC_ERROR);
      toast.error(GENERIC_ERROR);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Log in to continue monitoring your blood pressure"
      footer={<>Don&apos;t have an account? <Link to="/register" className="hs-link">Register</Link></>}
    >
      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <Form onSubmit={handleSubmit} noValidate>
        <Form.Group className="mb-3" controlId="login-email">
          <Form.Label className="hs-form-label">Email</Form.Label>
          <Form.Control
            type="email"
            name="email"
            value={values.email}
            onChange={handleChange}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
        </Form.Group>

        <Form.Group className="mb-4" controlId="login-password">
          <Form.Label className="hs-form-label">Password</Form.Label>
          <PasswordInput value={values.password} onChange={handleChange} required />
        </Form.Group>

        <Button type="submit" className="btn-hs-primary w-100" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </Button>
      </Form>
    </AuthCard>
  );
}
