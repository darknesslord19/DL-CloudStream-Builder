#!/usr/bin/env python3
"""Bounded, same-origin discovery engine for sites the operator is authorized to inspect."""
import argparse, ipaddress, json, os, re, socket, time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

UA = 'DL-CloudStream-Builder/2.0 (+authorized site analysis)'
MEDIA_RE = re.compile(r'\.(m3u8|mpd|mp4|webm)(?:$|[?#])', re.I)
ASSET_RE = re.compile(r'\.(?:jpg|jpeg|png|gif|webp|svg|css|js|pdf|zip|woff2?)(?:$|[?#])', re.I)

def validate_public_url(url):
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ValueError('Yalnızca http/https adresleri desteklenir.')
    host = p.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Yerel/ağ içi adreslere izin verilmez.')
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        if not infos:
            raise ValueError('DNS adresi bulunamadı.')
        for info in infos:
            if not ipaddress.ip_address(info[4][0]).is_global:
                raise ValueError('Özel veya genel erişime kapalı IP adresine izin verilmez.')
    except socket.gaierror as e:
        raise ValueError(f'DNS çözümlemesi başarısız: {e}')
    return p

def clean_url(url):
    url, _ = urldefrag(url)
    p = urlparse(url)
    return p._replace(fragment='', query=p.query[:500]).geturl()

def text(el):
    return el.get_text(' ', strip=True)[:300] if el else ''

