from chickadee.importer import plan_import

SITEMAP = [
    "https://example.org/research/a/",
    "https://example.org/research/b/",
    "https://example.org/about/",
]


def test_only_untracked_pages_are_added():
    plan = plan_import(SITEMAP, {"https://example.org/about/"})

    assert plan.to_add == (
        "https://example.org/research/a/",
        "https://example.org/research/b/",
    )


def test_contains_filter_and_limit_apply_in_order():
    plan = plan_import(SITEMAP, set(), contains="/research/", limit=1)

    assert plan.to_add == ("https://example.org/research/a/",)


def test_missing_pages_are_reported_only_for_the_sitemaps_domain():
    tracked = {"https://example.org/old-page/", "https://other-site.com/page/"}

    plan = plan_import(SITEMAP, tracked)

    assert plan.no_longer_listed == ("https://example.org/old-page/",)


def test_contains_filter_does_not_flag_unfiltered_pages_as_missing():
    plan = plan_import(SITEMAP, {"https://example.org/about/"}, contains="/research/")

    assert plan.no_longer_listed == ()
