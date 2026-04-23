# Copyright 2026  Akretion (https://www.akretion.com).
# @author Sébastien Alix <sebastien.alix@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, models
from odoo.osv import expression
from odoo.tools import groupby


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def cron_email_pull_requests_l1_reviewers(self):
        """Cron task sending an email to level 1 reviewers."""
        prs = self.env["pull.request"].search(self._pull_requests_l1_reviewers_domain())
        reviewers = prs.l1_internal_reviewer_ids
        for reviewer in reviewers:
            reviewer._send_email_l1_reviewer_pull_requests()
        return True

    @api.model
    def cron_email_pull_requests_l2_reviewers(self):
        """Cron task sending an email to level 2 reviewers."""
        prs = self.env["pull.request"].search(self._pull_requests_l2_reviewers_domain())
        reviewers = prs.l2_internal_reviewer_ids
        for reviewer in reviewers:
            reviewer._send_email_l2_reviewer_pull_requests()
        return True

    def _pull_requests_l1_reviewers_domain(self, users=None):
        domain = [
            ("state", "in", ("draft", "need_fix", "cancel", "waiting_review")),
            ("project_id", "!=", False),
        ]
        if users:
            user_domain = [("l1_internal_reviewer_ids", "in", users.ids)]
            domain = expression.AND([domain, user_domain])
        return domain

    def _pull_requests_l2_reviewers_domain(self, users=None):
        base_domain = [
            (
                "state",
                "in",
                (
                    "draft",
                    "need_fix",
                    "cancel",
                    "waiting_review",
                    "approved",
                    "approved_by_ak",
                ),
            ),
            ("project_id", "!=", False),
        ]
        internal_reviewers = self.search([("github_user_ids", "!=", False)])
        approval_domain = expression.OR(
            [
                [("state", "=", "approved")],
                [
                    (
                        "approved_reviewer_ids",
                        "in",
                        internal_reviewers.github_user_ids.ids,
                    )
                ],
            ]
        )
        domain = expression.AND([base_domain, approval_domain])
        if users:
            user_domain = [("l2_internal_reviewer_ids", "in", users.ids)]
            domain = expression.AND([domain, user_domain])
        return domain

    def _get_l1_pull_requests_by_project(self, migration_only=False):
        """Return the pull requests related to current level 1 reviewers.

        If `migration_only` is set, only PRs related to migration project will
        be returned.
        """
        prs = self.env["pull.request"].search(
            self._pull_requests_l1_reviewers_domain(users=self),
            order="state",
        )
        # Keep only PRs related to migration project
        if migration_only:
            prs = prs.filtered(
                lambda pr: pr.project_id.partner_id.target_odoo_version_id
                == pr.version_id
            )
        # NOTE: Convert defaultdict to dict so mail template doesn't crash.
        return dict(groupby(prs, key=lambda pr: pr.project_id))

    def _get_l2_pull_requests_by_project(self, migration_only=False):
        """Return the pull requests related to current level 2 reviewers.

        If `migration_only` is set, only PRs related to migration project will
        be returned.
        """
        prs = self.env["pull.request"].search(
            self._pull_requests_l2_reviewers_domain(users=self),
            order="state",
        )
        # Keep only PRs related to migration project
        if migration_only:
            prs = prs.filtered(
                lambda pr: pr.project_id.partner_id.target_odoo_version_id
                == pr.version_id
            )
        # NOTE: Convert defaultdict to dict so mail template doesn't crash.
        return dict(groupby(prs, key=lambda pr: pr.project_id))

    def _send_email_l1_reviewer_pull_requests(self):
        """Send pull requests status by e-mail to current level 1 reviewer."""
        self.ensure_one()
        template = self.env.ref(
            "module_info_pull_request_migration."
            "mail_template_pull_requests_l1_reviewer"
        )
        return template.send_mail(self.id)

    def _send_email_l2_reviewer_pull_requests(self):
        """Send pull requests status by e-mail to current level 2 reviewer."""
        self.ensure_one()
        template = self.env.ref(
            "module_info_pull_request_migration."
            "mail_template_pull_requests_l2_reviewer"
        )
        return template.send_mail(self.id)
