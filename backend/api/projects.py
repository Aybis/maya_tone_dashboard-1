from flask import Blueprint, jsonify
from ..jira_utils import JiraManager
from collections import Counter
import requests
from requests.auth import HTTPBasicAuth

projects_bp = Blueprint("projects", __name__)

def _mgr():
    """JiraManager using session credentials."""
    return JiraManager()

@projects_bp.route("/api/projects/overview", methods=["GET"])
def get_projects_overview():
    """Get project overview data for projects where the current user is involved."""
    try:
        jira_manager = _mgr()
        if not jira_manager or not jira_manager.session:
            return jsonify({"success": False, "error": "Jira connection not available"}), 400

        # Get current user
        current_user = jira_manager.get_current_user()
        username = current_user.get("name") or "currentUser()"
        
        # Search for issues where the current user is involved (assignee, reporter, or has worked on)
        user_involvement_jql = f"(assignee = '{username}' OR reporter = '{username}' OR worklogAuthor = '{username}') AND resolution = Unresolved"
        user_issues = jira_manager.search_issues(user_involvement_jql, 1000)
        
        # Extract unique project keys from the issues
        user_project_keys = set()
        for issue in user_issues:
            project_key = issue.get("fields", {}).get("project", {}).get("key")
            if project_key:
                user_project_keys.add(project_key)

        project_overview = []
        
        # Get details for each project the user is involved in
        for project_key in user_project_keys:
            # Get project details including lead
            project_detail_response = jira_manager.session.get(
                f"{jira_manager.base_url}/rest/api/2/project/{project_key}"
            )
            
            if project_detail_response.status_code != 200:
                continue
                
            project_details = project_detail_response.json()
            project_name = project_details.get("name", project_key)
            
            # Get project lead
            project_lead = project_details.get("lead", {})
            project_lead_name = project_lead.get("displayName", "Unassigned")
            project_lead_avatar = project_lead.get("avatarUrls", {}).get("48x48", "")
            
            # Get project category
            project_category = project_details.get("projectCategory", {})
            category_name = project_category.get("name", "Uncategorized")
            
            # Count epics in this project
            epic_jql = f'project = "{project_key}" AND issuetype = "Epic"'
            epic_issues = jira_manager.search_issues(epic_jql, 1000)
            total_epics = len(epic_issues)
            
            # Get all collaborators (assignees, reporters, etc.) from recent issues
            collaborators_jql = f'project = "{project_key}" AND updated >= -90d'
            recent_issues = jira_manager.search_issues(collaborators_jql, 500)
            
            # Collect unique collaborators
            collaborators = {}
            for issue in recent_issues:
                fields = issue.get("fields", {})
                
                # Add assignee
                assignee = fields.get("assignee")
                if assignee and assignee.get("displayName"):
                    user_key = assignee.get("name", assignee.get("accountId", assignee.get("displayName", "")))
                    if user_key and user_key not in collaborators:
                        collaborators[user_key] = {
                            "displayName": assignee.get("displayName", "Unknown User"),
                            "avatar": assignee.get("avatarUrls", {}).get("48x48", "")
                        }
                
                # Add reporter
                reporter = fields.get("reporter")
                if reporter and reporter.get("displayName"):
                    user_key = reporter.get("name", reporter.get("accountId", reporter.get("displayName", "")))
                    if user_key and user_key not in collaborators:
                        collaborators[user_key] = {
                            "displayName": reporter.get("displayName", "Unknown User"),
                            "avatar": reporter.get("avatarUrls", {}).get("48x48", "")
                        }
            
            # Convert collaborators dict to list and limit to reasonable number
            collaborator_list = list(collaborators.values())#[:20]  # Limit to 20 collaborators max
            
            project_overview.append({
                "projectKey": project_key,
                "projectName": project_name,
                "projectLead": {
                    "name": project_lead_name,
                    "avatar": project_lead_avatar
                },
                "projectCategory": category_name,
                "totalEpics": total_epics,
                "collaborators": collaborator_list,
                "totalCollaborators": len(collaborator_list)
            })
        
        return jsonify({
            "success": True,
            "projects": project_overview
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to fetch project overview: {str(e)}"
        }), 500