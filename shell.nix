{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    gnumake
    python3
    #(python3.withPackages (pp: with pp; [ pytest ]))
    nodejs
  ];
}
