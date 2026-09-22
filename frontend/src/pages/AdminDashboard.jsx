import { useMemo, useState } from 'react';
import { Button, Col, Container, Row } from 'react-bootstrap';
import { Eye, KeyRound, Pencil, Plus, Trash2, UserCog, Users } from 'lucide-react';
import Layout from '../components/Layout';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, RoleBadge, StatCard } from '../components/ui';
import ClinicianModal from '../components/admin/ClinicianModal';
import EditUserModal from '../components/admin/EditUserModal';
import ResetPasswordModal from '../components/admin/ResetPasswordModal';
import UserDetailModal from '../components/admin/UserDetailModal';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { deleteUser, getAllUsers, getUser } from '../api/admin';
import { errorMessage } from '../utils/format';

export default function AdminDashboard() {
  const { user: currentUser } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();

  const { data: users, loading, error, reload } = useAsync(getAllUsers, [], []);

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(null);
  const [resetting, setResetting] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);

  const counts = useMemo(
    () => ({
      patient: users.filter((u) => u.role === 'patient').length,
      clinician: users.filter((u) => u.role === 'clinician').length,
      admin: users.filter((u) => u.role === 'admin').length,
    }),
    [users],
  );

  async function openDetails(user) {
    // Show what we already have, then swap in the fuller record.
    setViewing(user);
    setViewLoading(true);
    try {
      setViewing(await getUser(user.user_id));
    } catch {
      toast.error('Could not load the full user record.');
    } finally {
      setViewLoading(false);
    }
  }

  async function handleDelete(user) {
    const confirmed = await confirm({
      title: `Delete ${user.full_name}?`,
      message: `This permanently removes this ${user.role} account and all associated data. This cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await deleteUser(user.user_id);
      toast.success('Account deleted.');
      reload();
    } catch (err) {
      toast.error(errorMessage(err, 'Could not delete account.'));
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader
          title="Admin"
          subtitle="Manage users and provision clinician accounts."
          action={
            <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => setShowCreate(true)}>
              <Plus size={16} /> Create clinician
            </Button>
          }
        />

        <Row className="g-3 mb-4">
          <Col md={4} sm={6}><StatCard label="Patients" icon={Users} value={counts.patient} /></Col>
          <Col md={4} sm={6}><StatCard label="Clinicians" icon={UserCog} value={counts.clinician} /></Col>
          <Col md={4} sm={6}><StatCard label="Admins" value={counts.admin} /></Col>
        </Row>

        <Panel title="All users">
          {loading ? (
            <Loader />
          ) : error ? (
            <ErrorState message="Could not load users." onRetry={reload} />
          ) : users.length === 0 ? (
            <EmptyState icon={Users} message="No users found." />
          ) : (
            users.map((user) => (
              <DataRow
                key={user.user_id}
                trailing={
                  <>
                    <RoleBadge role={user.role} />
                    <button type="button" className="hs-icon-action" onClick={() => openDetails(user)} aria-label={`View ${user.full_name}`}>
                      <Eye size={17} />
                    </button>
                    <button type="button" className="hs-icon-action" onClick={() => setEditing(user)} aria-label={`Edit ${user.full_name}`}>
                      <Pencil size={17} />
                    </button>
                    <button type="button" className="hs-icon-action" onClick={() => setResetting(user)} aria-label={`Reset password for ${user.full_name}`}>
                      <KeyRound size={17} />
                    </button>
                    {user.user_id !== currentUser?.user_id && (
                      <button type="button" className="hs-icon-action hs-icon-action-danger" onClick={() => handleDelete(user)} aria-label={`Delete ${user.full_name}`}>
                        <Trash2 size={18} />
                      </button>
                    )}
                  </>
                }
              >
                <div className="d-flex align-items-center">
                  <div className="hs-avatar me-3" aria-hidden="true">{user.full_name.charAt(0).toUpperCase()}</div>
                  <div>
                    <div className="hs-reading-value">{user.full_name}</div>
                    <div className="hs-reading-meta">{user.email}</div>
                  </div>
                </div>
              </DataRow>
            ))
          )}
        </Panel>
      </Container>

      <ClinicianModal
        show={showCreate}
        onHide={() => setShowCreate(false)}
        onCreated={(name) => {
          toast.success(`Clinician account created for ${name}.`);
          reload();
        }}
      />

      <EditUserModal
        user={editing}
        currentUserId={currentUser?.user_id}
        onHide={() => setEditing(null)}
        onSaved={() => {
          toast.success('User updated.');
          setEditing(null);
          reload();
        }}
      />

      <ResetPasswordModal
        user={resetting}
        onHide={() => setResetting(null)}
        onReset={(name) => {
          toast.success(`Password reset for ${name}.`);
          setResetting(null);
        }}
      />

      <UserDetailModal user={viewing} loading={viewLoading} onHide={() => setViewing(null)} />
    </Layout>
  );
}
