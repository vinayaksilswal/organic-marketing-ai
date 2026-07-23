import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Video, Image as ImageIcon, Send, Mail, Building2, Plus, Sparkles } from 'lucide-react';

const Sidebar = ({ user, activeWorkspaceId, onWorkspaceChange }) => {
  const workspaces = user?.businessProfiles || [];
  const navigate = useNavigate();
  const currentWorkspace = workspaces.find(w => w.id === activeWorkspaceId) || workspaces[0];

  return (
    <aside className="sidebar" style={{
      width: '260px',
      height: '100vh',
      position: 'fixed',
      left: 0,
      top: 0,
      background: 'rgba(10, 10, 15, 0.95)',
      backdropFilter: 'blur(16px)',
      borderRight: '1px solid var(--border-color)',
      padding: '1.5rem 1.25rem',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 1000,
      boxShadow: '4px 0 24px rgba(0, 0, 0, 0.4)'
    }}>
      {/* Brand Header */}
      <div className="nav-brand" style={{ 
        marginBottom: '1.75rem', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '0.75rem',
        fontSize: '1.2rem',
        fontWeight: '700',
        color: '#fff',
        letterSpacing: '-0.02em'
      }}>
        <div style={{
          width: '34px',
          height: '34px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 16px rgba(168, 85, 247, 0.4)'
        }}>
          <Sparkles size={18} color="#fff" />
        </div>
        <span>Organic<span style={{ color: 'var(--primary-color)' }}>AI</span></span>
      </div>
      
      {/* Multi-Tenant Workspace Selector */}
      <div style={{ 
        marginBottom: '1.75rem',
        padding: '0.85rem',
        background: 'rgba(255, 255, 255, 0.03)',
        borderRadius: '12px',
        border: '1px solid rgba(255, 255, 255, 0.06)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: '700', margin: 0 }}>
            Active Business
          </p>
          <button 
            onClick={() => navigate('/dashboard/workspaces')}
            style={{ background: 'none', border: 'none', color: 'var(--primary-color)', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center' }}
            title="Create or Manage Businesses"
          >
            <Plus size={14} />
          </button>
        </div>

        <select 
          value={activeWorkspaceId || ''} 
          onChange={(e) => onWorkspaceChange(e.target.value)}
          style={{ 
            width: '100%', 
            padding: '0.5rem 0.6rem', 
            borderRadius: '8px', 
            background: 'var(--bg-dark)', 
            color: 'var(--text-main)', 
            border: '1px solid var(--border-color)',
            fontSize: '0.85rem',
            fontWeight: '500',
            cursor: 'pointer',
            outline: 'none'
          }}
        >
          {workspaces.length === 0 && <option value="">Default Workspace</option>}
          {workspaces.map(wp => (
            <option key={wp.id} value={wp.id}>
              {wp.name || 'Untitled Business'} ({wp.businessModel || 'General'})
            </option>
          ))}
        </select>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', flex: 1 }}>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 0.5rem 0.5rem', fontWeight: '700' }}>
          Core Modules
        </p>
        
        <NavLink to="/dashboard" end className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={18} /> Overview
        </NavLink>

        <NavLink to="/dashboard/workspaces" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Building2 size={18} /> Businesses
        </NavLink>

        <NavLink to="/dashboard/video-studio" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Video size={18} /> AI Video Studio
        </NavLink>

        <NavLink to="/dashboard/media-catalog" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <ImageIcon size={18} /> Media & Catalog
        </NavLink>

        <NavLink to="/dashboard/social-scheduler" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Send size={18} /> Social Scheduler
        </NavLink>

        <NavLink to="/dashboard/email-suite" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Mail size={18} /> Email Suite
        </NavLink>
      </nav>

      {/* User Profile Footer */}
      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary-color), #ec4899)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.9rem', color: '#fff' }}>
          {user?.email?.[0].toUpperCase() || 'U'}
        </div>
        <div style={{ overflow: 'hidden', flex: 1 }}>
          <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: '600', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{user?.email}</p>
          <span style={{ fontSize: '0.7rem', color: 'var(--success)', background: 'rgba(16, 185, 129, 0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px', display: 'inline-block', fontWeight: '600' }}>
            Enterprise Plan
          </span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;

