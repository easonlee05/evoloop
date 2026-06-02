import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import './main-layout.css';

export function MainLayout({ children, title, breadcrumbs, noHeader }) {
  return (
    <div className="main-layout">
      <Sidebar />
      <div className="layout-content">
        <main className="main-area">
          {children}
        </main>
      </div>
    </div>
  );
}
