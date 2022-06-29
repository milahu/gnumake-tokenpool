// jobclient for the gnumake jobserver

// based on https://github.com/olsner/jobClient/blob/master/jobClient.h
// license: MIT
// copyright: (c) 2022 Milan Hauth <milahu@gmail.com>

// NOTE n-1 error
// make counts this jobclient as one job
// so we dont need a token for the first worker (serial processing).
// we only need tokens for 2 or more workers (parallel processing).

// NOTE maxJobs
// maxJobs is the global limit for all make jobs,
// so this jobclient can get less than (maxJobs-1) tokens.
// to find the maximum number of free tokens,
// you must acquire them all.

const process = require('process');
const fs = require('fs');



const debug = Boolean(process.env.DEBUG_JOBCLIENT);

const log = (msg) => console.error(`JobClient[${process.pid}][${new Date().toLocaleString('af')}.${String(Date.now() % 1000).padStart(3, '0')}]: ${msg}`); // print to stderr



function parseFlags(makeFlags) {

  let fdRead, fdWrite, maxJobs, maxLoad;

  for (const flag of makeFlags.split(/\s+/)) {
    let match;
    if (match = flag.match(/^--jobserver-fds=(\d+),(\d+)$/)) {
      fdRead = parseInt(match[1]);
      fdWrite = parseInt(match[2]);
    }
    else if (match = flag.match(/^--jobserver-auth=(\d+),(\d+)$/)) {
      fdRead = parseInt(match[1]);
      fdWrite = parseInt(match[2]);
    }
    else if (match = flag.match(/^-j(\d+)$/)) {
      maxJobs = parseInt(match[1]);
    }
    else if (match = flag.match(/^-l(\d+)$/)) {
      maxLoad = parseInt(match[1]);
    }
  }

  return { fdRead, fdWrite, maxJobs, maxLoad };
}



function validateToken(token) {

  if (token == null) {
    throw new Error('empty token');
  }

  if (typeof(token) != 'number' || token < 0 || 255 < token) {
    throw new Error('invalid token');
  }
}



// jobClient factory
exports.JobClient = function JobClient() {

  debug && log("init");

  const makeFlags = process.env.MAKEFLAGS;
  if (!makeFlags) {
    debug && log(`init failed: MAKEFLAGS is empty`);
    return null;
  }
  debug && log(`MAKEFLAGS: ${makeFlags}`);

  const { fdRead, fdWrite, maxJobs, maxLoad } = parseFlags(makeFlags);
  debug && log(`fdRead = ${fdRead}, fdWrite = ${fdWrite}, maxJobs = ${maxJobs}, maxLoad = ${maxLoad}`);

  if (fdRead == undefined) {
    debug && log(`init failed: fds missing in MAKEFLAGS`);
    return null;
  }

  if (maxJobs == 1) {
    debug && log(`init failed: maxJobs == 1`);
    return null;
  }

  const buffer = Buffer.alloc(1);

  const jobClient = {
    acquire: () => {
      let bytesRead = 0;
      debug && log(`acquire: read ...`);
      try {
        bytesRead = fs.readSync(fdRead, buffer);
      }
      catch (e) {
        if (e.errno == -11) {
          debug && log(`acquire: token = null`);
          return null; // jobserver is full, try again later
        }
        throw e;
      }
      debug && log(`acquire: read done: ${bytesRead} bytes`);
      if (bytesRead != 1) throw new Error('read failed');
      const token = buffer.readInt8();
      debug && log(`acquire: token = ${token}`);
      return token;
    },
    release: (token=43) => { // default token: str(+) == int(43)
      debug && log(`release: token = ${token}`);
      validateToken(token);
      buffer.writeInt8(token);
      let bytesWritten = 0;
      debug && log(`release: write ...`);
      try {
        bytesWritten = fs.writeSync(fdWrite, buffer);
      }
      catch (e) {
        //if (e.errno == -11) return false; // TODO errno?
        throw e;
      }
      debug && log(`release: write done: ${bytesWritten} bytes`);
      if (bytesWritten != 1) throw new Error('write failed');
      return true; // success
    },
  };

  // add read-only properties
  Object.defineProperties(jobClient, {
    maxJobs: { value: maxJobs, enumerable: true },
    maxLoad: { value: maxLoad, enumerable: true },
  });

  // TODO check fds
  // examples:
  // MAKEFLAGS="--jobserver-auth=3,4 -l32"
  // ls -nlv /proc/self/fd/
  //
  // jobserver on:
  // lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> pipe:[102600042]
  // l-wx------ 1 1000 100 64 Jun 27 14:29 4 -> pipe:[102600042]
  //
  // jobserver off:
  // lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> /proc/2370722/fd
  //
  // conditions for jobserver on:
  // * maxJobs is undefined // no. this is a bug in ninja-tokenpool. gnumake always sets -j in MAKEFLAGS
  // * fds 3 and 4 are connected
  // * fd 3 is readable
  // * fd 4 is writable
  // * fds 3 and 4 are pipes
  // * fds 3 and 4 are pipes with the same ID (?)

  // TODO windows: named semaphore

  const statsRead = fs.fstatSync(fdRead);
  if (!statsRead.isFIFO()) {
    debug && log(`init failed: fd ${fdRead} is no pipe`);
    return null;
  }
  if(statsRead.mode & fs.S_IRUSR == 0) {
    debug && log(`init failed: fd ${fdRead} is not readable`);
    return null;
  }

  const statsWrite = fs.fstatSync(fdWrite);
  if (!statsWrite.isFIFO()) {
    debug && log(`init failed: fd ${fdWrite} is no pipe`);
    return null;
  }
  if(statsWrite.mode & fs.S_IWUSR == 0) {
    debug && log(`init failed: fd ${fdWrite} is not writable`);
    return null;
  }

  // test acquire + release
  let token = null;
  try {
    token = jobClient.acquire();
    if (token == null) {
      debug && log("init ok: jobserver is full");
      return jobClient; // ok
    }
  }
  catch (e) {
    if (e.errno == -22) {
      debug && log("init failed: jobserver off");
      return null; // jobserver off
    }
    throw e; // unexpected error
  }
  if (jobClient.release(token) == false) {
    // TODO?
    //return null;
    throw new Error('release failed');
  }
  debug && log("init ok");
  return jobClient; // ok
}
