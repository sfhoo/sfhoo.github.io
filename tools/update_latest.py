#!/usr/bin/env python3
"""Update the "Latest" section of sfhoo.com from X posts tagged #sfhoo.

The site never loads anything from X at runtime. This script turns raw X API v2
post objects into static data (assets/latest.json), local images
(assets/img/latest/) and static HTML inside index.html between
<!-- LATEST:START --> / <!-- LATEST:END --> (plus the nav item between
<!-- LATEST-NAV:START --> / <!-- LATEST-NAV:END -->).

Usage (from the repo root):
    python3 tools/update_latest.py posts.json      # add/refresh posts from an X API response
    python3 tools/update_latest.py --remove ID     # drop a post and regenerate
    python3 tools/update_latest.py --render        # just regenerate HTML from latest.json

posts.json is the JSON body of
    GET /2/users/82902065/tweets?tweet.fields=created_at,entities,attachments,referenced_tweets
        &expansions=attachments.media_keys&media.fields=url,type,preview_image_url,alt_text
i.e. {"data": [...], "includes": {"media": [...]}} (a bare list of posts is accepted too).

Rules: only original posts whose text contains the hashtag #sfhoo (case-insensitive,
whole tag) are used; retweets are skipped. The #sfhoo tag is removed, t.co links are
replaced by their display text (media links are dropped), the first photo is
downloaded and resized to <= 800px wide (WebP + JPEG), posts are merged by id and
only the newest 3 are kept. All post text is HTML-escaped.

Requires Pillow only when a post has a photo (e.g. /workspace/resume-build/venv/bin/python).
Options: --allow-local-media lets media URLs be local files (testing only);
by default only https://pbs.twimg.com/ media is downloaded.
"""
import argparse, datetime as dt, html, io, json, os, re, sys, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'assets', 'latest.json')
INDEX = os.path.join(ROOT, 'index.html')
IMG_DIR = os.path.join(ROOT, 'assets', 'img', 'latest')
KEEP = 3
TZ = ZoneInfo('America/Chicago')
TAG_RE = re.compile(r'(?<![\w#])#sfhoo(?!\w)', re.I)
POST_URL = 'https://x.com/sfhoo/status/{}'

def load_json(path, default):
    if not os.path.exists(path): return default
    with open(path, encoding='utf-8') as f: return json.load(f)

def safe_http_url(u):
    try: p = urllib.parse.urlsplit(u or '')
    except ValueError: return None
    return u if p.scheme in ('http', 'https') and p.netloc else None

def is_retweet(post):
    if any(r.get('type') == 'retweeted' for r in post.get('referenced_tweets') or []): return True
    return (post.get('text') or '').startswith('RT @')

