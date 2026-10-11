# The vendor's download endpoint can advance before homebrew/cask's checksum.
# Keep this exception scoped to Warp; Homebrew manages installation and receipts.
cask "warp" do
  version :latest
  sha256 :no_check

  url "https://app.warp.dev/download?package=dmg"
  name "Warp"
  desc "Rust-based terminal"
  homepage "https://www.warp.dev/"

  depends_on macos: :monterey

  preflight_steps do
    run "/usr/bin/codesign",
                   args: ["--verify", "--deep", "--strict", "-R",
                          '=anchor apple generic and certificate leaf[subject.OU] = "2BBY89MBSN" and identifier "dev.warp.Warp-Stable"',
                          "Warp.app"],
                   chdir: "."
  end

  app "Warp.app"
end
