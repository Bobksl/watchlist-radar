import base64
import pytest
from newsletters import article_url, normalize, deduplicate

URL = 'https://seekingalpha.com/article/1234-test'


def test_tracking_decode_strips_private_parameters_and_refuses_login():
    encoded = base64.urlsafe_b64encode((URL + '?token=private').encode()).decode().rstrip('=')
    assert article_url('https://email-st.seekingalpha.com/click/123/' + encoded + '/tracking') == URL
    assert article_url('https://seekingalpha.com/account/email-auth?token=private') is None
    assert article_url('https://evil.com/article/1234-test') is None


def test_summary_remains_unverified_and_alert_is_not_company():
    item = normalize({'from': 'SA <account@seekingalpha.com>', 'subject': 'NVDA: AXT news'},
                     f'<div style="display: none">hidden</div><a href="{URL}">Title</a><ul><li>Claim</li></ul><p>You may also like:</p><li>Other article</li>', 'one')
    assert item['claims'] == ['Claim']
    assert item['alert_ticker'] == 'NVDA' and item['company_resolution'] == 'requires_review'
    assert item['licence'] == 'unknown' and item['validation'] == 'unverified'
    assert 'hidden' not in item['preview']


def test_byline_and_article_date_are_distinct_from_message_date():
    item = normalize({'from': 'account@seekingalpha.com', 'date': 'sent-date'},
                     f'<a href="{URL}">Title</a><p>Oct 08, 2026 08:12 AM</p><p>By: Example Author</p>', 'one')
    assert item['author'] == 'Example Author' and item['article_date_text'] == 'Oct 08, 2026 08:12 AM'
    assert item['message_date_header'] == 'sent-date'


def test_unapproved_sender_and_promotional_mail_refused():
    with pytest.raises(ValueError):
        normalize({'from': 'x@evil.com'}, f'<a href="{URL}">Title</a>', 'one')
    with pytest.raises(ValueError):
        normalize({'from': 'account@seekingalpha.com'}, '<p>Subscribe now</p>', 'one')


def test_duplicate_article_preserves_both_messages_and_richer_summary():
    base = normalize({'from': 'account@seekingalpha.com'}, f'<a href="{URL}">Title</a>', 'one')
    richer = {**base, 'message_id': 'two', 'claims': ['claim'], 'evidence_level': 'analysis_summary'}
    result = deduplicate([base, richer, richer])
    assert len(result) == 1 and result[0]['message_ids'] == ['one', 'two']
    assert result[0]['claims'] == ['claim']
