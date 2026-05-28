import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  ClipboardCheck,
  ScrollText,
  Calculator,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Leaf,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import clsx from 'clsx';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ingest', label: 'Ingest Data', icon: Upload },
  { to: '/review', label: 'Review Queue', icon: ClipboardCheck },
  { to: '/audit', label: 'Audit Log', icon: ScrollText },
  { to: '/factors', label: 'Emission Factors', icon: Calculator },
];

export function Layout() {
  const { user, tenants, logout, switchTenant } = useAuth();
  const navigate = useNavigate();
  const [tenantDropdown, setTenantDropdown] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSwitchTenant = async (id: number) => {
    await switchTenant(id);
    setTenantDropdown(false);
    window.location.reload();
  };

  const activeTenantId = localStorage.getItem('active_tenant_id');
  const activeTenant = activeTenantId ? tenants.find((t) => t.id === Number(activeTenantId)) : tenants[0];

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 w-60 bg-white border-r border-slate-200 flex flex-col transition-transform lg:translate-x-0 lg:static',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="h-14 flex items-center gap-2.5 px-5 border-b border-slate-200 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-semibold text-slate-800 text-sm">Breathe</span>
            <span className="font-semibold text-emerald-600 text-sm ml-1">ESG</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )
              }
            >
              <item.icon className="w-4.5 h-4.5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Tenant switcher */}
        {tenants.length > 0 && (
          <div className="px-3 pb-3 relative">
            <button
              onClick={() => setTenantDropdown(!tenantDropdown)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <div className="w-6 h-6 rounded bg-slate-100 flex items-center justify-center text-xs font-medium text-slate-500">
                {activeTenant?.name?.charAt(0) || 'T'}
              </div>
              <span className="flex-1 text-left truncate">{activeTenant?.name || 'Select Tenant'}</span>
              <ChevronDown className="w-4 h-4 text-slate-400" />
            </button>
            {tenantDropdown && (
              <div className="absolute bottom-full left-3 right-3 mb-1 bg-white rounded-lg border border-slate-200 shadow-lg py-1 z-50">
                {tenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleSwitchTenant(t.id)}
                    className={clsx(
                      'w-full text-left px-3 py-2 text-sm hover:bg-slate-50 transition-colors',
                      t.id === activeTenant?.id ? 'text-emerald-700 font-medium' : 'text-slate-700'
                    )}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* User / Logout */}
        <div className="px-3 pb-4 border-t border-slate-200 pt-3">
          <div className="flex items-center gap-2 px-3 py-1.5">
            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm font-medium text-slate-600">
              {user?.first_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-700 truncate">
                {user?.first_name ? `${user.first_name} ${user.last_name}` : user?.username}
              </p>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              title="Log out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar (mobile) */}
        <header className="h-14 flex items-center gap-3 px-4 border-b border-slate-200 bg-white lg:px-6 shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-1.5 rounded-md text-slate-500 hover:bg-slate-100"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="flex-1" />
          {activeTenant && (
            <span className="text-xs text-slate-400">
              Tenant: <span className="font-medium text-slate-600">{activeTenant.name}</span>
            </span>
          )}
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
