declare module '@milahu/gnumake-jobclient';
declare module 'gnumake-jobclient'; // alias

export function JobClient(): JobClient | null;

export type JobClient = {
    acquire: () => number | null,
    release: (token: number) => boolean,
    // read-only properties
    maxJobs: () => number,
    maxLoad: () => number | undefined,
};
