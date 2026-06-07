# Custom Analytics Architecture + Share Route Audit

**Date:** 2026-06-07  
**Scope:** Audit of current share route architecture; design of custom analytics system  
**Status:** Audit/planning only — no code changes  
**Source of truth:** Actual backend code in `gallery/share_helpers.py`, `gallery/share_views.py`, `gallery/share_urls.py`, `gallery/serializers.py`, `gallery/models.py`, `gallery/public_urls.py`, `config/urls.py`, `config/settings.py`

---

## Part 1 — Share Route Architecture Audit

### 1.1 Current URL chain for a shared video

The following sequence is derived entirely from `share_helpers.py` and `share_views.py`.

#### Step 1 — Facebook share URL (what the frontend's share button opens)

```
https://www.facebook.com/sharer/sharer.php
  ?u=https%3A%2F%2Fkata-wild-backend-5b989da54ce2.herokuapp.com%2Fshare%2Fvideos%2F{pk}%2F
```

Built in `share_helpers.py → _fb_url()`:

```python
def _fb_url(share_url: str) -> str:
    return (
        "https://www.facebook.com/sharer/sharer.php"
        f"?u={quote(share_url, safe='')}"
    )
```

The `share_url` fed into `_fb_url()` is `request.build_absolute_uri(f"/share/videos/{video.pk}/")`  — the backend Heroku host, not the frontend.

#### Step 2 — Share page URL (what Facebook's crawler fetches)

```
https://kata-wild-backend-5b989da54ce2.herokuapp.com/share/videos/{pk}/
```

Served by `VideoShareView` in `share_views.py`. Returns an HTML page with correct Open Graph and Twitter Card meta tags. **This step works correctly.** Privacy guard: returns 404 if `is_public=False` or `status != 'ready'`.

`og:url` in the rendered HTML is also set to the backend share URL (not the frontend), which is correct for Facebook's crawler.

#### Step 3 — "Pogledaj na Kata Wild →" link (inside the share page)

From `share_helpers.py → video_og_meta()`:

```python
"frontend_url": f"{_frontend_url()}/videos/{video.pk}",
```

With `FRONTEND_URL=https://kataphotos.com` (the default), this produces:

```
https://kataphotos.com/videos/{pk}
```

Where `{pk}` is an **integer database primary key** from `VideoClip.pk`.

#### Step 4 — What the human user lands on

```
https://kataphotos.com/videos/{pk}   →   404 Not Found
```

**This is the broken step.** The frontend SPA does not have a `/videos/<pk>` route (or any `/videos/` route at all based on observed behaviour), so the user sees a 404 page.

---

### 1.2 Which URL Facebook shares today

Facebook shares the backend share page URL:

```
https://kata-wild-backend-5b989da54ce2.herokuapp.com/share/videos/{pk}/
```

This is the URL passed to `sharer.php?u=`. Facebook's crawler fetches this URL and reads the OG tags. The sharing preview (thumbnail, title, description) is built from the backend `/share/videos/{pk}/` page.

**The share preview itself works.**

---

### 1.3 Which URL Facebook crawls today

```
https://kata-wild-backend-5b989da54ce2.herokuapp.com/share/videos/{pk}/
```

Same as above. Facebook's scraper requests this URL. The backend returns a complete HTML page with OG metadata. There is no auto-redirect. **This step works correctly.**

---

### 1.4 Which URL humans ultimately land on today

After clicking a shared Facebook link, a human user:

1. Is taken to the Facebook sharer page.
2. Sees the rich preview (image, title, description) pulled from the backend `/share/videos/{pk}/`.
3. Clicks the link or opens the post — arrives at `https://kata-wild-backend-5b989da54ce2.herokuapp.com/share/videos/{pk}/`.
4. Sees the minimal backend HTML page with a "Pogledaj na Kata Wild →" button.
5. Clicks the button — navigates to `https://kataphotos.com/videos/{pk}`.
6. Frontend returns **404**.

The human final destination today is a broken page at `https://kataphotos.com/videos/{pk}`.

---

### 1.5 Which URL is intended to become the canonical public video URL

