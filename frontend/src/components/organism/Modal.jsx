import React from 'react';

export default function Modal({ modalActive, closeModal, children }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      {/* backdrop */}
      <div
        className={`absolute inset-0 bg-black transition-opacity duration-200 ease-out ${
          modalActive ? 'opacity-50' : 'opacity-0'
        }`}
        onClick={closeModal}
      />

      {/* panel */}
      {children}
    </div>
  );
}
