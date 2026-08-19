import { useState } from 'react';
import { Form, InputGroup, Button } from 'react-bootstrap';
import { Eye, EyeOff } from 'lucide-react';

export default function PasswordInput({ value, onChange, name = 'password', placeholder = '••••••••', required = false, minLength, autoComplete = 'current-password' }) {
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
        onClick={() => setVisible((v) => !v)}
        tabIndex={-1}
        style={{ borderColor: 'var(--hs-border)' }}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </Button>
    </InputGroup>
  );
}