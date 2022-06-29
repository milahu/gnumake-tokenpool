/*
nix-build -E 'with import <nixpkgs> { }; callPackage ./default.nix { }'
*/

{ lib
, python3Packages
#, fetchFromGitHub
, gnumake
}:

python3Packages.buildPythonPackage rec {
  pname = "gnumake-jobclient";
  version = "0.0.1";
  src = ./.;
  /*
  src = fetchFromGitHub {
    owner = "milahu";
    repo = "gnumake-jobclient-py";
    rev = "6f9b2243a602c09cb7a9d5486ff719a08b753cb9";
    sha256 = "w3xsciGJKEUiDRbTB2ypCZbth/z4/rtGvaX2PN7andI=";
  };
  */
  checkInputs = [
    gnumake
  ];
  meta = with lib; {
    homepage = "https://github.com/milahu/gnumake-jobclient-py";
    description = "client for the GNU make jobserver";
    #maintainers = [];
    license = licenses.mit;
  };
}
