import React from 'react';
import './button.css';

export function Button({ 
  children, 
  variant = 'primary', // primary, secondary, ghost, icon
  size = 'md', // sm, md, lg
  icon, 
  rightIcon,
  className = '', 
  ...props 
}) {
  const baseClass = variant === 'icon' ? 'btn-icon' : `btn btn-${variant} btn-${size}`;
  
  return (
    <button className={`${baseClass} ${className}`} {...props}>
      {icon && <span className="btn-icon-left">{icon}</span>}
      <span className="btn-text">{children}</span>
      {rightIcon && <span className="btn-icon-right">{rightIcon}</span>}
    </button>
  );
}
