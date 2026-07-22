import React from 'react';
import { LogOut } from 'lucide-react';

const Navbar = ({ onLogout }) => {
  return (
    <nav className="navbar">
      <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="nav-brand">Organic<span>Marketing AI</span></div>
        <div className="nav-links">
          <button className="btn btn-secondary" onClick={onLogout}>
            <LogOut size={16} style={{ marginRight: '0.5rem' }} /> Sign Out
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
