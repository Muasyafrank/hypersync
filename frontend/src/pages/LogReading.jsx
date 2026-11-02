import { useMemo } from 'react';
import { Alert, Button, Container, Form } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Activity, HeartPulse, Info, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';
import { PageHeader } from '../components/ui';
import { useForm } from '../hooks/useForm';
import { useSubmit } from '../hooks/useSubmit';
import { useToast } from '../context/ToastContext';
import { createReading } from '../api/readings';
import { classifyBP, statusInfo, STATUS_NOTES } from '../utils/bpStatus';
import { toLocalDateTimeInput } from '../utils/format';

// Mirrors the Field(ge=…, le=…) constraints in backend/app/schemas/reading.py.
const LIMITS = {
  systolic: { min: 60, max: 260, label: 'Systolic', unit: 'mmHg' },
  diastolic: { min: 30, max: 180, label: 'Diastolic', unit: 'mmHg' },
  heart_rate: { min: 30, max: 220, label: 'Heart rate', unit: 'bpm' },
};

const SCALE = [
  { label: 'Low', color: '#2563EB' },
  { label: 'Controlled', color: '#16A34A' },
  { label: 'Elevated', color: '#EAB308' },
  { label: 'High', color: '#DC2626' },
];

/** Returns an error string, or null when the values are acceptable. */
function validate({ systolic, diastolic, heart_rate: heartRate }) {
  const sys = Number(systolic);
  const dia = Number(diastolic);
  const pulse = heartRate ? Number(heartRate) : null;

  if (!Number.isFinite(sys) || !Number.isFinite(dia)) return 'Enter both systolic and diastolic values.';
  if (sys < LIMITS.systolic.min || sys > LIMITS.systolic.max) {
    return `Systolic must be between ${LIMITS.systolic.min} and ${LIMITS.systolic.max} mmHg.`;
  }
  if (dia < LIMITS.diastolic.min || dia > LIMITS.diastolic.max) {
    return `Diastolic must be between ${LIMITS.diastolic.min} and ${LIMITS.diastolic.max} mmHg.`;
  }
  if (dia >= sys) return 'Diastolic must be lower than systolic.';
  if (pulse !== null && (pulse < LIMITS.heart_rate.min || pulse > LIMITS.heart_rate.max)) {
    return `Heart rate must be between ${LIMITS.heart_rate.min} and ${LIMITS.heart_rate.max} bpm.`;
  }
  return null;
}

/** Large numeric field used for the three measurement inputs. */
function MeasurementInput({ id, name, label, icon: Icon, iconColor, unit, value, onChange, limits, required, style }) {
  return (
    <>
      <div className="hs-input-box" style={style}>
        <label className="hs-input-box-label" htmlFor={id}>
          <Icon size={16} color={iconColor} /> {label}
        </label>
        <div className="d-flex align-items-center justify-content-between">
          <Form.Control
            id={id}
            type="number"
            inputMode="numeric"
            name={name}
            value={value}
            onChange={onChange}
            min={limits.min}
            max={limits.max}
            required={required}
            className="hs-measurement-input"
          />
          <span className="hs-reading-unit">{unit}</span>
        </div>
      </div>
      <div className="hs-input-hint">{limits.min}–{limits.max}</div>
    </>
  );
}

