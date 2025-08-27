import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import React, { useCallback, useRef, useEffect } from 'react';

export default function ChatInput({ value, onChange, onSubmit, disabled }) {
  const inputRef = useRef(null);

  const adjustHeight = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const max = 220;
    el.style.height = Math.min(el.scrollHeight, max) + 'px';
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className=" backdrop-blur-md border-b-none p-4 pb-6 mb-4">
      <div className="flex max-w-6xl mx-auto gap-3">
        <div className="relative flex-1">
          <div className="group/neon relative w-full rounded-3xl p-[2px] bg-gradient-to-r from-cyan-400 via-indigo-400 to-fuchsia-500 gradient-animate-x">
            {/* Glow layer */}
            <div className="absolute inset-0 rounded-3xl blur-xl opacity-0 group-focus-within/neon:opacity-70 transition-opacity duration-300 bg-gradient-to-r from-cyan-400 via-indigo-400 to-fuchsia-500" />
            <textarea
              ref={inputRef}
              className="relative z-10 flex-1 w-full resize-none rounded-3xl bg-zinc-900/80 backdrop-blur border border-white/5 focus:outline-none focus:ring-0 text-sm leading-relaxed scrollbar-thin px-5 py-5 pr-20 placeholder:text-zinc-400 text-zinc-100"
              placeholder="Ask something..."
              rows={1}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
            />
            <button
              onClick={onSubmit}
              aria-label="Send message"
              disabled={disabled || !value.trim()}
              className="absolute z-20 bottom-4 right-4 h-12 w-12 flex items-center justify-center rounded-full disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none group/button"
            >
              <span className="absolute inset-0 rounded-full p-[2px] bg-gradient-to-br from-cyan-400 via-indigo-400 to-fuchsia-500 opacity-80 group-hover/button:opacity-100 group-active/button:scale-95 transition-all duration-300"></span>
              <span className="absolute inset-0 rounded-full blur-lg bg-gradient-to-br from-cyan-400/40 via-indigo-400/30 to-fuchsia-500/40 opacity-0 group-hover/button:opacity-70 group-focus-visible/button:opacity-80 transition-opacity duration-300"></span>
              <span className="relative rounded-full h-full w-full flex items-center justify-center bg-zinc-900/90 backdrop-blur-sm border border-white/10 group-hover/button:border-white/20 transition-colors">
                <PaperAirplaneIcon className="h-5 -rotate-45 text-cyan-200 group-hover/button:text-fuchsia-200 transition-colors" />
              </span>
            </button>
          </div>
        </div>
      </div>

      <p className="text-[10px] md:text-sm text-zinc-400 text-center mt-2">
        Maya may make mistakes, so give clear instructions for best results.
      </p>
    </div>
  );
}
