"""A workspace with media and no campaigns must still publish.

Three businesses holding 5631 finished assets between them published nothing
for hours while two others on the same scheduler posted normally. The only
difference was whether a SocialCampaign row happened to exist:

    quantcai              SaaS          12 campaigns   posting
    Lumively              E-commerce    15 campaigns   posting
    BollyVerse            Social Page    0 campaigns   silent
    HollyVerse            Social Page    0 campaigns   silent
    Billionaire Goal777   Social Page    0 campaigns   silent

Social Page workspaces are built by bulk-importing a folder, which never
creates campaigns. The task returned "no_campaigns" in seconds, wrote no post
and raised nothing -- so the last-posted time never advanced and every cycle
repeated the same no-op forever.

A campaign supplies two things to this path: a base idea for the caption
prompt, and a fallback image for when the catalog is empty. Neither is
essential when the workspace has media. SocialPost.campaignId is nullable, so
nothing in the schema required one either.
"""

import inspect

import pytest

import worker


@pytest.fixture(scope="module")
def task_source() -> str:
    return inspect.getsource(worker.context_aggregation_task)


def test_media_alone_is_enough_to_publish(task_source):
    """The standard flow must not bail out purely for want of a campaign."""
    assert "if not campaign and not media_obj" in task_source, (
        "the standard flow still refuses to post without a campaign"
    )


def test_the_asset_description_becomes_the_base_idea(task_source):
    """It describes what is actually in the picture, which is what the caption
    should be about -- a better base idea than a campaign line."""
    assert "base_idea" in task_source
    assert "media_obj.caption" in task_source


def test_campaign_id_is_optional_on_the_post(task_source):
    from database import SocialPost

    assert SocialPost.__table__.columns["campaignId"].nullable, (
        "a post without a campaign could not be recorded"
    )
    assert "campaign_id = None" in task_source


def test_the_influencer_flow_has_the_same_rule(task_source):
    """A persona workspace built by importing a folder would hit the identical
    wall, so it takes the same escape hatch."""
    branch = task_source[task_source.index('== "AI Influencer"'):]
    branch = branch[: branch.index("            else:")]
    assert "influencer_idea" in branch
    assert "not campaign and not media_obj" in branch, (
        "the influencer flow still bails out purely for want of a campaign"
    )


def test_every_no_campaigns_exit_requires_no_media_too(task_source):
    """Each remaining exit must mean "nothing at all to post", never merely
    "no campaign row". That distinction is the whole bug."""
    for idx, line in enumerate(task_source.splitlines()):
        if line.strip() != 'return "no_campaigns"':
            continue
        # The guard is the nearest `if` above it.
        preceding = " ".join(task_source.splitlines()[max(0, idx - 8):idx])
        assert "not media_obj" in preceding or "not product" in preceding, (
            f"a no_campaigns exit at line {idx} fires without checking for "
            f"media: {preceding[-200:]}"
        )


def test_a_none_campaign_is_never_dereferenced(task_source):
    """Trading a silent no-op for an AttributeError is not an improvement.

    Parsed rather than grepped: every `campaign.<attr>` read must sit inside a
    branch that has established the campaign exists.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(task_source))

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.unsafe = []
            self.guarded_depth = 0

        def _walk_block(self, body):
            """Statements in order, honouring an early return as a guard.

            `if not campaign: return` protects everything after it in the same
            block -- which is how the E-commerce branch is written, and a
            checker that cannot see that would demand pointless changes there.
            """
            bailed = False
            for stmt in body:
                if (
                    isinstance(stmt, ast.If)
                    and "not campaign" in ast.unparse(stmt.test)
                    and any(isinstance(n, ast.Return) for n in stmt.body)
                ):
                    bailed = True
                    continue
                if bailed:
                    self.guarded_depth += 1
                    self.visit(stmt)
                    self.guarded_depth -= 1
                else:
                    self.visit(stmt)

        def visit_If(self, node):
            # A test that proves `campaign` is truthy makes the body safe.
            src = ast.unparse(node.test)
            if "campaign" in src and "not campaign" not in src:
                self.guarded_depth += 1
                self._walk_block(node.body)
                self.guarded_depth -= 1
                self._walk_block(node.orelse)
                return
            self.visit(node.test)
            self._walk_block(node.body)
            self._walk_block(node.orelse)

        def visit_IfExp(self, node):
            # `campaign.x if campaign else y` -- the guard is the condition.
            if "campaign" in ast.unparse(node.test):
                self.guarded_depth += 1
                self.visit(node.body)
                self.guarded_depth -= 1
                self.visit(node.orelse)
                return
            self.generic_visit(node)

        def visit_BoolOp(self, node):
            # `campaign and campaign.mediaUrl` -- short-circuit is a guard.
            if isinstance(node.op, ast.And) and any(
                isinstance(v, ast.Name) and v.id == "campaign" for v in node.values
            ):
                self.guarded_depth += 1
                self.generic_visit(node)
                self.guarded_depth -= 1
                return
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            self._walk_block(node.body)

        def visit_AsyncFunctionDef(self, node):
            self._walk_block(node.body)

        def visit_Attribute(self, node):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "campaign"
                and self.guarded_depth == 0
            ):
                self.unsafe.append(f"campaign.{node.attr} (line {node.lineno})")
            self.generic_visit(node)

    v = Visitor()
    v.visit(tree)
    assert not v.unsafe, f"campaign dereferenced without a guard: {v.unsafe}"


def test_inline_execution_reports_its_result():
    """The cycle summary said PUBLISHED for workspaces that had published
    nothing, because the task's return value was thrown away."""
    import services.scheduler as sched

    src = inspect.getsource(sched._execute_inline)
    assert "return str(result)" in src, (
        "the inline runner still discards what the task reported"
    )

    loop = inspect.getsource(sched.execute_marketing_loop)
    assert "result = await _execute_inline(workspace_id)" in loop
    assert "PUBLISHED inline" not in loop, (
        "the cycle still claims a publish happened rather than recording the "
        "task's own verdict"
    )
