import React from 'react';
import { marked } from 'marked';

export default function MessageBubble({
  message,
  isUser,
  sanitizeRender,
  transformAssistantContent,
}) {
  const baseClasses =
    'rounded-xl px-4 py-3 text-sm shadow-sm whitespace-pre-wrap break-words';
  const userSizing = (() => {
    // const len = message.content.length;
    // if (len < 50) return 'max-w-[55%]';
    // return 'max-w-[70%]'; // hard cap at 70%
  })();
  if (isUser) {
    return (
      <div className={`self-end ${userSizing}`}>
        <div className={`${baseClasses} bg-blue-500 text-white`}>
          {message.content}
        </div>
      </div>
    );
  }
  const html = transformAssistantContent
    ? transformAssistantContent(message.content)
    : sanitizeRender(marked.parse(message.content));
  return (
    <div className="self-start w-full flex flex-col gap-3 ">
      <div
        className={`${baseClasses} bg-slate-800/70 border border-slate-700/70 text-slate-100 w-fit prose prose-invert max-w-full [&_pre]:overflow-x-auto [&_table]:text-xs [&_table]:max-h-96 [&_table]:overflow-y-auto [&_th]:sticky [&_th]:top-0 [&_th]:bg-slate-900/80 [&_.md-card]:mb-5 [&_.md-card:last-child]:mb-0 overflow-auto`}
        dangerouslySetInnerHTML={{ __html: html }}
      ></div>
    </div>
  );
}
