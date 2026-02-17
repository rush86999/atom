---
phase: 06-social-layer
plan: 05
type: execute
wave: 1
depends_on: ["06-social-layer-02"]
files_modified:
  - backend/core/agent_social_layer.py
  - backend/core/social_post_generator.py
  - backend/core/episode_segmentation_service.py
  - backend/core/agent_graduation_service.py
autonomous: true

must_haves:
  truths:
    - "Social posts create episode segments for agent learning"
    - "Social posts reference relevant episodes when generated"
    - "Positive reactions count toward agent graduation criteria"
    - "Helpful replies increase agent reputation score"
    - "Agent maturity gates enforce per-tier rate limits"
    - "Graduation milestones auto-post to social feed"
  artifacts:
    - path: "backend/core/agent_social_layer.py"
      provides: "Enhanced social layer with episodic memory and graduation integration"
      min_lines: 900
      exports: ["create_post_with_episode", "get_agent_reputation", "check_rate_limit", "post_graduation_milestone"]
    - path: "backend/core/social_post_generator.py"
      provides: "Enhanced post generator with episode retrieval"
      min_lines: 400
      exports: ["generate_with_episode_context", "retrieve_relevant_episodes"]
    - path: "backend/tests/test_social_episodic_integration.py"
      provides: "Integration tests for social-episodic memory linkage"
      min_lines: 500
      exports: ["TestSocialPostEpisodeCreation", "TestEpisodeRetrievalForPosts", "TestGraduationMilestonePosting"]
    - path: "backend/tests/test_social_graduation_integration.py"
      provides: "Integration tests for social-graduation linkage"
      min_lines: 400
      exports: ["TestReactionCounting", "TestReputationScoring", "TestRateLimitEnforcement"]
  key_links:
    - from: "backend/core/agent_social_layer.py"
      to: "backend/core/episode_segmentation_service.py"
      via: "create_episode_segment() when agent creates post"
    - from: "backend/core/agent_social_layer.py"
      to: "backend/core/agent_graduation_service.py"
      via: "track_positive_interaction() for reactions and helpful replies"
    - from: "backend/core/social_post_generator.py"
      to: "backend/core/episode_retrieval_service.py"
      via: "retrieve_relevant_episodes() for context-aware posts"
    - from: "backend/core/agent_graduation_service.py"
      to: "backend/core/agent_social_layer.py"
      via: "post_graduation_milestone() on promotion"
---

<objective>
**Social Layer Enhanced Integration** - Complete the social layer by integrating with episodic memory and graduation systems for full agent learning lifecycle support.

**Purpose:** Enable agents to learn from social interactions, reference past experiences when posting, track reputation from community feedback, and celebrate graduation milestones on the social feed.

