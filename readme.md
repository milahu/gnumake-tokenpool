# gnumake-tokenpool

jobclient and jobserver for the GNU make tokenpool protocol

monorepo with implementations in multiple languages

* [python](py/)
* [javascript](js/)
* [c++](cc/)
* [bash](sh/)

## similar projects

* rust: https://github.com/alexcrichton/jobserver-rs
* C: https://github.com/olsner/jobclient

## gnumake tokenpool protocol spec

* [GNU make jobserver implementation](http://make.mad-scientist.net/papers/jobserver-implementation/)
* [Job Slots](https://www.gnu.org/software/make/manual/html_node/Job-Slots.html)
  * [POSIX Jobserver](https://www.gnu.org/software/make/manual/html_node/POSIX-Jobserver.html)
  * [Windows Jobserver](https://www.gnu.org/software/make/manual/html_node/Windows-Jobserver.html)

### reference implementation

[gnu.org/software/make/](https://www.gnu.org/software/make/)

* [savannah.gnu.org/git/?group=make](http://savannah.gnu.org/git/?group=make)
* [github.com/mirror/make](https://github.com/mirror/make)
  * [make/src/job.c](https://github.com/mirror/make/blob/master/src/job.c)
  * [make/src/posixos.c](https://github.com/mirror/make/blob/master/src/posixos.c)
  * [make/src/w32/w32os.c](https://github.com/mirror/make/blob/master/src/w32/w32os.c)

## related

* [ninja with jobclient and jobserver](https://gitlab.kitware.com/cmake/cmake/-/issues/21597)
* golang feature request: https://github.com/golang/go/issues/36868
