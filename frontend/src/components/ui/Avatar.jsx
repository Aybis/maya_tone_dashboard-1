import React from 'react';
export default function Avatar({ sender }) {
  const isUser = sender === 'user';
  const label = isUser ? 'U' : 'M';
  return (
    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold shadow ${isUser ? 'bg-blue-600 text-white' : 'bg-slate-500 dark:bg-slate-600 text-white'}`}>{label}</div>
  );
}