from repo_sentinel.core.repo_key import normalize_remote_url


def test_https_url():
    assert (
        normalize_remote_url("https://github.com/Routhern/repo-sentinel.git")
        == "github.com__Routhern__repo-sentinel"
    )


def test_ssh_shorthand_url():
    assert (
        normalize_remote_url("git@github.com:Routhern/repo-sentinel.git")
        == "github.com__Routhern__repo-sentinel"
    )


def test_url_without_git_suffix():
    assert (
        normalize_remote_url("https://github.com/Routhern/repo-sentinel")
        == "github.com__Routhern__repo-sentinel"
    )
