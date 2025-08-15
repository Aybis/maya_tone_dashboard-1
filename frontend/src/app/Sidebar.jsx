import RenderIf from '@/components/atoms/RenderIf';
import FooterSidebar from '@/components/templates/FooterSidebar';
import MenuHistoryChat from '@/components/templates/MenuHistoryChat';
import MenuItem from '@/components/templates/MenuItem';
import { ChevronLeftIcon, PlusIcon } from '@heroicons/react/24/solid';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import ModalLogout from '../components/templates/ModalLogout';
import { useChatContext } from '../context/ChatContext';

const Sidebar = ({ username, onLogout }) => {
  const { chats, createNewChat, deleteChat, renameChat, loadingChats } =
    useChatContext();
  const navigate = useNavigate();
  const location = useLocation();
  const [showSidebar, setshowSidebar] = useState(true);
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const openLogoutModal = (val) => {
    setShowLogoutModal(val);
    // allow next tick so transition classes apply
    setTimeout(() => setShowLogoutModal(true), 10);
  };

  // Extract second word from display name
  const getDisplayName = (fullName) => {
    const words = fullName.trim().split(/\s+/);
    return words.length >= 2 ? words[1] : words[0] || fullName;
  };

  const handleShowSidebar = () => {
    setshowSidebar(!showSidebar);
  };

  return (
    <>
      <aside
        className={[
          showSidebar ? 'w-64' : 'w-12',
          ' bg-[#0f0f23]/90 transition-all duration-500 backdrop-blur border-r border-blue-500/10 flex flex-col h-screen sticky top-0',
        ].join(' ')}
      >
        <div className="p-4 border-b border-blue-500/10 relative">
          <div
            className={[
              'flex items-center',
              showSidebar ? 'justify-between items-center' : 'justify-center',
            ].join(' ')}
          >
            <RenderIf condition={showSidebar}>
              <h1 className="text-blue-400 font-bold text-lg">Maya Tone </h1>
            </RenderIf>

            <button
              onClick={() => handleShowSidebar()}
              title="minimize"
              aria-label="minimize"
              className="p-2 rounded hover:bg-blue-100/20 transition-colors"
            >
              <ChevronLeftIcon
                className={[
                  !showSidebar ? 'rotate-180' : 'rotate-0',
                  'h-5 w-5 text-blue-500',
                ].join(' ')}
              />
            </button>
          </div>

          <RenderIf condition={showSidebar}>
            <div className="text-xs text-slate-400 mt-1">
              Welcome, {getDisplayName(username)}
            </div>

            <button
              onClick={async () => {
                const id = await createNewChat();
                if (id) navigate(`/chat/${id}`);
              }}
              className="text-sm transition-all duration-300 px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-500 w-full mt-4"
            >
              + New
            </button>
          </RenderIf>

          <RenderIf condition={!showSidebar}>
            <div className="flex justify-center mt-4">
              <button
                onClick={async () => {
                  const id = await createNewChat();
                  if (id) navigate(`/chat/${id}`);
                }}
                title="New chat"
                aria-label="New chat"
                className="p-2 rounded hover:bg-blue-100/20 transition-colors"
              >
                <PlusIcon className="h-5 w-5 text-blue-400" />
              </button>
            </div>
          </RenderIf>
        </div>

        <RenderIf condition={showSidebar}>
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-8">
            <div>
              <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                Main
              </h3>
              <nav className="flex flex-col gap-1">
                <MenuItem path="/" title="Dashboard" />
              </nav>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs uppercase tracking-wider text-slate-500">
                  History
                </h3>
              </div>
              <div className="space-y-1 h-full overflow-y-auto pr-1">
                {loadingChats && (
                  <div className="text-slate-500 text-xs">Loading...</div>
                )}
                {chats.map((c) => (
                  <MenuHistoryChat
                    key={c.id}
                    c={c}
                    location={location}
                    renameChat={renameChat}
                    deleteChat={deleteChat}
                  />
                ))}
                {!loadingChats && chats.length === 0 && (
                  <div className="text-slate-500 text-xs">No chats yet.</div>
                )}
              </div>
            </div>
          </div>
        </RenderIf>

        <FooterSidebar
          showSidebar={showSidebar}
          openLogoutModal={openLogoutModal}
        />
      </aside>

      <RenderIf condition={showLogoutModal}>
        <ModalLogout
          modalActive={showLogoutModal}
          closeLogoutModal={() => setShowLogoutModal(false)}
          onLogout={onLogout}
        />
      </RenderIf>
    </>
  );
};

export default Sidebar;
