import React, { useState } from 'react';
import { Users, Shield, UserPlus, MoreVertical, Check, Mail } from 'lucide-react';

export default function TeamManagement() {
  const [teamMembers, setTeamMembers] = useState([
    { id: 1, name: 'Alex Director', email: 'alex@organicai.com', role: 'Owner', status: 'Active' },
    { id: 2, name: 'Sarah Marketing', email: 'sarah@organicai.com', role: 'Editor', status: 'Active' },
    { id: 3, name: 'John Intern', email: 'john@organicai.com', role: 'Viewer', status: 'Pending' }
  ]);
  const [inviteEmail, setInviteEmail] = useState('');

  const handleInvite = (e) => {
    e.preventDefault();
    if (!inviteEmail) return;
    setTeamMembers([...teamMembers, { id: Date.now(), name: 'Pending User', email: inviteEmail, role: 'Viewer', status: 'Pending' }]);
    setInviteEmail('');
    alert(`Invitation sent to ${inviteEmail}`);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-8 flex justify-between items-center flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2 flex items-center gap-2">
            <Users size={24} className="text-purple-500" />
            Team Management
          </h1>
          <p className="text-gray-400">Manage your workspace members and access roles.</p>
        </div>
      </div>

      {/* Invite Section */}
      <div className="bg-[#1e1e1e] border border-white/10 rounded-lg p-6 mb-8 shadow-lg">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <UserPlus size={18} /> Invite new members
        </h2>
        <form onSubmit={handleInvite} className="flex gap-4 flex-wrap">
          <div className="flex-1 min-w-[250px] relative">
            <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input 
              type="email" 
              placeholder="colleague@company.com" 
              className="w-full bg-[#2a2a2a] border border-white/10 rounded p-2.5 pl-10 text-white focus:outline-none focus:border-purple-500 transition-colors"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              required
            />
          </div>
          <select className="bg-[#2a2a2a] border border-white/10 rounded p-2.5 text-white focus:outline-none focus:border-purple-500 min-w-[150px]">
            <option value="Viewer">Viewer</option>
            <option value="Editor">Editor</option>
            <option value="Admin">Admin</option>
          </select>
          <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white font-medium rounded px-6 py-2.5 transition-colors">
            Send Invite
          </button>
        </form>
      </div>

      {/* Team List */}
      <div className="bg-[#1e1e1e] border border-white/10 rounded-lg shadow-lg overflow-hidden">
        <div className="p-4 border-b border-white/10 flex items-center gap-2">
          <Shield size={18} className="text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Workspace Members ({teamMembers.length})</h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#2a2a2a]/50 text-xs uppercase tracking-wider text-gray-400">
                <th className="p-4 font-medium">User</th>
                <th className="p-4 font-medium">Role</th>
                <th className="p-4 font-medium">Status</th>
                <th className="p-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {teamMembers.map((member) => (
                <tr key={member.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white font-bold shadow-inner">
                        {member.name.charAt(0)}
                      </div>
                      <div>
                        <div className="font-medium text-white">{member.name}</div>
                        <div className="text-sm text-gray-400">{member.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className="inline-block px-2 py-1 bg-[#2a2a2a] border border-white/10 rounded text-xs font-medium text-gray-300">
                      {member.role}
                    </span>
                  </td>
                  <td className="p-4">
                    {member.status === 'Active' ? (
                      <span className="inline-flex items-center gap-1 text-green-400 text-sm">
                        <Check size={14} /> Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-yellow-400 text-sm">
                        Pending
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    <button className="p-2 text-gray-500 hover:text-white transition-colors rounded hover:bg-white/10">
                      <MoreVertical size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
