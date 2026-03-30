"""Output rendering for last30days skill."""

import html as _html_mod
import json
import os
import re as _re
import tempfile
from datetime import datetime as _dt
from pathlib import Path
from typing import Optional

from . import schema

OUTPUT_DIR = Path.home() / ".local" / "share" / "last30days" / "out"


def _xref_tag(item) -> str:
    """Return ' [also on: Reddit, HN]' string if item has cross_refs, else ''."""
    refs = getattr(item, 'cross_refs', None)
    if not refs:
        return ""
    source_names = set()
    for ref_id in refs:
        if ref_id.startswith('R'):
            source_names.add('Reddit')
        elif ref_id.startswith('X'):
            source_names.add('X')
        elif ref_id.startswith('YT'):
            source_names.add('YouTube')
        elif ref_id.startswith('TK'):
            source_names.add('TikTok')
        elif ref_id.startswith('IG'):
            source_names.add('Instagram')
        elif ref_id.startswith('HN'):
            source_names.add('HN')
        elif ref_id.startswith('BS'):
            source_names.add('Bluesky')
        elif ref_id.startswith('TS'):
            source_names.add('Truth Social')
        elif ref_id.startswith('PM'):
            source_names.add('Polymarket')
        elif ref_id.startswith('W'):
            source_names.add('Web')
    if source_names:
        return f" [also on: {', '.join(sorted(source_names))}]"
    return ""


def ensure_output_dir():
    """Ensure output directory exists. Supports env override and sandbox fallback."""
    global OUTPUT_DIR
    env_dir = os.environ.get("LAST30DAYS_OUTPUT_DIR")
    if env_dir:
        OUTPUT_DIR = Path(env_dir)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        OUTPUT_DIR = Path(tempfile.gettempdir()) / "last30days" / "out"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _assess_data_freshness(report: schema.Report) -> dict:
    """Assess how much data is actually from the last 30 days."""
    reddit_recent = sum(1 for r in report.reddit if r.date and r.date >= report.range_from)
    x_recent = sum(1 for x in report.x if x.date and x.date >= report.range_from)
    web_recent = sum(1 for w in report.web if w.date and w.date >= report.range_from)
    hn_recent = sum(1 for h in report.hackernews if h.date and h.date >= report.range_from)
    bsky_recent = sum(1 for b in report.bluesky if b.date and b.date >= report.range_from)
    ts_recent = sum(1 for ts in report.truthsocial if ts.date and ts.date >= report.range_from)
    pm_recent = sum(1 for p in report.polymarket if p.date and p.date >= report.range_from)

    tiktok_recent = sum(1 for t in report.tiktok if t.date and t.date >= report.range_from)
    ig_recent = sum(1 for ig in report.instagram if ig.date and ig.date >= report.range_from)

    total_recent = reddit_recent + x_recent + web_recent + hn_recent + bsky_recent + ts_recent + pm_recent + tiktok_recent + ig_recent
    total_items = len(report.reddit) + len(report.x) + len(report.web) + len(report.hackernews) + len(report.bluesky) + len(report.truthsocial) + len(report.polymarket) + len(report.tiktok) + len(report.instagram)

    return {
        "reddit_recent": reddit_recent,
        "x_recent": x_recent,
        "web_recent": web_recent,
        "total_recent": total_recent,
        "total_items": total_items,
        "is_sparse": total_recent < 5,
        "mostly_evergreen": total_items > 0 and total_recent < total_items * 0.3,
    }


