"use client";

import { useState, useEffect, useRef } from "react";
import { sendMessage, getAuthStatus, getLoginUrl } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Send, User, Bot, Sparkles, Database, Search, Mail, FileText, Trash2 } from "lucide-react";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string; task?: string }[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<string | null>(null);
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
      setMessages(prev => [...prev, { role: "assistant", content: "**Error:** AI connection lost. Please check the backend." }]);
    } finally {
      setLoading(false);
      setCurrentTask(null);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setHistory([]);
  };

  const getTaskIcon = (task?: string) => {
    if (!task) return <Sparkles size={14} />;
    if (task.includes("gmail")) return <Mail size={14} />;
    if (task.includes("drive")) return <FileText size={14} />;
    if (task.includes("search")) return <Search size={14} />;
    if (task.includes("memory")) return <Database size={14} />;
    return <Sparkles size={14} />;
  };

  if (authenticated === null) return <div className="flex h-screen items-center justify-center font-bold text-blue-600 animate-pulse text-2xl">Initializing...</div>;

  if (!authenticated) {
    return (
      <div className="flex h-screen flex-col items-center justify-center p-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-12 rounded-3xl text-center max-w-md w-full">
          <Sparkles className="mx-auto mb-6 text-blue-600" size={48} />
          <h1 className="text-4xl font-black mb-4 tracking-tighter text-slate-800">AI Personal Assistant</h1>
          <p className="text-slate-500 mb-8 font-medium">Your private intelligence layer, connected to your world.</p>
          <button onClick={async () => { const { url } = await getLoginUrl(); window.location.href = url; }} 
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-2xl shadow-xl transition-all active:scale-95">
            Login with Google
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto p-4 md:p-6 gap-4 font-sans text-slate-900">
      {/* Header */}
      <header className="glass-panel px-6 py-4 rounded-3xl flex justify-between items-center shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-xl text-white shadow-lg shadow-blue-200">
            <Sparkles size={20} />
          </div>
          <h1 className="font-black text-xl tracking-tighter uppercase">Assistant</h1>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={clearChat} className="p-2 text-slate-400 hover:text-red-500 transition-colors" title="Clear History">
            <Trash2 size={20} />
          </button>
          <div className="flex items-center gap-2 bg-green-50 px-3 py-1.5 rounded-full border border-green-100">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-[10px] font-black text-green-700 tracking-widest uppercase">Secured</span>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <main className="flex-1 glass-panel rounded-3xl overflow-hidden flex flex-col relative">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 hide-scrollbar">
          <AnimatePresence initial={false}>
            {messages.length === 0 && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full flex flex-col items-center justify-center text-center opacity-40 py-20">
                <div className="bg-slate-100 p-6 rounded-full mb-4"><Database size={40} className="text-slate-400" /></div>
                <p className="text-xl font-bold italic">Search your life. Ask me anything.</p>
              </motion.div>
            )}
            {messages.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} 
                className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border text-slate-400"}`}>
                  {m.role === "user" ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className={`max-w-[85%] rounded-2xl px-5 py-3.5 shadow-sm ${m.role === "user" ? "glass-card-user rounded-tr-none" : "glass-card-ai rounded-tl-none font-medium"}`}>
                  <div className="prose prose-sm max-w-none text-inherit leading-relaxed break-words prose-p:my-1 prose-headings:mb-2 prose-headings:mt-4">
                    <ReactMarkdown>
                      {m.content}
                    </ReactMarkdown>
                  </div>
                  {m.task && (
                    <div className="mt-3 pt-2 border-t border-slate-100/20 flex items-center gap-2 text-[10px] font-bold opacity-60 uppercase tracking-widest">
                      {getTaskIcon(m.task)}
                      Source: {m.task.replace(/_/g, ' ')}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-white border flex items-center justify-center shadow-sm text-blue-600"><Bot size={16} /></div>
              <div className="glass-card-ai rounded-2xl rounded-tl-none px-5 py-4 flex items-center gap-3">
                <div className="flex gap-1.5">
                  <div className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs font-bold text-slate-400 italic">Thinking...</span>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-white/50 backdrop-blur-sm border-t border-white/30">
          <div className="max-w-4xl mx-auto relative group">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask your assistant..."
              className="w-full bg-white border border-slate-200 rounded-2xl pl-6 pr-14 py-4 focus:outline-none focus:ring-4 focus:ring-blue-100 transition-all text-slate-800 font-medium shadow-xl shadow-blue-900/5 placeholder:text-slate-300"
            />
            <button onClick={handleSend} disabled={loading} 
              className="absolute right-2 top-2 p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl transition-all shadow-lg shadow-blue-600/20 active:scale-90">
              <Send size={20} />
            </button>
          </div>
        </div>
      </main>
      
      <footer className="text-center pb-2">
        <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em]">Encrypted Cloud Intelligence v2.5</p>
      </footer>
    </div>
  );
}
