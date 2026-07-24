import React from 'react';

export default function Legal({ title }) {
  return (
    <div className="min-h-screen bg-black text-white p-12 pt-32 font-sans">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">{title}</h1>
        <div className="prose prose-invert max-w-none text-gray-300">
          <p className="mb-4">Last updated: {new Date().toLocaleDateString()}</p>
          <p className="mb-4">
            This is a placeholder for the enterprise-grade {title} document. 
            Before going to production, please ensure your legal counsel reviews and provides the full text for this page.
          </p>
          <h2 className="text-2xl font-semibold mt-8 mb-4 text-white">1. Introduction</h2>
          <p className="mb-4">
            Welcome to OrganicAI. By using our services, you agree to these terms and conditions. 
            Our platform provides autonomous marketing solutions.
          </p>
          <h2 className="text-2xl font-semibold mt-8 mb-4 text-white">2. Data Privacy</h2>
          <p className="mb-4">
            We take your privacy seriously. All data is processed in accordance with global standards including GDPR and CCPA.
          </p>
        </div>
      </div>
    </div>
  );
}
