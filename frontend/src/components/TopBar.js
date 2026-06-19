import { useLocation } from 'react-router-dom';

const titles = {
  '/dashboard':  'Inicio',
  '/agenda':     'Agenda',
  '/pacientes':  'Pacientes',
  '/nueva-cita': 'Nueva Cita',
};

export default function TopBar() {
  const { pathname } = useLocation();
  const title = titles[pathname] ?? 'Elysium';

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6 shrink-0">
      <h2 className="text-base font-semibold text-slate-800">{title}</h2>
    </header>
  );
}