def img_url(el, page_url):
    if not el: return None
    for attr in ('data-src', 'data-lazy-src', 'data-original', 'data-lazyload', 'src', 'srcset'):
        value = (el.get(attr) or '').strip()
        if value:
            if attr == 'srcset': value = value.split(',')[0].strip().split(' ')[0]
            if value.startswith('data:'): continue
            return urljoin(page_url, value)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--max-pages', type=int, default=25)
    ap.add_argument('--timeout', type=int, default=15)
    ap.add_argument('--seeds', default='')
    ap.add_argument('--out', default='build/analysis')
    args = ap.parse_args()
    max_pages = max(1, min(50, args.max_pages)); timeout = max(3, min(25, args.timeout))
    base = clean_url(args.url); bp = validate_public_url(base)
    origin = (bp.scheme, bp.hostname, bp.port or (443 if bp.scheme == 'https' else 80))
    os.makedirs(args.out, exist_ok=True)
    session = requests.Session(); session.headers.update({'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml'})
    robots = RobotFileParser(); robots_url = f'{bp.scheme}://{bp.netloc}/robots.txt'
    try:
        rr = session.get(robots_url, timeout=timeout, allow_redirects=False)
        if rr.status_code in (401, 403): raise RuntimeError('robots.txt erişimi reddedildi; tarama durduruldu.')
        robots.parse(rr.text.splitlines() if rr.status_code == 200 else ['User-agent: *', 'Allow: /'])
    except requests.RequestException:
        robots.parse(['User-agent: *', 'Disallow: /'])
    seeds = [base] + [x.strip() for x in args.seeds.splitlines() if x.strip()]
    queue = deque(); errors = []; visited = set(); pages = []; all_links = set()
    for seed in seeds:
        try:
            sp = validate_public_url(seed)
            s_origin = (sp.scheme, sp.hostname, sp.port or (443 if sp.scheme == 'https' else 80))
            if s_origin == origin and robots.can_fetch(UA, seed): queue.append(clean_url(seed))
        except Exception as e: errors.append({'url': seed, 'error': str(e)[:180]})
    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited: continue
        visited.add(url)
        try:
            up = validate_public_url(url)
            u_origin = (up.scheme, up.hostname, up.port or (443 if up.scheme == 'https' else 80))
            if u_origin != origin: continue
            if not robots.can_fetch(UA, url):
                errors.append({'url': url, 'error': 'robots.txt tarafından izin verilmiyor'}); continue
            response = session.get(url, timeout=timeout, allow_redirects=False)
            if response.is_redirect:
                target = urljoin(url, response.headers.get('Location', ''))
                try:
                    tp = validate_public_url(target)
                    t_origin = (tp.scheme, tp.hostname, tp.port or (443 if tp.scheme == 'https' else 80))
                    if t_origin == origin and robots.can_fetch(UA, target) and target not in visited:
                        queue.appendleft(clean_url(target))
                    else: errors.append({'url': url, 'error': 'Alan adı dışına yönlendirme izlenmedi', 'location': target})
                except Exception as e: errors.append({'url': url, 'error': f'Güvenli olmayan yönlendirme: {e}'})
                continue
            if response.status_code >= 400:
                errors.append({'url': url, 'error': f'HTTP {response.status_code}'}); continue
            if 'html' not in response.headers.get('Content-Type', '').lower(): continue
            if len(response.content) > 2_500_000:
                errors.append({'url': url, 'error': 'HTML 2.5 MB sınırını aşıyor'}); continue
            soup = BeautifulSoup(response.text, 'html.parser')
            title = text(soup.title)
            meta_desc = soup.find('meta', attrs={'name': re.compile('description', re.I)})
            description = (meta_desc.get('content') or '')[:500] if meta_desc else ''
            canonical = soup.find('link', rel=lambda value: value and 'canonical' in value)
            og = soup.find('meta', property='og:image')
            og_image = urljoin(url, og.get('content', '')) if og and og.get('content') else None
            is_wp = bool(soup.find('link', href=re.compile(r'wp-content|wp-includes')) or soup.find('meta', attrs={'name': 'generator', 'content': re.compile('WordPress', re.I)}))
            posters = []
            for image_el in soup.select('img')[:500]:
                src = img_url(image_el, url)
                if not src: continue
                alt = (image_el.get('alt') or image_el.get('title') or '')[:200]
                cls = ' '.join(image_el.get('class', []))
                if any(k in (src + ' ' + alt + ' ' + cls).lower() for k in ('logo', 'avatar', 'icon', 'banner-ad', 'sprite')): continue
                posters.append({'url': src, 'alt': alt, 'width': image_el.get('width'), 'height': image_el.get('height')})
                if len(posters) >= 100: break
            anchors = []; iframes = []; media = []; categories = []
            for a in soup.select('a[href]')[:1500]:
                href = clean_url(urljoin(url, a.get('href', ''))); label = text(a)
                if not href.startswith(('http://', 'https://')): continue
                all_links.add(href)
                hp = urlparse(href); h_origin = (hp.scheme, hp.hostname, hp.port or (443 if hp.scheme == 'https' else 80))
                if h_origin == origin and href not in visited and not ASSET_RE.search(hp.path) and len(queue) < max_pages * 8:
                    if robots.can_fetch(UA, href): queue.append(href)
                match = MEDIA_RE.search(href)
                if match: media.append({'url': href, 'kind': match.group(1).lower()})
                anchors.append({'url': href, 'text': label})
                if any(word in (label + ' ' + hp.path).lower() for word in ('kategori', 'category', 'film', 'dizi', 'anime', 'son-bolum', 'son-bölüm', 'episode')) and len(label) < 120:
                    categories.append({'name': label, 'url': href})
                if len(anchors) >= 150: break
            for frame in soup.select('iframe[src], video[src], source[src]')[:60]:
                src = urljoin(url, frame.get('src', ''))
                if src.startswith(('http://', 'https://')):
                    if frame.name == 'iframe': iframes.append(src)
                    else:
                        match = MEDIA_RE.search(src)
                        if match: media.append({'url': src, 'kind': match.group(1).lower()})
            # JSON-LD gives structured title/poster/episode clues without executing scripts.
            jsonld = []
            for script in soup.select('script[type="application/ld+json"]')[:20]:
                try:
                    val = json.loads(script.string or script.get_text())
                    vals = val if isinstance(val, list) else [val]
                    for item in vals[:10]:
                        if isinstance(item, dict) and item.get('@type'):
                            jsonld.append({k: item.get(k) for k in ('@type', 'name', 'url', 'image', 'description', 'datePublished') if item.get(k) is not None})
                except Exception: pass
            pages.append({'url': url, 'status': response.status_code, 'title': title, 'description': description, 'canonical': urljoin(url, canonical.get('href')) if canonical and canonical.get('href') else None, 'og_image': og_image, 'wordpress_detected': is_wp, 'posters': posters, 'categories': categories[:100], 'links': anchors, 'iframes': list(dict.fromkeys(iframes)), 'media_candidates': media, 'jsonld': jsonld})
            time.sleep(0.1)
        except Exception as e:
            errors.append({'url': url, 'error': str(e)[:250]})
    all_titles = [p['title'] for p in pages if p.get('title')]
    report = {'engine': 'DL-CloudStream-Site-Engine', 'engineVersion': '2.0', 'requestedUrl': base, 'origin': bp.netloc, 'pagesVisited': len(visited), 'pagesParsed': len(pages), 'wordpressDetected': any(p.get('wordpress_detected') for p in pages), 'pages': pages, 'discoveredLinks': sorted(all_links)[:2000], 'errors': errors}
    with open(os.path.join(args.out, 'site-analysis.json'), 'w', encoding='utf-8') as f: json.dump(report, f, ensure_ascii=False, indent=2)
    summary = {'requestedUrl': base, 'pagesVisited': len(visited), 'pagesParsed': len(pages), 'wordpressDetected': report['wordpressDetected'], 'titles': all_titles[:100], 'categoryCandidates': list({(c['name'], c['url']): c for p in pages for c in p['categories']}.values())[:150], 'posterCandidates': list({x['url']: x for p in pages for x in p['posters']}.values())[:150], 'iframeCandidates': list(dict.fromkeys(x for p in pages for x in p['iframes']))[:150], 'mediaCandidates': list({x['url']: x for p in pages for x in p['media_candidates']}.values())[:150], 'errors': errors[:100]}
    with open(os.path.join(args.out, 'summary.json'), 'w', encoding='utf-8') as f: json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ('requestedUrl', 'pagesVisited', 'pagesParsed', 'wordpressDetected')}, ensure_ascii=False))

if __name__ == '__main__': main()
