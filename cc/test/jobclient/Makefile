all:
	g++ -g -o jobclient \
	jobclient.cc \
	../../src/tokenpool-gnu-make.cc \
	../../src/tokenpool-gnu-make-posix.cc \
	-I../../src/

	#+./jobclient
	#+strace ./jobclient
	+gdb -ex run ./jobclient
	#+gdb -ex run --args ./jobclient "hello world"