def render_compact(report: schema.Report, limit: int = 15, missing_keys: str = "none") -> str:
    """Render compact output for the assistant to synthesize.

    Args:
        report: Report data
        limit: Max items per source
        missing_keys: 'both', 'reddit', 'x', or 'none'

    Returns:
        Compact markdown string
    """
    lines = []

    # Header
    lines.append(f"## Research Results: {report.topic}")
    lines.append("")

    # Assess data freshness and add honesty warning if needed
    freshness = _assess_data_freshness(report)
    if freshness["is_sparse"]:
        lines.append("**⚠️ LIMITED RECENT DATA** - Few discussions from the last 30 days.")
        lines.append(f"Only {freshness['total_recent']} item(s) confirmed from {report.range_from} to {report.range_to}.")
        lines.append("Results below may include older/evergreen content. Be transparent with the user about this.")
        lines.append("")

    # Web-only mode banner (when no API keys)
    if report.mode == "web-only":
        lines.append("**🌐 WEB SEARCH MODE** - assistant will search blogs, docs & news")
        lines.append("")
        lines.append("---")
        lines.append("**⚡ Want better results?** Add API keys to unlock Reddit, TikTok, Instagram & X data:")
        lines.append("- `SCRAPECREATORS_API_KEY` → Reddit + TikTok + Instagram (one key, all three!) — 100 free calls, no CC — scrapecreators.com (no affiliation)")
        lines.append("- `XAI_API_KEY` → X posts with real likes & reposts")
        lines.append("- `OPENAI_API_KEY` (legacy) → Reddit threads (slower, higher cost)")
        lines.append("- Edit `~/.config/last30days/.env` to add keys")
        lines.append("---")
        lines.append("")

    # Cache indicator
    if report.from_cache:
        age_str = f"{report.cache_age_hours:.1f}h old" if report.cache_age_hours else "cached"
        lines.append(f"**⚡ CACHED RESULTS** ({age_str}) - use `--refresh` for fresh data")
        lines.append("")

    lines.append(f"**Date Range:** {report.range_from} to {report.range_to}")
    lines.append(f"**Mode:** {report.mode}")
    if report.openai_model_used:
        lines.append(f"**OpenAI Model:** {report.openai_model_used}")
    if report.xai_model_used:
        lines.append(f"**xAI Model:** {report.xai_model_used}")
    if report.resolved_x_handle:
        lines.append(f"**Resolved X Handle:** @{report.resolved_x_handle}")
    lines.append("")

    # Coverage note for partial coverage
    if report.mode == "reddit-only" and missing_keys in ("x", "none"):
        lines.append("*💡 Tip: Add an xAI key (`XAI_API_KEY`) for X/Twitter data and better triangulation.*")
        lines.append("")
    elif report.mode == "x-only" and missing_keys in ("reddit", "none"):
        lines.append("*💡 Tip: Add `SCRAPECREATORS_API_KEY` for Reddit + TikTok + Instagram data (one key, all three) — 100 free calls, no CC — scrapecreators.com (no affiliation)*")
        lines.append("")

    # Reddit items
    if report.reddit_error:
        lines.append("### Reddit Threads")
        lines.append("")
        lines.append(f"**ERROR:** {report.reddit_error}")
        lines.append("")
    elif report.mode in ("both", "reddit-only") and not report.reddit:
        lines.append("### Reddit Threads")
        lines.append("")
        lines.append("*No relevant Reddit threads found for this topic.*")
        lines.append("")
    elif report.reddit:
        lines.append("### Reddit Threads")
        lines.append("")
        for item in report.reddit[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.score is not None:
                    parts.append(f"{eng.score}pts")
                if eng.num_comments is not None:
                    parts.append(f"{eng.num_comments}cmt")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else " (date unknown)"
            conf_str = f" [date:{item.date_confidence}]" if item.date_confidence != "high" else ""

            lines.append(f"**{item.id}** (score:{item.score}) r/{item.subreddit}{date_str}{conf_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")

            # Top comment (elevated — Reddit's value IS the comments)
            if item.top_comments and item.top_comments[0].score >= 10:
                tc = item.top_comments[0]
                excerpt = tc.excerpt[:200]
                if len(tc.excerpt) > 200:
                    excerpt = excerpt.rstrip() + "..."
                lines.append(f'  \U0001f4ac Top comment ({tc.score} upvotes): "{excerpt}"')

            # Comment insights
            if item.comment_insights:
                lines.append("  Insights:")
                for insight in item.comment_insights[:3]:
                    lines.append(f"    - {insight}")

            lines.append("")

    # X items
    if report.x_error:
        lines.append("### X Posts")
        lines.append("")
        lines.append(f"**ERROR:** {report.x_error}")
        lines.append("")
    elif report.mode in ("both", "x-only", "all", "x-web") and not report.x:
        lines.append("### X Posts")
        lines.append("")
        lines.append("*No relevant X posts found for this topic.*")
        lines.append("")
    elif report.x:
        lines.append("### X Posts")
        lines.append("")
        for item in report.x[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.likes is not None:
                    parts.append(f"{eng.likes}likes")
                if eng.reposts is not None:
                    parts.append(f"{eng.reposts}rt")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else " (date unknown)"
            conf_str = f" [date:{item.date_confidence}]" if item.date_confidence != "high" else ""

            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_handle}{date_str}{conf_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.text[:200]}...")
            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # YouTube items
    if report.youtube_error:
        lines.append("### YouTube Videos")
        lines.append("")
        lines.append(f"**ERROR:** {report.youtube_error}")
        lines.append("")
    elif report.youtube:
        lines.append("### YouTube Videos")
        lines.append("")
        for item in report.youtube[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.views is not None:
                    parts.append(f"{eng.views:,} views")
                if eng.likes is not None:
                    parts.append(f"{eng.likes:,} likes")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) {item.channel_name}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            if item.transcript_highlights:
                lines.append("  Highlights:")
                for hl in item.transcript_highlights[:5]:
                    lines.append(f'    - "{hl}"')
            if item.transcript_snippet:
                word_count = len(item.transcript_snippet.split())
                lines.append(f"  <details><summary>Full transcript ({word_count} words)</summary>")
                lines.append(f"  {item.transcript_snippet}")
                lines.append("  </details>")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # TikTok items
    if report.tiktok_error:
        lines.append("### TikTok Videos")
        lines.append("")
        lines.append(f"**ERROR:** {report.tiktok_error}")
        lines.append("")
    elif report.tiktok:
        lines.append("### TikTok Videos")
        lines.append("")
        for item in report.tiktok[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.views is not None:
                    parts.append(f"{eng.views:,} views")
                if eng.likes is not None:
                    parts.append(f"{eng.likes:,} likes")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_name}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.text[:200]}")
            lines.append(f"  {item.url}")
            if item.caption_snippet and item.caption_snippet != item.text[:len(item.caption_snippet)]:
                snippet = item.caption_snippet[:200]
                if len(item.caption_snippet) > 200:
                    snippet += "..."
                lines.append(f"  Caption: {snippet}")
            if item.hashtags:
                lines.append(f"  Tags: {' '.join('#' + h for h in item.hashtags[:8])}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # Instagram items
    if report.instagram_error:
        lines.append("### Instagram Reels")
        lines.append("")
        lines.append(f"**ERROR:** {report.instagram_error}")
        lines.append("")
    elif report.instagram:
        lines.append("### Instagram Reels")
        lines.append("")
        for item in report.instagram[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.views is not None:
                    parts.append(f"{eng.views:,} views")
                if eng.likes is not None:
                    parts.append(f"{eng.likes:,} likes")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_name}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.text[:200]}")
            lines.append(f"  {item.url}")
            if item.caption_snippet and item.caption_snippet != item.text[:len(item.caption_snippet)]:
                snippet = item.caption_snippet[:200]
                if len(item.caption_snippet) > 200:
                    snippet += "..."
                lines.append(f"  Caption: {snippet}")
            if item.hashtags:
                lines.append(f"  Tags: {' '.join('#' + h for h in item.hashtags[:8])}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # Hacker News items
    if report.hackernews_error:
        lines.append("### Hacker News Stories")
        lines.append("")
        lines.append(f"**ERROR:** {report.hackernews_error}")
        lines.append("")
    elif report.hackernews:
        lines.append("### Hacker News Stories")
        lines.append("")
        for item in report.hackernews[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.score is not None:
                    parts.append(f"{eng.score}pts")
                if eng.num_comments is not None:
                    parts.append(f"{eng.num_comments}cmt")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) hn/{item.author}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.hn_url}")
            lines.append(f"  *{item.why_relevant}*")

            # Comment insights
            if item.comment_insights:
                lines.append(f"  Insights:")
                for insight in item.comment_insights[:3]:
                    lines.append(f"    - {insight}")

            lines.append("")

    # Bluesky items
    if report.bluesky_error:
        lines.append("### Bluesky Posts")
        lines.append("")
        lines.append(f"**ERROR:** {report.bluesky_error}")
        lines.append("")
    elif report.bluesky:
        lines.append("### Bluesky Posts")
        lines.append("")
        for item in report.bluesky[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.likes is not None:
                    parts.append(f"{eng.likes}lk")
                if eng.reposts is not None:
                    parts.append(f"{eng.reposts}rp")
                if eng.replies is not None:
                    parts.append(f"{eng.replies}re")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_handle}{date_str}{eng_str}{_xref_tag(item)}")
            if item.text:
                snippet = item.text[:200]
                if len(item.text) > 200:
                    snippet += "..."
                lines.append(f"  {snippet}")
            if item.url:
                lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # Truth Social items
    if report.truthsocial_error:
        lines.append("### Truth Social Posts")
        lines.append("")
        lines.append(f"**ERROR:** {report.truthsocial_error}")
        lines.append("")
    elif report.truthsocial:
        lines.append("### Truth Social Posts")
        lines.append("")
        for item in report.truthsocial[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.likes is not None:
                    parts.append(f"{eng.likes}lk")
                if eng.reposts is not None:
                    parts.append(f"{eng.reposts}rp")
                if eng.replies is not None:
                    parts.append(f"{eng.replies}re")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}) @{item.author_handle}{date_str}{eng_str}{_xref_tag(item)}")
            if item.text:
                snippet = item.text[:200]
                if len(item.text) > 200:
                    snippet += "..."
                lines.append(f"  {snippet}")
            if item.url:
                lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # Polymarket items
    if report.polymarket_error:
        lines.append("### Prediction Markets (Polymarket)")
        lines.append("")
        lines.append(f"**ERROR:** {report.polymarket_error}")
        lines.append("")
    elif report.polymarket:
        lines.append("### Prediction Markets (Polymarket)")
        lines.append("")
        for item in report.polymarket[:limit]:
            eng_str = ""
            if item.engagement:
                eng = item.engagement
                parts = []
                if eng.volume is not None:
                    if eng.volume >= 1_000_000:
                        parts.append(f"${eng.volume/1_000_000:.1f}M volume")
                    elif eng.volume >= 1_000:
                        parts.append(f"${eng.volume/1_000:.0f}K volume")
                    else:
                        parts.append(f"${eng.volume:.0f} volume")
                if eng.liquidity is not None:
                    if eng.liquidity >= 1_000_000:
                        parts.append(f"${eng.liquidity/1_000_000:.1f}M liquidity")
                    elif eng.liquidity >= 1_000:
                        parts.append(f"${eng.liquidity/1_000:.0f}K liquidity")
                    else:
                        parts.append(f"${eng.liquidity:.0f} liquidity")
                if parts:
                    eng_str = f" [{', '.join(parts)}]"

            date_str = f" ({item.date})" if item.date else ""

            lines.append(f"**{item.id}** (score:{item.score}){eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.question}")

            # Outcome prices with price movement
            if item.outcome_prices:
                outcomes = []
                for name, price in item.outcome_prices:
                    pct = price * 100
                    outcomes.append(f"{name}: {pct:.0f}%")
                outcome_line = " | ".join(outcomes)
                if item.outcomes_remaining > 0:
                    outcome_line += f" and {item.outcomes_remaining} more"
                if item.price_movement:
                    outcome_line += f" ({item.price_movement})"
                lines.append(f"  {outcome_line}")

            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    # Web items (if any - populated by the assistant)
    if report.web_error:
        lines.append("### Web Results")
        lines.append("")
        lines.append(f"**ERROR:** {report.web_error}")
        lines.append("")
    elif report.web:
        lines.append("### Web Results")
        lines.append("")
        for item in report.web[:limit]:
            date_str = f" ({item.date})" if item.date else " (date unknown)"
            conf_str = f" [date:{item.date_confidence}]" if item.date_confidence != "high" else ""

            lines.append(f"**{item.id}** [WEB] (score:{item.score}) {item.source_domain}{date_str}{conf_str}{_xref_tag(item)}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            lines.append(f"  {item.snippet[:150]}...")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    return "\n".join(lines)


def render_quality_nudge(quality: dict) -> str:
    """Render the quality score nudge block.

    Args:
        quality: Dict from quality_nudge.compute_quality_score()

    Returns:
        Markdown string with quality nudge, or empty string if no nudge.
    """
    nudge_text = quality.get("nudge_text")
    if not nudge_text:
        return ""

    lines = []
    lines.append("---")
    lines.append(f"**🔍 Research Coverage: {quality['score_pct']}%**")
    lines.append("")
    lines.append(nudge_text)
    lines.append("")
    return "\n".join(lines)


def render_source_status(report: schema.Report, source_info: dict = None) -> str:
    """Render source status footer showing what was used/skipped and why.

    Args:
        report: Report data
        source_info: Dict with source availability info:
            x_skip_reason, youtube_skip_reason, web_skip_reason

    Returns:
        Source status markdown string
    """
    if source_info is None:
        source_info = {}

    lines = []
    lines.append("---")
    lines.append("**Sources:**")

    # Reddit
    if report.reddit_error:
        lines.append(f"  ❌ Reddit: error — {report.reddit_error}")
    elif report.reddit:
        lines.append(f"  ✅ Reddit: {len(report.reddit)} threads")
    elif report.mode in ("both", "reddit-only", "all", "reddit-web"):
        pass  # Hide zero-result sources
    else:
        reason = source_info.get("reddit_skip_reason", "not configured")
        lines.append(f"  ⏭️ Reddit: skipped — {reason}")

    # X
    if report.x_error:
        lines.append(f"  ❌ X: error — {report.x_error}")
    elif report.x:
        x_line = f"  ✅ X: {len(report.x)} posts"
        if report.resolved_x_handle:
            x_line += f" (via @{report.resolved_x_handle} + keyword search)"
        lines.append(x_line)
    elif report.mode in ("both", "x-only", "all", "x-web"):
        pass  # Hide zero-result sources
    else:
        reason = source_info.get("x_skip_reason", "No Bird CLI or XAI_API_KEY")
        lines.append(f"  ⏭️ X: skipped — {reason}")

    # YouTube
    if report.youtube_error:
        lines.append(f"  ❌ YouTube: error — {report.youtube_error}")
    elif report.youtube:
        with_transcripts = sum(1 for v in report.youtube if getattr(v, 'transcript_snippet', None))
        lines.append(f"  ✅ YouTube: {len(report.youtube)} videos ({with_transcripts} with transcripts)")
    # Hide when zero results (no skip reason line needed)

    # TikTok
    if report.tiktok_error:
        lines.append(f"  ❌ TikTok: error — {report.tiktok_error}")
    elif report.tiktok:
        with_captions = sum(1 for v in report.tiktok if getattr(v, 'caption_snippet', None))
        lines.append(f"  ✅ TikTok: {len(report.tiktok)} videos ({with_captions} with captions)")
    # Hide when zero results

    # Instagram
    if report.instagram_error:
        lines.append(f"  ❌ Instagram: error — {report.instagram_error}")
    elif report.instagram:
        with_captions = sum(1 for v in report.instagram if getattr(v, 'caption_snippet', None))
        lines.append(f"  ✅ Instagram: {len(report.instagram)} reels ({with_captions} with captions)")
    # Hide when zero results

    # Xiaohongshu (from Web source bucket)
    xhs_count = 0
    if report.web:
        xhs_count = sum(
            1 for w in report.web
            if getattr(w, "source_domain", "").lower().endswith("xiaohongshu.com")
        )
    if xhs_count > 0:
        lines.append(f"  ✅ Xiaohongshu: {xhs_count} notes")
    else:
        reason = source_info.get("xiaohongshu_skip_reason")
        if reason:
            lines.append(f"  ⚡ Xiaohongshu: {reason}")

    # Hacker News
    if report.hackernews_error:
        lines.append(f"  ❌ HN: error - {report.hackernews_error}")
    elif report.hackernews:
        lines.append(f"  ✅ HN: {len(report.hackernews)} stories")
    # Hide when zero results

    # Bluesky
    if report.bluesky_error:
        lines.append(f"  ❌ Bluesky: error - {report.bluesky_error}")
    elif report.bluesky:
        lines.append(f"  ✅ Bluesky: {len(report.bluesky)} posts")
    # Hide when zero results

    # Truth Social
    if report.truthsocial_error:
        lines.append(f"  ❌ Truth Social: error - {report.truthsocial_error}")
    elif report.truthsocial:
        lines.append(f"  ✅ Truth Social: {len(report.truthsocial)} posts")
    # Hide when zero results

    # Polymarket
    if report.polymarket_error:
        lines.append(f"  ❌ Polymarket: error - {report.polymarket_error}")
    elif report.polymarket:
        lines.append(f"  ✅ Polymarket: {len(report.polymarket)} markets")
    # Hide when zero results

    # Web
    if report.web_error:
        lines.append(f"  ❌ Web: error — {report.web_error}")
    elif report.web:
        lines.append(f"  ✅ Web: {len(report.web)} pages")
    else:
        reason = source_info.get("web_skip_reason", "assistant will use WebSearch")
        lines.append(f"  ⚡ Web: {reason}")

    lines.append("")
    return "\n".join(lines)


def render_context_snippet(report: schema.Report) -> str:
    """Render reusable context snippet.

    Args:
        report: Report data

    Returns:
        Context markdown string
    """
    lines = []
    lines.append(f"# Context: {report.topic} (Last 30 Days)")
    lines.append("")
    lines.append(f"*Generated: {report.generated_at[:10]} | Sources: {report.mode}*")
    lines.append("")

    # Key sources summary
    lines.append("## Key Sources")
    lines.append("")

    all_items = []
    for item in report.reddit[:5]:
        all_items.append((item.score, "Reddit", item.title, item.url))
    for item in report.x[:5]:
        all_items.append((item.score, "X", item.text[:50] + "...", item.url))
    for item in report.tiktok[:5]:
        all_items.append((item.score, "TikTok", item.text[:50] + "...", item.url))
    for item in report.instagram[:5]:
        all_items.append((item.score, "Instagram", item.text[:50] + "...", item.url))
    for item in report.hackernews[:5]:
        all_items.append((item.score, "HN", item.title[:50] + "...", item.hn_url))
    for item in report.bluesky[:5]:
        all_items.append((item.score, "Bluesky", item.text[:50] + "...", item.url))
    for item in report.truthsocial[:5]:
        all_items.append((item.score, "Truth Social", item.text[:50] + "...", item.url))
    for item in report.polymarket[:5]:
        all_items.append((item.score, "Polymarket", item.question[:50] + "...", item.url))
    for item in report.web[:5]:
        all_items.append((item.score, "Web", item.title[:50] + "...", item.url))

    all_items.sort(key=lambda x: -x[0])
    for score, source, text, url in all_items[:7]:
        lines.append(f"- [{source}] {text}")

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("*See full report for best practices, prompt pack, and detailed sources.*")
    lines.append("")

    return "\n".join(lines)


def render_full_report(report: schema.Report) -> str:
    """Render full markdown report.

    Args:
        report: Report data

    Returns:
        Full report markdown
    """
    lines = []

    # Title
    lines.append(f"# {report.topic} - Last 30 Days Research Report")
    lines.append("")
    lines.append(f"**Generated:** {report.generated_at}")
    lines.append(f"**Date Range:** {report.range_from} to {report.range_to}")
    lines.append(f"**Mode:** {report.mode}")
    lines.append("")

    # Models
    lines.append("## Models Used")
    lines.append("")
    if report.openai_model_used:
        lines.append(f"- **OpenAI:** {report.openai_model_used}")
    if report.xai_model_used:
        lines.append(f"- **xAI:** {report.xai_model_used}")
    lines.append("")

    # Reddit section
    if report.reddit:
        lines.append("## Reddit Threads")
        lines.append("")
        for item in report.reddit:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            lines.append(f"- **Subreddit:** r/{item.subreddit}")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'} (confidence: {item.date_confidence})")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.score or '?'} points, {eng.num_comments or '?'} comments")

            if item.top_comments and item.top_comments[0].score >= 10:
                tc = item.top_comments[0]
                excerpt = tc.excerpt[:200]
                if len(tc.excerpt) > 200:
                    excerpt = excerpt.rstrip() + "..."
                lines.append("")
                lines.append(f'**\U0001f4ac Top Comment** ({tc.score} upvotes, u/{tc.author}):')
                lines.append(f'> {excerpt}')

            if item.comment_insights:
                lines.append("")
                lines.append("**Key Insights from Comments:**")
                for insight in item.comment_insights:
                    lines.append(f"- {insight}")

            lines.append("")

    # X section
    if report.x:
        lines.append("## X Posts")
        lines.append("")
        for item in report.x:
            lines.append(f"### {item.id}: @{item.author_handle}")
            lines.append("")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'} (confidence: {item.date_confidence})")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.likes or '?'} likes, {eng.reposts or '?'} reposts")

            lines.append("")
            lines.append(f"> {item.text}")
            lines.append("")

    # TikTok section
    if report.tiktok:
        lines.append("## TikTok Videos")
        lines.append("")
        for item in report.tiktok:
            lines.append(f"### {item.id}: @{item.author_name}")
            lines.append("")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.views or '?'} views, {eng.likes or '?'} likes, {eng.num_comments or '?'} comments")

            if item.hashtags:
                lines.append(f"- **Hashtags:** {' '.join('#' + h for h in item.hashtags[:10])}")

            lines.append("")
            lines.append(f"> {item.text[:300]}")
            lines.append("")

    # Instagram section
    if report.instagram:
        lines.append("## Instagram Reels")
        lines.append("")
        for item in report.instagram:
            lines.append(f"### {item.id}: @{item.author_name}")
            lines.append("")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.views or '?'} views, {eng.likes or '?'} likes, {eng.num_comments or '?'} comments")

            if item.hashtags:
                lines.append(f"- **Hashtags:** {' '.join('#' + h for h in item.hashtags[:10])}")

            lines.append("")
            lines.append(f"> {item.text[:300]}")
            lines.append("")

    # HN section
    if report.hackernews:
        lines.append("## Hacker News Stories")
        lines.append("")
        for item in report.hackernews:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            lines.append(f"- **Author:** {item.author}")
            lines.append(f"- **HN URL:** {item.hn_url}")
            if item.url:
                lines.append(f"- **Article URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.score or '?'} points, {eng.num_comments or '?'} comments")

            if item.comment_insights:
                lines.append("")
                lines.append("**Key Insights from Comments:**")
                for insight in item.comment_insights:
                    lines.append(f"- {insight}")

            lines.append("")

    # Bluesky section
    if report.bluesky:
        lines.append("## Bluesky Posts")
        lines.append("")
        for item in report.bluesky:
            lines.append(f"### {item.id}: @{item.author_handle}")
            lines.append("")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.likes or '?'} likes, {eng.reposts or '?'} reposts, {eng.replies or '?'} replies")

            lines.append("")
            lines.append(f"> {item.text[:300]}")
            lines.append("")

    # Truth Social section
    if report.truthsocial:
        lines.append("## Truth Social Posts")
        lines.append("")
        for item in report.truthsocial:
            lines.append(f"### {item.id}: @{item.author_handle}")
            lines.append("")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")

            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Engagement:** {eng.likes or '?'} likes, {eng.reposts or '?'} reposts, {eng.replies or '?'} replies")

            lines.append("")
            lines.append(f"> {item.text[:300]}")
            lines.append("")

    # Polymarket section
    if report.polymarket:
        lines.append("## Prediction Markets (Polymarket)")
        lines.append("")
        for item in report.polymarket:
            lines.append(f"### {item.id}: {item.question}")
            lines.append("")
            lines.append(f"- **Event:** {item.title}")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'}")
            lines.append(f"- **Score:** {item.score}/100")

            if item.outcome_prices:
                outcomes = [f"{name}: {price*100:.0f}%" for name, price in item.outcome_prices]
                lines.append(f"- **Outcomes:** {' | '.join(outcomes)}")
            if item.price_movement:
                lines.append(f"- **Trend:** {item.price_movement}")
            if item.engagement:
                eng = item.engagement
                lines.append(f"- **Volume:** ${eng.volume or 0:,.0f} | Liquidity: ${eng.liquidity or 0:,.0f}")

            lines.append("")

    # Web section
    if report.web:
        lines.append("## Web Results")
        lines.append("")
        for item in report.web:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            lines.append(f"- **Source:** {item.source_domain}")
            lines.append(f"- **URL:** {item.url}")
            lines.append(f"- **Date:** {item.date or 'Unknown'} (confidence: {item.date_confidence})")
            lines.append(f"- **Score:** {item.score}/100")
            lines.append(f"- **Relevance:** {item.why_relevant}")
            lines.append("")
            lines.append(f"> {item.snippet}")
            lines.append("")

    # Placeholders for assistant synthesis
    lines.append("## Best Practices")
    lines.append("")
    lines.append("*To be synthesized by assistant*")
    lines.append("")

    lines.append("## Prompt Pack")
    lines.append("")
    lines.append("*To be synthesized by assistant*")
    lines.append("")

    return "\n".join(lines)




