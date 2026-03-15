"use client";

import { useState, useEffect } from "react";
import { getRawMemories, importMemories } from "@/lib/api";
import { logger } from "@/lib/logger";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, Database, Check, ShieldCheck, RefreshCcw, Save, Plus } from "lucide-react";
import Link from "next/link";

export default function MemoryReview() {
  const [categories, setCategories] = useState<Record<string, string[]>>({});
  const [selectedFacts, setSelectedFacts] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [success, setSuccess] = useState(false);
  
  // Pagination State
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    fetchMemories(0);
  }, []);

  const fetchMemories = async (currentOffset: number, append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);

    try {
      const data = await getRawMemories(currentOffset, 50);
      
      const foundNewFacts = Object.keys(data.categories || {}).length > 0;
      
      if (append) {
        setCategories(prev => {
          const next = { ...prev };
          Object.entries(data.categories || {}).forEach(([cat, facts]: [string, any]) => {
            next[cat] = Array.from(new Set([...(next[cat] || []), ...facts]));
          });
          return next;
        });
      } else {
        setCategories(data.categories || {});
      }

      setHasMore(data.has_more);
      setTotalCount(data.total);
      const nextOffset = data.next_offset || currentOffset;
      setOffset(nextOffset);

      // Auto-select new facts
      const newSelections = new Set(selectedFacts);
      Object.values(data.categories || {}).forEach((list: any) => {
        list.forEach((f: string) => newSelections.add(f));
      });
      setSelectedFacts(newSelections);

      // AUTO-SCAN LOGIC: If no facts found and hasMore, keep going
      if (!foundNewFacts && data.has_more) {
        logger.info(`No facts in offset ${currentOffset}, auto-scanning next...`);
        return fetchMemories(nextOffset, true);
      }

    } catch (e) {
      logger.error("Failed to fetch memories", e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const handleLoadMore = () => {
    if (hasMore && !loadingMore) {
      fetchMemories(offset, true);
    }
  };

  const toggleFact = (fact: string) => {
    const next = new Set(selectedFacts);
    if (next.has(fact)) next.delete(fact);
    else next.add(fact);
    setSelectedFacts(next);
  };

  const handleImport = async () => {
    if (selectedFacts.size === 0) return;
    setSyncing(true);
    try {
      await importMemories(Array.from(selectedFacts));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 5000);
    } catch (e) {
      logger.error("Import failed", e);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="theme-glass min-h-screen p-4 md:p-8">
      <div className="max-w-4xl mx-auto space-y-8 pb-32">
        {/* Header */}
        <header className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-bold uppercase text-xs tracking-widest">
            <ChevronLeft size={20} /> Back to Assistant
          </Link>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-[10px] font-black uppercase text-slate-400">Scan Progress</p>
              <p className="text-xs font-bold text-slate-600">{Math.min(offset, totalCount)} / {totalCount} Raw Emails</p>
            </div>
            <button onClick={() => { setOffset(0); fetchMemories(0); }} className="p-2 text-slate-400 hover:text-blue-600 transition-colors">
              <RefreshCcw size={20} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </header>

        <section className="glass-panel p-8 rounded-[40px] relative overflow-hidden">
          <div className="relative z-10">
            <div className="flex items-center gap-4 mb-2">
              <div className="bg-blue-600 p-2 rounded-xl text-white shadow-lg shadow-blue-200">
                <Database size={24} />
              </div>
              <h1 className="text-3xl font-black uppercase tracking-tighter text-slate-800">Memory Review</h1>
            </div>
            <p className="text-slate-500 font-medium text-sm max-w-xl">
              Showing {Object.values(categories).flat().length} unique facts extracted from your first {offset} emails.
            </p>
          </div>
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <ShieldCheck size={120} />
          </div>
        </section>

        {loading && offset === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            <p className="font-black uppercase tracking-widest text-[10px] text-slate-400">Analyzing first batch...</p>
          </div>
        ) : Object.keys(categories).length === 0 ? (
          <div className="glass-panel p-20 rounded-[40px] text-center flex flex-col items-center gap-4">
            <p className="text-slate-400 font-bold italic">No new memories found in this batch.</p>
            {hasMore && (
               <button 
                onClick={handleLoadMore} 
                disabled={loadingMore}
                className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-black uppercase tracking-widest text-[10px] px-8 py-4 rounded-2xl shadow-xl transition-all active:scale-95 flex items-center gap-2"
               >
                 {loadingMore ? <RefreshCcw size={14} className="animate-spin" /> : <Plus size={14} />}
                 {loadingMore ? "Searching..." : "Try Next 50 Emails"}
               </button>
            )}
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(categories).map(([category, facts]) => (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} key={category} className="space-y-4">
                <h2 className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-600 ml-2">{category}</h2>
                <div className="grid gap-3">
                  {facts.map((fact, idx) => (
                    <div 
                      key={idx} 
                      onClick={() => toggleFact(fact)}
                      className={`glass-panel p-4 rounded-2xl cursor-pointer transition-all flex items-center justify-between group ${selectedFacts.has(fact) ? "border-blue-500/50 bg-blue-50/50" : "hover:border-slate-300"}`}
                    >
                      <p className={`text-sm font-bold ${selectedFacts.has(fact) ? "text-slate-800" : "text-slate-500"}`}>{fact}</p>
                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center transition-all ${selectedFacts.has(fact) ? "bg-blue-600 text-white" : "border-2 border-slate-200 group-hover:border-slate-300"}`}>
                        {selectedFacts.has(fact) && <Check size={14} strokeWidth={4} />}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}

            {hasMore && (
              <div className="flex justify-center py-8">
                <button 
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="flex items-center gap-2 px-8 py-4 bg-white border border-slate-200 rounded-2xl font-black uppercase tracking-widest text-[10px] text-slate-500 hover:bg-slate-50 transition-all shadow-sm active:scale-95"
                >
                  {loadingMore ? <RefreshCcw size={14} className="animate-spin" /> : <Plus size={14} />}
                  {loadingMore ? "Processing Next 50..." : "Load Next 50 Emails"}
                </button>
              </div>
            )}

            {/* Footer Action */}
            <footer className="fixed bottom-8 left-0 right-0 z-50 px-4 md:px-8 pointer-events-none">
              <div className="max-w-4xl mx-auto glass-panel p-4 rounded-3xl shadow-2xl flex items-center justify-between gap-6 border-t border-white/50 backdrop-blur-xl pointer-events-auto">
                <div className="flex flex-col ml-4">
                  <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Approved for Import</span>
                  <span className="text-xl font-black text-blue-600">{selectedFacts.size} <span className="text-slate-400 text-sm">facts</span></span>
                </div>
                <button 
                  onClick={handleImport}
                  disabled={syncing || selectedFacts.size === 0}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-black uppercase tracking-widest text-xs px-8 py-4 rounded-2xl shadow-xl shadow-blue-200 transition-all active:scale-95 flex items-center gap-2"
                >
                  {syncing ? (
                    <RefreshCcw size={16} className="animate-spin" />
                  ) : success ? (
                    <Check size={16} />
                  ) : (
                    <Save size={16} />
                  )}
                  {syncing ? "Syncing..." : success ? "Synced!" : "Commit to Memory"}
                </button>
              </div>
            </footer>
          </div>
        )}
      </div>

      <AnimatePresence>
        {success && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed bottom-32 left-1/2 -translate-x-1/2 bg-green-600 text-white px-8 py-4 rounded-2xl shadow-2xl font-bold flex items-center gap-3 z-[60]"
          >
            <ShieldCheck size={20} /> Successfully imported facts into Cloud Memory!
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
