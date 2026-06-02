import React from 'react';
import './badge.css';

export function Badge({ children, variant = 'danger', className = '' }) {
  return (
    <span className={`badge badge-${variant} ${className}`}>
      {children}
    </span>
  );
}
