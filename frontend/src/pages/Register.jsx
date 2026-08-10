import { useState } from 'react';
import { Container, Card, Form, Button, Alert, Row, Col } from 'react-bootstrap';
import { useNavigate, Link } from 'react-router-dom';
import { registerUser, loginUser, getCurrentUser } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { setTokens } from '../api/tokenStorage';

export default function Register() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'patient',
    date_of_birth: '',
    sex: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload = {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        role: form.role,
        ...(form.role === 'patient' && {
          date_of_birth: form.date_of_birth || null,
          sex: form.sex || null,
        }),
      };

      await registerUser(payload);

      const tokenData = await loginUser({ email: form.email, password: form.password });
      setTokens(tokenData);
      const userData = await getCurrentUser();
      login(tokenData, userData);
      navigate(userData.role === 'clinician' ? '/clinician' : '/dashboard');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Registration failed. Please check your details.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hs-auth-wrapper d-flex align-items-center justify-content-center py-5">
      <Container style={{ maxWidth: '480px' }}>
        <div className="hs-brand">
          <div className="hs-brand-icon">H</div>
          <span className="hs-brand-name">HyperSync</span>
        </div>

        <Card className="hs-auth-card p-4">
          <Card.Body>
            <h4 className="hs-title mb-1 text-center">Create your account</h4>
            <p className="hs-subtitle text-center mb-4">Start tracking your blood pressure at home</p>

            {error && <Alert variant="danger">{error}</Alert>}

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label className="hs-form-label">Full Name</Form.Label>
                <Form.Control
                  type="text"
                  name="full_name"
                  value={form.full_name}
                  onChange={handleChange}
                  required
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label className="hs-form-label">Email</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  required
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label className="hs-form-label">Password</Form.Label>
                <Form.Control
                  type="password"
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  minLength={8}
                  required
                />
                <Form.Text className="text-muted">At least 8 characters.</Form.Text>
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label className="hs-form-label">I am a...</Form.Label>
                <Form.Select name="role" value={form.role} onChange={handleChange}>
                  <option value="patient">Patient</option>
                  <option value="clinician">Clinician</option>
                </Form.Select>
              </Form.Group>

              {form.role === 'patient' && (
                <Row className="mb-3">
                  <Col>
                    <Form.Label className="hs-form-label">Date of Birth</Form.Label>
                    <Form.Control
                      type="date"
                      name="date_of_birth"
                      value={form.date_of_birth}
                      onChange={handleChange}
                    />
                  </Col>
                  <Col>
                    <Form.Label className="hs-form-label">Sex</Form.Label>
                    <Form.Select name="sex" value={form.sex} onChange={handleChange}>
                      <option value="">Select...</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                    </Form.Select>
                  </Col>
                </Row>
              )}

              <Button type="submit" className="btn-hs-primary w-100" disabled={loading}>
                {loading ? 'Creating account...' : 'Register'}
              </Button>
            </Form>

            <div className="text-center mt-4 hs-footer-text">
              Already have an account? <Link to="/login" className="hs-link">Log in</Link>
            </div>
          </Card.Body>
        </Card>
      </Container>
    </div>
  );
}