export default function LogReading() {
  const navigate = useNavigate();
  const toast = useToast();

  const { values, handleChange } = useForm({
    systolic: '',
    diastolic: '',
    heart_rate: '',
    recorded_at: toLocalDateTimeInput(),
    notes: '',
  });

  const { submit, submitting, error, setError } = useSubmit(
    async () => {
      const validationError = validate(values);
      if (validationError) {
        setError(validationError);
        return;
      }

      const created = await createReading({
        systolic: Number(values.systolic),
        diastolic: Number(values.diastolic),
        heart_rate: values.heart_rate ? Number(values.heart_rate) : null,
        recorded_at: new Date(values.recorded_at).toISOString(),
        notes: values.notes.trim() || null,
      });
      toast.success(`Reading saved — ${statusInfo(created.status).label} status recorded.`);
      navigate('/readings');
    },
    { fallback: 'Could not save reading.', onError: (message) => toast.error(message) },
  );

  const liveStatus = useMemo(
    () => classifyBP(Number(values.systolic) || null, Number(values.diastolic) || null),
    [values.systolic, values.diastolic],
  );
  const liveInfo = liveStatus ? statusInfo(liveStatus) : null;

  return (
    <Layout>
      <Container fluid className="px-0 hs-page-wide">
        <PageHeader
          title="Log new reading"
          subtitle="Enter your latest blood pressure measurement."
          onBack={() => navigate(-1)}
        />

        <div className="row g-4">
          <div className="col-lg-7">
            <div className="hs-tips-box">
              <div className="hs-tips-title"><Info size={16} /> Measurement tips</div>
              <ul className="hs-tips-list mb-0">
                <li>Rest for 5 minutes before taking a reading</li>
                <li>Sit comfortably with your back supported</li>
                <li>Keep your arm at heart level</li>
              </ul>
            </div>

            {error && <Alert variant="danger" role="alert">{error}</Alert>}

            <Form onSubmit={submit} noValidate>
              <div className="row g-3 mb-3">
                <div className="col-6">
                  <MeasurementInput
                    id="systolic"
                    name="systolic"
                    label="Systolic"
                    icon={HeartPulse}
                    iconColor="#DC2626"
                    unit="mmHg"
                    value={values.systolic}
                    onChange={handleChange}
                    limits={LIMITS.systolic}
                    required
                    style={liveInfo ? { borderColor: liveInfo.accent } : undefined}
                  />
                </div>
                <div className="col-6">
                  <MeasurementInput
                    id="diastolic"
                    name="diastolic"
                    label="Diastolic"
                    icon={HeartPulse}
                    iconColor="#2563EB"
                    unit="mmHg"
                    value={values.diastolic}
                    onChange={handleChange}
                    limits={LIMITS.diastolic}
                    required
                    style={liveInfo ? { borderColor: liveInfo.accent, backgroundColor: `${liveInfo.bg}55` } : undefined}
                  />
                </div>
              </div>

              <div className="row g-3 mb-3">
                <div className="col-6">
                  <MeasurementInput
                    id="heart_rate"
                    name="heart_rate"
                    label="Pulse (optional)"
                    icon={Activity}
                    iconColor="#EA580C"
                    unit="bpm"
                    value={values.heart_rate}
                    onChange={handleChange}
                    limits={LIMITS.heart_rate}
                  />
                </div>
                <div className="col-6">
                  <Form.Label className="hs-form-label" htmlFor="recorded_at">Date &amp; time</Form.Label>
                  <Form.Control
                    id="recorded_at"
                    type="datetime-local"
                    name="recorded_at"
                    value={values.recorded_at}
                    max={toLocalDateTimeInput()}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <Form.Group className="mb-4" controlId="notes">
                <Form.Label className="hs-form-label">Notes (optional)</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={3}
                  name="notes"
                  value={values.notes}
                  onChange={handleChange}
                  maxLength={1000}
                  placeholder="How are you feeling? Did you take medication?"
                />
              </Form.Group>

              <div className="d-flex justify-content-end gap-2">
                <Button variant="outline-secondary" onClick={() => navigate(-1)} disabled={submitting}>
                  Cancel
                </Button>
                <Button type="submit" className="btn-hs-primary" disabled={submitting}>
                  {submitting ? 'Saving…' : 'Save reading'}
                </Button>
              </div>
            </Form>
          </div>

          <div className="col-lg-5">
            <aside className="hs-preview-card" aria-live="polite">
              <div className="d-flex align-items-center gap-2 mb-3">
                <Sparkles size={16} color="var(--hs-teal)" />
                <span className="hs-preview-heading">Live preview</span>
              </div>

              {values.systolic && values.diastolic ? (
                <>
                  <div className="hs-preview-number">
                    {values.systolic}<span className="hs-preview-slash">/</span>{values.diastolic}
                    <span className="hs-preview-unit">mmHg</span>
                  </div>
                  {liveInfo && (
                    <span className="hs-preview-badge" style={{ backgroundColor: liveInfo.bg, color: liveInfo.text }}>
                      {liveInfo.label}
                    </span>
                  )}
                  <p className="hs-preview-note">{STATUS_NOTES[liveStatus]}</p>
                </>
              ) : (
                <p className="hs-preview-empty">
                  Start entering your systolic and diastolic values to see a live classification here.
                </p>
              )}

              <div className="hs-preview-scale">
                <div className="hs-preview-scale-track">
                  {SCALE.map((band) => (
                    <span key={band.label} style={{ background: band.color }} />
                  ))}
                </div>
                <div className="d-flex justify-content-between hs-preview-scale-labels">
                  {SCALE.map((band) => <span key={band.label}>{band.label}</span>)}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </Container>
    </Layout>
  );
}