**Output:** Enhanced agent_social_layer.py and social_post_generator.py with episodic memory and graduation integration, plus comprehensive integration tests.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@/Users/rushiparikh/projects/atom/backend/core/agent_social_layer.py
@/Users/rushiparikh/projects/atom/backend/core/social_post_generator.py
@/Users/rushiparikh/projects/atom/backend/core/episode_segmentation_service.py
@/Users/rushiparikh/projects/atom/backend/core/agent_graduation_service.py
@/Users/rushiparikh/projects/atom/backend/core/models.py
@/Users/rushiparikh/projects/atom/backend/tests/test_social_feed_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Enhance AgentSocialLayer with Episode Integration</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
    Enhance agent_social_layer.py with episodic memory integration by adding:

    1. **Episode-Aware Post Creation** (enhanced create_post method):
       ```python
       async def create_post_with_episode(
           self,
           agent_id: str,
           content: str,
           post_type: str = "status",
           episode_ids: Optional[List[str]] = None,
           **kwargs
       ) -> AgentPost:
           """
           Create social post and link to episodes.

           - Creates AgentPost record with mentioned_episode_ids
           - Creates EpisodeSegment for social interaction
           - Retrieves relevant episodes if not provided
           - Stores episode context in post metadata
           """
           # Retrieve relevant episodes if not provided
           if not episode_ids:
               episode_ids = await self._retrieve_relevant_episodes(
                   agent_id, content, limit=3
               )

           # Create post with episode references
           post = AgentPost(
               agent_id=agent_id,
               content=content,
               post_type=post_type,
               mentioned_episode_ids=episode_ids,  # Already in model
               **kwargs
           )
           self.db.add(post)
           self.db.commit()

           # Create episode segment for social interaction
           segment = EpisodeSegment(
               episode_id=episode_ids[0] if episode_ids else None,
               agent_id=agent_id,
               segment_type="social_post",
               content={"post_id": str(post.id), "content": content},
               metadata={
                   "post_type": post_type,
                   "engagement_count": 0,
                   "timestamp": datetime.utcnow().isoformat()
               }
           )
           self.db.add(segment)
           self.db.commit()

           return post
       ```

    2. **Relevant Episode Retrieval**:
       ```python
       async def _retrieve_relevant_episodes(
           self,
           agent_id: str,
           content: str,
           limit: int = 3
       ) -> List[str]:
           """
           Retrieve episodes relevant to post content.

           - Uses EpisodeRetrievalService.semantic_search()
           - Searches by content keywords and agent_id
           - Returns top N episode IDs
           """
           from core.episode_retrieval_service import EpisodeRetrievalService

           retrieval_service = EpisodeRetrievalService(self.db)
           results = await retrieval_service.retrieve_episodes(
               agent_id=agent_id,
               query_type="semantic",
               query=content,
               limit=limit
           )
           return [e.id for e in results]
       ```

    3. **Enhanced Feed with Episode Context**:
       ```python
       async def get_feed_with_episode_context(
           self,
           agent_id: Optional[str] = None,
           include_episode_context: bool = True,
           **kwargs
       ) -> Dict[str, Any]:
           """
           Retrieve social feed with episode context.

           - Returns posts with mentioned_episode_ids populated
           - Includes episode summaries if include_episode_context=True
           - Filters by agent, channel, post_type
           - Supports cursor pagination
       """
           posts = await self.get_feed(agent_id=agent_id, **kwargs)

           if include_episode_context:
               for post in posts["posts"]:
                   if post.get("mentioned_episode_ids"):
                       episodes = await self._get_episode_summaries(
                           post["mentioned_episode_ids"]
                       )
                       post["episode_context"] = episodes

           return posts
       ```

    Add 150+ lines to agent_social_layer.py (from 745 to 900+ lines).
  </action>
  <verify>
    pytest tests/test_social_episodic_integration.py::TestSocialPostEpisodeCreation -v
    # Expected: Episode segment created when agent posts
  </verify>
  <done>
    - Enhanced create_post to link episodes
    - Relevant episode retrieval implemented
    - Feed returns episode context
    - Episode segments created for social posts
  </done>
</task>

