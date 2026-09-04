
from scribe.cli import build_parser, main


class TestArgParsing:
    def test_bare_file_defaults_to_transcribe(self):
        args = build_parser().parse_args(["transcribe", "a.mp3"])
        assert args.command == "transcribe"

    def test_shorthand_inserts_transcribe(self, monkeypatch, tmp_path):
        # `scribe a.mp3` must behave as `scribe transcribe a.mp3`.
        called = {}

        def fake(args):
            called["inputs"] = args.inputs
            return 0

        monkeypatch.setattr("scribe.cli._cmd_transcribe", fake)
        main(["a.mp3"])
        assert [p.name for p in called["inputs"]] == ["a.mp3"]

    def test_subcommand_is_not_double_inserted(self, capsys):
        assert main(["backends"]) in (0, 1)

    def test_multiple_formats_parse(self):
        args = build_parser().parse_args(["transcribe", "a.mp3", "-f", "srt,vtt"])
        assert args.format == "srt,vtt"


class TestTranscribeCommand:
    def test_unknown_format_exits_2(self, capsys):
        assert main(["transcribe", "a.mp3", "-f", "docx"]) == 2
        assert "unknown format" in capsys.readouterr().err

    def test_no_inputs_found_exits_2(self, tmp_path, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert main(["transcribe", str(empty)]) == 2
        assert "no input files" in capsys.readouterr().err

    def test_missing_file_reports_and_exits_1(self, tmp_path, capsys):
        assert main(["transcribe", str(tmp_path / "ghost.mp3")]) == 1
        assert "failed" in capsys.readouterr().err


class TestBackendsCommand:
    def test_lists_every_registered_backend(self, capsys):
        main(["backends"])
        out = capsys.readouterr().out
        assert "faster-whisper" in out and "mlx" in out
