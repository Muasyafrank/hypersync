import { useState, useEffect } from 'react';
import { Container, Card, Form, Button, Alert, Row, Col, Table, Navbar } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { createReading, getMyReadings } from '../api/readings';
import { useAuth } from '../context/AuthContext';
import StatusBadge from '../components/StatusBadge';

export default function Readings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    systolic: '',
    diastolic: '',
    heart_rate: '',
    recorded_at: '',
    source: 'manual',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [readings, setReadings] = useState([]);
  const [loadingReadings, setLoadingReadings] = useState(true);

  useEffect(() => {
    loadReadings();
  }, []);

  async function loadReadings() {
    setLoadingReadings(true);
    try {
      const data = await getMyReadings();
      setReadings(data);
    } catch (err) {
      setError('Could not load your readings.');
    } finally {
      setLoadingReadings(false);
    }
  }

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const payload = {
        systolic: Number(form.systolic),
        diastolic: Number(form.diastolic),
        heart_rate: form.heart_rate ? Number(form.heart_rate) : null,
        recorded_at: form.recorded_at ? new Date(form.recorded_at).toISOString() : null,
        source: form.source,
      };

      const created = await createReading(payload);
      setSuccess(`Reading saved  status: ${created.status}`);
      setForm({ systolic: '', diastolic: '', heart_rate: '', recorded_at: '', source: 'manual' });
      loadReadings();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || 'Could not save reading. Please check your values.'
      );
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div style={{ backgroundColor: 'var(--hs-bg)', minHeight: '100vh' }}>
<Navbar className="hs-navbar" variant="dark" expand="lg">
  <Container>
    <Navbar.Brand className="hs-brand-name">HyperSync</Navbar.Brand>
    <div className="d-flex gap-2">
      <Button variant="outline-light" size="sm" onClick={() => navigate('/trend')}>
        View Trend
      </Button>
      <Button variant="outline-light" size="sm" onClick={handleLogout}>
        Log out
      </Button>
    </div>
  </Container>
</Navbar>

      <Container className="py-5">
        <h3 className="hs-title mb-1">Blood Pressure Readings</h3>
        <p className="hs-subtitle mb-4">Log a new reading and view your recent history</p>

        <Row className="g-4">
          <Col md={5}>
            <Card className="hs-auth-card p-4">
              <Card.Body>
                <h5 className="hs-title mb-3">Log a Reading</h5>

                {error && <Alert variant="danger">{error}</Alert>}
                {success && <Alert variant="success">{success}</Alert>}

                <Form onSubmit={handleSubmit}>
                  <Row>
                    <Col>
                      <Form.Group className="mb-3">
                        <Form.Label className="hs-form-label">Systolic (mmHg)</Form.Label>
                        <Form.Control
                          type="number"
                          name="systolic"
                          value={form.systolic}
                          onChange={handleChange}
                          min={1}
                          max={299}
                          required
                        />
                      </Form.Group>
                    </Col>
                    <Col>
                      <Form.Group className="mb-3">
                        <Form.Label className="hs-form-label">Diastolic (mmHg)</Form.Label>
                        <Form.Control
                          type="number"
                          name="diastolic"
                          value={form.diastolic}
                          onChange={handleChange}
                          min={1}
                          max={199}
                          required
                        />
                      </Form.Group>
                    </Col>
                  </Row>

                  <Form.Group className="mb-3">
                    <Form.Label className="hs-form-label">Heart Rate (bpm)</Form.Label>
                    <Form.Control
                      type="number"
                      name="heart_rate"
                      value={form.heart_rate}
                      onChange={handleChange}
                      min={1}
                      max={249}
                      placeholder="Optional"
                    />
                  </Form.Group>

                  <Form.Group className="mb-3">
                    <Form.Label className="hs-form-label">Date &amp; Time</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      name="recorded_at"
                      value={form.recorded_at}
                      onChange={handleChange}
                    />
                    <Form.Text className="text-muted">Leave blank to use the current time.</Form.Text>
                  </Form.Group>

                  <Form.Group className="mb-4">
                    <Form.Label className="hs-form-label">Source</Form.Label>
                    <Form.Select name="source" value={form.source} onChange={handleChange}>
                      <option value="manual">Manual Entry</option>
                      <option value="device">BP Monitor Device</option>
                    </Form.Select>
                  </Form.Group>

                  <Button type="submit" className="btn-hs-primary w-100" disabled={loading}>
                    {loading ? 'Saving...' : 'Save Reading'}
                  </Button>
                </Form>
              </Card.Body>
            </Card>
          </Col>

          <Col md={7}>
            <Card className="hs-auth-card p-4">
              <Card.Body>
                <h5 className="hs-title mb-3">Recent Readings</h5>

                {loadingReadings ? (
                  <p className="hs-subtitle">Loading...</p>
                ) : readings.length === 0 ? (
                  <p className="hs-subtitle">No readings logged yet. Add your first one to get started.</p>
                ) : (
                  <Table hover responsive className="align-middle">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Systolic</th>
                        <th>Diastolic</th>
                        <th>Heart Rate</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {readings.map((r) => (
                        <tr key={r.reading_id}>
                          <td>{new Date(r.recorded_at).toLocaleString()}</td>
                          <td>{r.systolic}</td>
                          <td>{r.diastolic}</td>
                          <td>{r.heart_rate ?? '—'}</td>
                          <td><StatusBadge status={r.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Container>
    </div>
  );
}