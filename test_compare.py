from wikikg.compare import compare_links, missing_only, summarize
from wikikg.wikipedia_client import WikiLink


def test_matched_link_is_recognized():
    wp_links = [WikiLink(title="Baum", qid="Q10884")]
    wd_claims = {"Q10884": ["P279"]}  # subclass of

    results = compare_links(wp_links, wd_claims)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].via_properties == ["P279"]


def test_missing_link_is_flagged():
    wp_links = [WikiLink(title="Zellulose", qid="Q179961")]
    wd_claims = {}  # nothing linked in Wikidata

    results = compare_links(wp_links, wd_claims)

    assert results[0].status == "missing"
    assert results[0].qid == "Q179961"


def test_link_without_wikidata_item_is_not_comparable():
    wp_links = [WikiLink(title="Irgendeine Begriffsklärungsseite", qid=None)]
    wd_claims = {"Q999": ["P31"]}

    results = compare_links(wp_links, wd_claims)

    assert results[0].status == "no_wikidata_item"


def test_summarize_counts_each_status():
    wp_links = [
        WikiLink(title="A", qid="Q1"),
        WikiLink(title="B", qid="Q2"),
        WikiLink(title="C", qid=None),
    ]
    wd_claims = {"Q1": ["P31"]}

    results = compare_links(wp_links, wd_claims)
    summary = summarize(results)

    assert summary == {"matched": 1, "missing": 1, "no_wikidata_item": 1, "total": 3}


def test_missing_only_filters_correctly():
    wp_links = [WikiLink(title="A", qid="Q1"), WikiLink(title="B", qid="Q2")]
    wd_claims = {"Q1": ["P31"]}

    results = compare_links(wp_links, wd_claims)
    missing = missing_only(results)

    assert len(missing) == 1
    assert missing[0].title == "B"


def test_multiple_properties_to_same_target_are_all_recorded():
    wp_links = [WikiLink(title="Baum", qid="Q10884")]
    wd_claims = {"Q10884": ["P279", "P361"]}  # subclass of + part of

    results = compare_links(wp_links, wd_claims)

    assert results[0].status == "matched"
    assert set(results[0].via_properties) == {"P279", "P361"}