**Not yet defined on the frontend.** The backend currently assumes:

```
https://kataphotos.com/videos/{pk}
```

However `VideoClip` has no slug field. Its only string identifier is `cloudflare_uid` (a Cloudflare-assigned opaque string stored in `VideoClip.cloudflare_uid`). This means the canonical public URL options are:

| Option | Example | Notes |
|---|---|---|
| `/videos/{pk}` | `/videos/42` | Integer PK — current backend assumption, but frontend 404s |
| `/videos/{cloudflare_uid}` | `/videos/abc123def456...` | Cloudflare UID — unique, but opaque and non-human-friendly |
| `/albums/{slug}` | `/albums/divlje-ptice` | Album route — works if videos are embedded in albums |
| `/albums/{slug}/videos/{pk}` | `/albums/divlje-ptice/videos/42` | Nested — requires frontend nested routing |
| `/albums/{slug}?video={pk}` | `/albums/divlje-ptice?video=42` | Query param approach |

The correct canonical URL **must be agreed with the frontend team** before it can be fixed in the backend.

---

### 1.6 Which frontend routes the backend currently assumes exist

Derived from `share_helpers.py → video_og_meta()`, `album_og_meta()`, `media_og_meta()`:

| Content type | Backend-assumed frontend URL | Status |
|---|---|---|
| Album | `https://kataphotos.com/albums/{album.slug}` | Likely correct (slug-based routing is standard) |
| Video | `https://kataphotos.com/videos/{video.pk}` | **BROKEN** — frontend 404s |
| Image | `https://kataphotos.com/images/{media_item.pk}` | Unconfirmed — no evidence frontend has `/images/{pk}` |

The `FRONTEND_URL` setting defaults to `https://kataphotos.com` and is read from the `FRONTEND_URL` environment variable (`config/settings.py` line 211).

---

### 1.7 Whether backend-generated frontend URLs match actual frontend routing

| Route | Backend generates | Actual frontend | Match |
|---|---|---|---|
| Albums | `/albums/{slug}` | Presumed to exist | Unconfirmed but likely ✓ |
| Videos | `/videos/{pk}` (integer) | Does not exist | **NO — 404** |
| Images | `/images/{pk}` (integer) | Unconfirmed | Unknown |

**Root cause:** `VideoClip` has no slug. When `share_helpers.py` was implemented, it used `video.pk` as the only available unique identifier. The frontend routing convention for videos was not confirmed at implementation time.

---

### 1.8 Risk summary

| Risk | Severity | Impact |
|---|---|---|
| Users who click shared video links land on frontend 404 | **Critical** | Every Facebook video share is a dead end for humans |
| `frontend_url` in `PublicVideoCardSerializer` and `PublicVideoDetailSerializer` is wrong | High | Any frontend component rendering `frontend_url` links to a dead page |
| `frontend_url` for images (`/images/{pk}`) is unconfirmed | Medium | May be broken if frontend lacks `/images/<pk>` route |
| Analytics built on video share traffic will be misleading until route is fixed | High | Share attribution cannot be properly measured |
| `og:url` correctly points to backend share URL (not frontend) | Not a risk | Facebook crawling works; this is correct |

---

### 1.9 What should be done before analytics (Phase 0)

Analytics for video share traffic and conversion (share → visit → engagement) **cannot be meaningfully implemented** until:

1. The canonical frontend URL for videos is defined (with the frontend team).
2. `share_helpers.py → video_og_meta()` and `video_share_info()` are updated to generate a working `frontend_url`.
3. Optionally: the same is confirmed for images.

Until the route is fixed, any analytics system will count share-page visits (on the backend) but will not be able to track whether users successfully reach content — because they do not.

---

## Part 2 — Custom Analytics Architecture

### 2.1 Design principles

- No Google Analytics, Meta Pixel, or third-party tracking scripts.
- No full IP addresses stored permanently.
- No fingerprinting.
- No tracking admin pages.
- No one-row-per-page-view-forever storage.
- No write amplification from video playhead events.
- GDPR-minimal: no personal data beyond optional hashed daily visitor estimates.
- No cookie banner required for basic view counting.
- Heroku Postgres must not be overloaded by analytics writes.

