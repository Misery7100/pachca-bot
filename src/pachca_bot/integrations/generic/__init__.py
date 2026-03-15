"""Generic webhook integration: deploys, alerts."""

from pachca_bot.integrations.generic.deploy_tracker import DeployTracker
from pachca_bot.integrations.generic.handler import GenericHandler

__all__ = ["GenericHandler", "DeployTracker"]
