//import { JobClient } from 'gnumake-tokenpool';
import { JobClient } from '../../src/gnumake-tokenpool/tokenpool.js';

//import process from 'process';

//const sleep = ms => new Promise(r => setTimeout(r, ms));

const testName = process.argv.slice(2).join(' ');

//console.log(`test: ${testName}`);

const jobClient = JobClient();

function parseFlags(makeFlags) {

  let fdRead, fdWrite, maxJobs, maxLoad;

  for (const flag of makeFlags.split(/\s+/)) {
    let match;
    if (
      (match = flag.match(/^--jobserver-auth=(\d+),(\d+)$/)) ||
      (match = flag.match(/^--jobserver-fds=(\d+),(\d+)$/))
    ) {
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

const makeFlags = process.env.MAKEFLAGS;
if (!makeFlags) {
  console.log(`test failed: MAKEFLAGS is empty`);
  process.exit(1);
}
//console.log(`init: MAKEFLAGS: ${makeFlags}`);

const { fdRead, fdWrite, maxJobs, maxLoad } = parseFlags(makeFlags);

if (!jobClient) {
  if (testName == 'jobserver on' && maxJobs > 1) {
    console.log(`test: jobClient init failed`);
    process.exit(1);
  }
}
else {
  console.log(`test: jobClient init ok`);

  console.log(`test: jobClient maxJobs = ${jobClient.maxJobs}`);
  console.log(`test: jobClient maxLoad = ${jobClient.maxLoad}`);

  const tokenList = [];

  // NOTE n-1 error: dont acquire token for the first worker
  // only acquire tokens if we need 2 or more workers (parallelism)
  // assumption: the worker-scheduler produces zero cpu load
  for (let i = 0; i < jobClient.maxJobs; i++) {
    let token;
    try {
      token = jobClient.acquire();
    }
    catch (e) {
      console.log(`test: failed to acquire token: ${e}`);
      break;
    }
    if (token == null) {
      console.log(`test: failed to acquire token: jobserver is full`);
      break;
    }
    tokenList.push(token);
    console.log(`test: acquired token ${token}. tokenList.length = ${tokenList.length}`);
    //await sleep(100);
  }

  // all tokens acquired
  // try one more -> should fail
  let token;
  try {
    token = jobClient.acquire();
    if (token == null) {
      console.log(`test: ok: jobserver is full`);
    }
    else {
      console.log(`test: error: acquired token ${token}. tokenList.length = ${tokenList.length}`);
    }
  }
  catch (e) {
    console.log(`test: failed to acquire token: ${e}`);
  }

  while (tokenList.length > 0) {
    const token = tokenList.pop();
    jobClient.release(token);
    console.log(`test: released token ${token}. tokenList.length = ${tokenList.length}`);
    //await sleep(100);
  }
}
console.log('');
