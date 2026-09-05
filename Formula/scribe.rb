class Scribe < Formula
  include Language::Python::Virtualenv

  desc "Transcribe audio and video locally, with no API keys and no upload"
  homepage "https://github.com/OlixIgnacious/scribe"
  url "https://github.com/OlixIgnacious/scribe/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_TARBALL_SHA256"
  license "Apache-2.0"

  depends_on "ffmpeg"
  depends_on "python@3.12"

  # faster-whisper pulls ctranslate2, tokenizers, onnxruntime and huggingface-hub;
  # each needs its own resource stanza. Generate them rather than writing by hand:
  #   brew install homebrew/cask/... ; pip install homebrew-pypi-poet
  #   poet -r scribe >> Formula/scribe.rb
  # or use `brew update-python-resources Formula/scribe.rb` once the formula is in a tap.

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "scribe", shell_output("#{bin}/scribe --version")
    assert_match "faster-whisper", shell_output("#{bin}/scribe backends")
  end
end
