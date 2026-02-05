{
  description = "Simple iCal Server dev shell using uv2nix";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      # Create an overlay that provides the python packages defined in the workspace
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };
          python = pkgs.python313;

          # Overrides for python packages
          pyprojectOverrides =
            final: prev:
            {
              # package source filtering for simple-ical-server package
              simple-ical-server = prev.simple-ical-server.overrideAttrs (old: {
                src = lib.cleanSourceWith {
                  src = ./.;
                  filter =
                    path: type:
                    let
                      baseName = baseNameOf (toString path);
                    in
                    baseName == "pyproject.toml" || baseName == "uv.lock" || baseName == "README.md";
                };
              });
            };
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
          stdenv = pkgs.stdenv.override {
            targetPlatform = pkgs.stdenv.targetPlatform // {
              # https://pyproject-nix.github.io/uv2nix/platform-quirks.html
              # See https://en.wikipedia.org/wiki/MacOS_version_history#Releases for more background on version numbers.
              darwinSdkVersion = "26.1";
            };
          };
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
              pyprojectOverrides
            ]
          )
      );

    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          virtualenv = pythonSet.mkVirtualEnv "ical-server-venv" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
              pkgs.ruff
            ];
            env = {
              PYTHONPATH = ".";
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              export PYTHONPATH="."
              export REPO_ROOT=$(git rev-parse --show-toplevel)
              # Link the nix-built virtualenv to .venv for IDE support
              rm -rf .venv
              ln -s ${virtualenv} .venv
            '';
          };
        }
      );

      packages = forAllSystems (system: {
        default = pythonSets.${system}.mkVirtualEnv "ical-server-venv" workspace.deps.default;
      });
    };
}
