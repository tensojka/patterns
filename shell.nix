{ pkgs ? import <nixpkgs> {} }:
# Note: wikiextractor requires Python 3.9

let
  python39 = pkgs.python39;
  python313 = pkgs.python313;

  wikiextractor = python39.pkgs.buildPythonPackage rec {
    pname = "wikiextractor";
    version = "3.0.6";
    src = python39.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "cEH/V4hMFkCem5EczQEGwhi4jLzqu4bdFENjevqChN4=";
    };
    doCheck = false;
  };

  python39WithPackages = python39.withPackages (ps: [ wikiextractor ]);
  python313WithPackages = python313.withPackages (ps: with ps; [
    regex 
    numpy
    scikit-learn
  ]);

  texliveWithPackages = pkgs.texlive.withPackages (ps: [ ps.patgen ]);

in pkgs.mkShell {
  buildInputs = with pkgs; [
    rustc
    cargo
    espeak
    python39WithPackages
    python313WithPackages
    texliveWithPackages
    libiconv
  ];

  shellHook = ''
    alias python3.8=${python39WithPackages}/bin/python
    alias pip3.8=${python39WithPackages}/bin/pip
    alias python3.12=${python313WithPackages}/bin/python
    alias pip3.12=${python313WithPackages}/bin/pip
    alias wikiextractor=${python39WithPackages}/bin/wikiextractor

    # Set Python 3.13 as default
    alias python=${python313WithPackages}/bin/python
    alias pip=${python313WithPackages}/bin/pip
    
    export PATH="${python313WithPackages}/bin:${python39WithPackages}/bin:$PATH"
  '';
}