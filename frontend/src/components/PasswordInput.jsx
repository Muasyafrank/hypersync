import { useState } from 'react';
import { Button, Form, InputGroup } from 'react-bootstrap';
import { Eye, EyeOff } from 'lucide-react';

/** Password field with a show/hide toggle. Must sit inside a <FormField> (or Form.Group). */
export default function PasswordInput({
  value,
  onChange,
  name = 'password',
  placeholder = '••••••••',
  required = false,
  minLength,
  autoComplete = 'current-password',
}) {
  const [visible, setVisible] = useState(false);

  return (
    <InputGroup>
      <Form.Control
        type={visible ? 'text' : 'password'}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
      />
      <Button
        variant="outline-secondary"
        className="hs-password-toggle"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </Button>
    </InputGroup>
  );
}
