import React from "react";
import Avatar from "./ui/Avatar";
import InlineArtifactBlock from "./InlineArtifactBlock";

export default function MessageBubble({
  msg,
  index,
  panelOpen,
  renderMarkdown,
  onExpandArtifact,
  copyToClipboard,
}) {
  const isUser = msg.sender === "user";
  const widthClass = panelOpen ? "max-w-3xl" : "max-w-2xl";
  return (
    <div
      key={index}
      className={`group relative flex items-start gap-3 my-6 ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      <Avatar sender={msg.sender} />
      <div
        className={`${widthClass} w-fit ${
          isUser ? "ml-auto" : ""
        } rounded-lg prose prose-invert prose-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 p-3"
            : "bg-slate-700/70 p-4 border border-blue-500/10"
        } [&_pre]:bg-slate-900 [&_pre]:p-3 [&_pre]:rounded-md [&_code]:text-pink-300 [&_a]:text-blue-300 [&_table]:w-full [&_table]:text-xs [&_table]:border [&_table]:border-slate-600/50 [&_th]:bg-slate-800/70 [&_th]:border [&_th]:border-slate-700/50 [&_td]:border [&_td]:border-slate-700/50 [&_tbody_tr:nth-child(even)]:bg-slate-800/30 overflow-x-scroll`}
      >
        <div
          dangerouslySetInnerHTML={{
            __html: renderMarkdown(msg.cleaned || msg.content),
          }}
        />
        {!isUser &&
          msg.artifacts &&
          msg.artifacts.map((a) => (
            <InlineArtifactBlock
              key={a.id}
              artifact={a}
              onExpand={() => onExpandArtifact(a)}
            />
          ))}
        {!isUser && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-2 text-[10px] mt-2 overflow-x-auto">
            <button
              onClick={() => copyToClipboard(msg.content)}
              className="px-2 py-1 rounded bg-slate-800/70 hover:bg-slate-700 text-slate-300"
            >
              Copy
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
