import React from 'react';
import RenderIf from '../atoms/RenderIf';
import { ArrowRightOnRectangleIcon } from '@heroicons/react/24/solid';

export default function FooterSidebar({ showSidebar, openLogoutModal }) {
  return (
    <div className="p-4 border-t border-blue-500/10 mt-auto">
      <RenderIf condition={showSidebar}>
        <button
          onClick={openLogoutModal}
          className="w-full text-xs text-slate-400 hover:text-red-400 py-2 px-3 rounded border border-slate-600 hover:border-red-500/50 transition-colors"
        >
          Logout
        </button>
        <div className="text-[10px] text-slate-500 mt-2 text-center">
          © {new Date().getFullYear()} Maya - Tone
        </div>
      </RenderIf>

      <RenderIf condition={!showSidebar}>
        <div className="flex justify-center">
          <button
            onClick={openLogoutModal}
            title="Logout"
            aria-label="Logout"
            className="p-2 rounded hover:bg-blue-100/20 transition-colors"
          >
            <ArrowRightOnRectangleIcon className="h-5 w-5 text-red-400" />
          </button>
        </div>
      </RenderIf>
    </div>
  );
}
