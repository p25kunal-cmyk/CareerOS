"""Unit and integration tests for AI Resume Optimization, Caching, and Verification Safeguards."""

import pytest
from src.ai.cache import AICacheManager
from src.ai.optimizer import ResumeOptimizer
from src.ai.provider import RuleBasedOfflineProvider
from src.resume.models import BulletItem, ResumeVersionData, SectionItem
from src.resume.repository import ResumeRepository
from src.tracker.models import JobPosting
from src.tracker.repository import TrackerRepository


def test_ai_cache(db):
    """Test deterministic SHA-256 caching of prompt outputs."""
    cache = AICacheManager(db)

    prompt = "Optimize: worked on sales reports."
    input_hash = cache.generate_hash(prompt, provider="test", model="test-v1")
    assert len(input_hash) == 64

    # Miss
    assert cache.get_cached_response(input_hash) is None

    # Store
    cache.store_cached_response(
        input_hash=input_hash,
        prompt=prompt,
        response_text="Spearheaded enterprise revenue reporting.",
        provider="test",
        model="test-v1",
        tokens_in=10,
        tokens_out=12,
        cost_usd=0.001,
    )

    # Hit
    cached_val = cache.get_cached_response(input_hash)
    assert cached_val == "Spearheaded enterprise revenue reporting."


def test_rule_based_offline_provider():
    """Verify offline provider rephrases bullets with strong action verbs."""
    provider = RuleBasedOfflineProvider()
    prompt = "- responsible for managing client accounts and sales."

    resp, tin, tout, cost = provider.generate(prompt)
    assert "Spearheaded" in resp or "Accelerated" in resp or "Optimized" in resp
    assert cost == 0.0


def test_resume_optimizer_and_branch_application(db):
    """Test end-to-end optimization workflow, verification, and branching."""
    resume_repo = ResumeRepository(db)
    tracker_repo = TrackerRepository(db)
    optimizer = ResumeOptimizer(db, provider=RuleBasedOfflineProvider())

    # Create test resume
    r_id = resume_repo.create_resume(name="Optimization Test Resume")
    sec = SectionItem(
        section_type="experience",
        title="Experience",
        bullets=[
            BulletItem(content="Responsible for developing backend web services."),
            BulletItem(content="Worked with marketing team on product launch."),
        ],
    )
    v1 = resume_repo.create_version(resume_id=r_id, version_name="v1.0", sections=[sec])

    # Create job
    job_id, _ = tracker_repo.add_or_update_job(JobPosting(title="Product Lead", company="Paytm"))

    # 1. Run optimization
    sugs = optimizer.optimize_version(resume_version_id=v1.id, job_id=job_id)
    assert len(sugs) >= 1

    # Verify ai_suggestions in DB
    db_sugs = optimizer.list_suggestions(v1.id)
    assert len(db_sugs) >= 1
    sug_id = db_sugs[0]["id"]

    # Verify ai_usage_records in DB
    usage_rows = db.execute("SELECT * FROM ai_usage_records WHERE operation = 'bullet_optimization'")
    assert len(usage_rows) >= 1

    # 2. Update status to verified
    optimizer.update_suggestion_status(sug_id, "verified")
    updated_sugs = optimizer.list_suggestions(v1.id)
    target_sug = next(s for s in updated_sugs if s["id"] == sug_id)
    assert target_sug["verification_status"] == "verified"

    # 3. Apply approved suggestions into new branched version
    v2 = optimizer.apply_approved_suggestions(v1.id, new_version_name="v2.0 (AI Optimized)")
    assert v2.id != v1.id
    assert v2.parent_version_id == v1.id
    assert "Optimized" in v2.version_name

    # Verify bullet was replaced with proposed text
    exp_sec = next(s for s in v2.sections if s.section_type == "experience")
    all_bullet_texts = [b.content for b in exp_sec.bullets]
    assert any(target_sug["proposed_text"] in t or "Spearheaded" in t or "Accelerated" in t for t in all_bullet_texts)

    # Verify suggestion is now marked applied
    sugs_after_apply = optimizer.list_suggestions(v1.id)
    applied_sug = next(s for s in sugs_after_apply if s["id"] == sug_id)
    assert applied_sug["is_applied"] == 1
    assert applied_sug["applied_to_version_id"] == v2.id


def test_ai_provider_factory_selection(db):
    """Test dynamic selection of AI providers based on database user settings."""
    from src.ai.provider import get_ai_provider, GeminiProvider, OpenAIProvider, RuleBasedOfflineProvider

    # Default without key
    p_default = get_ai_provider(db)
    assert isinstance(p_default, RuleBasedOfflineProvider)

    # Configure Gemini
    with db.transaction() as conn:
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_provider', 'google', 'ai')")
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_api_key', 'AIzaSyFakeTestKey123456789', 'ai')")
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_model', 'gemini-1.5-flash', 'ai')")

    p_gemini = get_ai_provider(db)
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.model == "gemini-1.5-flash"

    # Configure OpenAI
    with db.transaction() as conn:
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_provider', 'openai', 'ai')")
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_api_key', 'sk-fakeopenai1234567890abcdef', 'ai')")
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_model', 'gpt-4o-mini', 'ai')")

    p_openai = get_ai_provider(db)
    assert isinstance(p_openai, OpenAIProvider)
    assert p_openai.model == "gpt-4o-mini"
