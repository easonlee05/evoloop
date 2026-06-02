import React from 'react';
import './card.css';

export function Card({ children, className = '', variant = 'solid', hoverable = false, ...props }) {
  const variantClass = variant === 'glass' ? 'card-glass' : 'card-solid';
  const hoverClass = hoverable ? 'card-hoverable' : '';
  
  return (
    <div className={`card ${variantClass} ${hoverClass} ${className}`} {...props}>
      {children}
    </div>
  );
}
