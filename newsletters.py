"""Normalize approved newsletter exports into private, deduplicated evidence."""
import argparse
import base64
import datetime as dt
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent


class NewsletterHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links, self.bullets, self.stack = [], [], [], []
        self.finished = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (tag in ('style', 'script', 'head') or 'display:none' in
                  attrs.get('style', '').replace(' ', '').lower())
        if tag not in ('img', 'meta', 'link', 'br', 'hr', 'input'):
            self.stack.append((tag, hidden or any(v for _, v in self.stack)))
        if self.finished or any(v for _, v in self.stack):
            return
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'li':
            self.bullets.append([])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.finished or any(v for _, v in self.stack):
            return
        value = re.sub(r'\s+', ' ', data).strip()
        if value.startswith(('You may also like', 'Manage Alerts')):
            self.finished = True
            return
        if value:
            self.text.append(value)
            if self.bullets and any(t == 'li' for t, _ in self.stack):
                self.bullets[-1].append(value)


def article_url(link):
    """Decode a newsletter redirect locally; never visit tracking or login links."""
    parsed = urlsplit(link)
    if parsed.hostname == 'email-st.seekingalpha.com' and parsed.path.startswith('/click/'):
        try:
            encoded = parsed.path.split('/')[3]
            link = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8')
            parsed = urlsplit(link)
        except (ValueError, UnicodeError, IndexError):
            return None
    if (parsed.scheme != 'https' or parsed.hostname != 'seekingalpha.com'
            or not re.match(r'^/(article|news)/\d+-', parsed.path) or parsed.username):
        return None
    return urlunsplit(('https', 'seekingalpha.com', parsed.path, '', ''))


def normalize(headers, html, message_id):
    sender = parseaddr(headers.get('from', ''))[1].lower()
    # ponytail: only Seeking Alpha is verified; add named publishers with their own fixtures.
    if sender not in ('account@seekingalpha.com', 'subscriptions@seekingalpha.com'):
        raise ValueError('Sender is not approved')
    parsed = NewsletterHTML()
    parsed.feed(html)
    links = list(dict.fromkeys(u for link in parsed.links if (u := article_url(link))))
    if not links:
        raise ValueError('No canonical research/news article')
    body = ' '.join(parsed.text).split('You may also like:')[0].split('Manage Alerts')[0]
    bullets = [' '.join(b) for b in parsed.bullets if b]
    subject = headers.get('subject', '')
    match = re.match(r'^([A-Z]{1,6}):', subject)
    author = next((t.removeprefix('By:').strip() for t in parsed.text if t.startswith('By:')), None)
    article_date = next((t for t in parsed.text if re.match(r'^[A-Z][a-z]{2} \d{2}, \d{4} ', t)), None)
    return {'message_id': message_id, 'sender': sender, 'subject': subject,
            'message_date_header': headers.get('date'), 'article_url': links[0],
            'author': author, 'article_date_text': article_date,
            'evidence_level': 'analysis_summary' if bullets else 'headline_preview',
            'alert_ticker': match[1] if match else None,
            'company_resolution': 'requires_review', 'claims': bullets[:12],
            'preview': body[:1800], 'licence': 'unknown', 'validation': 'unverified'}


def from_gmail(message):
    headers = {h['name'].lower(): h['value'] for h in message['payload']['headers']}
    parts = []
    def walk(part):
        if part.get('mime_type') == 'text/html' and part.get('body', {}).get('content'):
            parts.append(part['body']['content'])
        for child in part.get('parts') or []:
            walk(child)
    walk(message['payload'])
    return normalize(headers, '\n'.join(parts), message['id'])


def from_eml(path):
    mail = BytesParser(policy=policy.default).parsebytes(Path(path).read_bytes())
    part = mail.get_body(preferencelist=('html',))
    if part is None:
        raise ValueError('No HTML newsletter body')
    return normalize({k.lower(): str(v) for k, v in mail.items()}, part.get_content(), str(mail['Message-ID']))


def deduplicate(items):
    groups = {}
    for item in items:
        key = item['article_url']
        if key not in groups:
            groups[key] = {**item, 'message_ids': [item['message_id']]}
        else:
            group = groups[key]
            if item['message_id'] not in group['message_ids']:
                group['message_ids'].append(item['message_id'])
            if len(item['claims']) > len(group['claims']):
                groups[key] = {**item, 'message_ids': group['message_ids']}
    return list(groups.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path, help='EML or exported Gmail full-message JSON')
    args = parser.parse_args()
    items, refused = [], []
    for path in args.files[:30]:
        try:
            items.append(from_eml(path) if path.suffix.lower() == '.eml' else from_gmail(json.loads(path.read_text(encoding='utf-8'))))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            refused.append({'file': path.name, 'error': type(exc).__name__})
    output = ROOT / 'local' / 'research' / 'newsletter-evidence.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    from daily import atomic_write
    atomic_write(output, json.dumps({'collected_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                                   'items': deduplicate(items), 'refused': refused,
                                   'limit': 30, 'truncated': len(args.files) > 30}, indent=2))
    print(f'Private evidence: {len(items)} accepted, {len(refused)} refused; {output}')


if __name__ == '__main__':
    main()
