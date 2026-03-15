"""GitHub webhook event handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pachca_bot.config import DISPLAY_NAME_GITHUB
from pachca_bot.models.messages import (
    FieldsBlock,
    GitHubCIMessage,
    GitHubDeploymentMessage,
    GitHubPRMessage,
    GitHubReleaseMessage,
    HeaderBlock,
    PRStatus,
    Severity,
    StructuredMessage,
    TextBlock,
    _gh_repo_link,
)
from pachca_bot.models.webhooks import GitHubWebhookPayload

if TYPE_CHECKING:
    from pachca_bot.gh_deploy_tracker import GHDeployTracker
    from pachca_bot.pr_tracker import PRTracker

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = {
    "release",
    "check_run",
    "workflow_run",
    "pull_request",
    "check_suite",
    "deployment",
    "deployment_status",
}

_PR_ACTIONS_TO_STATUS: dict[str, PRStatus | None] = {
    "opened": None,
    "reopened": PRStatus.REOPENED,
    "closed": None,
    "ready_for_review": PRStatus.READY_FOR_REVIEW,
    "converted_to_draft": PRStatus.DRAFT,
}


def _resolve_pr_status(action: str, merged: bool, draft: bool) -> PRStatus | None:
    if action == "opened":
        return PRStatus.DRAFT if draft else PRStatus.OPEN
    if action == "closed":
        return PRStatus.MERGED if merged else PRStatus.CLOSED
    return _PR_ACTIONS_TO_STATUS.get(action)


def _try_post_ci_to_pr_thread(
    pr_tracker: PRTracker | None,
    repo: str,
    pr_numbers: list[int],
    ci_msg: GitHubCIMessage,
) -> bool:
    if not pr_tracker or not pr_numbers:
        return False
    for pr_num in pr_numbers:
        thread_id = pr_tracker.get_thread_id_for_pr(repo, pr_num)
        if thread_id is not None:
            ci_msg_for_thread = ci_msg.model_copy(update={"for_pr_thread": True})
            pr_tracker._client.post_to_thread(
                thread_id,
                ci_msg_for_thread.to_structured().render(),
                display_name=DISPLAY_NAME_GITHUB,
            )
            return True
    return False


def handle_github_event(
    event_type: str,
    payload: GitHubWebhookPayload,
    pr_tracker: PRTracker | None = None,
    gh_deploy_tracker: GHDeployTracker | None = None,
) -> StructuredMessage | dict | None:
    repo = payload.repository.full_name

    if event_type == "release" and payload.release is not None:
        rel = payload.release
        return GitHubReleaseMessage(
            repo=repo,
            tag=rel.tag_name,
            release_name=rel.name or rel.tag_name,
            author=rel.author.login or payload.sender.login,
            url=rel.html_url,
            body=rel.body or "",
            prerelease=rel.prerelease,
        ).to_structured()

    if event_type == "workflow_run" and payload.workflow_run is not None:
        wr = payload.workflow_run
        if payload.action != "completed":
            return None
        if wr.conclusion in (None, "success", "neutral", "skipped"):
            return None

        ci_msg = GitHubCIMessage(
            workflow_name=wr.name,
            commit_sha=wr.head_sha,
            repo=repo,
            conclusion=wr.conclusion or "unknown",
            url=wr.html_url,
        )

        pr_nums = [pr.number for pr in wr.pull_requests if pr.number]
        if _try_post_ci_to_pr_thread(pr_tracker, repo, pr_nums, ci_msg):
            return {"id": None, "posted_to_pr_thread": True}

        return ci_msg.to_structured()

    if event_type == "check_run" and payload.check_run is not None:
        cr = payload.check_run
        if payload.action != "completed":
            return None
        if cr.conclusion in (None, "success", "neutral", "skipped"):
            return None

        ci_msg = GitHubCIMessage(
            workflow_name=cr.name,
            commit_sha=cr.check_suite.head_sha,
            repo=repo,
            conclusion=cr.conclusion or "unknown",
            url=cr.html_url,
        )
        return ci_msg.to_structured()

    if event_type == "pull_request" and payload.pull_request is not None:
        pr = payload.pull_request
        status = _resolve_pr_status(payload.action, pr.merged, pr.draft)
        if status is None:
            return None

        pr_msg = GitHubPRMessage(
            repo=repo,
            number=pr.number,
            title=pr.title,
            author=pr.user.login or payload.sender.login,
            url=pr.html_url,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            body=pr.body or "",
            status=status,
        )

        if pr_tracker is not None:
            return pr_tracker.handle_pr_event(pr_msg)
        return StructuredMessage().add(TextBlock(text=pr_msg.to_parent()))

    if event_type == "check_suite" and payload.check_suite is not None:
        cs = payload.check_suite
        if payload.action != "completed" or cs.conclusion != "success":
            return None
        if not cs.pull_requests or pr_tracker is None:
            return None

        result = None
        for pr_ref in cs.pull_requests:
            pr_msg = GitHubPRMessage(
                repo=repo,
                number=pr_ref.number,
                title="",
                author="",
                url=f"https://github.com/{repo}/pull/{pr_ref.number}",
                base_branch="",
                head_branch="",
                status=PRStatus.CHECKS_PASSED,
            )
            result = pr_tracker.handle_pr_event(pr_msg)
        return result

    if event_type in ("deployment", "deployment_status") and payload.deployment is not None:
        dep = payload.deployment
        state = ""
        url = ""
        description = dep.description or ""

        if payload.deployment_status is not None:
            ds = payload.deployment_status
            state = ds.state
            url = ds.target_url or ds.log_url or ""
            if ds.description:
                description = ds.description

        if not url:
            url = f"{payload.repository.html_url}/deployments"

        deploy_msg = GitHubDeploymentMessage(
            repo=repo,
            environment=dep.environment or "unknown",
            description=description,
            state=state,
            creator=dep.creator.login or payload.sender.login,
            sha=dep.sha,
            ref=dep.ref,
            url=url,
        )

        if gh_deploy_tracker is not None:
            return gh_deploy_tracker.handle_deploy_event(deploy_msg)
        return StructuredMessage().add(TextBlock(text=deploy_msg.to_parent()))

    if event_type == "ping":
        repo_link = _gh_repo_link(repo)
        msg = StructuredMessage()
        msg.add(HeaderBlock(text=f"{Severity.INFO.emoji} GitHub webhook connected", level=2))
        msg.add(FieldsBlock(fields={"Repository": repo_link}))
        msg.add(TextBlock(text="Webhook ping received successfully."))
        return msg

    logger.debug("Ignoring unsupported GitHub event: %s", event_type)
    return None