---

### 2.2 Public resources to track

Derived from actual public endpoints in `gallery/public_urls.py`:

| Resource | Backend API endpoint | Worth tracking |
|---|---|---|
| Video detail | `GET /api/public/videos/<pk>/` | Yes |
| Video play start | No backend endpoint — frontend must signal | Yes (Phase 2) |
| Album detail | `GET /api/public/albums/<slug>/` | Yes |
| Album media list | `GET /api/public/albums/<slug>/media/` | Lower priority |
| Album video list | `GET /api/public/albums/<slug>/videos/` | Lower priority |
| Video list | `GET /api/public/videos/` | Low (list, not detail) |
| Hero video | `GET /api/public/hero-video/` | Low |
| Field note detail | `GET /api/gallery/field-notes/<slug>/` | Yes |
| Field note list | `GET /api/gallery/field-notes/` | Low |
| Contact form | `POST /api/public/messages/` | Yes (already a DB write) |
| Timestamp comment | `POST /api/public/videos/<pk>/comments/` | Yes (already a DB write) |
| Facebook share click | No backend endpoint — frontend must signal | Yes (Phase 2) |
| Copy-link share click | No backend endpoint — frontend must signal | Yes (Phase 2) |

**What should NOT be tracked:**

- Admin pages (`/api/gallery/admin/...`) — authenticated, no public value
- Health checks or static file requests
- Every video playback second, pause, seek, or buffering event
- Failed API requests (errors are not engagement)
- Bot/crawler traffic (basic mitigation: ignore requests without a `User-Agent` or with known bot UAs)

---

### 2.3 Event design recommendation

| Event | Recommended | Method | Notes |
|---|---|---|---|
| `album_view` | Yes — Phase 1 | Backend middleware/view hook | Count on `GET /api/public/albums/<slug>/` |
| `video_detail_view` | Yes — Phase 1 | Backend middleware/view hook | Count on `GET /api/public/videos/<pk>/` |
| `video_play` | Yes — Phase 2 | Frontend signals backend endpoint | Only after actual playback starts, not on page load |
| `image_view` | Yes — Phase 1 | Backend view hook | Count on `GET /api/public/albums/<slug>/media/` detail-equivalent |
| `field_note_view` | Yes — Phase 1 | Backend view hook | Count on `GET /api/gallery/field-notes/<slug>/` |
| `contact_form_submit` | Yes — Phase 1 | Inferred from `VisitorMessage.objects.create()` | No extra model needed; query existing table |
| `comment_submit` | Yes — Phase 1 | Inferred from `VideoTimestampComment` | No extra model needed |
| `share_click_facebook` | Yes — Phase 2 | Frontend signals `POST /api/public/analytics/share-click/` | After route is fixed |
| `share_click_copy` | Yes — Phase 2 | Frontend signals same endpoint | |

**Events NOT recommended:**

| Event | Reason |
|---|---|
| `site_page_view` | Too coarse; album/video/image views are more useful individually |
| Video pause | Write amplification, no promotional value |
| Video seek | Write amplification, no promotional value |
| Video playhead update | Write amplification, no promotional value |
| Admin page views | No public value; admin users are not the audience |

---

### 2.4 Proposed database models

#### Model A — `DailyContentViewStats`

One row per (date, content type, object ID). Updated with atomic `F()` increments.

```python
class DailyContentViewStats(models.Model):
    CONTENT_TYPE_ALBUM      = 'album'
    CONTENT_TYPE_VIDEO      = 'video'
    CONTENT_TYPE_IMAGE      = 'image'
    CONTENT_TYPE_FIELD_NOTE = 'field_note'

    CONTENT_TYPE_CHOICES = [
        (CONTENT_TYPE_ALBUM,      'Album'),
        (CONTENT_TYPE_VIDEO,      'Video'),
        (CONTENT_TYPE_IMAGE,      'Image'),
        (CONTENT_TYPE_FIELD_NOTE, 'Field Note'),
    ]

    date         = models.DateField()
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    object_id    = models.PositiveIntegerField()   # Album.pk / VideoClip.pk / MediaItem.pk / FieldNote.pk

    view_count             = models.PositiveIntegerField(default=0)
    video_play_count       = models.PositiveIntegerField(default=0)
    facebook_referrer_count = models.PositiveIntegerField(default=0)
    google_referrer_count   = models.PositiveIntegerField(default=0)
    instagram_referrer_count = models.PositiveIntegerField(default=0)
    direct_referrer_count   = models.PositiveIntegerField(default=0)
    other_referrer_count    = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('date', 'content_type', 'object_id')]
        indexes = [
            models.Index(fields=['content_type', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['content_type', '-view_count']),
        ]
```

