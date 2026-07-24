import React, { useState } from 'react';
import { HelpCircle, X, MessageSquare, Book, LifeBuoy } from 'lucide-react';

export default function HelpWidget() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen && (
        <div className="absolute bottom-16 right-0 w-80 bg-[#1e1e1e] border border-white/10 rounded-lg shadow-2xl overflow-hidden flex flex-col mb-2 transform transition-all duration-200">
          <div className="p-4 bg-gradient-to-r from-purple-900/50 to-indigo-900/50 border-b border-white/10 flex justify-between items-center">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <LifeBuoy size={18} /> Support Center
            </h3>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white transition-colors">
              <X size={18} />
            </button>
          </div>
          <div className="p-4 flex flex-col gap-3">
            <button className="flex items-center gap-3 p-3 bg-white/5 rounded-md hover:bg-white/10 transition-colors text-left" onClick={() => alert('Opening live chat...')}>
              <MessageSquare size={18} className="text-purple-400" />
              <div>
                <div className="text-sm font-medium text-white">Live Chat</div>
                <div className="text-xs text-gray-400">Typically replies in under 5 mins</div>
              </div>
            </button>
            <button className="flex items-center gap-3 p-3 bg-white/5 rounded-md hover:bg-white/10 transition-colors text-left" onClick={() => alert('Opening documentation...')}>
              <Book size={18} className="text-blue-400" />
              <div>
                <div className="text-sm font-medium text-white">Documentation</div>
                <div className="text-xs text-gray-400">Read our guides and API docs</div>
              </div>
            </button>
          </div>
          <div className="p-3 border-t border-white/10 text-center text-xs text-gray-500">
            Enterprise Support is available 24/7
          </div>
        </div>
      )}
      
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-12 h-12 rounded-full bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center shadow-lg transition-transform hover:scale-105"
      >
        {isOpen ? <X size={24} /> : <HelpCircle size={24} />}
      </button>
    </div>
  );
}
