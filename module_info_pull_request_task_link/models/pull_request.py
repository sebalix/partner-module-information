import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PullRequest(models.Model):
    _inherit = "pull.request"

    project_id = fields.Many2one(
        "project.project",
        "Project",
        compute="_compute_project_id",
        store=True,
        readonly=False,
        index=True,
    )
    task_id = fields.Many2one(
        "project.task",
        "Task",
        compute="_compute_task_id",
        store=True,
        readonly=False,
        index=True,
        domain="[('project_id', '=?', project_id)]",
    )
    internal_reviewer_ids = fields.Many2many(
        "res.users",
        compute="_compute_internal_reviewer_ids",
        string="Internal Reviewer",
        store=True,
        readonly=False,
        help=(
            "On github you may not have the access right to request a review."
            "Here you can define an internal reviewer, so this person can do a"
            "review"
        ),
    )
    l1_internal_reviewer_ids = fields.Many2many(
        comodel_name="res.users",
        relation="pull_request_l1_internal_reviewer_rel",
        column1="pull_request_id",
        column2="internal_reviewer_id",
        compute="_compute_level_internal_reviewer_ids",
        store=True,
        string="Internal Reviewer Level 1",
        help="Level 1 reviewers are those doing the first reviews.",
    )
    l2_internal_reviewer_ids = fields.Many2many(
        comodel_name="res.users",
        relation="pull_request_l2_internal_reviewer_rel",
        column1="pull_request_id",
        column2="internal_reviewer_id",
        compute="_compute_level_internal_reviewer_ids",
        store=True,
        string="Internal Reviewer Level 2",
        help=(
            "Level 2 reviewers are those approving for good the PR."
            " They come after level 1 reviewers."
        ),
    )
    waiting_for_l1_reviewers = fields.Many2many(
        comodel_name="github.user",
        compute="_compute_waiting_for_reviewers",
        string="Waiting for Level 1 Reviewers",
    )
    waiting_for_l2_reviewers = fields.Many2many(
        comodel_name="github.user",
        compute="_compute_waiting_for_reviewers",
        string="Waiting for Level 2 Reviewers",
    )
    all_waiting_reviewer_ids = fields.Many2many(
        "github.user",
        compute="_compute_all_waiting_reviewer_ids",
        relation="github_user_pull_request_all_waiting_rel",
        readonly=True,
        store=True,
        help="This include internal reviewer + github reviewer",
    )

    @api.depends(
        "waiting_reviewer_ids",
        "approved_reviewer_ids",
        "refused_reviewer_ids",
        "internal_reviewer_ids",
    )
    def _compute_all_waiting_reviewer_ids(self):
        for record in self:
            waiting_internal = record.internal_reviewer_ids.github_user_ids
            waiting_internal -= (
                record.approved_reviewer_ids + record.refused_reviewer_ids
            )
            record.all_waiting_reviewer_ids = (
                waiting_internal + record.waiting_reviewer_ids
            )

    @api.depends("task_id.reviewer_ids")
    def _compute_internal_reviewer_ids(self):
        for record in self:
            record.internal_reviewer_ids = record.task_id.reviewer_ids

    @api.depends("task_id")
    def _compute_project_id(self):
        for line in self:
            if line.task_id and not line.project_id:
                line.project_id = line.task_id.project_id

    @api.depends("project_id")
    def _compute_task_id(self):
        for line in self:
            if line.project_id != line.task_id.project_id:
                line.task_id = False

    @api.depends("internal_reviewer_ids", "project_id.l2_internal_reviewer_ids")
    def _compute_level_internal_reviewer_ids(self):
        for record in self:
            record.l1_internal_reviewer_ids = (
                record.internal_reviewer_ids
                - record.project_id.l2_internal_reviewer_ids
            )
            record.l2_internal_reviewer_ids = (
                record.internal_reviewer_ids
                & record.project_id.l2_internal_reviewer_ids
            )

    @api.depends("all_waiting_reviewer_ids", "l1_internal_reviewer_ids")
    def _compute_waiting_for_reviewers(self):
        for record in self:
            record.waiting_for_l1_reviewers = (
                record.all_waiting_reviewer_ids
                & record.l1_internal_reviewer_ids.github_user_ids
            )
            record.waiting_for_l2_reviewers = (
                record.all_waiting_reviewer_ids
                & record.l2_internal_reviewer_ids.github_user_ids
            )

    def _update_state(self):
        res = super()._update_state()
        for record in self:
            if record.state == "need_reviewer" and record.internal_reviewer_ids:
                record.state = "waiting_review"
        return res
