import React from 'react';
import Modal from '../organism/Modal';

export default function ModalLogout({
  modalActive,
  closeLogoutModal,
  onLogout,
}) {
  return (
    <Modal modalActive={modalActive} closeModal={closeLogoutModal}>
      <div
        className={`relative bg-[#0b1220] border border-blue-500/20 rounded-md p-4 w-11/12 max-w-sm z-10 transform transition-all duration-200 ease-out ${
          modalActive
            ? 'opacity-100 translate-y-0 scale-100'
            : 'opacity-0 -translate-y-3 scale-95'
        }`}
      >
        <div className="text-sm text-slate-200 font-semibold mb-2">
          Confirm logout
        </div>
        <div className="text-xs text-slate-400 mb-4">
          Are you sure you want to logout?
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={closeLogoutModal}
            className="px-3 py-1 text-xs rounded bg-slate-700 text-slate-200 hover:bg-slate-600"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              // trigger parent to close modal (runs animation) then call onLogout
              closeLogoutModal();
              setTimeout(() => {
                onLogout();
              }, 250);
            }}
            className="px-3 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-500"
          >
            Logout
          </button>
        </div>
      </div>
    </Modal>
  );
}
