import React from 'react';
import { NavLink } from 'react-router-dom';

export default function MenuItem({ path, title }) {
  return (
    <NavLink
      to={path}
      end
      className={({ isActive }) =>
        `px-3 py-2 rounded-md text-sm font-medium ${
          isActive
            ? 'bg-blue-500/20 text-blue-300'
            : 'text-slate-400 hover:text-blue-300 hover:bg-blue-500/10'
        }`
      }
    >
      {title}
    </NavLink>
  );
}