**Row growth:** Maximum one row per piece of content per day. For 100 videos + 50 albums + 200 images + 20 field notes = 370 content pieces × 365 days = ~135,050 rows per year. Completely manageable in Heroku Postgres.

---

#### Model B — `DailySiteStats`

One row per day for site-wide totals. Simple to query for dashboards.

```python
class DailySiteStats(models.Model):
    date = models.DateField(unique=True)

    total_page_views         = models.PositiveIntegerField(default=0)
    total_video_views        = models.PositiveIntegerField(default=0)
    total_album_views        = models.PositiveIntegerField(default=0)
    total_image_views        = models.PositiveIntegerField(default=0)
    total_field_note_views   = models.PositiveIntegerField(default=0)

    facebook_referrer_count  = models.PositiveIntegerField(default=0)
    google_referrer_count    = models.PositiveIntegerField(default=0)
    instagram_referrer_count = models.PositiveIntegerField(default=0)
    direct_referrer_count    = models.PositiveIntegerField(default=0)
    other_referrer_count     = models.PositiveIntegerField(default=0)

    total_contact_submissions  = models.PositiveIntegerField(default=0)
    total_comment_submissions  = models.PositiveIntegerField(default=0)
    total_facebook_share_clicks = models.PositiveIntegerField(default=0)
    total_copy_link_clicks      = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['-date']),
        ]
```

**Row growth:** One row per day. 365 rows per year. Negligible.

---

#### Model C — `DailyCampaignStats` (Phase 2)

For UTM parameter tracking. Supports campaigns like:

```
?utm_source=facebook&utm_medium=social&utm_campaign=wild_boars_lunch_time
```

```python
class DailyCampaignStats(models.Model):
    date         = models.DateField()
    utm_source   = models.CharField(max_length=100, db_default='')
    utm_medium   = models.CharField(max_length=100, db_default='')
    utm_campaign = models.CharField(max_length=200, db_default='')
    visit_count  = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('date', 'utm_source', 'utm_medium', 'utm_campaign')]
        indexes = [
            models.Index(fields=['date', 'utm_source']),
            models.Index(fields=['utm_campaign', 'date']),
        ]
```

**Row growth:** One row per unique UTM combination per day. Bounded by the number of distinct campaigns run. For a small wildlife site: low double-digits per day at most.

---

#### Optional Model D — `AnalyticsEventBuffer` (only if replay is needed)

Not recommended for Phase 1. Only if you later need raw event replay for debugging or back-filling aggregates.

If implemented:

```python
class AnalyticsEventBuffer(models.Model):
    EVENT_CHOICES = [
        ('album_view', 'Album View'),
        ('video_detail_view', 'Video Detail View'),
        ('video_play', 'Video Play'),
        ('image_view', 'Image View'),
        ('field_note_view', 'Field Note View'),
        ('share_click_facebook', 'Share Click Facebook'),
        ('share_click_copy', 'Share Click Copy'),
    ]

    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type   = models.CharField(max_length=40, choices=EVENT_CHOICES)
    content_type = models.CharField(max_length=20, blank=True)
    object_id    = models.PositiveIntegerField(null=True, blank=True)
    referrer_class = models.CharField(max_length=20, blank=True)  # facebook/google/direct/other
    visitor_hash = models.CharField(max_length=16, blank=True)    # privacy-safe daily hash
    utm_source   = models.CharField(max_length=100, blank=True)
    utm_medium   = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
```

