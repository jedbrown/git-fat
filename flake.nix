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
    ...
  } @ inputs:
    flake-utils.lib.eachDefaultSystem (system: let
      # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
      p2n = poetry2nix.legacyPackages.${system};
      inherit (p2n) mkPoetryApplication;
      pkgs = nixpkgs.legacyPackages.${system};
      pypkgs-build-requirements = {
        path-py = ["setuptools"];
        pytest = ["hatchling"];
        pytest-env = ["hatchling" "hatch-vcs"];
        pytest-git = ["setuptools"];
      };
      p2n-overrides = p2n.defaultPoetryOverrides.extend (
        self: super:
          builtins.mapAttrs (
            package: build-requirements:
              (builtins.getAttr package super).overridePythonAttrs (old: {
                buildInputs =
                  (old.buildInputs or [])
                  ++ (builtins.map (pkg:
                    if builtins.isString pkg
                    then builtins.getAttr pkg super
                    else pkg)
                  build-requirements);
              })
          )
          pypkgs-build-requirements
      );
    in {
      packages = {
        git-fat = mkPoetryApplication {
          projectDir = self;
          overrides = p2n-overrides;
        };
        default = self.packages.${system}.git-fat;
      };

      devShells.default = pkgs.mkShell {
        buildInputs = [
          pkgs.poetry
        ];
      };
    });
}
