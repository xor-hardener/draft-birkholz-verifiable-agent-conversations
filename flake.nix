{
  # Templated from: https://github.com/kittyandrew/dotfiles/tree/main/templates/python
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = {
    nixpkgs,
    flake-utils,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {inherit system;};

        pythonExtended = pkgs.python3.override {
          self = pythonExtended;
          packageOverrides = _pyfinal: _pyprev: {
            fawltydeps = with pkgs.python3Packages;
              buildPythonPackage rec {
                pname = "fawltydeps";
                version = "0.19.0";
                format = "pyproject";

                src = pkgs.fetchPypi {
                  inherit pname version;
                  sha256 = "sha256-D76bFzbzoccGDVs0ieJPWUGHoMmK+l6oiLJ+cOY7CuA=";
                };

                nativeBuildInputs = [poetry-core];
                propagatedBuildInputs = [
                  pyyaml
                  importlib-metadata
                  isort
                  pip-requirements-parser
                  pydantic
                ];
              };
          };
        };

        pythonCustom = pythonExtended.withPackages (ps:
          with ps; [
            # Setup utils for packages and builds.
            pip
            wheel
            packaging
            setuptools
            # @TODO: Replace this with nix shell stuff.
            virtualenv # Local pythonic dev-env management.
            # Static analysis and formatting packages.
            flake8
            mypy
            black
            isort
            fawltydeps
          ]);
        libs = with pkgs; [
          stdenv.cc.cc
          zlib
          glib
        ];
        gdk = pkgs.google-cloud-sdk.withExtraComponents (with pkgs.google-cloud-sdk.components; [
          gke-gcloud-auth-plugin
        ]);
      in {
        devShell = pkgs.mkShell {
          buildInputs = [
            pythonCustom # installing our custom python with pre-installed packages
            pkgs.bore-cli # for when we require reverse-proxy (local gh app testing)
            pkgs.pre-commit # cli for pre-commit hook stuff
            pkgs.act # for testing gh actions locally
            gdk # for gcloud tools and authentication
            pkgs.gh
            pkgs.cddl
            pkgs.ruff
          ];
          # Upon installation we need to do additional configurations.
          shellHook = ''
            # Some python packages do RUNTIME DL loading from the provided paths, sigh.
            export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath libs}

            python -m virtualenv -q .venv && source .venv/bin/activate
            if [[ -f requirements.txt ]]; then # We want to install additional requirements into a virtual env [for now].
              python -m pip install -qr requirements.txt
            fi
            if [[ -f requirements-test.txt ]]; then # Installing TEST requirements for dev.
              python -m pip install -qr requirements-test.txt
            fi
            if [[ -f requirements-bench.txt ]]; then # Installing BENCH requirements for dev.
              python -m pip install -qr requirements-bench.txt
            fi
            if [[ -f requirements-dev.txt ]]; then # Installing DEV requirements for dev.
              python -m pip install -qr requirements-dev.txt
            fi

            echo -e "\nWelcome to the shell :)\n"
          '';
        };
      }
    );
}