<task type="auto">
  <name>Task 2: Enhance SocialPostGenerator with Episode Retrieval</name>
  <files>backend/core/social_post_generator.py</files>
  <action>
    Enhance social_post_generator.py to retrieve and reference relevant episodes:

    1. **Episode-Aware Post Generation**:
       ```python
       async def generate_with_episode_context(
           self,
           agent_id: str,
           operation: Dict[str, Any],
           limit: int = 3
       ) -> SocialPost:
           """
           Generate social post with relevant episode context.

           - Retrieves episodes relevant to current operation
           - Includes episode references in generated post
           - Adds "Similar to past experiences:" context
           - Falls back to standard generation if no episodes
           """
           # Retrieve relevant episodes
           episodes = await self._retrieve_relevant_episodes(
               agent_id, operation, limit
           )

           # Build episode context for LLM
           episode_context = self._format_episode_context(episodes)

           # Generate post with episode context
           system_prompt = self._build_system_prompt(with_episodes=True)
           user_prompt = self._build_user_prompt(operation, episode_context)

           # Call LLM with episode context
           response = await self.llm_client.chat.completions.create(
               model=self.model,
               messages=[
                   {"role": "system", "content": system_prompt},
                   {"role": "user", "content": user_prompt}
               ],
               max_tokens=150,
               timeout=5
           )

           content = response.choices[0].message.content.strip()

           return SocialPost(
               agent_id=agent_id,
               content=content,
               post_type=self._categorize_operation(operation),
               mentioned_episode_ids=[e.id for e in episodes],
               metadata={
                   "operation": operation,
                   "episode_count": len(episodes),
                   "generated_with_context": len(episodes) > 0
               }
           )
       ```

    2. **Episode Context Formatting**:
       ```python
       def _format_episode_context(self, episodes: List[Episode]) -> str:
           """
           Format episodes for LLM context.

           - Returns "Similar to past experiences:" section
           - Includes episode summaries and timestamps
           - Limits to 280 characters total context
           """
           if not episodes:
               return ""

           context_parts = []
           for episode in episodes[:3]:  # Max 3 episodes
               summary = episode.summary[:100]  # Truncate summaries
               context_parts.append(f"- {summary}")

           context = "Similar to past experiences:\n" + "\n".join(context_parts)

           # Limit context length
           if len(context) > 280:
               context = context[:280] + "..."

           return context
       ```

    3. **Enhanced System Prompt with Episodes**:
       ```python
       def _build_system_prompt(self, with_episodes: bool = False) -> str:
           """
           Build system prompt with or without episode context.

           - If with_episodes: encourage referencing past experiences
           - Casual, friendly tone (<280 characters)
           - Max 2 emoji
           """
           base_prompt = (
               "You are an AI assistant sharing status updates about your work. "
               "Write casual, friendly posts under 280 characters. Use max 2 emoji."
           )

           if with_episodes:
               base_prompt += (
                   " When relevant, reference similar past experiences to show "
                   "learning and continuity. Use phrases like 'Similar to when I...' "
                   "or 'Building on my previous work...'"
               )

           return base_prompt
       ```

    Add 100+ lines to social_post_generator.py (from 299 to 400+ lines).
  </action>
  <verify>
    pytest tests/test_social_episodic_integration.py::TestEpisodeRetrievalForPosts -v
    # Expected: Posts reference relevant episodes
  </verify>
  <done>
    - Episode retrieval integrated into post generation
    - LLM prompts enhanced with episode context
    - Episode context formatted for LLM
    - Fallback to standard generation if no episodes
  </done>
</task>

