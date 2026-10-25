"""JSON shapes shared by the API routes."""

from dataclasses import asdict

from sahifa.config import Settings
from sahifa.domain.lifecycle import limits_for
from sahifa.models import MediaItem, Museum


def media_url(settings: Settings, rel: str | None) -> str | None:
    return f"{settings.public_api_url}/media/{rel}" if rel else None


def media_out(settings: Settings, item: MediaItem) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "url": media_url(settings, item.path),
        "thumb_url": media_url(settings, item.thumb_path),
        "caption": item.caption,
        "taken_on": item.taken_on,
        "position": item.position,
    }


def museum_settings(settings: Settings, m: Museum) -> dict:
    return {
        "title": m.title,
        "recipient_name": m.recipient_name,
        "theme": m.theme,
        "mascot": m.mascot,
        "opening_style": m.opening_style,
        "letter_text": m.letter_text,
        "music_id": m.music_id,
        "music_url": media_url(settings, m.music_path),
        "voice_url": media_url(settings, m.voice_path),
        "open_at": m.open_at.isoformat() if m.open_at else None,
        "rooms": limits_for(m.extra_rooms).rooms,
    }


def museum_summary(settings: Settings, m: Museum, counts: dict, cover: MediaItem | None) -> dict:
    return {
        "id": m.id,
        "slug": m.slug,
        "title": m.title,
        "status": m.status,
        "template": m.template,
        "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        "cover_thumb": media_url(settings, cover.thumb_path) if cover else None,
        "counts": counts,
        "limits": asdict(limits_for(m.extra_rooms)),
    }


def museum_full(settings: Settings, m: Museum, items: list[MediaItem]) -> dict:
    counts = {"image": 0, "video": 0}
    for item in items:
        counts[item.kind] += 1
    return {
        **museum_summary(settings, m, counts, items[0] if items else None),
        **museum_settings(settings, m),
        "paid_at": m.paid_at.isoformat() if m.paid_at else None,
        "locked": m.paid_at is not None,
        "media": [media_out(settings, i) for i in items],
    }