**Retention policy:** 7 days maximum. A daily management command runs at midnight, aggregates the previous day's buffer rows into `DailyContentViewStats` and `DailySiteStats`, then deletes them.

**Cleanup strategy:** `AnalyticsEventBuffer.objects.filter(created_at__date__lt=today - timedelta(days=7)).delete()` — run as a Heroku Scheduler job.

**Storage limits:** At 1,000 visits/day × 7 days = 7,000 rows maximum. Each row ~200 bytes = ~1.4 MB. Entirely negligible.

**Skip this model for Phase 1.** The aggregate-first approach (Models A and B) is simpler and sufficient for a wildlife photography site.

---

### 2.5 Write strategy — avoiding write amplification

**Use Django `F()` expressions for all counter increments.** This performs a single atomic `UPDATE` on the database, with no SELECT–modify–UPDATE cycle and no lock contention:

```python
from django.db.models import F
from django.utils import timezone

def record_video_view(video_pk: int, referrer_class: str) -> None:
    today = timezone.localdate()
    obj, _ = DailyContentViewStats.objects.get_or_create(
        date=today,
        content_type=DailyContentViewStats.CONTENT_TYPE_VIDEO,
        object_id=video_pk,
    )
    update_kwargs = {
        'view_count': F('view_count') + 1,
    }
    if referrer_class == 'facebook':
        update_kwargs['facebook_referrer_count'] = F('facebook_referrer_count') + 1
    elif referrer_class == 'google':
        update_kwargs['google_referrer_count'] = F('google_referrer_count') + 1
    elif referrer_class == 'instagram':
        update_kwargs['instagram_referrer_count'] = F('instagram_referrer_count') + 1
    elif referrer_class == 'direct':
        update_kwargs['direct_referrer_count'] = F('direct_referrer_count') + 1
    else:
        update_kwargs['other_referrer_count'] = F('other_referrer_count') + 1

    DailyContentViewStats.objects.filter(pk=obj.pk).update(**update_kwargs)
```

This is **two queries per tracked view** (one `get_or_create`, one `update`). For a small site this is acceptable inline. For high traffic, a task queue (Celery, RQ) or batching could defer these writes.

**Traffic spike protection:**

- The `unique_together` constraint ensures only one row per (date, content_type, object_id).
- Concurrent `F()` increments are safe — Postgres serialises the `UPDATE` at row level.
- No row locks are held during request processing.
- For burst traffic: the worst case is multiple `get_or_create` calls racing to create the row. Postgres will raise an `IntegrityError` on the second insert; catch it and retry the update.

---

### 2.6 Aggregation strategy

**No aggregation cron job is needed for Models A and B** because they are already aggregated (one row per content/day). The counters are incremented in real time.

If the optional `AnalyticsEventBuffer` (Model D) is used, a management command aggregates and clears it:

```
Management command: gallery/management/commands/aggregate_analytics.py
Schedule: Heroku Scheduler — daily at 00:05 UTC
```

The command:
1. Groups yesterday's buffer rows by `(event_type, content_type, object_id, referrer_class)`.
2. Upserts into `DailyContentViewStats` and `DailySiteStats`.
3. Deletes buffer rows older than 7 days.

---

### 2.7 Indexes needed

| Table | Index | Reason |
|---|---|---|
| `DailyContentViewStats` | `(content_type, date)` | Top-N queries by type and time window |
| `DailyContentViewStats` | `(date)` | Date-range queries |
| `DailyContentViewStats` | `(content_type, -view_count)` | Sorting by popularity |
| `DailyContentViewStats` | `unique_together(date, content_type, object_id)` | Prevents duplicate rows (also the primary unique constraint) |
| `DailySiteStats` | `(-date)` | Most-recent-first queries |
| `DailyCampaignStats` | `(date, utm_source)` | Filter by date + source |
| `DailyCampaignStats` | `(utm_campaign, date)` | Campaign performance over time |

---

### 2.8 Referrer classification

Implemented as a pure function, no DB queries:

