"use client";

import { useState, useEffect, useRef } from "react";
import { sendMessage, getAuthStatus, getLoginUrl } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Send, User, Bot, Sparkles, Database, Search, Mail, FileText, Trash2, Palette } from "lucide-react";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string; task?: string }[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState("theme-glass");
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { checkAuth(); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const checkAuth = async () => {
    try {
      const status = await getAuthStatus();
      setAuthenticated(status.authenticated);
    } catch (e) { setAuthenticated(false); }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input;
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setLoading(true);
    try {
      const data = await sendMessage(userMsg, history);
      setMessages(prev => [...prev, { role: "assistant", content: data.response, task: data.task }]);
      setHistory(data.history);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "**Error:** AI connection lost." }]);
    } finally {
      setLoading(false);
    }
  };

  const getTaskIcon = (task?: string) => {
    if (!task) return <Sparkles size={12} />;
    if (task.includes("gmail")) return <Mail size={12} />;
    if (task.includes("drive")) return <FileText size={12} />;
    if (task.includes("search")) return <Search size={12} />;
    if (task.includes("memory")) return <Database size={12} />;
    return <Sparkles size={12} />;
  };

  if (authenticated === null) return <div className="flex h-screen items-center justify-center font-bold text-blue-600 animate-pulse text-2xl">Initializing...</div>;

  if (!authenticated) {
    return (
      <div className={`h-screen ${theme}`}>
        <div className="flex h-full flex-col items-center justify-center p-4">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-12 rounded-3xl text-center max-w-md w-full">
            <Sparkles className="mx-auto mb-6 text-blue-600" size={48} />
            <h1 className="text-4xl font-black mb-4 tracking-tighter text-slate-800 uppercase">AI Assistant</h1>
            <button onClick={async () => { const { url } = await getLoginUrl(); window.location.href = url; }} 
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-2xl shadow-xl transition-all">
              Login with Google
            </button>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className={`${theme} h-screen transition-colors duration-500`}>
      <div className="flex flex-col h-full max-w-5xl mx-auto p-4 md:p-6 gap-4 font-sans">
        
        {/* Header */}
        <header className="glass-panel px-6 py-4 rounded-3xl flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600 p-2 rounded-xl text-white shadow-lg shadow-blue-200">
              <Sparkles size={20} />
            </div>
            <h1 className="font-black text-xl tracking-tighter uppercase">Assistant</h1>
          </div>
          <div className="flex items-center gap-3">
            {/* Theme Switcher */}
            <div className="relative group">
              <div className="flex items-center gap-2 bg-white/50 px-3 py-2 rounded-xl border border-slate-200 cursor-pointer hover:bg-white transition-all">
                <Palette size={18} className="text-slate-500" />
                <select 
                  value={theme} 
                  onChange={(e) => setTheme(e.target.value)}
                  className="bg-transparent text-[10px] font-black uppercase tracking-widest outline-none border-none cursor-pointer"
                >
                  <option value="theme-glass">Glass</option>
                  <option value="theme-midnight">Midnight</option>
                  <option value="theme-minimal">Paper</option>
                </select>
              </div>
            </div>
            <button onClick={() => { setMessages([]); setHistory([]); }} className="p-2 text-slate-400 hover:text-red-500 transition-colors">
              <Trash2 size={20} />
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <main className="flex-1 glass-panel rounded-3xl overflow-hidden flex flex-col relative">
          <div className="flex-1 overflow-y-auto p-6 space-y-6 hide-scrollbar">
            <AnimatePresence initial={false}>
              {messages.length === 0 && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full flex flex-col items-center justify-center text-center opacity-40 py-20">
                  <Database size={40} className="text-slate-400 mb-4" />
                  <p className="text-xl font-bold italic">Connected to Gmail & Drive</p>
                </motion.div>
              )}
              {messages.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} 
                  className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border text-slate-400"}`}>
                    {m.role === "user" ? <User size={16} /> : <Bot size={16} />}
                  </div>
                  <div className={`max-w-[85%] rounded-2xl px-5 py-3 shadow-sm ${m.role === "user" ? "glass-card-user rounded-tr-none" : "glass-card-ai rounded-tl-none font-medium"}`}>
                    <div className="prose prose-sm max-w-none text-inherit leading-relaxed break-words">
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </div>
                    {m.task && (
                      <div className="mt-2 pt-2 border-t border-white/10 flex items-center gap-2 text-[10px] font-black opacity-50 uppercase tracking-[0.1em]">
                        {getTaskIcon(m.task)} {m.task.replace(/_/g, ' ')}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {loading && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                <div className="w-8 h-8 rounded-xl bg-white border flex items-center justify-center shadow-sm text-blue-600 animate-spin"><Sparkles size={16} /></div>
                <div className="glass-card-ai rounded-2xl rounded-tl-none px-5 py-4 flex items-center gap-3">
                  <span className="text-xs font-black text-slate-400 uppercase tracking-widest animate-pulse">Processing...</span>
                </div>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <div className="p-4 bg-white/20 backdrop-blur-md border-t border-white/20">
            <div className="max-w-4xl mx-auto relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask anything..."
                className="w-full bg-white/80 border border-slate-200 rounded-2xl pl-6 pr-14 py-4 focus:outline-none focus:ring-4 focus:ring-blue-100 transition-all text-slate-800 font-bold shadow-xl"
              />
              <button onClick={handleSend} disabled={loading} 
                className="absolute right-2 top-2 p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl shadow-lg active:scale-90 transition-all">
                <Send size={20} />
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