<task type="auto">
  <name>Task 3: Integrate Social Interactions with Graduation</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
    Integrate social interactions with agent graduation system:

    1. **Track Positive Interactions**:
       ```python
       async def track_positive_interaction(
           self,
           post_id: str,
           interaction_type: str,
           user_id: Optional[str] = None
       ) -> None:
           """
           Track positive interactions for agent graduation.

           - Counts emoji reactions (👍, ❤️, 🎉, etc.)
           - Counts helpful replies (user replies "thanks!", "helpful")
           - Updates agent reputation score
           - Links to AgentFeedback for learning
           """
           post = self.db.query(AgentPost).filter(AgentPost.id == post_id).first()
           if not post:
               return

           # Determine if interaction is positive
           is_positive = self._is_positive_interaction(interaction_type)

           if is_positive:
               # Get or create agent feedback record
               from core.agent_graduation_service import AgentGraduationService

               graduation_service = AgentGraduationService(self.db)

               # Track positive interaction for graduation
               await graduation_service.track_social_interaction(
                   agent_id=post.agent_id,
                   interaction_type=interaction_type,
                   post_id=post_id,
                   user_id=user_id,
                   timestamp=datetime.utcnow()
               )

               # Update agent reputation
               await self._update_agent_reputation(
                   post.agent_id, interaction_type
               )
       ```

    2. **Agent Reputation Scoring**:
       ```python
       async def get_agent_reputation(
           self,
           agent_id: str
       ) -> Dict[str, Any]:
           """
           Calculate agent reputation from social interactions.

           - Returns reputation score (0-100)
           - Breakdown by interaction type (reactions, replies, posts)
           - Trend over last 30 days
           - Percentile rank among all agents
           """
           # Get agent's posts
           posts = self.db.query(AgentPost).filter(
               AgentPost.agent_id == agent_id
           ).all()

           # Calculate metrics
           total_reactions = sum(p.reaction_count or 0 for p in posts)
           total_replies = sum(p.reply_count or 0 for p in posts)
           helpful_replies = await self._count_helpful_replies(agent_id)

           # Base reputation score
           score = min(100, (
               total_reactions * 2 +  # 2 points per reaction
               helpful_replies * 5 +   # 5 points per helpful reply
               len(posts) * 1          # 1 point per post
           ))

           # Get percentile rank
           percentile = await self._calculate_percentile_rank(agent_id, score)

           return {
               "agent_id": agent_id,
               "reputation_score": score,
               "total_reactions": total_reactions,
               "total_replies": total_replies,
               "helpful_replies": helpful_replies,
               "post_count": len(posts),
               "percentile_rank": percentile,
               "trend": await self._get_reputation_trend(agent_id)
           }
       ```

    3. **Graduation Milestone Posting**:
       ```python
       async def post_graduation_milestone(
           self,
           agent_id: str,
           from_maturity: str,
           to_maturity: str
       ) -> AgentPost:
           """
           Post agent graduation milestone to social feed.

           - Creates announcement post
           - Broadcasts to all agents (global topic)
           - Includes emoji celebration (🎉)
           - Public post (is_public=True)
           """
           # Get agent details
           agent = self.db.query(AgentRegistry).filter(
               AgentRegistry.id == agent_id
           ).first()

           # Generate celebration message
           message = (
               f"🎉 Exciting news! {agent.name} has graduated from "
               f"{from_maturity} to {to_maturity}! "
               f"Keep up the great work! 💪"
           )

           # Create milestone post
           post = await self.create_post(
               agent_id=agent_id,
               content=message,
               post_type="announcement",
               is_public=True,
               metadata={
                   "milestone_type": "graduation",
                   "from_maturity": from_maturity,
                   "to_maturity": to_maturity
               }
           )

           # Broadcast to all agents
           await self.event_bus.publish(
               {
                   "type": "graduation_milestone",
                   "agent_id": agent_id,
                   "from_maturity": from_maturity,
                   "to_maturity": to_maturity,
                   "post_id": str(post.id)
               },
               ["global", "alerts"]
           )

           return post
       ```

    Add 150+ lines to agent_social_layer.py (from 900 to 1050+ lines).
  </action>
  <verify>
    pytest tests/test_social_graduation_integration.py::TestReactionCounting -v
    # Expected: Reactions tracked for graduation
  </verify>
  <done>
    - Positive interactions tracked
    - Agent reputation calculated
    - Graduation milestones posted to feed
    - Social feedback linked to AgentFeedback
  </done>
</task>

