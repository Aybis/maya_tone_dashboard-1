import React, { useRef, useState } from 'react';

export default function ChatHero({ onSubmit, disabled }) {
  const [value, setValue] = useState('');
  const inputRef = useRef(null);

  const handleKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (value.trim()) {
        onSubmit({ contentOverride: value });
        setValue('');
      }
    }
  };

  const send = () => {
    if (!value.trim()) return;
    onSubmit({ contentOverride: value });
    setValue('');
  };

  return (
    <div className="w-full flex flex-col items-center gap-10 pt-28 md:pt-40 select-none">
      <h1 className="text-center text-lg md:text-2xl font-medium text-slate-200 tracking-wide">
        Hey,{' '}
        {typeof window !== 'undefined' && localStorage.getItem('username')
          ? localStorage.getItem('username')
          : 'User'}
        . Ready to dive in?
      </h1>
      <div className="w-full max-w-3xl px-4">
        <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-700/60 rounded-full pl-5 pr-2 py-2 shadow-sm backdrop-blur">
          <span className="text-slate-400 text-xl leading-none">+</span>
          <input
            ref={inputRef}
            className="flex-1 bg-transparent outline-none text-slate-100 text-sm md:text-base placeholder-slate-500"
            placeholder="Ask anything"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled}
          />
          <button
            onClick={send}
            disabled={disabled || !value.trim()}
            className="h-9 w-9 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 flex items-center justify-center text-white text-xs font-medium"
          >
            ↵
          </button>
        </div>
      </div>
      <p className="text-[10px] md:text-xs text-slate-500 text-center">
        Maya helps you manage JIRA tickets and worklogs (create, read, update,
        delete). It may make mistakes, so give clear instructions for best
        results.
      </p>
    </div>
  );
}
