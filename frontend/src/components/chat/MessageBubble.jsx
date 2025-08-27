import React, { useEffect, useRef, useState } from 'react';
import { marked } from 'marked';

export default function MessageBubble({
  message,
  isUser,
  sanitizeRender,
  transformAssistantContent,
  showTimeOnly = false,
}) {
  const baseClasses = 'rounded-xl text-sm break-words';
  const bubbleRef = useRef(null);
  const [bubbleTop, setBubbleTop] = useState(0);

  // Update bubbleTop in real time on scroll, resize, and animation frame
  useEffect(() => {
    let animationFrameId;
    const updatePosition = () => {
      if (bubbleRef.current) {
        setBubbleTop(bubbleRef.current.getBoundingClientRect().top);
      }
      animationFrameId = requestAnimationFrame(updatePosition);
    };
    window.addEventListener('scroll', updatePosition, { passive: true });
    window.addEventListener('resize', updatePosition);
    updatePosition();
    return () => {
      window.removeEventListener('scroll', updatePosition);
      window.removeEventListener('resize', updatePosition);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  // Helper to interpolate between two colors
  function interpolateColor(color1, color2, factor) {
    const c1 = color1.match(/\w\w/g).map((x) => parseInt(x, 16));
    const c2 = color2.match(/\w\w/g).map((x) => parseInt(x, 16));
    const result = c1.map((v, i) => Math.round(v + (c2[i] - v) * factor));
    return `#${result.map((x) => x.toString(16).padStart(2, '0')).join('')}`;
  }

  // Define color stops for gradient
  const stops = [
    { top: 0, from: '#d946ef', to: '#a21caf' }, // fuchsia-500 to fuchsia-600
    { top: 250, from: '#d946ef', to: '#6366f1' }, // fuchsia-500 to indigo-500
    { top: 500, from: '#6366f1', to: '#4338ca' }, // indigo-500 to indigo-600
    { top: 750, from: '#4338ca', to: '#4338ca' }, // indigo-600 to indigo-600
  ];

  function getSmoothGradient(top) {
    // Clamp top to [0, 750]
    const clampedTop = Math.max(0, Math.min(top, 750));
    let from = stops[0].from;
    let to = stops[0].to;
    for (let i = 1; i < stops.length; i++) {
      if (clampedTop <= stops[i].top) {
        const prev = stops[i - 1];
        const range = stops[i].top - prev.top;
        const factor = range === 0 ? 0 : (clampedTop - prev.top) / range;
        from = interpolateColor(prev.from, stops[i].from, factor);
        to = interpolateColor(prev.to, stops[i].to, factor);
        break;
      }
    }
    return `linear-gradient(135deg, ${from}, ${to})`;
  }

  if (isUser) {
    return (
      <div className="self-end flex flex-col items-end">
        <div
          ref={bubbleRef}
          className={`${baseClasses} text-white px-4 py-2 rounded-br-none`}
          style={{
            background: getSmoothGradient(bubbleTop),
            transition: 'background 0.5s cubic-bezier(0.4,0,0.2,1)',
          }}
        >
          {message.content}
        </div>
        {message.timestamp && (
          <span className="text-xs text-gray-400 mt-1 ">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
            })}
          </span>
        )}
      </div>
    );
  }

  const html = transformAssistantContent
    ? transformAssistantContent(message.content)
    : sanitizeRender(marked.parse(message.content));

  return (
    <div className="self-start w-full flex flex-col gap-1 ">
      <div
        ref={bubbleRef}
        className={`${baseClasses} text-zinc-100 w-fit prose prose-invert max-w-full [&_pre]:overflow-x-auto [&_table]:text-sm [&_table]:max-h-96 [&_table]:overflow-y-auto [&_th]:sticky [&_th]:top-0 [&_th]:bg-zinc-900/80 [&_.md-card]:mb-5 [&_.md-card:last-child]:mb-0 overflow-auto`}
        dangerouslySetInnerHTML={{ __html: html }}
      ></div>
      {message.timestamp && (
        <span className="text-xs text-gray-400 mt-1">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
          })}
        </span>
      )}
    </div>
  );
}
