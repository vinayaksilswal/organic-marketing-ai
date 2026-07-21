import React from 'react';
import { LogOut } from 'lucide-react';

const Navbar = ({ onLogout }) => {
  return (
    <nav className="navbar">
      <div className="nav-brand">Organic<span>Marketing AI</span></div>
      <div className="nav-links">
        <button className="btn btn-secondary" onClick={onLogout}>
          <LogOut size={16} style={{ marginRight: '0.5rem' }} /> Sign Out
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
