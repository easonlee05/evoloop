import React from 'react';
import './avatar.css';

export function Avatar({ src, alt = '', size = 'md', className = '' }) {
  return (
    <div className={`avatar avatar-${size} ${className}`}>
      {src ? (
        <img src={src} alt={alt} />
      ) : (
        <div className="avatar-fallback">{alt.charAt(0).toUpperCase()}</div>
      )}
    </div>
  );
}