def clean_post(post):
    """Return (text, links) for display."""
    text = html.unescape(post.get('text') or '')       # API text has &amp; etc.
    links, seen = [], set()
    for u in (post.get('entities') or {}).get('urls') or []:
        tco = u.get('url') or ''
        expanded = u.get('expanded_url') or u.get('unwound_url') or ''
        is_media = bool(u.get('media_key')) or re.search(r'^https?://(x|twitter)\.com/[^/]+/status/\d+/(photo|video)/', expanded or '')
        if is_media:
            text = text.replace(tco, '')
            continue
        safe = safe_http_url(expanded)
        display = (u.get('display_url') or expanded or tco).strip()
        if not safe:
            text = text.replace(tco, display); continue
        text = text.replace(tco, display)
        if safe not in seen:
            seen.add(safe); links.append({'url': safe, 'display': display})
    text = TAG_RE.sub('', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text, links

def fetch_bytes(url, allow_local):
    if allow_local and not re.match(r'^https?://', url):
        path = url[7:] if url.startswith('file://') else url
        with open(path, 'rb') as f: return f.read()
    if not url.startswith('https://pbs.twimg.com/'):
        raise ValueError(f'refusing to download media from {url!r}')
    req = urllib.request.Request(url, headers={'User-Agent': 'sfhoo-latest-updater'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read(15_000_000 + 1)
    if len(data) > 15_000_000: raise ValueError('image too large')
    return data

def save_image(post_id, url, allow_local):
    from PIL import Image
    im = Image.open(io.BytesIO(fetch_bytes(url, allow_local)))
    im.load()
    im = im.convert('RGB')                    # also drops EXIF / metadata
    if im.width > 800:
        im = im.resize((800, round(im.height * 800 / im.width)), Image.LANCZOS)
    os.makedirs(IMG_DIR, exist_ok=True)
    base = os.path.join(IMG_DIR, post_id)
    im.save(base + '.webp', 'WEBP', quality=80, method=6)
    im.save(base + '.jpg', 'JPEG', quality=82, optimize=True, progressive=True)
    return {'src': f'/assets/img/latest/{post_id}.jpg', 'webp': f'/assets/img/latest/{post_id}.webp',
            'width': im.width, 'height': im.height}

def delete_images(post_id):
    for ext in ('.jpg', '.webp'):
        p = os.path.join(IMG_DIR, post_id + ext)
        if os.path.exists(p): os.remove(p)

def parse_input(raw):
    if isinstance(raw, list): return raw, {}
    media = {m.get('media_key'): m for m in (raw.get('includes') or {}).get('media') or []}
    data = raw.get('data') or []
    data = data if isinstance(data, list) else [data]
    for d in data:  # long posts (>280 chars): full text + entities live in note_tweet
        nt = d.get('note_tweet') or {}
        if nt.get('text'):
            d['text'] = nt['text']
            ents = dict(d.get('entities') or {})
            ents.update(nt.get('entities') or {})
            d['entities'] = ents
    return data, media

def to_entry(post, media, allow_local):
    pid = str(post.get('id') or '')
    if not re.fullmatch(r'\d{1,25}', pid): return None, 'bad id'
    if is_retweet(post): return None, 'retweet'
    if not TAG_RE.search(html.unescape(post.get('text') or '')): return None, 'no #sfhoo'
    created = post.get('created_at')
    try:
        when = dt.datetime.fromisoformat(created.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    except Exception:
        return None, 'bad created_at'
    text, links = clean_post(post)
    image = None
    for key in (post.get('attachments') or {}).get('media_keys') or []:
        m = media.get(key) or {}
        if m.get('type') == 'photo' and m.get('url'):
            try:
                image = save_image(pid, m['url'], allow_local)
                image['alt'] = (m.get('alt_text') or '').strip()
            except Exception as e:
                print(f'  ! image for {pid} skipped: {e}', file=sys.stderr)
            break
    return {'id': pid, 'url': POST_URL.format(pid), 'created_at': when.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'text': text, 'links': links, 'image': image}, None

# ---------------------------------------------------------------- rendering
def esc(s): return html.escape(s or '', quote=True)

def render_text(text, links):
    """Escape text; turn the display text of known links into anchors."""
    out, i = [], 0
    targets = [(l['display'], l['url']) for l in links if l.get('display')]
    while i < len(text):
        hit = None
        for disp, url in targets:
            j = text.find(disp, i)
            if j != -1 and (hit is None or j < hit[0]): hit = (j, disp, url)
        if not hit:
            out.append(esc(text[i:])); break
        j, disp, url = hit
        out.append(esc(text[i:j]))
        out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener nofollow ugc" data-latest-link="link">{esc(disp)}</a>')
        i = j + len(disp)
    return ''.join(out).replace('\n', '<br>')

def fmt_date(iso):
    d = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ)
    return f'{d:%b} {d.day}, {d.year}'

def render_section(posts):
    if not posts:
        return '\n        '
    cards = []
    for p in posts:
        img = ''
        if p.get('image'):
            im = p['image']
            img = (f'<picture class="latest-media"><source type="image/webp" srcset="{esc(im["webp"])}">'
                   f'<img src="{esc(im["src"])}" width="{int(im["width"])}" height="{int(im["height"])}" loading="lazy" decoding="async" alt="{esc(im.get("alt") or "")}"></picture>')
        cards.append(
            f'''        <article class="latest-card" data-latest-id="{esc(p["id"])}">
        <p class="eyebrow"><time datetime="{esc(p["created_at"])}">{esc(fmt_date(p["created_at"]))}</time></p>
        {img}<p class="latest-text">{render_text(p["text"], p.get("links") or [])}</p>
        <a class="latest-x" href="{esc(p["url"])}" target="_blank" rel="noopener nofollow ugc" data-latest-link="x">View on X <span aria-hidden="true">↗</span></a>
        </article>''')
    return f'''
        <section class="profile-section latest-section" id="latest" aria-labelledby="latest-title">
        <div class="container">
        <p class="eyebrow">04 / Latest</p>
        <h2 id="latest-title">What I'm sharing.</h2>
        <p class="section-intro">Recent notes I've posted on X and tagged #sfhoo.</p>
        <div class="latest-grid">
{chr(10).join(cards)}
        </div>
        </div>
        </section>
        '''

def replace_between(s, start, end, new):
    a, b = s.index(start) + len(start), s.index(end)
    return s[:a] + new + s[b:]

def render(posts):
    with open(INDEX, encoding='utf-8') as f: s = f.read()
    s = replace_between(s, '<!-- LATEST:START -->', '<!-- LATEST:END -->', render_section(posts))
    s = replace_between(s, '<!-- LATEST-NAV:START -->', '<!-- LATEST-NAV:END -->',
                        '<a href="#latest">Latest</a>' if posts else '')
    s = re.sub(r'<p class="eyebrow">0[45] / Connect</p>',
               f'<p class="eyebrow">{"05" if posts else "04"} / Connect</p>', s)
    with open(INDEX, 'w', encoding='utf-8') as f: f.write(s)

def save(posts):
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2); f.write('\n')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='?', help='X API v2 JSON response file')
    ap.add_argument('--remove', metavar='ID', action='append', default=[], help='remove a post by id (repeatable)')
    ap.add_argument('--render', action='store_true', help='only regenerate HTML from latest.json')
    ap.add_argument('--allow-local-media', action='store_true', help=argparse.SUPPRESS)
    a = ap.parse_args()
    if not (a.input or a.remove or a.render): ap.error('give an input file, --remove ID, or --render')

    posts = {p['id']: p for p in load_json(DATA, [])}
    before = set(posts)
    added, updated, skipped = [], [], []
    if a.input:
        raw_posts, media = parse_input(load_json(a.input, {}))
        for post in raw_posts:
            entry, why = to_entry(post, media, a.allow_local_media)
            if not entry:
                skipped.append((str(post.get('id')), why)); continue
            (updated if entry['id'] in posts else added).append(entry['id'])
            posts[entry['id']] = entry
    removed = []
    for pid in a.remove:
        if posts.pop(pid, None) is not None: removed.append(pid)
        else: print(f'  - {pid} not in latest.json')
    ordered = sorted(posts.values(), key=lambda p: p['created_at'], reverse=True)
    keep, dropped = ordered[:KEEP], [p['id'] for p in ordered[KEEP:]]
    for pid in dropped + removed:
        delete_images(pid)
    save(keep); render(keep)

    print(f'latest.json: {len(before)} -> {len(keep)} post(s)')
    for pid in added: print(f'  + added    {pid}' + ('' if pid in {p["id"] for p in keep} else ' (older than newest 3, not shown)'))
    for pid in updated: print(f'  ~ updated  {pid}')
    for pid in removed: print(f'  - removed  {pid}')
    for pid in dropped: print(f'  - dropped  {pid} (beyond newest {KEEP})')
    for pid, why in skipped: print(f'  . skipped  {pid}: {why}')
    print('Section is', 'visible' if keep else 'hidden (no posts)')

if __name__ == '__main__':
    main()
