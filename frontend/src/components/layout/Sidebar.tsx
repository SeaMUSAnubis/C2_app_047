import { NavLink } from 'react-router-dom';
import { SIDEBAR_ITEMS } from '../../lib/constants';

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <strong>Vespionage</strong>
        <span>UEBA Dashboard</span>
      </div>

      <nav className="sidebar-nav">
        {SIDEBAR_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              isActive ? 'sidebar-link active' : 'sidebar-link'
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
