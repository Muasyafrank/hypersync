import { useState, useEffect } from 'react';
import { Container, Form, Button, Alert, Spinner } from 'react-bootstrap';
import { Moon, Brain, Salad, Pill, Calendar, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import { createFactor, getMyFactors, deleteFactor } from '../api/factors';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';

const STRESS_OPTIONS = [
  { value: 'low', label: 'Low', color: '#16A34A' },
  { value: 'moderate', label: 'Moderate', color: '#CA8A04' },
  { value: 'high', label: 'High', color: '#DC2626' },
];

export default function Lifestyle() {
  const toast = useToast();
  const confirm = useConfirm();

  const [form, setForm] = useState({
    stress_level: '',
    sleep_hours: '',
    diet_adherence: null,
    medication_taken: null,
    logged_date: new Date().toISOString().slice(0, 10),
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [entries, setEntries] = useState([]);
  const [loadingEntries, setLoadingEntries] = useState(true);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoadingEntries(true);
    getMyFactors().then(setEntries).finally(() => setLoadingEntries(false));
  }

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function toggleBool(field) {
    setForm({ ...form, [field]: form[field] === true ? false : form[field] === false ? null : true });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await createFactor({
        stress_level: form.stress_level || null,
        sleep_hours: form.sleep_hours ? Number(form.sleep_hours) : null,
        diet_adherence: form.diet_adherence,
        medication_taken: form.medication_taken,
        logged_date: form.logged_date,
      });
      toast.success('Lifestyle entry saved.');
      setForm({ ...form, stress_level: '', sleep_hours: '', diet_adherence: null, medication_taken: null });
      load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not save entry.');
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id) {
    const confirmed = await confirm({
      title: 'Delete this entry?',
      message: 'This lifestyle log entry will be permanently removed.',
      confirmLabel: 'Delete',
      cancelLabel: 'Cancel',
      variant: 'danger',
    });
    if (!confirmed) return;
    await deleteFactor(id);
    toast.success('Entry deleted.');
    load();
  }

  function BoolPill({ value, onClick, label, icon }) {
    const bg = value === true ? '#DCFCE7' : value === false ? '#FEE2E2' : 'var(--hs-neu)';
    const text = value === true ? '#166534' : value === false ? '#991B1B' : '#64748B';
    const shadow = value === null
      ? 'inset 4px 4px 8px var(--hs-neu-dark-soft), inset -4px -4px 8px var(--hs-neu-light-soft)'
      : '3px 3px 8px var(--hs-neu-dark-soft), -3px -3px 8px var(--hs-neu-light-soft)';
    return (
      <button
        type="button"
        onClick={onClick}
        style={{
          border: 'none', borderRadius: 12, padding: '0.65rem 0.9rem', width: '100%',
          background: bg, color: text, fontWeight: 600, fontSize: '0.88rem',
          display: 'flex', alignItems: 'center', gap: 8, boxShadow: shadow, cursor: 'pointer',
        }}
      >
        {icon}
        {label}: {value === true ? 'Yes' : value === false ? 'No' : 'Not logged'}
      </button>
    );
  }

  return (
    <Layout>
      <Container fluid className="px-0" style={{ maxWidth: 900 }}>
        <h2 className="hs-title mb-1">Lifestyle &amp; environment</h2>
        <p className="hs-subtitle mb-4">Track stress, sleep, diet, and medication adherence alongside your readings.</p>

        <div className="row g-4">
          <div className="col-lg-6">
            <div className="hs-panel">
              <h5 className="hs-title mb-3">Log today's entry</h5>
              {error && <Alert variant="danger">{error}</Alert>}

              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label className="hs-form-label d-flex align-items-center gap-2">
                    <Calendar size={15} /> Date
                  </Form.Label>
                  <Form.Control type="date" name="logged_date" value={form.logged_date} onChange={handleChange} />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label className="hs-form-label d-flex align-items-center gap-2">
                    <Brain size={15} /> Stress level
                  </Form.Label>
                  <div className="d-flex gap-2">
                    {STRESS_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setForm({ ...form, stress_level: opt.value })}
                        style={{
                          flex: 1, border: 'none', borderRadius: 12, padding: '0.6rem',
                          background: form.stress_level === opt.value ? opt.color + '22' : 'var(--hs-neu)',
                          color: form.stress_level === opt.value ? opt.color : '#64748B',
                          fontWeight: 600, fontSize: '0.85rem',
                          boxShadow: form.stress_level === opt.value
                            ? 'inset 4px 4px 8px var(--hs-neu-dark-soft), inset -4px -4px 8px var(--hs-neu-light-soft)'
                            : '3px 3px 8px var(--hs-neu-dark-soft), -3px -3px 8px var(--hs-neu-light-soft)',
                          cursor: 'pointer',
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label className="hs-form-label d-flex align-items-center gap-2">
                    <Moon size={15} /> Sleep (hours)
                  </Form.Label>
                  <Form.Control
                    type="number"
                    name="sleep_hours"
                    value={form.sleep_hours}
                    onChange={handleChange}
                    min={0}
                    max={24}
                    step={0.5}
                    placeholder="e.g. 7.5"
                  />
                </Form.Group>

                <div className="row g-2 mb-4">
                  <div className="col-6">
                    <BoolPill
                      value={form.diet_adherence}
                      onClick={() => toggleBool('diet_adherence')}
                      label="Diet followed"
                      icon={<Salad size={15} />}
                    />
                  </div>
                  <div className="col-6">
                    <BoolPill
                      value={form.medication_taken}
                      onClick={() => toggleBool('medication_taken')}
                      label="Medication taken"
                      icon={<Pill size={15} />}
                    />
                  </div>
                </div>

                <Button type="submit" className="btn-hs-primary w-100" disabled={loading}>
                  {loading ? 'Saving...' : 'Save entry'}
                </Button>
              </Form>
            </div>
          </div>

          <div className="col-lg-6">
            <div className="hs-panel">
              <h5 className="hs-title mb-3">Recent entries</h5>
              {loadingEntries ? (
                <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
              ) : entries.length === 0 ? (
                <p className="hs-subtitle">No entries logged yet.</p>
              ) : (
                entries.map((e) => {
                  const stressOpt = STRESS_OPTIONS.find((s) => s.value === e.stress_level);
                  return (
                    <div key={e.factor_id} className="hs-reading-row">
                      <div>
                        <div style={{ fontWeight: 700, color: 'var(--hs-navy)', fontSize: '0.9rem' }}>
                          {new Date(e.logged_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                        </div>
                        <div className="d-flex gap-3 mt-1" style={{ fontSize: '0.8rem', color: '#64748B' }}>
                          {stressOpt && <span style={{ color: stressOpt.color, fontWeight: 600 }}>{stressOpt.label} stress</span>}
                          {e.sleep_hours != null && <span>{e.sleep_hours}h sleep</span>}
                          {e.diet_adherence != null && <span>{e.diet_adherence ? '✓' : '✗'} diet</span>}
                          {e.medication_taken != null && <span>{e.medication_taken ? '✓' : '✗'} meds</span>}
                        </div>
                      </div>
                      <Trash2 size={17} color="#94A3B8" style={{ cursor: 'pointer' }} onClick={() => handleDelete(e.factor_id)} />
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </Container>
    </Layout>
  );
}