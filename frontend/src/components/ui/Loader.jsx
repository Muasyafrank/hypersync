import { Spinner } from 'react-bootstrap';

/** Centred loading spinner in the app's accent colour. */
export default function Loader({ size, className = 'py-4', label = 'Loading' }) {
  return (
    <div className={`text-center ${className}`}>
      <Spinner animation="border" size={size} role="status" style={{ color: 'var(--hs-teal)' }}>
        <span className="visually-hidden">{label}</span>
      </Spinner>
    </div>
  );
}
