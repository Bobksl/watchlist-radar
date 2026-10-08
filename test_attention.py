from page import render
from radar import scan_changes, WEIGHTS
from test_page_tradingview import snapshot


def test_changes_are_frozen_and_missing_tickers_are_not_new_flags():
    past = {'generated_et': '2026-10-07 10:00', 'weights': WEIGHTS, 'picks': ['MU'],
            'rows': [{'ticker': 'MU', 'flags': ['news']}]}
    result = scan_changes([{'ticker': 'MU', 'flags': ['squeeze']}, {'ticker': 'NEW', 'flags': ['news']}], ['NEW'], [past])
    assert result['entered'] == ['NEW'] and result['left'] == ['MU']
    assert result['flags'] == {'MU': {'added': ['squeeze'], 'removed': ['news']}}
    assert scan_changes([], [], [])['status'] == 'no_previous_snapshot'
    assert scan_changes([], [], [{**past, 'weights': {}}])['status'] == 'incomparable_rules_or_legacy'


def test_lanes_preserve_global_rank_and_escape_changes():
    run = snapshot(['AAPL', 'NOW'])
    run['rows'][1]['watchlist'] = False
    run['changes'] = {'status': 'comparable', 'since': '<script>', 'entered': ['NOW'], 'left': [], 'flags': {}}
    html = render(run)
    assert 'From your watchlist · 1' in html and 'Discoveries outside your watchlist · 1' in html
    assert 'Global rank order: AAPL, NOW' in html
    assert 'Compared with &lt;script&gt;' in html
    assert 'symbol=NYSE%3ANOW' in html and 'id="watchlist-search"' in html


def test_private_research_never_enters_public_render():
    research = {'newsletters': [{'subject': 'PRIVATE_SENTINEL', 'article_url': 'javascript:alert(1)',
                                'claims': ['<script>private</script>']}], 'reports': []}
    public = render(snapshot([]), research=research)
    local = render(snapshot([]), local=True, research=research)
    assert 'PRIVATE_SENTINEL' not in public and 'Private research queue' not in public
    assert 'PRIVATE_SENTINEL' in local and '&lt;script&gt;private&lt;/script&gt;' in local
    assert 'href="javascript:' not in local
