# Copyright 2025 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


{
    "name": "Module Info Pull Request Task Link",
    "summary": "Allow to link PR to a task",
    "version": "16.0.1.0.0",
    "development_status": "Alpha",
    "category": "Uncategorized",
    "website": "https://github.com/akretion/partner-module-information",
    "author": " Akretion",
    "license": "AGPL-3",
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "module_info_pull_request",
        "project_reviewer",
    ],
    "data": [
        "views/project_project_view.xml",
        "views/project_task_view.xml",
        "views/pull_request_view.xml",
    ],
    "demo": [],
}
