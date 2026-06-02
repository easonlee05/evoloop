import React from 'react';
import { Search } from 'lucide-react';
import './search-input.css';

export function SearchInput({ className = '', placeholder = '搜索', shortcut = '⌘K', ...props }) {
  return (
    <div className={`search-container ${className}`}>
      <Search size={16} className="search-icon" />
      <input type="text" className="search-input" placeholder={placeholder} {...props} />
      {shortcut && <div className="search-shortcut">{shortcut}</div>}
    </div>
  );
}
