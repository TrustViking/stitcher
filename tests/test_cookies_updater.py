"""Тесты для cookies_updater."""
import logging
import subprocess

from app.runtime.cookies_updater import check_cookies


def test_cookies_not_configured():
    """Если cookies_file=None — статус «не настроены», файл не найден."""
    status = check_cookies(
        cookies_file=None,
        warn_age_days=7,
        logger=logging.getLogger("test"),
        ytdlp_path=None,
    )
    assert status.cookies_file is None
    assert not status.file_exists
    assert status.file_age_days is None
    assert status.message == "не настроены"
    assert status.account_name is None


def test_cookies_file_missing(tmp_path):
    """Если файл не существует — статус «файл не найден»."""
    missing = tmp_path / "cookies.txt"
    status = check_cookies(
        cookies_file=missing,
        warn_age_days=7,
        logger=logging.getLogger("test"),
        ytdlp_path=None,
    )
    assert not status.file_exists
    assert status.file_age_days is None
    assert "не найден" in status.message
    assert status.account_name is None


def test_cookies_file_exists_without_ytdlp_probe(tmp_path, monkeypatch):
    """Если ytdlp_path=None — поведение не меняется, subprocess не вызывается."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")

    import app.runtime.cookies_updater as cookies_updater

    def _unexpected_subprocess_call(*_args, **_kwargs):
        raise AssertionError("subprocess.run не должен вызываться при ytdlp_path=None")

    monkeypatch.setattr(cookies_updater.subprocess, "run", _unexpected_subprocess_call)

    status = check_cookies(
        cookies_file=cookies,
        warn_age_days=7,
        logger=logging.getLogger("test"),
        ytdlp_path=None,
    )
    assert status.file_exists
    assert status.file_age_days is not None
    assert status.file_age_days >= 0
    assert status.account_name is None


def test_cookies_file_exists_with_account_probe(tmp_path, monkeypatch):
    """Если ytdlp_path задан и yt-dlp вернул канал — записываем account_name."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    ytdlp_path = tmp_path / "yt-dlp.exe"
    ytdlp_path.write_text("")

    import app.runtime.cookies_updater as cookies_updater

    def _mock_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="MyTestChannel\n",
            stderr="",
        )

    monkeypatch.setattr(cookies_updater.subprocess, "run", _mock_run)

    status = check_cookies(
        cookies_file=cookies,
        warn_age_days=7,
        logger=logging.getLogger("test"),
        ytdlp_path=ytdlp_path,
    )
    assert status.file_exists
    assert status.account_name == "MyTestChannel"
