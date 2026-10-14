'use client';

import { useState } from 'react';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [link, setLink] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus('Processing...');

    const formData = new FormData();
    if (file) formData.append('file', file);
    if (link) formData.append('link', link);

    try {
      const response = await fetch('http://localhost:8000/simulate', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (response.ok) {
        setStatus(`Simulation Started! ID: ${data.id}`);
      } else {
        setStatus(`Error: ${data.detail || 'Failed to start'}`);
      }
    } catch (error) {
      console.error(error);
      setStatus('Error connecting to backend');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 text-white font-sans">
      <div className="container mx-auto px-6 py-20 flex flex-col items-center">
        <h1 className="text-6xl font-extrabold mb-4 animate-pulse">
          Buy you Before
        </h1>
        <p className="text-xl mb-12 text-gray-300">
          Advanced Room Simulator - Visualize before you buy.
        </p>

        <div className="bg-white/10 backdrop-blur-md p-8 rounded-2xl shadow-2xl w-full max-w-2xl border border-white/20">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">Upload Room Image</label>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full p-3 bg-white/5 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
              />
            </div>

            <div className="flex items-center space-x-4">
              <hr className="flex-grow border-white/10" />
              <span className="text-sm text-gray-400">OR</span>
              <hr className="flex-grow border-white/10" />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Paste Product Link</label>
              <input
                type="text"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="https://example.com/item"
                className="w-full p-3 bg-white/5 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-gradient-to-r from-pink-500 to-purple-600 rounded-xl font-bold text-lg hover:scale-105 active:scale-95 transition-transform disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
            >
              {loading ? 'Initializing Microservices...' : 'Generate Simulation'}
            </button>
          </form>

          {status && (
            <div className={`mt-6 p-4 rounded-lg text-center font-medium ${status.includes('Error') ? 'bg-red-500/20 text-red-200' : 'bg-green-500/20 text-green-200'}`}>
              {status}
            </div>
          )}
        </div>

        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          <FeatureCard title="vLLM Powered" description="State-of-the-art vision models for realistic rendering." />
          <FeatureCard title="Shapely Optimized" description="Precise geometric calculations for furniture placement." />
          <FeatureCard title="Dapr Enabled" description="Robust microservice orchestration for high scalability." />
        </div>
      </div>
    </main>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="p-6 bg-black/30 rounded-xl border border-white/5 hover:border-purple-500/50 transition">
      <h3 className="text-xl font-bold mb-2 text-purple-400">{title}</h3>
      <p className="text-gray-400 text-sm">{description}</p>
    </div>
  );
}
