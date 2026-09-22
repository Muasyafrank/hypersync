import { Card, Container } from 'react-bootstrap';
import logoMark from '../assets/logo-mark.svg';

/** Shared shell for the login and registration screens. */
export default function AuthCard({ title, subtitle, maxWidth = 420, children, footer }) {
  return (
    <div className="hs-auth-wrapper d-flex align-items-center justify-content-center py-5">
      <Container style={{ maxWidth }}>
        <div className="hs-brand">
          <img src={logoMark} alt="HyperSync" width={44} height={44} className="hs-brand-mark" />
          <span className="hs-brand-name">HyperSync</span>
        </div>

        <Card className="hs-auth-card p-4">
          <Card.Body>
            <h4 className="hs-title mb-1 text-center">{title}</h4>
            {subtitle && <p className="hs-subtitle text-center mb-4">{subtitle}</p>}
            {children}
            {footer && <div className="text-center mt-4 hs-footer-text">{footer}</div>}
          </Card.Body>
        </Card>
      </Container>
    </div>
  );
}