```python
def classify_referrer(referrer_header: str) -> str:
    """
    Classify an HTTP Referer header value into one of:
    facebook | instagram | google | direct | other
    """
    if not referrer_header:
        return 'direct'
    url = referrer_header.lower()
    if any(x in url for x in ('facebook.com', 'fb.com', 'fb.me', 'm.facebook.com')):
        return 'facebook'
    if 'instagram.com' in url:
        return 'instagram'
    if any(x in url for x in ('google.', 'googlebot', 'googleapis')):
        return 'google'
    return 'other'
```

**Note on Facebook referrer:** When a user clicks a shared link in Facebook's native mobile app, the `Referer` header is often absent or set to `facebook.com`. When coming from a Facebook in-app browser, it may still be absent. UTM parameters are more reliable for tracking Facebook campaign traffic. The `Referer` header alone should not be the sole source of truth.

**UTM parameter support (Phase 2):**

Extract from the request query string. UTM params are not PII — no cookie or consent required:

```python
def extract_utm(request) -> dict:
    return {
        'utm_source':   request.GET.get('utm_source', '')[:100],
        'utm_medium':   request.GET.get('utm_medium', '')[:100],
        'utm_campaign': request.GET.get('utm_campaign', '')[:200],
    }
```

Frontend share buttons should append UTM params to links:

```
https://kataphotos.com/albums/divlje-ptice
  ?utm_source=facebook
  &utm_medium=social
  &utm_campaign=wild_boars_june_2026
```

---

### 2.9 Privacy strategy

#### Full IP addresses

**Do not store full IP addresses permanently.** The backend receives the IP from `request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')`. On Heroku this is set by the load balancer.

For **unique visitor estimation** (optional), use a daily-scoped hash:

