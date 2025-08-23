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
    <div className="border-t border-slate-800 p-4 bg-slate-950 ">
      <div className="flex gap-3 items-end max-w-3xl mx-auto">
        <textarea
          ref={inputRef}
          className="flex-1 resize-none rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-400 px-3 py-2 text-sm bg-slate-800"
          placeholder="Ask something..."
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <button
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md shadow"
        >
          Send
        </button>
      </div>
    </div>
  );
}
