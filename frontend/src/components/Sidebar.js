import { NavLink, useNavigate } from 'react-router-dom';
import { CalendarDays, LayoutDashboard, LogOut, PlusCircle, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/dashboard', label: 'Inicio',      Icon: LayoutDashboard },
  { to: '/agenda',    label: 'Agenda',       Icon: CalendarDays    },
  { to: '/pacientes', label: 'Pacientes',    Icon: Users           },
  { to: '/nueva-cita',label: 'Nueva Cita',   Icon: PlusCircle      },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="w-64 bg-slate-900 flex flex-col shrink-0">
      {/* Brand */}
      <div className="px-6 py-5 border-b border-slate-800">
        <h1 className="text-xl font-bold text-teal-400 tracking-tight">Elysium</h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest mt-0.5">Fisio · Pilates</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-teal-600 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User + logout */}
      <div className="px-3 py-4 border-t border-slate-800">
        <div className="px-3 py-2 mb-1">
          <p className="text-sm font-medium text-slate-200 truncate">{user?.nombre ?? 'Usuario'}</p>
          <p className="text-xs text-slate-500 truncate">{user?.sub}</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
