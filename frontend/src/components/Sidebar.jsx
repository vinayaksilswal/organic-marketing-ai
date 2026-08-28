import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import Logo from './Logo';
import { LayoutDashboard, Video, Image as ImageIcon, Send, Mail, Building2, Plus, Sparkles, Users, CreditCard, LifeBuoy, LogOut, Flame , BarChart3, Film, Inbox, ScrollText } from 'lucide-react';
import { API_BASE, authFetch } from '../config';

const Sidebar = ({ user, token, activeWorkspaceId, onWorkspaceChange, onLogout }) => {
  const workspaces = user?.businessProfiles || [];
  const navigate = useNavigate();
  const currentWorkspace = workspaces.find(w => w.id === activeWorkspaceId) || workspaces[0];

  // The badge here read "Enterprise Plan" for every account, including free
  // ones. Now that plans are real and metered, show the plan the user is
  // actually on — a made-up tier is both a lie and a lost upgrade prompt.
  const [planName, setPlanName] = useState(null);
  useEffect(() => {
    if (!token) return;
    authFetch(`${API_BASE}/billing/me`, {}, token)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (d?.plan?.name) setPlanName(d.plan.name); })
      .catch(() => {});
  }, [token]);

  return (
    <aside className="sidebar" style={{
      width: '260px',
      height: '100vh',
      position: 'fixed',
      left: 0,
      top: 0,
      background: 'rgba(255, 255, 255, 0.96)',
      backdropFilter: 'blur(16px)',
      borderRight: '1px solid var(--border-color)',
      padding: '0.85rem 0.85rem 0.65rem',
      display: 'flex',
      flexDirection: 'column',
      boxSizing: 'border-box',
      overflow: 'hidden',
      zIndex: 1000,
      boxShadow: '4px 0 24px rgba(0, 0, 0, 0.04)'
    }}>
      {/* Brand Header */}
      <div className="nav-brand" style={{ 
        marginBottom: '0.85rem', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '0.75rem',
        fontSize: '1.2rem',
        fontWeight: '700',
        color: 'var(--text-main)',
        letterSpacing: '-0.02em',
        flexShrink: 0,
      }}>
        <Logo size={38} showWordmark />
      </div>
      
      {/* Multi-Tenant Workspace Selector */}
      <div style={{ 
        marginBottom: '0.85rem',
        padding: '0.65rem 0.75rem',
        background: 'rgba(11, 16, 32, 0.03)',
        borderRadius: '10px',
        border: '1px solid rgba(11, 16, 32, 0.06)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: '700', margin: 0 }}>
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
            padding: '0.42rem 0.55rem', 
            borderRadius: '8px', 
            background: 'var(--bg-dark)', 
            color: 'var(--text-main)', 
            border: '1px solid var(--border-color)',
            fontSize: '0.82rem',
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

      {/* Navigation Links - Scrollable container with minHeight: 0 */}
      <nav className="sidebar-nav" style={{
        flex: '1 1 0%',
        minHeight: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
        paddingRight: '3px',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.15rem',
      }}>
        {/* Grouped by what somebody is trying to DO, not by which subsystem
            built it. The old grouping put Overview, Businesses, two studios,
            the validator, insights and the media library all under one
            heading called "Core Platform", which told a new customer nothing
            about where to start.

            The order is the actual sequence of work: set the business up,
            make something, publish it, see what happened. */}

        <NavLink to="/dashboard" end className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={16} /> <span>Home</span>
        </NavLink>

        <div className="sidebar-section-title" style={{ marginTop: '0.35rem' }}>
          Create
        </div>

        <NavLink to="/dashboard/video-studio" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Video size={16} /> <span>Campaigns &amp; video</span>
        </NavLink>

        <NavLink to="/dashboard/faceless-studio" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Film size={16} /> <span>Faceless shorts</span>
        </NavLink>

        {/* Was "PostShip Multi-Platform" with an "X·LI·RD" badge. Nobody
            arriving for the first time knows what either means. */}
        <NavLink to="/dashboard/postship" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Sparkles size={16} /> <span>Write a post</span>
        </NavLink>

        <NavLink to="/dashboard/viral-validator" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Flame size={16} /> <span>Check an idea</span>
        </NavLink>

        <div className="sidebar-section-title">
          Publish
        </div>

        <NavLink to="/dashboard/social-scheduler" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Send size={16} /> <span>Schedule &amp; queue</span>
          <span className="sidebar-badge" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--success)' }}>
            Auto
          </span>
        </NavLink>

        <NavLink to="/dashboard/media-catalog" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <ImageIcon size={16} /> <span>Media library</span>
        </NavLink>

        <NavLink to="/dashboard/email-suite" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Mail size={16} /> <span>Email</span>
        </NavLink>

        <div className="sidebar-section-title">
          Results
        </div>

        <NavLink to="/dashboard/account-insights" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <BarChart3 size={16} /> <span>Insights &amp; leads</span>
        </NavLink>

        <NavLink to="/dashboard/activity" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <ScrollText size={16} /> <span>Activity log</span>
        </NavLink>

        <div className="sidebar-section-title">
          Setup
        </div>

        <NavLink to="/dashboard/workspaces" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Building2 size={16} /> <span>Businesses &amp; accounts</span>
          {workspaces.length > 0 && (
            <span className="sidebar-badge" style={{ background: 'rgba(139,92,246,0.12)', color: 'var(--primary-color)' }}>
              {workspaces.length}
            </span>
          )}
        </NavLink>

        <NavLink to="/dashboard/team" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Users size={16} /> <span>Team & Roles</span>
        </NavLink>
        <NavLink to="/dashboard/billing" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <CreditCard size={16} /> <span>Plan & Billing</span>
        </NavLink>
        <NavLink to="/dashboard/support" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <LifeBuoy size={16} /> <span>Support & Reviews</span>
          <span className="sidebar-badge" style={{ background: 'rgba(37, 99, 235,0.12)', color: 'var(--secondary-color)' }}>
            24/7
          </span>
        </NavLink>

        {/* The operator's inbox, where customers' tickets arrive. It was
            routed and nothing linked to it, so the only way to read a ticket
            was to know the URL. Server-side it is already superadmin-only;
            this just stops it being invisible to the one person who needs it. */}
        {user?.isSuperAdmin && (
          <NavLink to="/dashboard/inbox" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <Inbox size={16} /> <span>Customer Inbox</span>
            <span className="sidebar-badge" style={{ background: 'rgba(109, 40, 217,0.15)', color: 'var(--primary-color)' }}>
              Admin
            </span>
          </NavLink>
        )}
      </nav>

      {/* User Profile Footer */}
      <div style={{ 
        marginTop: 'auto', 
        paddingTop: '0.75rem', 
        borderTop: '1px solid var(--border-color)', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '0.65rem',
        flexShrink: 0,
      }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary-color), #ec4899)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.9rem', color: '#fff', flexShrink: 0 }}>
          {user?.email?.[0].toUpperCase() || 'U'}
        </div>
        <div style={{ overflow: 'hidden', flex: 1, minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: '0.83rem', fontWeight: '600', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{user?.email}</p>
          <span
            onClick={() => navigate('/dashboard/billing')}
            title="View plan and usage"
            style={{ fontSize: '0.7rem', color: 'var(--success)', background: 'rgba(16, 185, 129, 0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px', display: 'inline-block', fontWeight: '600', cursor: 'pointer' }}
          >
            {planName ? `${planName} plan` : 'View plan'}
          </span>
        </div>

        {/* Sign out */}
        <button
          onClick={() => {
            if (window.confirm('Sign out of Organiflo?')) onLogout?.();
          }}
          title="Sign out"
          aria-label="Sign out"
          style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: '0.45rem',
            borderRadius: 8, color: 'var(--text-muted)', display: 'flex', flexShrink: 0,
          }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--error)'; e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'none'; }}
        >
          <LogOut size={17} />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;