def write_outputs(
    report: schema.Report,
    raw_openai: Optional[dict] = None,
    raw_xai: Optional[dict] = None,
    raw_reddit_enriched: Optional[list] = None,
):
    """Write all output files.

    Args:
        report: Report data
        raw_openai: Raw OpenAI API response
        raw_xai: Raw xAI API response
        raw_reddit_enriched: Raw enriched Reddit thread data
    """
    ensure_output_dir()

    # report.json
    with open(OUTPUT_DIR / "report.json", 'w') as f:
        json.dump(report.to_dict(), f, indent=2)

    # report.md
    with open(OUTPUT_DIR / "report.md", 'w') as f:
        f.write(render_full_report(report))

    # last30days.context.md
    with open(OUTPUT_DIR / "last30days.context.md", 'w') as f:
        f.write(render_context_snippet(report))

    # Raw responses
    if raw_openai:
        with open(OUTPUT_DIR / "raw_openai.json", 'w') as f:
            json.dump(raw_openai, f, indent=2)

    if raw_xai:
        with open(OUTPUT_DIR / "raw_xai.json", 'w') as f:
            json.dump(raw_xai, f, indent=2)

    if raw_reddit_enriched:
        with open(OUTPUT_DIR / "raw_reddit_threads_enriched.json", 'w') as f:
            json.dump(raw_reddit_enriched, f, indent=2)


