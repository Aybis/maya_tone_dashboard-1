import React, { useState, useEffect } from 'react';

function ProjectOverview() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // useEffect(() => {
  //   fetchProjectsOverview();
  // }, []);

  const fetchProjectsOverview = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/projects/overview');
      const data = await response.json();

      if (data.success) {
        setProjects(data.projects);
      } else {
        setError(data.error || 'Failed to fetch projects');
      }
    } catch (err) {
      setError('Network error occurred');
    } finally {
      setLoading(false);
    }
  };

  const renderCollaborators = (collaborators, totalCollaborators) => {
    const maxVisible = 2;
    const visibleCollaborators = collaborators.slice(0, maxVisible);
    const remainingCount = totalCollaborators - maxVisible;

    return (
      <div className="flex items-center space-x-1">
        {visibleCollaborators.map((collaborator, index) => (
          <div
            key={index}
            className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-medium overflow-hidden ring-2 ring-blue-500/20"
            title={collaborator.displayName}
          >
            {collaborator.avatar ? (
              <img
                src={collaborator.avatar}
                alt={collaborator.displayName}
                className="w-full h-full object-cover"
              />
            ) : (
              collaborator.displayName.charAt(0).toUpperCase()
            )}
          </div>
        ))}
        {remainingCount > 0 && (
          <div className="w-8 h-8 rounded-full bg-slate-600/80 flex items-center justify-center text-white text-xs font-medium ring-2 ring-slate-500/20">
            +{remainingCount}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center py-12 text-slate-400">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          Loading projects...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded text-center">
          Error: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <header className="mb-8 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-50 mb-1">
            Project Overview
          </h1>
          <p className="text-slate-400">
            Overview of projects you're involved in
          </p>
        </div>
        <button
          onClick={fetchProjectsOverview}
          className="px-3 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors"
          disabled={loading}
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </header>

      {projects.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <div className="mb-4">
            <svg
              className="w-16 h-16 mx-auto text-slate-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-slate-300 mb-2">
            No projects found
          </h3>
          <p className="text-slate-500">
            You're not currently involved in any projects, or there might be an
            issue connecting to Jira.
          </p>
        </div>
      ) : (
        <div className="bg-[#0f0f23]/90 border border-blue-500/20 rounded-xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-blue-500/20 bg-gradient-to-r from-[#0f0f23]/80 to-[#1a1a2e]/80">
                  <th className="text-left py-5 px-6 text-slate-200 font-semibold text-sm uppercase tracking-wider">
                    Project Name
                  </th>
                  <th className="text-left py-5 px-6 text-slate-200 font-semibold text-sm uppercase tracking-wider">
                    Project Lead
                  </th>
                  <th className="text-left py-5 px-6 text-slate-200 font-semibold text-sm uppercase tracking-wider">
                    Category
                  </th>
                  <th className="text-left py-5 px-6 text-slate-200 font-semibold text-sm uppercase tracking-wider">
                    Total Epic
                  </th>
                  <th className="text-left py-5 px-6 text-slate-200 font-semibold text-sm uppercase tracking-wider">
                    Collaborators
                  </th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project, index) => (
                  <tr
                    key={project.projectKey}
                    className="border-b border-blue-500/10 hover:bg-gradient-to-r hover:from-blue-500/5 hover:to-purple-500/5 transition-all duration-200 group"
                  >
                    <td className="py-5 px-6">
                      <div className="flex flex-col">
                        <span className="text-slate-100 font-semibold text-base group-hover:text-blue-300 transition-colors">
                          {project.projectName}
                        </span>
                        <span className="text-slate-400 text-sm font-mono bg-slate-800/50 px-2 py-1 rounded-md inline-block mt-1 w-fit">
                          {project.projectKey}
                        </span>
                      </div>
                    </td>
                    <td className="py-5 px-6">
                      <div className="flex items-center space-x-3">
                        <div className="relative">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-sm font-bold overflow-hidden ring-2 ring-blue-500/20">
                            {project.projectLead.avatar ? (
                              <img
                                src={project.projectLead.avatar}
                                alt={project.projectLead.name}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              project.projectLead.name.charAt(0).toUpperCase()
                            )}
                          </div>
                          <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-[#0f0f23]"></div>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-slate-200 font-medium">
                            {project.projectLead.name}
                          </span>
                          <span className="text-slate-400 text-xs">
                            Project Lead
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-5 px-6">
                      <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-blue-300 border border-blue-500/30 shadow-sm">
                        {project.projectCategory}
                      </span>
                    </td>
                    <td className="py-5 px-6">
                      <div className="flex items-center space-x-2">
                        <div className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 rounded-lg px-3 py-2 border border-green-500/30">
                          <span className="text-2xl font-bold text-green-300">
                            {project.totalEpics}
                          </span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-slate-400 text-xs">Total</span>
                          <span className="text-slate-400 text-xs">Epics</span>
                        </div>
                      </div>
                    </td>
                    <td className="py-5 px-6">
                      {project.totalCollaborators > 0 ? (
                        <div className="flex items-center space-x-3">
                          <div className="flex items-center space-x-1">
                            {renderCollaborators(
                              project.collaborators,
                              project.totalCollaborators,
                            )}
                          </div>
                          <div className="flex flex-col">
                            <span className="text-slate-200 font-medium">
                              {project.totalCollaborators}
                            </span>
                            <span className="text-slate-400 text-xs">
                              collaborators
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-2">
                          <div className="w-8 h-8 rounded-full bg-slate-600/50 flex items-center justify-center">
                            <span className="text-slate-400 text-xs">—</span>
                          </div>
                          <span className="text-slate-400 text-sm">
                            No collaborators
                          </span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProjectOverview;
