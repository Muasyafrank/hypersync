import { Alert, Button, Col, Form, Row } from 'react-bootstrap';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../components/AuthCard';
import PasswordInput from '../components/PasswordInput';
import { FormField } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useForm } from '../hooks/useForm';
import { useSubmit } from '../hooks/useSubmit';
import { registerUser } from '../api/auth';
import { MIN_PASSWORD_LENGTH } from '../utils/constants';
import { toLocalDateInput } from '../utils/format';

const SEX_OPTIONS = ['Male', 'Female', 'Other'];

export default function Register() {
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const toast = useToast();

  const { values, handleChange } = useForm({
    full_name: '',
    email: '',
    password: '',
    date_of_birth: '',
    sex: '',
  });

  const { submit, submitting, error } = useSubmit(
    async () => {
      const email = values.email.trim();
      await registerUser({
        full_name: values.full_name.trim(),
        email,
        password: values.password,
        date_of_birth: values.date_of_birth || null,
        sex: values.sex || null,
      });

      // Log straight in so the patient lands on their dashboard.
      await signIn({ email, password: values.password });
      toast.success('Account created successfully!');
      navigate('/dashboard', { replace: true });
    },
    {
      fallback: 'Registration failed. Please check your details.',
      onError: (message) => toast.error(message),
    },
  );

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start tracking your blood pressure at home"
      maxWidth={480}
      footer={<>Already have an account? <Link to="/login" className="hs-link">Log in</Link></>}
    >
      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <Form onSubmit={submit} noValidate>
        <FormField
          id="register-name"
          label="Full name"
          name="full_name"
          value={values.full_name}
          onChange={handleChange}
          autoComplete="name"
          required
        />

        <FormField
          id="register-email"
          label="Email"
          type="email"
          name="email"
          value={values.email}
          onChange={handleChange}
          autoComplete="email"
          required
        />

        <FormField
          id="register-password"
          label="Password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <PasswordInput
            value={values.password}
            onChange={handleChange}
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
        </FormField>

        <Row className="mb-4">
          <Col>
            <FormField
              id="register-dob"
              label="Date of birth"
              className="mb-0"
              type="date"
              name="date_of_birth"
              value={values.date_of_birth}
              max={toLocalDateInput()}
              onChange={handleChange}
            />
          </Col>
          <Col>
            <FormField id="register-sex" label="Sex" className="mb-0">
              <Form.Select name="sex" value={values.sex} onChange={handleChange}>
                <option value="">Select…</option>
                {SEX_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </Form.Select>
            </FormField>
          </Col>
        </Row>

        <Button type="submit" className="btn-hs-primary w-100" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Register'}
        </Button>
      </Form>
    </AuthCard>
  );
}
