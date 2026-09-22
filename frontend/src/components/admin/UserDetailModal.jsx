import { Button, Col, Modal, Row } from 'react-bootstrap';
import { Loader, RoleBadge } from '../ui';
import { formatFullDate } from '../../utils/format';

function DetailRow({ label, children }) {
  return (
    <Row className="mb-2">
      <Col xs={5} className="hs-subtitle">{label}</Col>
      <Col>{children}</Col>
    </Row>
  );
}

export default function UserDetailModal({ user, loading, onHide }) {
  return (
    <Modal show={Boolean(user)} onHide={onHide} centered>
      <Modal.Body className="p-4">
        <h5 className="hs-title mb-3">User details</h5>

        {loading ? (
          <Loader className="py-3" />
        ) : user && (
          <div>
            <DetailRow label="Full name"><span className="hs-reading-value">{user.full_name}</span></DetailRow>
            <DetailRow label="Email">{user.email}</DetailRow>
            <DetailRow label="Role"><RoleBadge role={user.role} /></DetailRow>
            <DetailRow label="Joined">{formatFullDate(user.created_at, '—')}</DetailRow>
            {user.role === 'patient' && (
              <>
                <DetailRow label="Date of birth">{user.date_of_birth || '—'}</DetailRow>
                <DetailRow label="Sex">{user.sex || '—'}</DetailRow>
                <DetailRow label="Readings logged">{user.reading_count ?? 0}</DetailRow>
              </>
            )}
          </div>
        )}

        <div className="d-flex justify-content-end mt-3">
          <Button variant="outline-secondary" onClick={onHide}>Close</Button>
        </div>
      </Modal.Body>
    </Modal>
  );
}
