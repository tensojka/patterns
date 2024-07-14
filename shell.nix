{ pkgs ? import <nixpkgs> {} }:
# Note: wikiextractor requires Python 3.9

let
  python39 = pkgs.python39;
  python312 = pkgs.python312;

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
  python312WithPackages = python312.withPackages (ps: with ps; [ regex ]);

  texliveWithPackages = pkgs.texlive.withPackages (ps: [ ps.patgen ]);

in pkgs.mkShell {
  buildInputs = with pkgs; [
    rustc
    cargo
    espeak
    python39WithPackages
    python312WithPackages
    texliveWithPackages
  ];

  shellHook = ''
    alias python3.8=${python39WithPackages}/bin/python
    alias pip3.8=${python39WithPackages}/bin/pip
    alias python3.12=${python312WithPackages}/bin/python
    alias pip3.12=${python312WithPackages}/bin/pip
    alias wikiextractor=${python39WithPackages}/bin/wikiextractor

    # Set Python 3.12 as default
    alias python=${python312WithPackages}/bin/python
    alias pip=${python312WithPackages}/bin/pip
    
    export PATH="${python312WithPackages}/bin:${python39WithPackages}/bin:$PATH"
  '';
}