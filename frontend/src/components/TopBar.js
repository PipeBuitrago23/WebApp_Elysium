import { useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';

const titles = {
  '/dashboard':  'Inicio',
  '/agenda':     'Agenda',
  '/pacientes':  'Pacientes',
  '/nueva-cita': 'Nueva Cita',
};

export default function TopBar({ onMenuClick }) {
  const { pathname } = useLocation();
  const title = titles[pathname] ?? 'Elysium';

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center px-4 md:px-6 shrink-0 gap-3">
      <button
        onClick={onMenuClick}
        className="md:hidden p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
        aria-label="Abrir menú"
      >
        <Menu size={20} />
      </button>
      <h2 className="text-base font-semibold text-slate-800">{title}</h2>
    </header>
  );
}