def get_context_path() -> str:
    """Get path to context file."""
    return str(OUTPUT_DIR / "last30days.context.md")


def _slug(text: str) -> str:
    s = _re.sub(r'[^\w\s-]', '', text.lower())
    s = _re.sub(r'\s+', '-', s).strip('-')
    return s[:50]


def _e(text) -> str:
    return _html_mod.escape(str(text)) if text is not None else ""


def _build_html(
    report: schema.Report,
    run_dt: str,
    missing_keys: str,
    source_info: dict,
    quality: dict,
) -> str:
    topic = _e(report.topic)
    date_range = f"{_e(report.range_from)} → {_e(report.range_to)}"
    mode = _e(report.mode)

    p = []

    p.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>last30days: {topic}</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--text:#e2e8f0;--muted:#8892a4;--accent:#6366f1;--reddit:#ff4500;--x:#1d9bf0;--youtube:#ff0000;--tiktok:#69c9d0;--instagram:#e1306c;--hn:#ff6600;--bluesky:#0085ff;--web:#10b981;--polymarket:#8b5cf6;}}
@media(prefers-color-scheme:light){{:root{{--bg:#f8fafc;--surface:#ffffff;--border:#e2e8f0;--text:#1e293b;--muted:#64748b;}}}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
header{{background:var(--surface);border-bottom:1px solid var(--border);padding:1rem 2rem;position:sticky;top:0;z-index:100}}
.hi{{max-width:960px;margin:0 auto;display:flex;align-items:center;gap:1.25rem}}
.logo{{font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);white-space:nowrap;padding:2px 8px;border:1px solid var(--accent);border-radius:4px}}
.hm{{flex:1;min-width:0}}
.ht{{font-size:1.05rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hr{{font-size:.72rem;color:var(--muted);margin-top:1px}}
main{{max-width:960px;margin:2rem auto;padding:0 2rem 4rem}}
.sec{{margin-bottom:2.5rem}}
.st{{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:.75rem;display:flex;align-items:center;gap:.5rem}}
.st::after{{content:'';flex:1;height:1px;background:var(--border)}}
.dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem;margin-bottom:.625rem}}
.ch{{display:flex;align-items:flex-start;gap:.625rem;margin-bottom:.375rem}}
.cid{{font-size:.65rem;font-weight:700;color:var(--muted);font-family:monospace;white-space:nowrap;padding-top:3px}}
.ct{{font-size:.9375rem;font-weight:500;line-height:1.4}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
.cm{{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem;font-size:.72rem;color:var(--muted)}}
.pill{{background:var(--border);border-radius:4px;padding:1px 6px;white-space:nowrap}}
.rel{{font-size:.8rem;color:var(--muted);margin-top:.5rem;font-style:italic}}
.tc{{background:var(--bg);border-left:3px solid var(--reddit);border-radius:0 4px 4px 0;padding:.5rem .75rem;margin-top:.625rem;font-size:.8rem}}
.ins{{margin-top:.5rem}}
.ins-item{{font-size:.8rem;color:var(--muted);padding:.1rem 0}}
.ins-item::before{{content:'· '}}
.warn{{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);border-radius:8px;padding:.75rem 1rem;font-size:.8rem;color:#fbbf24;margin-bottom:1.5rem}}
.ss{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem}}
.sr{{display:flex;align-items:center;gap:.5rem;padding:.175rem 0;font-size:.8rem;color:var(--muted)}}
.ok{{color:#10b981}}.err{{color:#ef4444}}
details summary{{font-size:.75rem;color:var(--accent);cursor:pointer;margin-top:.5rem;user-select:none}}
.tc2{{margin-top:.5rem;font-size:.78rem;color:var(--muted);max-height:200px;overflow-y:auto;border-left:2px solid var(--border);padding-left:.75rem;white-space:pre-wrap}}
.body-text{{font-size:.85rem;margin-top:.25rem;line-height:1.5}}
</style>
</head>
<body>
<header>
<div class="hi">
  <div class="logo">last30days</div>
  <div class="hm">
    <div class="ht">{topic}</div>
    <div class="hr">Run {_e(run_dt)}&nbsp;&nbsp;·&nbsp;&nbsp;{mode}&nbsp;&nbsp;·&nbsp;&nbsp;{date_range}</div>
  </div>
</div>
</header>
<main>
""")

    freshness = _assess_data_freshness(report)
    if freshness["is_sparse"]:
        p.append(f'<div class="warn">⚠️ Limited recent data — only {freshness["total_recent"]} item(s) confirmed from the last 30 days. Results may include older content.</div>\n')

    if quality and quality.get("nudge_text"):
        p.append(f'<div class="warn">🔍 Research Coverage: {_e(str(quality.get("score_pct", "?")))}% — {_e(quality["nudge_text"])}</div>\n')

    # Reddit
    if report.reddit:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--reddit)"></span>Reddit</div>\n')
        for item in report.reddit:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.score is not None: eng_pills.append(f"{eng.score} pts")
                if eng.num_comments is not None: eng_pills.append(f"{eng.num_comments} comments")
            date_str = _e(item.date) if item.date else "date unknown"
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">{_e(item.title)}</a></div>')
            p.append(f'<div class="cm"><span class="pill">r/{_e(item.subreddit)}</span><span class="pill">{date_str}</span><span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            if item.top_comments and item.top_comments[0].score >= 10:
                tc = item.top_comments[0]
                excerpt = tc.excerpt[:200] + ("..." if len(tc.excerpt) > 200 else "")
                p.append(f'<div class="tc">💬 <strong>Top comment</strong> ({tc.score} upvotes): {_e(excerpt)}</div>')
            if item.comment_insights:
                p.append('<div class="ins">')
                for insight in item.comment_insights[:3]:
                    p.append(f'<div class="ins-item">{_e(insight)}</div>')
                p.append('</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # X
    if report.x:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--x)"></span>X / Twitter</div>\n')
        for item in report.x:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.likes is not None: eng_pills.append(f"{eng.likes} likes")
                if eng.reposts is not None: eng_pills.append(f"{eng.reposts} reposts")
            date_str = _e(item.date) if item.date else "date unknown"
            text_preview = _e(item.text[:200]) + ("..." if len(item.text) > 200 else "")
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">@{_e(item.author_handle)}</a></div>')
            p.append(f'<div class="body-text">{text_preview}</div>')
            p.append(f'<div class="cm"><span class="pill">{date_str}</span><span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # YouTube
    if report.youtube:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--youtube)"></span>YouTube</div>\n')
        for item in report.youtube:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.views is not None: eng_pills.append(f"{eng.views:,} views")
                if eng.likes is not None: eng_pills.append(f"{eng.likes:,} likes")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">{_e(item.title)}</a></div>')
            p.append(f'<div class="cm"><span class="pill">{_e(item.channel_name)}</span>')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.transcript_highlights:
                p.append('<div class="ins">')
                for hl in item.transcript_highlights[:5]:
                    p.append(f'<div class="ins-item">{_e(hl)}</div>')
                p.append('</div>')
            if item.transcript_snippet:
                wc = len(item.transcript_snippet.split())
                p.append(f'<details><summary>Full transcript ({wc} words)</summary><div class="tc2">{_e(item.transcript_snippet)}</div></details>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # TikTok
    if report.tiktok:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--tiktok)"></span>TikTok</div>\n')
        for item in report.tiktok:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.views is not None: eng_pills.append(f"{eng.views:,} views")
                if eng.likes is not None: eng_pills.append(f"{eng.likes:,} likes")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">@{_e(item.author_name)}</a></div>')
            p.append(f'<div class="body-text">{_e(item.text[:200])}</div>')
            p.append(f'<div class="cm">')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            if item.hashtags:
                p.append(f'<span class="pill">{_e(" ".join("#"+h for h in item.hashtags[:6]))}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Instagram
    if report.instagram:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--instagram)"></span>Instagram</div>\n')
        for item in report.instagram:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.views is not None: eng_pills.append(f"{eng.views:,} views")
                if eng.likes is not None: eng_pills.append(f"{eng.likes:,} likes")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">@{_e(item.author_name)}</a></div>')
            p.append(f'<div class="body-text">{_e(item.text[:200])}</div>')
            p.append(f'<div class="cm">')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            if item.hashtags:
                p.append(f'<span class="pill">{_e(" ".join("#"+h for h in item.hashtags[:6]))}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Hacker News
    if report.hackernews:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--hn)"></span>Hacker News</div>\n')
        for item in report.hackernews:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.score is not None: eng_pills.append(f"{eng.score} pts")
                if eng.num_comments is not None: eng_pills.append(f"{eng.num_comments} comments")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.hn_url)}" target="_blank" rel="noopener">{_e(item.title)}</a></div>')
            p.append(f'<div class="cm"><span class="pill">hn/{_e(item.author)}</span>')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.comment_insights:
                p.append('<div class="ins">')
                for insight in item.comment_insights[:3]:
                    p.append(f'<div class="ins-item">{_e(insight)}</div>')
                p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Bluesky
    if report.bluesky:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--bluesky)"></span>Bluesky</div>\n')
        for item in report.bluesky:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.likes is not None: eng_pills.append(f"{eng.likes} likes")
                if eng.reposts is not None: eng_pills.append(f"{eng.reposts} reposts")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">@{_e(item.author_handle)}</a></div>')
            if item.text:
                p.append(f'<div class="body-text">{_e(item.text[:200])}</div>')
            p.append(f'<div class="cm">')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Truth Social
    if report.truthsocial:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--reddit)"></span>Truth Social</div>\n')
        for item in report.truthsocial:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.likes is not None: eng_pills.append(f"{eng.likes} likes")
                if eng.reposts is not None: eng_pills.append(f"{eng.reposts} reposts")
            date_str = _e(item.date) if item.date else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">@{_e(item.author_handle)}</a></div>')
            if item.text:
                p.append(f'<div class="body-text">{_e(item.text[:200])}</div>')
            p.append(f'<div class="cm">')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Polymarket
    if report.polymarket:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--polymarket)"></span>Polymarket</div>\n')
        for item in report.polymarket:
            eng_pills = []
            if item.engagement:
                eng = item.engagement
                if eng.volume is not None:
                    v = eng.volume
                    eng_pills.append(f"${v/1_000_000:.1f}M vol" if v >= 1_000_000 else f"${v/1_000:.0f}K vol" if v >= 1_000 else f"${v:.0f} vol")
            date_str = _e(item.date) if item.date else ""
            outcomes_str = " | ".join(f"{n}: {pr*100:.0f}%" for n, pr in item.outcome_prices[:3]) if item.outcome_prices else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">{_e(item.question)}</a></div>')
            if outcomes_str:
                p.append(f'<div style="font-size:.82rem;margin-top:.3rem;color:var(--muted)">{_e(outcomes_str)}</div>')
            p.append(f'<div class="cm">')
            if date_str: p.append(f'<span class="pill">{date_str}</span>')
            p.append(f'<span class="pill">score {item.score}/100</span>')
            for ep in eng_pills:
                p.append(f'<span class="pill">{_e(ep)}</span>')
            p.append('</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Web
    if report.web:
        p.append('<div class="sec"><div class="st"><span class="dot" style="background:var(--web)"></span>Web</div>\n')
        for item in report.web:
            date_str = _e(item.date) if item.date else "date unknown"
            snippet = _e(item.snippet[:150]) if item.snippet else ""
            p.append(f'<div class="card"><div class="ch"><div class="cid">{_e(item.id)}</div><div style="flex:1">')
            p.append(f'<div class="ct"><a href="{_e(item.url)}" target="_blank" rel="noopener">{_e(item.title)}</a></div>')
            p.append(f'<div class="cm"><span class="pill">{_e(item.source_domain)}</span><span class="pill">{date_str}</span><span class="pill">score {item.score}/100</span></div>')
            if snippet:
                p.append(f'<div class="body-text" style="color:var(--muted)">{snippet}…</div>')
            if item.why_relevant:
                p.append(f'<div class="rel">{_e(item.why_relevant)}</div>')
            p.append('</div></div></div>\n')
        p.append('</div>\n')

    # Source status
    p.append('<div class="sec"><div class="st">Sources</div><div class="ss">\n')

    def _sr(icon, label, text, css=""):
        return f'<div class="sr {css}"><span>{icon}</span><span style="font-weight:600;min-width:90px">{_e(label)}</span><span>{_e(text)}</span></div>\n'

    if report.reddit_error:
        p.append(_sr("❌", "Reddit", report.reddit_error, "err"))
    elif report.reddit:
        p.append(_sr("✅", "Reddit", f"{len(report.reddit)} threads", "ok"))
    if report.x_error:
        p.append(_sr("❌", "X", report.x_error, "err"))
    elif report.x:
        p.append(_sr("✅", "X", f"{len(report.x)} posts", "ok"))
    if report.youtube_error:
        p.append(_sr("❌", "YouTube", report.youtube_error, "err"))
    elif report.youtube:
        wt = sum(1 for v in report.youtube if getattr(v, 'transcript_snippet', None))
        p.append(_sr("✅", "YouTube", f"{len(report.youtube)} videos ({wt} with transcripts)", "ok"))
    if report.tiktok_error:
        p.append(_sr("❌", "TikTok", report.tiktok_error, "err"))
    elif report.tiktok:
        p.append(_sr("✅", "TikTok", f"{len(report.tiktok)} videos", "ok"))
    if report.instagram_error:
        p.append(_sr("❌", "Instagram", report.instagram_error, "err"))
    elif report.instagram:
        p.append(_sr("✅", "Instagram", f"{len(report.instagram)} reels", "ok"))
    if report.hackernews_error:
        p.append(_sr("❌", "Hacker News", report.hackernews_error, "err"))
    elif report.hackernews:
        p.append(_sr("✅", "Hacker News", f"{len(report.hackernews)} stories", "ok"))
    if report.bluesky_error:
        p.append(_sr("❌", "Bluesky", report.bluesky_error, "err"))
    elif report.bluesky:
        p.append(_sr("✅", "Bluesky", f"{len(report.bluesky)} posts", "ok"))
    if report.truthsocial_error:
        p.append(_sr("❌", "Truth Social", report.truthsocial_error, "err"))
    elif report.truthsocial:
        p.append(_sr("✅", "Truth Social", f"{len(report.truthsocial)} posts", "ok"))
    if report.polymarket_error:
        p.append(_sr("❌", "Polymarket", report.polymarket_error, "err"))
    elif report.polymarket:
        p.append(_sr("✅", "Polymarket", f"{len(report.polymarket)} markets", "ok"))
    if report.web_error:
        p.append(_sr("❌", "Web", report.web_error, "err"))
    elif report.web:
        p.append(_sr("✅", "Web", f"{len(report.web)} pages", "ok"))
    else:
        p.append(_sr("⚡", "Web", source_info.get("web_skip_reason", "assistant will use WebSearch")))

    p.append('</div></div>\n')
    p.append('</main>\n</body>\n</html>')
    return "".join(p)


def save_html(
    report: schema.Report,
    missing_keys: str = "none",
    source_info: dict = None,
    quality: dict = None,
) -> Path:
    """Save report as a styled HTML file. Returns the saved path.

    Filename: {topic-slug}_{YYYY-MM-DD_HH-MM-SS}.html
    """
    ensure_output_dir()
    if source_info is None:
        source_info = {}

    slug = _slug(report.topic)
    ts = _dt.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dt = _dt.now().strftime("%B %d, %Y at %I:%M %p")
    out_path = OUTPUT_DIR / f"{slug}_{ts}.html"

    html_content = _build_html(report, run_dt, missing_keys, source_info, quality)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return out_path
