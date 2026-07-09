import { NavLink, useNavigate } from 'react-router-dom';
import { CalendarDays, LayoutDashboard, LogOut, PlusCircle, Users, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { to: '/dashboard', label: 'Inicio',      Icon: LayoutDashboard },
  { to: '/agenda',    label: 'Agenda',       Icon: CalendarDays    },
  { to: '/pacientes', label: 'Pacientes',    Icon: Users           },
  { to: '/nueva-cita',label: 'Nueva Cita',   Icon: PlusCircle      },
];

export default function Sidebar({ isOpen, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className={`
      fixed inset-y-0 left-0 z-50 w-64 bg-zinc-950 flex flex-col shrink-0
      transform transition-transform duration-300 ease-in-out
      md:relative md:z-auto md:translate-x-0
      ${isOpen ? 'translate-x-0' : '-translate-x-full'}
    `}>
      {/* Mobile close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors md:hidden"
      >
        <X size={18} />
      </button>

      {/* Brand */}
      <div className="px-6 py-5 border-b border-zinc-800">
        <h1 className="text-lg font-light tracking-widest uppercase text-white">Elysium</h1>
        <p className="text-[10px] text-zinc-500 uppercase tracking-widest mt-1">Fisioterapia & Pilates</p>
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
                  ? 'bg-zinc-700 text-white'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User + logout */}
      <div className="px-3 py-4 border-t border-zinc-800">
        <div className="px-3 py-2 mb-1">
          <p className="text-sm font-medium text-zinc-100 truncate">{user?.nombre ?? 'Usuario'}</p>
          <p className="text-xs text-zinc-500 truncate">{user?.sub}</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
        >
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
