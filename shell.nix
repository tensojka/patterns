{ pkgs ? import (fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/23.05.tar.gz";
  }) {} }:
# Note: wikiextractor requires Python 3.8

let
  python38 = pkgs.python38;
  python311 = pkgs.python311;

  wikiextractor = python38.pkgs.buildPythonPackage rec {
    pname = "wikiextractor";
    version = "3.0.6";
    src = python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "cEH/V4hMFkCem5EczQEGwhi4jLzqu4bdFENjevqChN4=";
    };
    doCheck = false;
  };

  python38WithPackages = python38.withPackages (ps: [ wikiextractor ]);
  python311WithPackages = python311.withPackages (ps: with ps; [
    regex 
    numpy
    scikit-learn
  ]);

  texliveCombined = pkgs.texlive.combine {
    inherit (pkgs.texlive) scheme-basic patgen;
  };

in pkgs.mkShell {
  buildInputs = with pkgs; [
    rustc
    cargo
    espeak
    python38WithPackages
    python311WithPackages
    texliveCombined
    libiconv
    gnumake
    wget
    bzip2
  ];

  shellHook = ''
    alias python3.8=${python38WithPackages}/bin/python
    alias pip3.8=${python38WithPackages}/bin/pip
    alias python3.12=${python311WithPackages}/bin/python
    alias pip3.12=${python311WithPackages}/bin/pip
    alias wikiextractor=${python38WithPackages}/bin/wikiextractor

    # Set Python 3.11 as default
    alias python=${python311WithPackages}/bin/python
    alias pip=${python311WithPackages}/bin/pip
    
    export PATH="${python311WithPackages}/bin:${python38WithPackages}/bin:$PATH"
  '';
}