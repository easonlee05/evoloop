import React from 'react';
import { ChevronRight, Home } from 'lucide-react';
import './header.css';

export function Header({ title, breadcrumbs }) {
  return (
    <header className="header">
      <div className="breadcrumbs">
        {breadcrumbs ? (
          breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && <ChevronRight size={12} className="bc-sep" />}
              <span className={i === breadcrumbs.length - 1 ? 'bc-current' : 'bc-link'}>
                {crumb.label}
              </span>
            </React.Fragment>
          ))
        ) : (
          <span className="bc-current">{title}</span>
        )}
      </div>

      <div className="header-right">
        <button className="header-btn">Invite</button>
        <button className="header-btn">Help</button>
      </div>
    </header>
  );
}
