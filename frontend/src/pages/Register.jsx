import { useState } from 'react';
import { Alert, Button, Col, Form, Row } from 'react-bootstrap';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../components/AuthCard';
import PasswordInput from '../components/PasswordInput';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useForm } from '../hooks/useForm';
import { getCurrentUser, loginUser, registerUser } from '../api/auth';
import { setTokens } from '../api/tokenStorage';
import { errorMessage } from '../utils/format';

const MIN_PASSWORD_LENGTH = 8;
const SEX_OPTIONS = ['Male', 'Female', 'Other'];

export default function Register() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const toast = useToast();

  const { values, handleChange } = useForm({
    full_name: '',
    email: '',
    password: '',
    date_of_birth: '',
    sex: '',
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await registerUser({
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        password: values.password,
        date_of_birth: values.date_of_birth || null,
        sex: values.sex || null,
      });

      // Log straight in so the patient lands on their dashboard.
      const tokens = await loginUser({ email: values.email.trim(), password: values.password });
      setTokens(tokens);
      const user = await getCurrentUser();
      login(tokens, user);
      toast.success('Account created successfully!');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const message = errorMessage(err, 'Registration failed. Please check your details.');
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start tracking your blood pressure at home"
      maxWidth={480}
      footer={<>Already have an account? <Link to="/login" className="hs-link">Log in</Link></>}
    >
      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <Form onSubmit={handleSubmit} noValidate>
        <Form.Group className="mb-3" controlId="register-name">
          <Form.Label className="hs-form-label">Full name</Form.Label>
          <Form.Control name="full_name" value={values.full_name} onChange={handleChange} autoComplete="name" required />
        </Form.Group>

        <Form.Group className="mb-3" controlId="register-email">
          <Form.Label className="hs-form-label">Email</Form.Label>
          <Form.Control type="email" name="email" value={values.email} onChange={handleChange} autoComplete="email" required />
        </Form.Group>

        <Form.Group className="mb-3" controlId="register-password">
          <Form.Label className="hs-form-label">Password</Form.Label>
          <PasswordInput
            value={values.password}
            onChange={handleChange}
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
          <Form.Text className="text-muted">At least {MIN_PASSWORD_LENGTH} characters.</Form.Text>
        </Form.Group>

        <Row className="mb-4">
          <Col>
            <Form.Label className="hs-form-label" htmlFor="register-dob">Date of birth</Form.Label>
            <Form.Control
              id="register-dob"
              type="date"
              name="date_of_birth"
              value={values.date_of_birth}
              max={new Date().toISOString().slice(0, 10)}
              onChange={handleChange}
            />
          </Col>
          <Col>
            <Form.Label className="hs-form-label" htmlFor="register-sex">Sex</Form.Label>
            <Form.Select id="register-sex" name="sex" value={values.sex} onChange={handleChange}>
              <option value="">Select…</option>
              {SEX_OPTIONS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </Form.Select>
          </Col>
        </Row>

        <Button type="submit" className="btn-hs-primary w-100" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Register'}
        </Button>
      </Form>
    </AuthCard>
  );
}
