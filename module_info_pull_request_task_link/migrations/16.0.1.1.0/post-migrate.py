import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_pull_requests_state(env)
    _recompute_pull_requests_partner_id(env)


def _fix_pull_requests_state(env):
    prs = env["pull.request"].search([])
    _logger.info("Fix state of %s 'pull.request' records", len(prs))
    prs._update_state()


def _recompute_pull_requests_partner_id(env):
    prs = env["pull.request"].search([])
    _logger.info("Update partner_id of %s 'pull.request' records", len(prs))
    field = prs._fields["partner_id"]
    to_compute = prs.filtered(
        # a field is protected if it is being written
        lambda rec: not env.is_protected(field, rec)
    )
    env.add_to_compute(field, to_compute)
    prs.modified(["partner_id"])
