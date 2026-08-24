import { useState, useMemo } from 'react';
import { Container, Form, Button, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Info, HeartPulse, Activity, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';
import { createReading } from '../api/readings';
import { useToast } from '../context/ToastContext';
import { statusInfo, classifyBP } from '../utils/statusColors';

function toLocalDateTimeInputValue(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function LogReading() {
  const navigate = useNavigate();
  const toast = useToast();

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

  const liveStatus = useMemo(
    () => classifyBP(Number(form.systolic) || null, Number(form.diastolic) || null),
    [form.systolic, form.diastolic]
  );
  const liveInfo = liveStatus ? statusInfo(liveStatus) : null;

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    const sys = Number(form.systolic);
    const dia = Number(form.diastolic);

    if (dia >= sys) {
      setError('Diastolic must be lower than systolic.');
      return;
    }
    if (sys < 60 || sys > 260) {
      setError('Systolic must be between 60 and 260 mmHg.');
      return;
    }
    if (dia < 30 || dia > 180) {
      setError('Diastolic must be between 30 and 180 mmHg.');
      return;
    }
    if (form.heart_rate && (Number(form.heart_rate) < 30 || Number(form.heart_rate) > 220)) {
      setError('Heart rate must be between 30 and 220 bpm.');
      return;
    }

    setLoading(true);
    try {
      const created = await createReading({
        systolic: sys,
        diastolic: dia,
        heart_rate: form.heart_rate ? Number(form.heart_rate) : null,
        recorded_at: new Date(form.recorded_at).toISOString(),
        notes: form.notes || null,
        source: 'manual',
      });
      toast.success(`Reading saved — ${statusInfo(created.status).label} status recorded.`);
      navigate('/readings');
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : detail || 'Could not save reading.';
      toast.error(message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0" style={{ maxWidth: 820 }}>
        <div className="d-flex align-items-center gap-3 mb-1">
          <ArrowLeft size={20} style={{ cursor: 'pointer', color: 'var(--hs-navy)' }} onClick={() => navigate(-1)} />
          <h2 className="hs-title mb-0">Log new reading</h2>
        </div>
        <p className="hs-subtitle mb-4">Enter your latest blood pressure measurement.</p>

        <div className="row g-4">
          {/* Left: form */}
          <div className="col-lg-7">
            <div className="hs-tips-box">
              <div className="hs-tips-title"><Info size={16} /> Measurement tips</div>
              <ul className="mb-0" style={{ fontSize: '0.88rem', color: '#475569', paddingLeft: '1.2rem' }}>
                <li>Rest for 5 minutes before taking a reading</li>
                <li>Sit comfortably with your back supported</li>
                <li>Keep your arm at heart level</li>
              </ul>
            </div>

            {error && <Alert variant="danger">{error}</Alert>}

            <Form onSubmit={handleSubmit}>
              <div className="row g-3 mb-3">
                <div className="col-6">
                  <div
                    className="hs-input-box"
                    style={liveInfo ? { boxShadow: `inset 5px 5px 10px ${liveInfo.accent}33, inset -5px -5px 10px var(--hs-neu-light)` } : {}}
                  >
                    <div className="hs-input-box-label"><HeartPulse size={16} color="#DC2626" /> Systolic</div>
                    <div className="d-flex align-items-center justify-content-between">
                      <Form.Control
                        // type="number"
                        name="systolic"
                        value={form.systolic}
                        onChange={handleChange}
                        min={60}
                        max={260}
                        required
                        style={{ border: 'none', background: 'transparent', fontSize: '1.6rem', fontWeight: 700, padding: 0, boxShadow: 'none', color: 'var(--hs-navy)' }}
                      />
                      <span style={{ color: '#94A3B8', fontSize: '0.8rem' }}>mmHg</span>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.3rem' }}>60–260</div>
                </div>

                <div className="col-6">
                  <div
                    className="hs-input-box"
                    style={liveInfo ? { borderColor: liveInfo.accent, backgroundColor: liveInfo.bg + '55' } : {}}
                  >
                    <div className="hs-input-box-label"><HeartPulse size={16} color="#2563EB" /> Diastolic</div>
                    <div className="d-flex align-items-center justify-content-between">
                      <Form.Control
                        // type="number"
                        name="diastolic"
                        value={form.diastolic}
                        onChange={handleChange}
                        min={30}
                        max={180}
                        required
                        style={{ border: 'none', background: 'transparent', fontSize: '1.6rem', fontWeight: 700, padding: 0, boxShadow: 'none', color: 'var(--hs-navy)' }}
                      />
                      <span style={{ color: '#94A3B8', fontSize: '0.8rem' }}>mmHg</span>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.3rem' }}>30–180</div>
                </div>
              </div>

              <div className="row g-3 mb-3">
                <div className="col-6">
                  <div className="hs-input-box">
                    <div className="hs-input-box-label"><Activity size={16} color="#EA580C" /> Pulse (optional)</div>
                    <div className="d-flex align-items-center justify-content-between">
                      <Form.Control
                        // type="number"
                        name="heart_rate"
                        value={form.heart_rate}
                        onChange={handleChange}
                        min={30}
                        max={220}
                        style={{ border: 'none', background: 'transparent', fontSize: '1.6rem', fontWeight: 700, padding: 0, boxShadow: 'none', color: 'var(--hs-navy)' }}
                      />
                      <span style={{ color: '#94A3B8', fontSize: '0.8rem' }}>bpm</span>
                    </div>
                  </div>
                </div>

                <div className="col-6">
                  <Form.Label className="hs-form-label">Date &amp; time</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    name="recorded_at"
                    value={form.recorded_at}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <Form.Group className="mb-4">
                <Form.Label className="hs-form-label">Notes (optional)</Form.Label>
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
                  {loading ? 'Saving...' : 'Save reading'}
                </Button>
              </div>
            </Form>
          </div>

          {/* Right: live preview */}
          <div className="col-lg-5">
            <div className="hs-preview-card">
              <div className="d-flex align-items-center gap-2 mb-3">
                <Sparkles size={16} color="var(--hs-teal)" />
                <span style={{ fontWeight: 600, color: 'var(--hs-navy)', fontSize: '0.92rem' }}>Live preview</span>
              </div>

              {form.systolic && form.diastolic ? (
                <>
                  <div className="hs-preview-number">
                    {form.systolic}<span className="hs-preview-slash">/</span>{form.diastolic}
                    <span className="hs-preview-unit">mmHg</span>
                  </div>
                  {liveInfo && (
                    <span
                      className="hs-preview-badge"
                      style={{ backgroundColor: liveInfo.bg, color: liveInfo.text }}
                    >
                      {liveInfo.label}
                    </span>
                  )}
                  <p className="hs-preview-note">
                    {liveStatus === 'high' && "This reading is high. Consider contacting your clinician if it's persistent."}
                    {liveStatus === 'elevated' && 'This reading is a little elevated — worth keeping an eye on.'}
                    {liveStatus === 'controlled' && "This reading is within a healthy, controlled range."}
                    {liveStatus === 'low' && 'This reading is on the low side. Note how you feel alongside it.'}
                  </p>
                </>
              ) : (
                <p className="hs-preview-empty">Start entering your systolic and diastolic values to see a live classification here.</p>
              )}

              <div className="hs-preview-scale">
                <div className="hs-preview-scale-track">
                  <span style={{ background: '#2563EB' }} />
                  <span style={{ background: '#16A34A' }} />
                  <span style={{ background: '#EAB308' }} />
                  <span style={{ background: '#DC2626' }} />
                </div>
                <div className="d-flex justify-content-between" style={{ fontSize: '0.7rem', color: '#94A3B8' }}>
                  <span>Low</span><span>Controlled</span><span>Elevated</span><span>High</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Container>
    </Layout>
  );
}