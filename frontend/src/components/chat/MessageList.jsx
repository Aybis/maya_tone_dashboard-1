import React from 'react';
import Avatar from './Avatar';
import MessageBubble from './MessageBubble';
import ExportDownload from './ExportDownload';
import ChartRenderer from './ChartRenderer';

export default function MessageList({
  messages,
  getExportForId,
  extractChartSpec,
  sanitizeRender,
  transformAssistantContent,
}) {
  return (
    <div className="flex flex-col gap-6 w-full">
      {messages.map((msg) => {
        const isUser = msg.sender === 'user';
        const chartSpec = extractChartSpec(msg.content);
        const exportData = getExportForId(msg.id);
        return (
          <div
            key={msg.id}
            className={`flex items-start w-full gap-4 ${
              isUser ? 'justify-end' : ''
            }`}
          >
            {!isUser && <Avatar sender={msg.sender} size={40} />}
            <div
              className={`flex flex-col gap-2 max-w-full ${
                isUser ? 'items-end' : 'w-full'
              }`}
            >
              <MessageBubble
                message={msg}
                isUser={isUser}
                sanitizeRender={sanitizeRender}
                transformAssistantContent={transformAssistantContent}
              />
              {chartSpec && <ChartRenderer spec={chartSpec} />}
              {!isUser && exportData && (
                <ExportDownload exportData={exportData} />
              )}
            </div>
            {isUser && <Avatar sender={msg.sender} size={40} />}
          </div>
        );
      })}
    </div>
  );
}
