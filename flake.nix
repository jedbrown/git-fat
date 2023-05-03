{
  description = "Git-fat packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    poetry2nix,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
      inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication mkPoetryEnv;
      poetryEnv = mkPoetryEnv {
        projectDir = ./.;
        overrides =
          pkgs.poetry2nix.defaultPoetryOverrides.extend
          (self: super: {
            path-py =
              super.path-py.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or []) ++ [super.setuptools];
                }
              );
            attrs =
              super.attrs.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or []) ++ [super.hatchling super.hatch-vcs super.hatch-fancy-pypi-readme];
                }
              );
            pytest-env =
              super.pytest-env.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or []) ++ [super.hatchling super.hatch-vcs super.hatch-fancy-pypi-readme];
                }
              );
            pytest-git =
              super.pytest-git.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or []) ++ [super.setuptools super.setuptools-git];
                }
              );
            pytest-shutil =
              super.pytest-shutil.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or []) ++ [super.setuptools super.setuptools-git];
                }
              );
            cryptography = pkgs.python3Packages.cryptography;
            pynacl = pkgs.python3Packages.pynacl;
          });
        editablePackageSources = {
          git-fat = ./.;
        };
      };
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      packages = {
        git-fat = mkPoetryApplication {projectDir = self;};
        default = self.packages.${system}.git-fat;
      };

      devShells.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          python3
          poetry
          poetryEnv
        ];
      };
    });
}
