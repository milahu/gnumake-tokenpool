// jobclient for the gnumake jobserver
// based on https://github.com/olsner/jobClient/blob/master/jobClient.h
// license: MIT
// copyright: (c) 2022 Milan Hauth <milahu@gmail.com>

const process = require('process');
const fs = require('fs');



const debug = process.env.DEBUG_JOBCLIENT
  ? (msg) => console.log(`JobClient: ${msg}`)
  : (_msg) => {};



function parseFlags(makeFlags) {

  let fdRead, fdWrite, maxJobs, maxLoad;

  for (const flag of makeFlags.split(/\s+/)) {
    let match;
    if (match = flag.match(/^--jobserver-auth=(\d+),(\d+)$/)) {
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

  debug("init");

  const makeFlags = process.env.MAKEFLAGS;
  debug(`makeFlags = ${makeFlags}`);
  if (!makeFlags) return null;

  const { fdRead, fdWrite, maxJobs, maxLoad } = parseFlags(makeFlags);
  debug(`fdRead = ${fdRead}, fdWrite = ${fdWrite}, maxJobs = ${maxJobs}, maxLoad = ${maxLoad}`);
  if (maxJobs == 1) {
    debug(`maxJobs == 1 -> jobserver off`);
  }
  if (fdRead == undefined) return null;

  const buffer = Buffer.alloc(1);

  const jobClient = {
    acquire: () => {
      let bytesRead = 0;
      try {
        bytesRead = fs.readSync(fdRead, buffer);
      }
      catch (e) {
        if (e.errno == -11) {
          debug(`acquire: token = null`);
          return null; // jobserver is full, try again later
        }
        throw e;
      }
      if (bytesRead != 1) throw new Error('read failed');
      const token = buffer.readInt8();
      debug(`acquire: token = ${token}`);
      return token;
    },
    release: (token) => {
      debug(`release: token = ${token}`);
      validateToken(token);
      buffer.writeInt8(token);
      let bytesWritten = 0;
      try {
        bytesWritten = fs.writeSync(fdWrite, buffer);
      }
      catch (e) {
        //if (e.errno == -11) return false; // TODO errno?
        throw e;
      }
      if (bytesWritten != 1) throw new Error('write failed');
      return true; // success
    },
    // read-only properties
    maxJobs: () => (maxJobs - 1), // one job is used by make
    maxLoad: () => maxLoad,
  };

  // test acquire + release
  let token = null;
  try {
    token = jobClient.acquire();
    if (token == null) {
      debug("init ok: jobserver is full");
      return jobClient; // ok
    }
  }
  catch (e) {
    if (e.errno == -22) {
      debug("init fail: jobserver off");
      return null; // jobserver off
    }
    throw e; // unexpected error
  }
  if (jobClient.release(token) == false) {
    // TODO?
    //return null;
    throw new Error('release failed');
  }
  debug("init ok");
  return jobClient; // ok
}
