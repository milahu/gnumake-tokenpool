// jobclient for the gnumake jobserver
// based on https://github.com/olsner/jobclient/blob/master/jobclient.h
// license: MIT
// copyright: (c) 2022 Milan Hauth <milahu@gmail.com>

import process from 'process';
import fs from 'fs';
import util from 'util';

fs.promises.read = util.promisify(fs.read);
fs.promises.write = util.promisify(fs.write);



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



// jobclient factory
export async function Jobclient() {

  const makeFlags = process.env.MAKEFLAGS;
  if (!makeFlags) return null;

  const { fdRead, fdWrite, maxJobs, maxLoad } = parseFlags(makeFlags);
  if (fdRead == undefined) return null;

  const buffer = await Buffer.alloc(1);

  // jobclient
  const jobclient = {
    acquire: async () => {
      // non-blocking. throws { errno: -11 } if jobserver is full
      const result = await fs.promises.read(fdRead, buffer);
      if (result.bytesRead != 1) throw new Error('read failed');
      return buffer.readInt8();
    },
    release: async (token) => {
      buffer.writeInt8(token);
      const result = await fs.promises.write(fdWrite, buffer);
      if (result.bytesWritten != 1) throw new Error('write failed');
    },
    // read-only properties
    maxTokens: () => (maxJobs - 1), // one job is used by make
    maxJobs: () => maxJobs,
    maxLoad: () => maxLoad,
  };

  // test
  let token = -1;
  try {
    token = await jobclient.acquire();
  }
  catch (e) {
    if (e.errno == -22) { // EINVAL: invalid argument
      // possible reasons:
      // make -j1
      // jobserver is disabled
      return null;
    }
    if (e.errno == -11) { // EAGAIN: resource temporarily unavailable
      // jobserver is full, try again later
      return jobserver;
    }
    throw e; // unexpected error
  }
  await jobclient.release(token);

  // ok
  return jobclient;
}