<task type="auto">
  <name>Task 4: Implement Maturity-Based Rate Limits</name>
  <files>backend/core/agent_social_layer.py</files>
  <action>
    Implement per-tier rate limiting for social posts:

    1. **Rate Limit Checking**:
       ```python
       async def check_rate_limit(
           self,
           agent_id: str
       ) -> Tuple[bool, Optional[str]]:
           """
           Check if agent is within rate limit for posting.

           Returns:
               (allowed, reason): (True, None) if allowed,
                                  (False, reason) if blocked

           Rate limits by maturity:
           - STUDENT: Read-only (0 posts/hour)
           - INTERN: 1 post per hour
           - SUPERVISED: 12 posts per hour (1 per 5 minutes)
           - AUTONOMOUS: Unlimited
           """
           # Get agent maturity
           agent = await self._get_agent(agent_id)
           maturity = agent.status

           # Check maturity-based limits
           if maturity == "STUDENT":
               return False, "STUDENT agents are read-only"

           if maturity == "INTERN":
               return await self._check_hourly_limit(agent_id, max_posts=1)

           if maturity == "SUPERVISED":
               return await self._check_hourly_limit(agent_id, max_posts=12)

           # AUTONOMOUS has no limit
           return True, None

       async def _check_hourly_limit(
           self,
           agent_id: str,
           max_posts: int
       ) -> Tuple[bool, Optional[str]]:
           """
           Check hourly post limit for agent.

           - Counts posts in last hour
           - Returns (False, "Rate limit exceeded") if over limit
           - Returns (True, None) if under limit
           """
           one_hour_ago = datetime.utcnow() - timedelta(hours=1)

           post_count = self.db.query(AgentPost).filter(
               AgentPost.agent_id == agent_id,
               AgentPost.sender_type == "agent",
               AgentPost.created_at >= one_hour_ago
           ).count()

           if post_count >= max_posts:
               return (
                   False,
                   f"Rate limit exceeded: {max_posts} post(s) per hour"
               )

           return True, None
       ```

    2. **Rate Limit Info in Feed**:
       ```python
       async def get_rate_limit_info(
           self,
           agent_id: str
       ) -> Dict[str, Any]:
           """
           Get rate limit information for agent.

           Returns:
               {
                   "maturity": "INTERN",
                   "max_posts_per_hour": 1,
                   "posts_last_hour": 0,
                   "remaining_posts": 1,
                   "reset_at": "2026-02-17T15:00:00Z"
               }
           """
           agent = await self._get_agent(agent_id)
           maturity = agent.status

           # Get limits by maturity
           limits = {
               "STUDENT": {"max_posts_per_hour": 0},
               "INTERN": {"max_posts_per_hour": 1},
               "SUPERVISED": {"max_posts_per_hour": 12},
               "AUTONOMOUS": {"max_posts_per_hour": None}
           }

           max_posts = limits[maturity]["max_posts_per_hour"]

           if max_posts is None:
               return {
                       "maturity": maturity,
                       "max_posts_per_hour": None,
                       "posts_last_hour": 0,
                       "remaining_posts": None,
                       "unlimited": True
                   }

           # Count posts last hour
           one_hour_ago = datetime.utcnow() - timedelta(hours=1)
           posts_last_hour = self.db.query(AgentPost).filter(
               AgentPost.agent_id == agent_id,
               AgentPost.sender_type == "agent",
               AgentPost.created_at >= one_hour_ago
           ).count()

           return {
               "maturity": maturity,
               "max_posts_per_hour": max_posts,
               "posts_last_hour": posts_last_hour,
               "remaining_posts": max(0, max_posts - posts_last_hour),
               "reset_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
           }
       ```

    Add 80+ lines to agent_social_layer.py (from 1050 to 1130+ lines).
  </action>
  <verify>
    pytest tests/test_social_graduation_integration.py::TestRateLimitEnforcement -v
    # Expected: Rate limits enforced by maturity
  </verify>
  <done>
    - STUDENT agents blocked (0 posts/hour)
    - INTERN limited to 1 post/hour
    - SUPERVISED limited to 12 posts/hour
    - AUTONOMOUS unlimited
    - Rate limit info endpoint available
  </done>
</task>

<task type="auto">
  <name>Task 5: Create Integration Tests for Social-Episodic Linkage</name>
  <files>backend/tests/test_social_episodic_integration.py</files>
  <action>
    Create comprehensive integration test file for social-episodic memory linkage:

    1. **Social Post Episode Creation Tests** (8 tests):
       - test_create_post_creates_episode_segment: Episode segment created
       - test_create_post_links_episodes: mentioned_episode_ids populated
       - test_create_post_retrieves_relevant_episodes: Auto-retrieval works
       - test_feed_includes_episode_context: Feed returns episode summaries
       - test_episode_context_filterable: Filter by episode_id
       - test_multiple_episodes_per_post: Multiple episode links work
       - test_post_without_episodes: Graceful handling when no episodes
       - test_episode_segment_metadata: Segment has correct metadata

    2. **Episode Retrieval for Posts Tests** (7 tests):
       - test_retrieve_episodes_by_content: Semantic search for episodes
       - test_retrieve_episodes_by_operation_type: Type-based retrieval
       - test_retrieve_episodes_limits_results: Limit parameter respected
       - test_retrieve_episodes_fallback_empty: Empty list if no episodes
       - test_episode_context_formatted: Context formatted for LLM
       - test_episode_context_truncated: Context limited to 280 chars
       - test_retrieve_episodes_by_agent: Agent-specific retrieval

    3. **Post Generation with Episodes Tests** (5 tests):
       - test_generate_post_with_episode_context: generate_with_episode_context works
       - test_generated_post_references_episodes: Post mentions similar experiences
       - test_generate_post_fallback_no_episodes: Falls back if no episodes
       - test_generate_post_episode_count_limit: Limits to 3 episodes
       - test_generated_post_episode_metadata: Post has episode metadata

    Create 500+ line test file with 20 tests.
  </action>
  <verify>
    pytest tests/test_social_episodic_integration.py -v
    # Expected: 20+ tests passing
  </verify>
  <done>
    - New test file test_social_episodic_integration.py with 20 tests
    - Social post episode creation verified
    - Episode retrieval for posts verified
    - Post generation with episodes verified
  </done>
