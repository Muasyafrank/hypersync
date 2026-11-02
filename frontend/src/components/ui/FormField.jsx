import { Form } from 'react-bootstrap';

/**
 * Label + control + optional hint, wired together by `id`.
 *
 * With no children it renders a plain <Form.Control> and forwards the rest of
 * its props to it (type, name, value, onChange, required…). Pass children for
 * anything else — a <Form.Select>, a <PasswordInput>.
 */
export default function FormField({ id, label, hint, className = 'mb-3', children, ...controlProps }) {
  return (
    <Form.Group className={className} controlId={id}>
      <Form.Label className="hs-form-label">{label}</Form.Label>
      {children ?? <Form.Control {...controlProps} />}
      {hint && <Form.Text className="text-muted">{hint}</Form.Text>}
    </Form.Group>
  );
}
