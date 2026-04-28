import logging
import re
from datetime import date

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from ..tools import naive_dt

_logger = logging.getLogger(__name__)


class PullRequest(models.Model):
    _name = "pull.request"

    title = fields.Char(index=True, readonly=True)
    repo_id = fields.Many2one(
        "module.repo", string="Host Repository", index=True, readonly=True
    )
    date_open = fields.Datetime(string="Opening Date", readonly=True)
    date_updated = fields.Datetime(string="Date of Last Update", readonly=True)
    date_closed = fields.Datetime(string="Date of close", readonly=True)
    module_ids = fields.Many2many(
        "module.information", string="Related Modules", readonly=True
    )
    version_id = fields.Many2one("odoo.version", readonly=True, index=True)
    is_dead = fields.Boolean(
        inverse="_inverse_is_dead",
        help=(
            "A PR could be canceled automatically, and could be re-opened later."
            ' But PR canceled on purpose can be flagged as "dead", so we don\'t'
            " get back on it."
        ),
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("need_reviewer", "Need Reviewer"),
            ("waiting_review", "Waiting Review"),
            ("need_fix", "Need Fix"),
            ("approved", "Approved"),
            ("approved_by_ak", "Approved by Ak."),
            ("done", "Merged"),
            ("cancel", "Cancel"),
            ("dead", "Dead"),
        ],
        index=True,
        readonly=True,
    )
    date_last_state_changed = fields.Date(readonly=True)
    url = fields.Char(readonly=True)
    number = fields.Integer(index=True, string="Github number", readonly=True)
    author = fields.Char(index=True, readonly=True)
    orga = fields.Char(index=True, readonly=True)
    need_review = fields.Boolean(string="Review requested")
    author_user_id = fields.Many2one(
        "res.users", compute="_compute_author_user_id", store=True
    )
    waiting_reviewer_ids = fields.Many2many(
        "github.user",
        relation="github_user_pull_request_waiting_rel",
        readonly=True,
    )
    approved_reviewer_ids = fields.Many2many(
        "github.user",
        relation="github_user_pull_request_approved_rel",
        readonly=True,
    )
    refused_reviewer_ids = fields.Many2many(
        "github.user",
        relation="github_user_pull_request_refused_rel",
        readonly=True,
    )
    approved_internal_reviewer_ids = fields.Many2many(
        comodel_name="github.user",
        compute="_compute_approved_internal_reviewer_ids",
        string="Approving Internal Reviewers",
    )
    blocked_for_one_week = fields.Boolean(
        string="Blocked For One Week+",
        compute="_compute_blocked_for_x",
        search="_search_blocked_for_one_week",
    )
    blocked_for_one_month = fields.Boolean(
        string="Blocked For One Month+",
        compute="_compute_blocked_for_x",
        search="_search_blocked_for_one_month",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        ondelete="set null",
        string="Customer",
    )

    _sql_constraints = [
        (
            "uniq_number_and_repo",
            "unique(number, repo_id)",
            "the pair pr number and repo must be unique",
        ),
    ]

    @api.depends("state")
    def _compute_blocked_for_x(self):
        states = ("draft", "need_fix", "waiting_review", "cancel")
        one_week_ago = fields.Datetime.subtract(fields.Datetime.now(), weeks=1)
        one_month_ago = fields.Datetime.subtract(fields.Datetime.now(), months=1)
        for record in self:
            record.blocked_for_one_week = (
                record.state in states and record.date_updated <= one_week_ago
            )
            record.blocked_for_one_month = (
                record.state in states and record.date_updated <= one_month_ago
            )

    def _search_blocked_for_x(self, date):
        states = ("draft", "need_fix", "waiting_review", "cancel")
        return [
            ("state", "in", states),
            ("date_updated", "<=", date),
        ]

    def _search_blocked_for_one_week(self, operator, value):
        if operator != "=":
            raise UserError(_("Operation not supported"))
        if not value:
            raise UserError(_("False value not supported"))
        one_week_ago = fields.Datetime.subtract(fields.Datetime.now(), weeks=1)
        one_month_ago = fields.Datetime.subtract(fields.Datetime.now(), months=1)
        domain = self._search_blocked_for_x(one_week_ago)
        # Excluse PRs blocked for one month
        domain += [("date_updated", ">=", one_month_ago)]
        return domain

    def _search_blocked_for_one_month(self, operator, value):
        if operator != "=":
            raise UserError(_("Operation not supported"))
        if not value:
            raise UserError(_("False value not supported"))
        one_month_ago = fields.Datetime.subtract(fields.Datetime.now(), months=1)
        return self._search_blocked_for_x(one_month_ago)

    # TODO in next version replace the author char by
    # an m2o author_id (github.user)
    @api.depends("author")
    def _compute_author_user_id(self):
        gh_users = self.env["github.user"].search([("user_id", "!=", False)])
        for record in self:
            record.author_user_id = gh_users.filtered(
                lambda s, author=record.author: s.login == author
            ).user_id

    @api.depends("approved_reviewer_ids")
    def _compute_approved_internal_reviewer_ids(self):
        internal_reviewers = self.env["res.users"].search(
            [("github_user_ids", "!=", False)]
        )
        for record in self:
            record.approved_internal_reviewer_ids = (
                record.approved_reviewer_ids & internal_reviewers.github_user_ids
            )

    def _inverse_is_dead(self):
        for record in self:
            record._update_state()

    def _get_module_from_pr(self, url, modules):
        git_token = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("module.info.pull.request.git.token")
        )
        response = requests.get(
            url, headers={"authorization": f"Bearer {git_token}"}, timeout=10
        )
        matchs = re.findall(r"\+{3,5} b.*", response.text)
        module_ids = []
        for line in matchs:
            # regex get first /module/
            module_name = re.search(r"(?<=/)(\w*)(?=/)", line)
            if not module_name:
                continue
            module_name = module_name.group(0)
            module_id = modules.get(module_name)
            if module_id and module_id not in module_ids:
                module_ids.append(module_id)
        return module_ids

    def _get_reviewer_info(self, pr):
        waiting_for = []
        for reviewer in pr.requested_reviewers:
            waiting_for.append(self.env["github.user"]._get_or_create(reviewer).id)

        # get the last review of each user
        user2review = {}
        for review in pr.get_reviews():
            user2review[review.user] = review.state

        approved_by = []
        refused_by = []
        for reviewer, state in user2review.items():
            github_user = self.env["github.user"]._get_or_create(reviewer)
            if github_user.id in waiting_for:
                # If a user is have a requested review we do not care
                # of his previous review
                continue
            if state == "APPROVED":
                approved_by.append(github_user.id)
            elif state == "CHANGES_REQUESTED":
                refused_by.append(github_user.id)
        return approved_by, refused_by, waiting_for

    def is_approved(self, repo, approved_by):
        # OCA orga need 2 approved move this in an extra module
        if repo.organization.lower() == "oca":
            return len(approved_by) >= 2
        else:
            return bool(approved_by)

    def _prepare_update_pr(self, repo, pr):
        approved_by, refused_by, waiting_for = self._get_reviewer_info(pr)
        vals = {
            "date_updated": naive_dt(pr.updated_at),
            "title": pr.title,
            "date_closed": naive_dt(pr.closed_at),
            "waiting_reviewer_ids": [Command.set(waiting_for)],
            "approved_reviewer_ids": [Command.set(approved_by)],
            "refused_reviewer_ids": [Command.set(refused_by)],
        }

        if pr.state == "closed":
            state = "done" if pr.merged else "cancel"
        elif pr.draft:
            state = "draft"
        elif refused_by:
            state = "need_fix"
        elif waiting_for:
            state = "waiting_review"
        elif self.is_approved(repo, approved_by):
            state = "approved"
        else:
            state = "need_reviewer"
        if self.state != state:
            # Note in case of create the self is an empty browse record
            # and so the state is always different
            vals.update(
                {
                    "state": state,
                    "date_last_state_changed": date.today(),
                }
            )
        return vals

    def _prepare_create_pr(self, repo, pr):
        modules = {m.name: m.id for m in repo.module_ids}
        vals = {
            "repo_id": repo.id,
            "number": pr.number,
            "date_open": naive_dt(pr.created_at),
            "module_ids": [(6, 0, self._get_module_from_pr(pr.diff_url, modules))],
            "version_id": self.env["odoo.version"]._get_id(pr.base.ref[:4]),
            "url": pr.html_url,
            "author": pr.user.login,
            "orga": pr.head.user.login if pr.head.user else pr.user.login,
        }
        vals.update(self._prepare_update_pr(repo, pr))
        return vals

    def update_pr(self):
        g = self.env["module.repo"]._get_github_client()
        for record in self:
            gh_repo = g.get_repo(f"{record.repo_id.organization}/{record.repo_id.name}")
            gh_pr = gh_repo.get_pull(record.number)
            record.write(self._prepare_update_pr(self.repo_id, gh_pr))
            record._post_update()

    def _post_update(self):
        for record in self:
            record._update_state()
            record._update_module_version()

    def _update_state(self):
        """Fix/update PR state based on internal data."""
        for record in self:
            if record.state == "cancel" and record.is_dead:
                record.state = "dead"
            elif record.state == "approved" and record.approved_internal_reviewer_ids:
                record.state = "approved_by_ak"

    # TODO review this behaviour of module version
    def _update_module_version(self):
        # manage module version depending on PRs
        # If there is a PR, then make sure we have at least a pending module version
        # if a PR close, make sure to delete related pending version if not other PR
        # for this module and this version.
        self.ensure_one()
        if self.state == "open":
            for module in self.module_ids:
                module_version = self.env["module.version"].search(
                    [
                        ("module_id", "=", module.id),
                        ("version_id", "=", self.version_id.id),
                    ]
                )
                if not module_version:
                    self.env["module.version"].create(
                        {
                            "state": "pending",
                            "module_id": module.id,
                            "version_id": self.version_id.id,
                        }
                    )
        else:
            # PR is closed, if we have a pending module version, we should unlink it
            # if there is no other PR
            module_versions = self.env["module.version"].search(
                [
                    ("module_id", "in", self.module_ids.ids),
                    ("version_id", "=", self.version_id.id),
                    ("state", "=", "pending"),
                ]
            )
            to_unlink = self.env["module.version"]
            for module_version in module_versions:
                other_pr = self.search(
                    [
                        ("module_ids", "=", module_version.module_id.id),
                        ("version_id", "=", module_version.version_id.id),
                        ("state", "=", "open"),
                    ]
                )
                if not other_pr:
                    to_unlink |= module_version
            to_unlink.unlink()

    def open_url(self):
        return {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": self.url,
        }
