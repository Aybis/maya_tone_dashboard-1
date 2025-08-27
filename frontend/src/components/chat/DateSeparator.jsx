import React from 'react';

export default function DateSeparator({ date }) {
  // Format: Monday, August 25, 2025
  const formatted = new Date(date).toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
  return (
    <div className="flex justify-center my-2">
      <span className="bg-gray-200 text-gray-600 text-xs px-3 py-1 rounded-full shadow-sm">
        {formatted}
      </span>
    </div>
  );
}
