import { useState, useEffect } from 'react';
import { Container, Row, Col, Spinner, Form, Button, Modal, Alert } from 'react-bootstrap';
import { Users, UserCog, Plus, KeyRound, Eye, Pencil, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import { getAllUsers, createClinician, deleteUser, updateUser, resetPassword } from '../api/admin';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { useAuth } from '../context/AuthContext';
import { getUser } from '../api/admin';
import PasswordInput from '../components/PasswordInput';


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

  const [editUser, setEditUser] = useState(null);
  const [editForm, setEditForm] = useState({ full_name: '', email: '', role: '' });
  const [editError, setEditError] = useState(' ');
  const [saving, setSaving] = useState(false);

  const [resetUser, setResetUser] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetting, setResetting] = useState('');

  const [viewUser, setViewUser] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);



  async function handleEditSave(e) {
    e.preventDefault();
    setEditError('');
    setSaving(true);
    try {
      const payload = {
        full_name: editForm.full_name,
        email: editForm.email,
        role: editForm.role,
      };
      if (editForm.password) payload.password = editForm.password;

      await updateUser(editUser.user_id, payload);
      toast.success('User Updated');
      setEditUser(null);
      load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setEditError(typeof detail === 'string' ? detail : 'Could not update user.');

    } finally {
      setSaving(false);
    }
  }

  async function openView(u) {
    setViewUser({ ...u });
    setViewLoading(true);
    try {
      const full = await getUser(u.user_id);
      setViewUser(full);
    } catch {
      toast.error("Could not load user details")
    } finally {
      setViewLoading(false);
    }
  }

  function openEdit(u) {
    setEditUser(u);
    setEditForm({ full_name: u.full_name, email: u.email, role: u.role, password: '' });
    setEditError('');
  }


  function openReset(u) {
    setResetUser(u);
    setNewPassword('');
    setResetError('');
  }

  async function handleResetSave(e) {
    e.preventDefault();
    setResetError('');
    setResetting(true);

    try {
      await resetPassword(resetUser.user_id, newPassword);
      toast.success(`Password reset for ${resetUser.full_name}.`);
      setResetUser(null)
    } catch (err) {
      const detail = err.response?.data?.detail;
      setResetError(typeof detail === 'string' ? detail : 'Could not reset password.');
    } finally {
      setResetting(false);
    }
  }

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
                  <Eye size={17} color="#94A3B8" style={{ cursor: 'pointer' }} onClick={() => openView(u)} />
                  <Pencil size={17} color="#94A3B8" style={{ cursor: 'pointer' }} onClick={() => openEdit(u)} />
                  {u.user_id !== currentUser?.user_id && (
                    <Trash2 size={18} color="#94A3B8" style={{ cursor: 'pointer' }} onClick={() => handleDelete(u)} />
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
              <Form.Control type="email" name="email" onChange={handleFormChange} required />
            </Form.Group>
            <Form.Group className="mb-4">
              <Form.Label className="hs-form-label">Temporary Password</Form.Label>
              <PasswordInput
                // value={form.password}
                onChange={handleFormChange}
                minLength={8}
                autoComplete="new-password"
              />
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

      <Modal show={!!editUser} onHide={() => setEditUser(null)} centered>
        <Modal.Body className="p-4">
          <h5 className="hs-title mb-3">Edit User</h5>
          {editError && <Alert variant="danger">{editError}</Alert>}
          <Form onSubmit={handleEditSave}>
            <Form.Group className="mb-3">
              <Form.Label className="hs-form-label">Full Name</Form.Label>
              <Form.Control value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} required />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label className="hs-form-label">Email</Form.Label>
              <Form.Control type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} required />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label className="hs-form-label">Role</Form.Label>
              <Form.Select
                value={editForm.role}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                disabled={editUser?.user_id === currentUser?.user_id}
              >
                <option value="patient">Patient</option>
                <option value="clinician">Clinician</option>
                <option value="admin">Admin</option>
              </Form.Select>
              {editUser?.user_id === currentUser?.user_id && (
                <Form.Text className="text-muted">You can't change your own role.</Form.Text>
              )}
            </Form.Group>
            <Form.Group className="mb-4">
              <Form.Label className="hs-form-label">New Password</Form.Label>
              <PasswordInput
                value={editForm.password}
                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                minLength={8}
                autoComplete="new-password"
              />
              <Form.Text className="text-muted">Leave blank to keep the current password.</Form.Text>
            </Form.Group>
            <div className="d-flex justify-content-end gap-2">
              <Button variant="outline-secondary" onClick={() => setEditUser(null)} disabled={saving}>Cancel</Button>
              <Button type="submit" className="btn-hs-primary" disabled={saving}>{saving ? 'Saving...' : 'Save Changes'}</Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>

      <Modal show={!!resetUser} onHide={() => setResetUser(null)} centered>
        <Modal.Body className="p-4">
          <h5 className="hs-title mb-1">Reset Password</h5>
          <p className="hs-subtitle mb-3" style={{ fontSize: '0.88rem' }}>
            Set a new password for {resetUser?.full_name}. Share it with them securely.
          </p>

          {resetError && <Alert variant="danger">{resetError}</Alert>}

          <Form onSubmit={handleResetSave}>
            <Form.Group className="mb-4">
              <Form.Label className="hs-form-label">New Password</Form.Label>
              <Form.Control
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                required
              />
              <Form.Text className="text-muted">At least 8 characters.</Form.Text>
            </Form.Group>

            <div className="d-flex justify-content-end gap-2">
              <Button variant="outline-secondary" onClick={() => setResetUser(null)} disabled={resetting}>
                Cancel
              </Button>
              <Button type="submit" className="btn-hs-primary" disabled={resetting}>
                {resetting ? 'Resetting...' : 'Reset Password'}
              </Button>
            </div>
          </Form>
        </Modal.Body>
      </Modal>

      <Modal show={!!viewUser} onHide={() => setViewUser(null)} centered>
        <Modal.Body className="p-4">
          <h5 className="hs-title mb-3">User Details</h5>
          {viewLoading ? (
            <div className="text-center py-3"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : viewUser && (
            <div>
              <Row className="mb-2"><Col xs={5} className="hs-subtitle">Full Name</Col><Col style={{ color: 'var(--hs-navy)', fontWeight: 600 }}>{viewUser.full_name}</Col></Row>
              <Row className="mb-2"><Col xs={5} className="hs-subtitle">Email</Col><Col>{viewUser.email}</Col></Row>
              <Row className="mb-2"><Col xs={5} className="hs-subtitle">Role</Col><Col>{roleBadge(viewUser.role)}</Col></Row>
              <Row className="mb-2"><Col xs={5} className="hs-subtitle">Joined</Col><Col>{new Date(viewUser.created_at).toLocaleDateString()}</Col></Row>
              {viewUser.role === 'patient' && (
                <>
                  <Row className="mb-2"><Col xs={5} className="hs-subtitle">Date of Birth</Col><Col>{viewUser.date_of_birth || '—'}</Col></Row>
                  <Row className="mb-2"><Col xs={5} className="hs-subtitle">Sex</Col><Col>{viewUser.sex || '—'}</Col></Row>
                  <Row className="mb-2"><Col xs={5} className="hs-subtitle">Readings Logged</Col><Col>{viewUser.reading_count ?? 0}</Col></Row>
                </>
              )}
            </div>
          )}
          <div className="d-flex justify-content-end mt-3">
            <Button variant="outline-secondary" onClick={() => setViewUser(null)}>Close</Button>
          </div>
        </Modal.Body>
      </Modal>

    </Layout>
  );
}