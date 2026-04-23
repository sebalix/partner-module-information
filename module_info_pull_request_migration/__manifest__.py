# Copyright 2025 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Module Info Pull Request Migration",
    "summary": "Link pull request to migration task",
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
        "module_info_pull_request_task_link",
        "module_info_migration",
    ],
    "data": [
        "data/ir_cron.xml",
        "data/mail_template.xml",
    ],
    "demo": [],
}
