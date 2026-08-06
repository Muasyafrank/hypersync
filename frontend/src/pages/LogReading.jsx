import { useState } from 'react';
import { Container, Form, Button, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Info, Heart, Activity } from 'lucide-react';
import Layout from '../components/Layout';
import { createReading } from '../api/readings';

function toLocalDateTimeInputValue(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function LogReading() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    systolic: '',
    diastolic: '',
    heart_rate: '',
    recorded_at: toLocalDateTimeInputValue(new Date()),
    notes: '',
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
      await createReading({
        systolic: Number(form.systolic),
        diastolic: Number(form.diastolic),
        heart_rate: form.heart_rate ? Number(form.heart_rate) : null,
        recorded_at: new Date(form.recorded_at).toISOString(),
        notes: form.notes || null,
        source: 'manual',
      });
      navigate('/readings');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : detail || 'Could not save reading.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0" style={{ maxWidth: 760 }}>
        <div className="d-flex align-items-center gap-3 mb-1">
          <ArrowLeft size={20} style={{ cursor: 'pointer', color: 'var(--hs-navy)' }} onClick={() => navigate(-1)} />
          <h2 className="hs-title mb-0">Log New Reading</h2>
        </div>
        <p className="hs-subtitle mb-4">Enter your latest blood pressure measurement.</p>

        <div className="hs-tips-box">
          <div className="hs-tips-title"><Info size={16} /> Measurement Tips</div>
          <ul className="mb-0" style={{ fontSize: '0.88rem', color: '#475569', paddingLeft: '1.2rem' }}>
            <li>Rest for 5 minutes before taking a reading</li>
            <li>Sit comfortably with your back supported</li>
            <li>Keep your arm at heart level</li>
          </ul>
        </div>

        {error && <Alert variant="danger">{error}</Alert>}

        <Form onSubmit={handleSubmit}>
          <div className="row g-3 mb-3">
            <div className="col-md-6">
              <div className="hs-input-box">
                <div className="hs-input-box-label"><Heart size={16} color="#DC2626" fill="#DC2626" /> Systolic</div>
                <div className="d-flex align-items-center justify-content-between">
                  <Form.Control
                    type="number"
                    name="systolic"
                    value={form.systolic}
                    onChange={handleChange}
                    min={60}
                    max={300}
                    required
                    style={{ border: 'none', fontSize: '1.3rem', fontWeight: 600, padding: 0, boxShadow: 'none' }}
                  />
                  <span style={{ color: '#94A3B8', fontSize: '0.85rem' }}>mmHg</span>
                </div>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#94A3B8', marginTop: '0.35rem' }}>Top number (60-300)</div>
            </div>

            <div className="col-md-6">
              <div className="hs-input-box">
                <div className="hs-input-box-label"><Heart size={16} color="#2563EB" fill="#2563EB" /> Diastolic</div>
                <div className="d-flex align-items-center justify-content-between">
                  <Form.Control
                    type="number"
                    name="diastolic"
                    value={form.diastolic}
                    onChange={handleChange}
                    min={40}
                    max={200}
                    required
                    style={{ border: 'none', fontSize: '1.3rem', fontWeight: 600, padding: 0, boxShadow: 'none' }}
                  />
                  <span style={{ color: '#94A3B8', fontSize: '0.85rem' }}>mmHg</span>
                </div>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#94A3B8', marginTop: '0.35rem' }}>Bottom number (40-200)</div>
            </div>
          </div>

          <div className="row g-3 mb-3">
            <div className="col-md-6">
              <div className="hs-input-box">
                <div className="hs-input-box-label"><Activity size={16} color="#EA580C" /> Pulse (Optional)</div>
                <div className="d-flex align-items-center justify-content-between">
                  <Form.Control
                    type="number"
                    name="heart_rate"
                    value={form.heart_rate}
                    onChange={handleChange}
                    min={1}
                    max={249}
                    style={{ border: 'none', fontSize: '1.3rem', fontWeight: 600, padding: 0, boxShadow: 'none' }}
                  />
                  <span style={{ color: '#94A3B8', fontSize: '0.85rem' }}>bpm</span>
                </div>
              </div>
            </div>

            <div className="col-md-6">
              <Form.Label className="hs-form-label">Date &amp; Time</Form.Label>
              <Form.Control
                type="datetime-local"
                name="recorded_at"
                value={form.recorded_at}
                onChange={handleChange}
              />
            </div>
          </div>

          <Form.Group className="mb-4">
            <Form.Label className="hs-form-label">Notes (Optional)</Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              name="notes"
              value={form.notes}
              onChange={handleChange}
              placeholder="How are you feeling? Did you take medication?"
            />
          </Form.Group>

          <div className="d-flex justify-content-end gap-2">
            <Button variant="outline-secondary" onClick={() => navigate(-1)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="btn-hs-primary" disabled={loading}>
              {loading ? 'Saving...' : 'Save Reading'}
            </Button>
          </div>
        </Form>
      </Container>
    </Layout>
  );
}