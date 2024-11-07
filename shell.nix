{ pkgs ? import <nixpkgs> {} }:
# Note: wikiextractor requires Python 3.9

let
  python38 = pkgs.python38;
  python312 = pkgs.python312;

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
  python312WithPackages = python312.withPackages (ps: with ps; [
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
    python38WithPackages
    python312WithPackages
    texliveWithPackages
    libiconv
  ];

  shellHook = ''
    alias python3.8=${python38WithPackages}/bin/python
    alias pip3.8=${python38WithPackages}/bin/pip
    alias python3.12=${python312WithPackages}/bin/python
    alias pip3.12=${python312WithPackages}/bin/pip
    alias wikiextractor=${python38WithPackages}/bin/wikiextractor

    # Set Python 3.12 as default
    alias python=${python312WithPackages}/bin/python
    alias pip=${python312WithPackages}/bin/pip
    
    export PATH="${python312WithPackages}/bin:${python38WithPackages}/bin:$PATH"
  '';
}