</task>

<task type="auto">
  <name>Task 6: Create Integration Tests for Social-Graduation Linkage</name>
  <files>backend/tests/test_social_graduation_integration.py</files>
  <action>
    Create comprehensive integration test file for social-graduation linkage:

    1. **Reaction Counting Tests** (6 tests):
       - test_track_positive_interaction_reaction: Emoji reactions tracked
       - test_track_positive_interaction_reply: Helpful replies tracked
       - test_negative_ignored: Negative interactions not counted
       - test_multiple_reactions: All reactions counted
       - test_interaction_creates_feedback: AgentFeedback record created
       - test_interaction_updates_graduation_metrics: Graduation metrics updated

    2. **Reputation Scoring Tests** (7 tests):
       - test_reputation_score_calculated: Score calculated correctly
       - test_reputation_breakdown: Reactions, replies, posts counted
       - test_reputation_percentile: Percentile rank calculated
       - test_reputation_trend: 30-day trend returned
       - test_reputation_zero_new_agent: New agents have score 0
       - test_reputation_top_agent: Top agents score 100
       - test_reputation_helpful_replies_weighted: Helpful replies worth 5x

    3. **Rate Limit Enforcement Tests** (7 tests):
       - test_student_blocked: STUDENT agents blocked from posting
       - test_intern_hourly_limit: INTERN limited to 1 post/hour
       - test_supervised_five_min_limit: SUPERVISED limited to 12 posts/hour
       - test_autonomous_unlimited: AUTONOMOUS has no limit
       - test_rate_limit_info: Rate limit info returned
       - test_rate_limit_reset: Limits reset after 1 hour
       - test_rate_limit_exceeded_message: Clear error message

    4. **Graduation Milestone Tests** (4 tests):
       - test_post_graduation_milestone: Milestone posted to feed
       - test_milestone_broadcast: Milestone broadcast to all agents
       - test_milestone_emoji: Celebration emoji included
       - test_milestone_public: Milestone post is public

    Create 400+ line test file with 24 tests.
  </action>
  <verify>
    pytest tests/test_social_graduation_integration.py -v
    # Expected: 24+ tests passing
  </verify>
  <done>
    - New test file test_social_graduation_integration.py with 24 tests
    - Reaction counting verified
    - Reputation scoring verified
    - Rate limit enforcement verified
    - Graduation milestone posting verified
  </done>
</task>

</tasks>

<verification>
**Overall Verification:**
1. Run integration tests: `pytest tests/test_social_episodic_integration.py tests/test_social_graduation_integration.py -v`
2. Verify 95%+ test pass rate
3. Run coverage report: `pytest --cov=core/agent_social_layer --cov=core/social_post_generator --cov-report=term-missing`
4. Verify >80% coverage for both modules
5. Verify episode segments created when agents post
6. Verify graduation milestones posted to social feed
7. Verify rate limits enforced by maturity level
8. Run 3 times to verify no flaky tests (TQ-04 requirement)
</verification>

<success_criteria>
1. **Episode Integration**: 20+ tests, social posts create episode segments
2. **Graduation Integration**: 24+ tests, reactions count toward graduation
3. **Rate Limits**: 7+ tests, per-tier limits enforced
4. **Reputation**: Agent reputation score calculated from interactions
5. **Milestones**: Graduation milestones auto-post to feed
6. **Flaky Tests**: Zero flaky tests across 3 runs (TQ-04)
</success_criteria>

<output>
After completion, create `.planning/phases/06-social-layer/06-social-layer-05-SUMMARY.md` with:
- Episode integration implementation details
- Graduation integration implementation details
- Rate limit enforcement details
- Test count and pass rate
- Coverage metrics
- Discovered bugs or edge cases
- Overall summary with recommendations
</output>
