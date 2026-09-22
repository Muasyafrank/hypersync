import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Activity, AlertTriangle, Bell, Heart, LayoutGrid, LineChart, LogOut, Menu, UserCog, Users, X,
} from 'lucide-react';
import logoMark from '../assets/logo-mark.svg';
import { useAuth } from '../context/AuthContext';
import { useConfirm } from '../context/ConfirmContext';
import { roleHome } from '../utils/format';

/** Nav entries per role, so the sidebar is data rather than nested ternaries. */
const NAV_ITEMS = {
  patient: [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
    { to: '/readings', label: 'Readings', icon: Heart },
    { to: '/trend', label: 'Trends', icon: LineChart },
    { to: '/lifestyle', label: 'Lifestyle', icon: Activity },
    { to: '/alerts', label: 'Alerts', icon: Bell },
  ],
  clinician: [
    { to: '/clinician', label: 'Patients', icon: Users },
    { to: '/clinician/alerts', label: 'Alert queue', icon: AlertTriangle },
  ],
  admin: [
    { to: '/admin', label: 'Admin', icon: UserCog },
  ],
};

const linkClass = ({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`;

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const role = user?.role;
  const items = NAV_ITEMS[role] ?? [];
  const initial = user?.full_name?.charAt(0)?.toUpperCase() || '?';

  const closeSidebar = () => setSidebarOpen(false);

  async function handleLogout() {
    const confirmed = await confirm({
      title: 'Log out?',
      message: "You'll need to log back in to access your dashboard.",
      confirmLabel: 'Log out',
      cancelLabel: 'Stay logged in',
      variant: 'primary',
    });
    if (!confirmed) return;
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="hs-app-shell">
      <header className="hs-topbar">
        <NavLink to={roleHome(role)} className="hs-topbar-brand">
          <img src={logoMark} alt="" width={26} height={26} className="hs-brand-mark" />
          HyperSync
        </NavLink>
        <button type="button" className="hs-icon-btn" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
          <Menu size={24} />
        </button>
      </header>

      <div
        className={`hs-sidebar-backdrop${sidebarOpen ? ' open' : ''}`}
        onClick={closeSidebar}
        aria-hidden="true"
      />

      <aside className={`hs-sidebar${sidebarOpen ? ' open' : ''}`}>
        <div className="d-flex justify-content-between align-items-center">
          <div className="hs-sidebar-brand mb-0">
            <img src={logoMark} alt="" width={30} height={30} className="hs-brand-mark" />
            <span>HyperSync</span>
          </div>
          <button type="button" onClick={closeSidebar} className="hs-icon-btn d-lg-none" aria-label="Close menu">
            <X size={20} />
          </button>
        </div>

        <nav className="hs-sidebar-nav" aria-label="Main navigation">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end onClick={closeSidebar} className={linkClass}>
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="hs-sidebar-footer">
          <div className="hs-sidebar-user">
            <div className="hs-avatar" aria-hidden="true">{initial}</div>
            <div>
              <div className="hs-sidebar-user-name">{user?.full_name || '—'}</div>
              <div className="hs-sidebar-user-role">{role}</div>
            </div>
          </div>
          <button type="button" className="hs-sidebar-logout" onClick={handleLogout}>
            <LogOut size={16} /> Log out
          </button>
        </div>
      </aside>

      <main className="hs-main">{children}</main>
    </div>
  );
}
