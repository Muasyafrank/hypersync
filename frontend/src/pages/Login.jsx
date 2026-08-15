import { useState } from 'react';
import { Container, Card, Form, Button, Alert, Toast } from 'react-bootstrap';
import { useNavigate, Link } from 'react-router-dom';
import { loginUser, getCurrentUser } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { setTokens } from '../api/tokenStorage';
import { useToast } from '../context/ToastContext';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const toast = useToast();

  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }
  function roleHome(role) {
    if (role === 'admin') return '/admin';
    if (role === 'clinician') return '/clinician';
    return '/dashboard';
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const tokenData = await loginUser(form);
      setTokens(tokenData);
      const userData = await getCurrentUser();
      login(tokenData, userData);
      toast.success(`Welcome back, ${userData.full_name}!`);
      navigate(roleHome(userData.role))
    } catch (err) {
      toast.error('Incorrect email or password.');
      setError('Incorrect email or password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hs-auth-wrapper d-flex align-items-center justify-content-center">
      <Container style={{ maxWidth: '420px' }}>
        <div className="hs-brand">
          <div className="hs-brand-icon">H</div>
          <span className="hs-brand-name">HyperSync</span>
        </div>

        <Card className="hs-auth-card p-4">
          <Card.Body>
            <h4 className="hs-title mb-1 text-center">Welcome back</h4>
            <p className="hs-subtitle text-center mb-4">Log in to continue monitoring your blood pressure</p>

            {error && <Alert variant="danger">{error}</Alert>}

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label className="hs-form-label">Email</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  required
                />
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label className="hs-form-label">Password</Form.Label>
                <Form.Control
                  type="password"
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  required
                />
              </Form.Group>

              <Button type="submit" className="btn-hs-primary w-100" disabled={loading}>
                {loading ? 'Logging in...' : 'Log In'}
              </Button>
            </Form>

            <div className="text-center mt-4 hs-footer-text">
              Don't have an account? <Link to="/register" className="hs-link">Register</Link>
            </div>
          </Card.Body>
        </Card>
      </Container>
    </div>
  );
}