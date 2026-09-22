import { Form } from 'react-bootstrap';

const PERIOD_OPTIONS = [7, 14, 30, 90];

/** Period picker shared by the patient and clinician trend views. */
export default function PeriodSelect({ value, onChange, id = 'period-select' }) {
  return (
    <>
      <label className="visually-hidden" htmlFor={id}>Time period</label>
      <Form.Select
        id={id}
        style={{ width: 'auto' }}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        {PERIOD_OPTIONS.map((days) => (
          <option key={days} value={days}>Last {days} days</option>
        ))}
      </Form.Select>
    </>
  );
}
