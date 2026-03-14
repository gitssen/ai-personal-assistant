"use client";

import { useState, useEffect, useRef } from "react";
import { sendMessage, getAuthStatus, getLoginUrl } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    try {
      const data = await sendMessage(input, history);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
      setHistory(data.history);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error: Could not reach the AI." }]);
    } finally {
      setLoading(false);
    }
  };

  // Helper to render text with clickable links
  const renderContent = (text: string) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    return parts.map((part, i) => {
      if (part.match(urlRegex)) {
        return (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-700 underline break-all hover:text-blue-900"
          >
            {part}
          </a>
        );
      }
      return part;
    });
  };

  if (authenticated === null) return <div className="flex h-screen items-center justify-center">Loading...</div>;

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
        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full uppercase tracking-wider font-bold">Connected</span>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-20">
            <p className="text-lg font-bold">Ask me about your emails, drive, or photos!</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-2xl p-4 shadow-sm border ${
                m.role === "user" ? "bg-blue-600 text-white border-blue-700" : "bg-slate-100 text-black font-bold border-slate-300"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{renderContent(m.content)}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-50 text-slate-400 p-4 rounded-2xl animate-pulse font-bold">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t bg-white">
        <div className="max-w-4xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type your question..."
            className="flex-1 border-2 border-slate-200 rounded-full px-6 py-3 focus:outline-none focus:border-blue-500 text-black font-semibold"
          />
          <button onClick={handleSend} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-3 w-12 h-12 flex items-center justify-center shadow-md">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
