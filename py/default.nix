/*
nix-build -E 'with import <nixpkgs> { }; callPackage ./default.nix { }'
*/

{ lib
, python3Packages
#, fetchFromGitHub
, gnumake
}:

python3Packages.buildPythonPackage rec {
  pname = "gnumake-tokenpool";
  version = "0.0.1";
  src = ../.;
  /*
  src = fetchFromGitHub {
    owner = "milahu";
    repo = "gnumake-tokenpool";
    rev = "";
    sha256 = "";
  };
  */
  /*
  checkInputs = [
    gnumake
  ];
  */
  pythonImportsCheck = [
    "gnumake_tokenpool"
  ];
  meta = with lib; {
    homepage = "https://github.com/milahu/gnumake-tokenpool";
    description = "jobclient and jobserver for the GNU make tokenpool protocol";
    #maintainers = [];
    license = licenses.mit;
  };
}
