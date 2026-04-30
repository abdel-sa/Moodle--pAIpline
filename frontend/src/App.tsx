import React, { useState, useRef } from 'react';
import { Layers, FileText, Settings, Play, Square, Download, UploadCloud, CheckCircle, X } from 'lucide-react';

function App() {
  const [activeTab, setActiveTab] = useState<'doc' | 'topic'>('doc');
  
  // Workflow A State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState('');
  const [docCategory, setDocCategory] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  
  // Workflow B State
  const [topic, setTopic] = useState('');
  
  // Settings State
  const [showSettings, setShowSettings] = useState(false);
  const [provider, setProvider] = useState<'ollama' | 'groq'>('ollama');
  const [model, setModel] = useState('llama3.2');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Drag and Drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-white p-6 font-sans relative">
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Layers className="text-[var(--color-primary)] w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-tight">Moodle <span className="text-[var(--color-primary)]">pAIpline</span></h1>
        </div>
        <div className="relative">
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className="glass px-4 py-2 rounded-full flex items-center gap-2 hover:bg-white/5 transition-colors"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm font-medium">Settings</span>
          </button>
          
          {showSettings && (
            <div className="absolute right-0 top-12 w-64 glass p-4 rounded-xl shadow-2xl border border-white/10 z-50 animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-sm">Settings</h3>
                <button onClick={() => setShowSettings(false)} className="text-slate-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Provider</label>
                  <select 
                    value={provider}
                    onChange={(e) => setProvider(e.target.value as 'ollama' | 'groq')}
                    className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)]"
                  >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="groq">Groq (Cloud)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Model</label>
                  <input 
                    type="text" 
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-primary)]" 
                    placeholder="e.g. llama3.2 or mistral" 
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        
        <div className="lg:col-span-1 xl:col-span-2 space-y-6">
          {/* Tabs */}
          <div className="glass p-1 rounded-xl inline-flex gap-1 mb-2">
            <button 
              onClick={() => setActiveTab('doc')}
              className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'doc' ? 'bg-[var(--color-primary)] text-slate-900 shadow-lg' : 'text-slate-300 hover:text-white'}`}
            >
              Document to Questions
            </button>
            <button 
              onClick={() => setActiveTab('topic')}
              className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'topic' ? 'bg-[var(--color-primary)] text-slate-900 shadow-lg' : 'text-slate-300 hover:text-white'}`}
            >
              Topic to Course
            </button>
          </div>

          {/* Workflow A: Document to Questions */}
          {activeTab === 'doc' && (
            <div className="glass rounded-2xl p-8 border border-white/5 relative overflow-hidden group animate-in fade-in slide-in-from-bottom-4">
              <div className="absolute inset-0 bg-gradient-to-br from-[var(--color-primary)]/5 to-transparent pointer-events-none" />
              
              <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 relative z-10">
                <FileText className="w-5 h-5 text-[var(--color-primary)]" />
                Upload Document
              </h2>
              
              <div 
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer relative z-10
                  ${isDragging ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10' : 'border-slate-600/50 bg-slate-800/20 hover:border-[var(--color-primary)]/50'}`}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileChange} 
                  className="hidden" 
                  accept=".pdf,.txt,.md,.pptx" 
                />
                <div className="mx-auto w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 transition-colors">
                  {selectedFile ? (
                    <CheckCircle className="w-8 h-8 text-[var(--color-success)]" />
                  ) : (
                    <UploadCloud className="w-8 h-8 text-slate-400 group-hover:text-[var(--color-primary)]" />
                  )}
                </div>
                <p className="text-slate-200 font-medium mb-1">
                  {selectedFile ? selectedFile.name : 'Drag and drop your file here'}
                </p>
                <p className="text-slate-500 text-sm">
                  {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : 'Supports PDF, PPTX, TXT, MD'}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 relative z-10">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Title</label>
                  <input 
                    type="text" 
                    value={docTitle}
                    onChange={(e) => setDocTitle(e.target.value)}
                    className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--color-primary)] transition-colors" 
                    placeholder="e.g. Chapter 1: Intro" 
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Category Path</label>
                  <input 
                    type="text" 
                    value={docCategory}
                    onChange={(e) => setDocCategory(e.target.value)}
                    className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--color-primary)] transition-colors" 
                    placeholder="e.g. basics/intro" 
                  />
                </div>
              </div>

              <div className="mt-8 flex justify-end relative z-10">
                <button 
                  disabled={!selectedFile || !docTitle || !docCategory}
                  className="bg-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#a5b4fc] text-slate-900 font-semibold px-6 py-3 rounded-xl flex items-center gap-2 transition-all shadow-[0_0_20px_rgba(180,190,254,0.3)] disabled:shadow-none"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Start Generation
                </button>
              </div>
            </div>
          )}

          {/* Workflow B: Topic to Course */}
          {activeTab === 'topic' && (
            <div className="glass rounded-2xl p-8 border border-white/5 relative overflow-hidden group animate-in fade-in slide-in-from-bottom-4">
              <div className="absolute inset-0 bg-gradient-to-br from-[var(--color-secondary)]/5 to-transparent pointer-events-none" />
              
              <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 relative z-10">
                <Layers className="w-5 h-5 text-[var(--color-secondary)]" />
                Generate Full Course
              </h2>
              
              <div className="mt-4 relative z-10">
                <label className="block text-sm font-medium text-slate-400 mb-2">Course Topic</label>
                <textarea 
                  rows={4}
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-5 py-4 text-base focus:outline-none focus:border-[var(--color-secondary)] transition-colors resize-none" 
                  placeholder="e.g. Photosynthese und die Bedeutung für unser Ökosystem..." 
                />
              </div>

              <div className="mt-8 flex justify-end relative z-10">
                <button 
                  disabled={!topic}
                  className="bg-[var(--color-secondary)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#f472b6] text-slate-900 font-semibold px-6 py-3 rounded-xl flex items-center gap-2 transition-all shadow-[0_0_20px_rgba(243,139,168,0.3)] disabled:shadow-none"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Build Course
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Live Terminal & Logs */}
        <div className="glass rounded-2xl border border-white/5 flex flex-col overflow-hidden h-[600px] xl:col-span-1">
          <div className="bg-slate-900/80 px-4 py-3 flex items-center justify-between border-b border-white/5">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[var(--color-error)]" />
              <div className="w-3 h-3 rounded-full bg-[var(--color-warning)]" />
              <div className="w-3 h-3 rounded-full bg-[var(--color-success)]" />
            </div>
            <span className="text-xs font-mono text-slate-400">pipeline.log</span>
            <button className="text-slate-400 hover:text-[var(--color-error)] transition-colors" title="Stop execution">
              <Square className="w-4 h-4 fill-current" />
            </button>
          </div>
          
          <div className="flex-1 p-4 font-mono text-sm text-slate-300 overflow-y-auto bg-[#0a0a0f]">
            <p className="text-slate-500">Waiting for pipeline to start...</p>
            {/* Terminal lines will go here */}
          </div>
        </div>

      </main>
    </div>
  );
}

export default App;
