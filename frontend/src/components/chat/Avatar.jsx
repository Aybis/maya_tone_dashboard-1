import React from 'react';

export default function Avatar({ sender, size = 40 }) {
  const isUser = sender === 'user';
  const dimension = `${size}px`;
  return (
    <div
      className={`flex-shrink-0 rounded-full flex items-center justify-center text-white font-semibold shadow-sm ring-1 ring-slate-900/40 ${
        isUser ? 'bg-blue-500' : 'bg-slate-600'
      }`}
      style={{ width: dimension, height: dimension, marginTop: 2 }}
    >
      {isUser ? 'U' : 'M'}
    </div>
  );
}
