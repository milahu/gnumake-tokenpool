{
  pkgs ? import <nixpkgs> {}
  #pkgs ? import ./. {}
}:

let
  python = pkgs.python3.withPackages (pp: with pp; [
    #requests
  ]);
in

pkgs.mkShell {

buildInputs = (with pkgs; [
  gnumake
]) ++ [ python ];

}
