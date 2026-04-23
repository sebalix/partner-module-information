import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_pull_requests_state(env)


def _fix_pull_requests_state(env):
    prs = env["pull.request"].search([])
    _logger.info("Fix state of %s 'pull.request' records", len(prs))
    prs._update_state()
