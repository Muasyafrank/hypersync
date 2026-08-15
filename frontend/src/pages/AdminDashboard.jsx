import { useState, useEffect } from 'react';
import { Container, Row, Col, Spinner, Form, Button, Modal, Alert } from 'react-bootstrap';
import { Users, UserCog, Plus, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import { getAllUsers, createClinician, deleteUser } from '../api/admin';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { useAuth } from '../context/AuthContext';

export default function AdminDashboard() {
  const { user: currentUser } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ full_name: '', email: '', password: '' });
  const [formError, setFormError] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    getAllUsers()
      .then(setUsers)
      .catch(() => toast.error('Could not load users.'))
      .finally(() => setLoading(false));
  }

  function handleFormChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleCreateClinician(e) {
    e.preventDefault();
    setFormError('');
    setCreating(true);
    try {
      await createClinician(form);
      toast.success(`Clinician account created for ${form.full_name}.`);
      setForm({ full_name: '', email: '', password: '' });
      setShowModal(false);
      load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setFormError(typeof detail === 'string' ? detail : 'Could not create clinician account.');
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(u) {
    const confirmed = await confirm({
      title: `Delete ${u.full_name}?`,
      message: `This will permanently remove this ${u.role} account and all associated data. This cannot be undone.`,
      confirmLabel: 'Delete',
      cancelLabel: 'Cancel',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await deleteUser(u.user_id);
      toast.success('Account deleted.');
      load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not delete account.');
    }
  }

  const patientCount = users.filter((u) => u.role === 'patient').length;
  const clinicianCount = users.filter((u) => u.role === 'clinician').length;
  const adminCount = users.filter((u) => u.role === 'admin').length;

  const roleBadge = (role) => {
    const styles = {
      patient: { bg: '#DCFCE7', text: '#166534' },
      clinician: { bg: '#DBEAFE', text: '#1E40AF' },
      admin: { bg: '#FEF9C3', text: '#854D0E' },
    };
    const s = styles[role] || { bg: '#F1F5F9', text: '#64748B' };
    return (
      <span style={{ backgroundColor: s.bg, color: s.text, fontWeight: 600, padding: '0.3rem 0.65rem', borderRadius: '20px', fontSize: '0.78rem', textTransform: 'capitalize' }}>
        {role}
      </span>
    );
  };

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
          <div>
            <h2 className="hs-title mb-1">Admin</h2>
            <p className="hs-subtitle mb-0">Manage users and provision clinician accounts.</p>
          </div>
          <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => setShowModal(true)}>
            <Plus size={16} /> Create Clinician
          </Button>
        </div>

        <Row className="g-3 mb-4">
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>Patients</span><Users size={16} color="#94A3B8" /></div>
              <div className="hs-stat-value">{patientCount}</div>
            </div>
          </Col>
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>Clinicians</span><UserCog size={16} color="#94A3B8" /></div>
              <div className="hs-stat-value">{clinicianCount}</div>
            </div>
          </Col>
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>Admins</span></div>
              <div className="hs-stat-value">{adminCount}</div>
            </div>
          </Col>
        </Row>

        <div className="hs-panel">
          <h5 className="hs-title mb-3">All Users</h5>

          {loading ? (
            <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : users.length === 0 ? (
            <p className="hs-subtitle">No users found.</p>
          ) : (
            users.map((u) => (
              <div key={u.user_id} className="hs-reading-row">
                <div className="d-flex align-items-center">
                  <div className="hs-avatar me-3">{u.full_name.charAt(0).toUpperCase()}</div>
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--hs-navy)' }}>{u.full_name}</div>
                    <div style={{ fontSize: '0.82rem', color: '#94A3B8' }}>{u.email}</div>
                  </div>
                </div>
                <div className="d-flex align-items-center gap-3">
                  {roleBadge(u.role)}
                  {u.user_id !== currentUser?.user_id && (
                    <Trash2
                      size={18}
                      color="#94A3B8"
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleDelete(u)}
                    />
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </Container>

      <Modal show={showModal} onHide={() => setShowModal(false)} centered>
        <Modal.Body className="p-4">
          <h5 className="hs-title mb-1">Create Clinician Account</h5>
          <p className="hs-subtitle mb-3" style={{ fontSize: '0.88rem' }}>
            Clinician accounts can't be self-registered — they're provisioned here.
          </p>

          {formError && <Alert variant="danger">{formError}</Alert>}

          <Form onSubmit={handleCreateClinician}>
            <Form.Group className="mb-3">
              <Form.Label className="hs-form-label">Full Name</Form.Label>
              <Form.Control name="full_name" value={form.full_name} onChange={handleFormChange} required />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label className="hs-form-label">Email</Form.Label>
              <Form.Control type="email" name="email" value={form.email} onChange={handleFormChange} required />
            </Form.Group>
            <Form.Group className="mb-4">
              <Form.Label className="hs-form-label">Temporary Password</Form.Label>
              <Form.Control type="password" name="password" value={form.password} onChange={handleFormChange} minLength={8} required />
              <Form.Text className="text-muted">At least 8 characters. Share this with the clinician securely.</Form.Text>
            </Form.Group>

            <div className="d-flex justify-content-end gap-2">
              <Button variant="outline-secondary" onClick={() => setShowModal(false)} disabled={creating}>
                Cancel
              </Button>
              <Button type="submit" className="btn-hs-primary" disabled={creating}>
                {creating ? 'Creating...' : 'Create Account'}
              </Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>
    </Layout>
  );
}