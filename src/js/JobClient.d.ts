declare module '@milahu/gnumake-jobclient';

export function JobClient(): JobClient | null;

export type JobClient = {
    acquire: () => number | null,
    release: (token: number) => boolean,
    // read-only properties
    maxJobs: number | undefined,
    maxLoad: number | undefined,
};
