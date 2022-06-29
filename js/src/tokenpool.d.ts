declare module '@milahu/gnumake-tokenpool';

export function JobClient(): JobClient | null;

export type JobClient = {
    acquire: () => number | null,
    release: (token?: number) => boolean,
    // read-only properties
    maxJobs: number | undefined,
    maxLoad: number | undefined,
};
