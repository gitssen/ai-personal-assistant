"use client";

import { useState, useEffect, useRef } from "react";
import { sendMessage, getAuthStatus, getLoginUrl } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const checkAuth = async () => {
    try {
      const status = await getAuthStatus();
      setAuthenticated(status.authenticated);
    } catch (e) {
      setAuthenticated(false);
    }
  };

  const handleLogin = async () => {
    const { url } = await getLoginUrl();
    window.location.href = url;
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setCurrentTask("Thinking...");

    try {
      // In a real app with long operations, we'd use WebSockets for real-time task updates.
      // Here, we simulate the 'Thinking' process until the response returns.
      const data = await sendMessage(input, history);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
      setHistory(data.history);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error: AI disconnected." }]);
    } finally {
      setLoading(false);
      setCurrentTask(null);
    }
  };

  const getTaskLabel = (task: string | null) => {
    if (!task) return "Thinking...";
    if (task.includes("search_gmail")) return "Searching your emails...";
    if (task.includes("search_drive")) return "Searching your files...";
    if (task.includes("read_drive_file")) return "Reading document content...";
    if (task.includes("read_gmail_message")) return "Reading full email thread...";
    if (task.includes("google_search")) return "Searching the web...";
    return "Analyzing data...";
  };

  const renderContent = (text: string) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    return parts.map((part, i) => {
      if (part.match(urlRegex)) {
        return <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline break-all font-bold">{part}</a>;
      }
      return part;
    });
  };

  if (authenticated === null) return <div className="flex h-screen items-center justify-center font-bold">Loading...</div>;

  if (!authenticated) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-white text-black">
        <h1 className="text-3xl font-bold mb-8">AI Personal Assistant</h1>
        <button onClick={handleLogin} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-full shadow-lg transition-all">
          Login with Google
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-white">
      <header className="p-4 border-b bg-slate-50 flex justify-between items-center">
        <h1 className="font-bold text-xl text-blue-600 uppercase tracking-tighter">AI Personal Assistant</h1>
        <div className="flex items-center gap-2">
          {loading && <span className="text-xs font-black text-orange-500 animate-pulse uppercase tracking-widest">Processing...</span>}
          <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase tracking-wider font-bold border border-green-200">Connected</span>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/30">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-20">
            <p className="text-lg font-bold">What can I help you find today?</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl p-4 shadow-sm border ${m.role === "user" ? "bg-blue-600 text-white border-blue-700" : "bg-white text-black font-bold border-slate-200"}`}>
              <p className="whitespace-pre-wrap leading-relaxed text-sm md:text-base">{renderContent(m.content)}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border-2 border-slate-100 text-slate-500 p-4 rounded-2xl flex items-center gap-3 shadow-sm">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              <span className="font-bold text-sm ml-2 italic">{getTaskLabel(currentTask)}</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t bg-white shadow-inner">
        <div className="max-w-4xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type your message..."
            className="flex-1 border-2 border-slate-200 rounded-xl px-6 py-3 focus:outline-none focus:border-blue-500 text-black font-semibold shadow-sm transition-all"
          />
          <button onClick={handleSend} disabled={loading} className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl px-6 py-3 font-bold transition-all shadow-md flex items-center justify-center">
            {loading ? '...' : 'SEND'}
          </button>
        </div>
      </div>
    </div>
  );
}
