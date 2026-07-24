from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from services.temporal_activities import (
        context_aggregation_task,
        synthesis_task,
        video_rendering_task,
        publishing_distribution_task,
    )

@workflow.defn
class MarketingCampaignWorkflow:
    @workflow.run
    async def run(self, workspace_id: str, post_id: str) -> str:
        # Step 1: Context Aggregation
        aggregation_result = await workflow.execute_activity(
            context_aggregation_task,
            args=[workspace_id],
            start_to_close_timeout=timedelta(seconds=60),
        )
        
        # Step 2: Synthesis
        synthesis_result = await workflow.execute_activity(
            synthesis_task,
            args=[workspace_id, {}],
            start_to_close_timeout=timedelta(seconds=120),
        )

        # Step 3: Video Rendering
        rendering_result = await workflow.execute_activity(
            video_rendering_task,
            args=[workspace_id, {}],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 4: Publishing and Distribution
        publishing_result = await workflow.execute_activity(
            publishing_distribution_task,
            args=[workspace_id, post_id],
            start_to_close_timeout=timedelta(minutes=2),
        )

        return f"Campaign deployed successfully: {publishing_result}"
