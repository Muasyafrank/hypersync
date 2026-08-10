import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Heart, LayoutGrid, LineChart, Activity, Bell, LogOut, Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useConfirm} from '../context/ConfirmContext'

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const confirm = useConfirm();

    async function handleLogout() {
        const confirmed = await confirm({
            title: 'Log out?',
            message: "You'll need to log back in to access your dashboard.",
            confirmLabel: 'Log out',
            cancelLabel: 'Stay logged in',
            variant: 'primary',
        });
        if (confirmed){
            await logout();
            navigate('/login')
        }
    }

    function closeSidebar() {
        setSidebarOpen(false);
    }

    const initial = user?.full_name?.charAt(0)?.toUpperCase() || '?';
    const role = user?.role;

    return (
        <div className="hs-app-shell" style={{ backgroundColor: 'var(--hs-bg)' }}>
            <div className="hs-topbar">
                <div className="d-flex align-items-center gap-2" style={{ fontWeight: 700, color: 'var(--hs-navy)' }}>
                    <Heart size={20} fill="var(--hs-teal)" color="var(--hs-teal)" />
                    HyperSync
                </div>
                <button
                    onClick={() => setSidebarOpen(true)}
                    style={{ background: 'none', border: 'none', color: 'var(--hs-navy)' }}
                    aria-label="Open menu"
                >
                    <Menu size={24} />
                </button>
            </div>

            <div className={`hs-sidebar-backdrop${sidebarOpen ? ' open' : ''}`} onClick={closeSidebar} />

            <aside className={`hs-sidebar${sidebarOpen ? ' open' : ''}`}>
                <div className="d-flex justify-content-between align-items-center">
                    <div className="hs-sidebar-brand mb-0">
                        <Heart size={22} fill="currentColor" />
                        <span>HyperSync</span>
                    </div>
                    <button
                        onClick={closeSidebar}
                        className="d-lg-none"
                        style={{ background: 'none', border: 'none', color: 'var(--hs-navy)' }}
                        aria-label="Close menu"
                    >
                        <X size={20} />
                    </button>
                </div>

                <nav className="hs-sidebar-nav">
                    <NavLink to="/dashboard" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                        <LayoutGrid size={18} /> Dashboard
                    </NavLink>
                    {role === 'patient' && (
                        <>
                            <NavLink to="/readings" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                                <Heart size={18} /> Readings
                            </NavLink>
                            <NavLink to="/trend" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                                <LineChart size={18} /> Trends
                            </NavLink>
                            <NavLink to="/lifestyle" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                                <Activity size={18} /> Lifestyle
                            </NavLink>
                        </>
                    )}
                    <NavLink to="/alerts" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                        <Bell size={18} /> Alerts
                    </NavLink>

                    {role === 'clinician' && (
                        <NavLink to="/alerts" onClick={closeSidebar} className={({ isActive }) => `hs-sidebar-link${isActive ? ' active' : ''}`}>
                            <Bell size={18} /> Clinician
                        </NavLink>
                    )}

                </nav>

                <div className="hs-sidebar-footer">
                    <div className="hs-sidebar-user">
                        <div className="hs-avatar">{initial}</div>
                        <div>
                            <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--hs-navy)' }}>
                                {user?.full_name || '—'}
                            </div>
                            <div style={{ fontSize: '0.78rem', color: '#94A3B8', textTransform: 'capitalize' }}>
                                {user?.role}
                            </div>
                        </div>
                    </div>
                    <button className="hs-sidebar-logout" onClick={handleLogout}>
                        <LogOut size={16} /> Log out
                    </button>
                </div>
            </aside>

            <main className="hs-main">{children}</main>
        </div>
    );
}