```python
import hashlib
import os

_DAILY_SALT = os.getenv('ANALYTICS_IP_SALT', 'changeme-in-production')

def hash_visitor(ip: str, date) -> str:
    """
    Return a 16-character hex hash of (ip + date + salt).
    Not linkable across days. Cannot be reversed to the original IP.
    """
    raw = f"{ip}:{date.isoformat()}:{_DAILY_SALT}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

The full IP is **never written to the database**. Only the 16-character hash is stored, and only in `AnalyticsEventBuffer.visitor_hash` if that model is used. The hash is day-scoped: the same IP on two different days produces two different hashes, preventing cross-day tracking.

**Alternative if unique visitor estimation is not needed:** do not hash or store any IP-derived value at all. View counts without unique visitor de-duplication are still highly useful for promotional analytics.

#### Cookies

Basic view counting requires **zero cookies**. No consent banner is required.

UTM parameter tracking also requires no cookies — UTM values are in the URL query string, not stored client-side.

If unique visitor estimation using the day-scoped hash is implemented: still no cookies required on the client. The hash is computed server-side from the IP and discarded immediately after incrementing a counter.

#### GDPR implications

| Data stored | Personal data? | Retention | Risk |
|---|---|---|---|
| View counts per content/day | No | Indefinite (aggregates) | None |
| Referrer class (facebook/google/etc.) | No | Indefinite (aggregates) | None |
| UTM parameters | No (not linked to a person) | Indefinite (aggregates) | None |
| Day-scoped visitor hash | No (irreversible, day-scoped) | 7 days if in buffer | Very low |
| Full IP address | **Yes — do not store** | N/A | Not applicable |

**Summary:** The proposed architecture stores no personal data. GDPR Article 5(1)(c) (data minimisation) is satisfied. No Data Protection Impact Assessment (DPIA) is triggered. No consent banner is required.

---

### 2.10 Video tracking — safe strategy

**Phase 1:** Count one `view` when the video detail API endpoint is called (`GET /api/public/videos/<pk>/`). This is backend-side and requires no frontend changes.

**Phase 2:** Count one `video_play` when actual playback starts. This requires the frontend to call a lightweight backend endpoint:

```
POST /api/public/analytics/video-play/
Body: { "video_id": 42 }
```

Rules for video play counting:
- One play per user session per video per page load is sufficient.
- Do NOT track pause, resume, seek, or playhead position.
- Do NOT track every second of playback.
- A play event is recorded only after the video stream has actually started (i.e., after `canplay` or `playing` event fires in the browser, not on hover or thumbnail click).
- Optional: debounce on the frontend — if playback starts but the user skips away in under 3 seconds, consider not counting.

The backend endpoint increments `DailyContentViewStats.video_play_count` using `F('video_play_count') + 1`. No session state needed on the server.

---

### 2.11 Admin reporting recommendations

All reports are simple aggregate queries on `DailyContentViewStats` and `DailySiteStats`. No complex dashboard is needed.

#### Recommended first reports (Phase 1)

| Report | Query description |
|---|---|
| Top 10 videos (last 7 days) | `DailyContentViewStats.objects.filter(date__gte=7_days_ago, content_type='video').values('object_id').annotate(total=Sum('view_count')).order_by('-total')[:10]` |
| Top 10 videos (last 30 days) | Same with `date__gte=30_days_ago` |
| Top 10 albums (last 7 days) | Same with `content_type='album'` |
| Top 10 albums (last 30 days) | Same |
| Top 10 images (all time) | `content_type='image'`, no date filter |
| Traffic by referrer source | Sum `facebook_referrer_count`, `google_referrer_count`, etc. across `DailySiteStats` |
| Daily views trend (last 30 days) | `DailySiteStats.objects.filter(date__gte=30_days_ago).order_by('date')` |
| Contact submissions per week | Query `VisitorMessage.objects.filter(created_at__gte=...).count()` — no new model needed |

#### Phase 2 reports (after UTM tracking)

| Report | Query description |
|---|---|
| Top campaigns (30 days) | `DailyCampaignStats.objects.filter(date__gte=30_days_ago).values('utm_campaign').annotate(total=Sum('visit_count')).order_by('-total')` |
| Facebook campaign traffic | Filter `utm_source='facebook'` |
| Share performance | Sum `total_facebook_share_clicks` from `DailySiteStats` |

#### Admin implementation approach

Expose these reports via read-only admin-only API endpoints under `/api/gallery/admin/analytics/`. Alternatively, surface them directly in the Django Admin using `SimpleListFilter` and `ModelAdmin.changelist_view` overrides. No separate dashboard service is needed.

---

## Part 3 — Phased Implementation Roadmap

### Phase 0 — Routing Foundation (prerequisite)

**Do this first. Analytics for video shares are not meaningful until this is done.**

Tasks:
1. Agree with the frontend team on the canonical URL for a public video.
2. Update `share_helpers.py → video_og_meta()` and `video_share_info()` to generate the correct `frontend_url`.
3. Confirm whether the frontend has a `/images/{pk}` route or whether `media_og_meta()` also needs to change.
4. Update the `frontend_url` generated in `PublicVideoCardSerializer` and `PublicVideoDetailSerializer`.
5. Manually test: shared video → Facebook preview → click → correct frontend page.

**No analytics work should land in production until Phase 0 is complete.** Counting Facebook referrals to a 404 page produces misleading data.

---

### Phase 1 — Safe Analytics Foundation

**Backend-only. No frontend changes.**

Deliverables:
- New `analytics` Django app (or add models to `gallery` app).
- `DailyContentViewStats` and `DailySiteStats` models + migration.
- `classify_referrer()` utility function.
- View hooks on `PublicVideoDetailView`, `PublicAlbumDetailView`, `FieldNoteDetailView` to increment counters.
- No hooks on list views (too coarse).
- No hooks on admin views.
- Two read-only admin API endpoints: top-N content, site-wide daily stats.
- `manage.py check` passes.
- No tests (per project convention at this stage).

What Phase 1 answers:
- Which videos get the most API hits?
- Which albums get the most API hits?
- What fraction of traffic comes from Facebook vs. Google vs. direct?

---

### Phase 2 — Promotional Insights

**Requires Phase 0 (working frontend routes) to be meaningful.**

Deliverables:
- `DailyCampaignStats` model + migration.
- UTM parameter extraction in view hooks.
- `POST /api/public/analytics/video-play/` endpoint.
- `POST /api/public/analytics/share-click/` endpoint (for `share_click_facebook` and `share_click_copy`).
- `ANALYTICS_IP_SALT` environment variable documented.
- Admin reports for campaigns and share performance.
- Heroku Scheduler job if `AnalyticsEventBuffer` is added.

What Phase 2 answers:
- Which Facebook campaigns bring traffic?
- How many video plays result from Facebook shares?
- Which campaigns perform best?
- Do visitors who arrive from Facebook contact us?

---

### Phase 3 — Advanced Analytics (optional)

**Only if Phase 1 and Phase 2 data reveals a need.**

Candidates:
- Language preference analytics (count `?lang=bs` vs `?lang=en` requests — already available in request query params via `LangContextMixin`).
- Tag/wildlife topic analytics (join `DailyContentViewStats` with album/video tags).
- Visitor return rate estimation (day-scoped hashes across a week window).
- Field note topic analytics.
- Search term analytics (if search is implemented on the frontend).

---

## Part 4 — Recommended Next Implementation Prompt

The following prompt is ready to send to Copilot/Codex after Phase 0 is complete:

---

> **Backend: Phase 1 Analytics — DailyContentViewStats + DailySiteStats**
>
> Implement Phase 1 custom analytics for Kata Wild backend. Do not add Google Analytics or any third-party tracking.
>
> **New models** (in a new `analytics` app or added to `gallery/models.py`):
>
> - `DailyContentViewStats` with fields: `date`, `content_type` (choices: album/video/image/field_note), `object_id`, `view_count`, `video_play_count`, `facebook_referrer_count`, `google_referrer_count`, `instagram_referrer_count`, `direct_referrer_count`, `other_referrer_count`. `unique_together = [('date', 'content_type', 'object_id')]`. Indexes on `(content_type, date)`, `(date,)`.
> - `DailySiteStats` with fields: `date` (unique), `total_page_views`, `total_video_views`, `total_album_views`, `total_image_views`, `total_field_note_views`, `facebook_referrer_count`, `google_referrer_count`, `instagram_referrer_count`, `direct_referrer_count`, `other_referrer_count`, `total_contact_submissions`, `total_comment_submissions`.
>
> **Utility function** `classify_referrer(referer_header: str) -> str` returning one of: `facebook`, `instagram`, `google`, `direct`, `other`.
>
> **View hooks** (inline, not middleware): increment `DailyContentViewStats` and `DailySiteStats` counters using Django `F()` expressions inside `PublicVideoDetailView.get()`, `PublicAlbumDetailView.get()`, `FieldNoteDetailView.get()`. Do not track list views. Do not track admin views.
>
> **Read-only admin endpoints** (require `IsAdminUser`):
> - `GET /api/gallery/admin/analytics/top-content/?days=7&content_type=video&limit=10`
> - `GET /api/gallery/admin/analytics/site-stats/?days=30`
>
> Do not store full IP addresses. Do not add third-party packages. Do not add tests. Run `manage.py check` and confirm 0 issues. Write a brief implementation report.

---

## Appendix — Backend File Reference

| File | Relevant to this audit |
|---|---|
| `gallery/share_helpers.py` | Generates all `frontend_url`, `share_url`, `facebook_share_url` values |
| `gallery/share_views.py` | `AlbumShareView`, `VideoShareView`, `ImageShareView` — OG HTML pages |
| `gallery/share_urls.py` | Routes: `/share/albums/<slug>/`, `/share/videos/<pk>/`, `/share/images/<pk>/` |
| `config/urls.py` | Mounts `/share/` prefix |
| `config/settings.py` | `FRONTEND_URL`, `FALLBACK_OG_IMAGE` settings (lines 211–214) |
| `gallery/public_urls.py` | All public API endpoints — defines what is trackable |
| `gallery/serializers.py` | `PublicVideoCardSerializer`, `PublicVideoDetailSerializer`, `PublicAlbumCardSerializer`, `PublicAlbumDetailSerializer`, `MediaItemPublicSerializer` — all include share fields |
| `gallery/models.py` | `VideoClip` has no slug; only `pk` and `cloudflare_uid` as identifiers |
